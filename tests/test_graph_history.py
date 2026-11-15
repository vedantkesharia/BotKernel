"""Read-only graph contracts against explicitly isolated PostgreSQL fixtures."""
import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from botkernel.api import app
from botkernel.core import engine
from botkernel.security import operator_headers
from botkernel.stability import graph


def history_fixture(count):
    resource = 'history-' + uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text('INSERT INTO agents(id) VALUES(:r)'), {'r': resource})
        c.execute(text('INSERT INTO resources VALUES(:r,4,:v)'), {'r': resource, 'v': count})
        c.execute(text('INSERT INTO external_resources VALUES(:r,4)'), {'r': resource})
        rows = [{'id':str(uuid.uuid4()), 'key':resource+str(v), 'r':resource,'v':v,
                 'payload':json.dumps({'capacity':4,'expected_version':v-1})} for v in range(1,count+1)]
        c.execute(text("INSERT INTO actions(id,idempotency_key,agent,resource,payload,delta,state) VALUES(:id,:key,:r,:r,CAST(:payload AS jsonb),0,'SUCCEEDED')"), rows)
        c.execute(text('INSERT INTO receipts(action_id) VALUES(:id)'), rows)
        c.execute(text('INSERT INTO outbox(action_id,published) VALUES(:id,true)'), rows)
        c.execute(text('INSERT INTO effects(action_id,resource,agent,version,before_capacity,after_capacity,latency) VALUES(:id,:r,:r,:v,4,4,120)'), rows)
    return resource


def test_history_windows_and_api_validation():
    resource = history_fixture(3)
    with engine.begin() as c:
        c.execute(text("UPDATE effects SET observed_at=now()-interval '2 days' WHERE resource=:r AND version=1"), {'r':resource})
        c.execute(text("UPDATE effects SET observed_at=now()-interval '20 days' WHERE resource=:r AND version=2"), {'r':resource})
    client = TestClient(app)
    for window, versions in [(3600,[3]),(86400,[3]),(604800,[1,3]),(0,[1,2,3])]:
        response = client.get('/graph',params={'window':window,'resource':resource},headers=operator_headers())
        assert response.status_code == 200
        assert [r['version'] for r in response.json()['evidence']] == versions
        assert response.json()['truncated'] is False
    assert len(client.get('/graph',params={'resource':resource},headers=operator_headers()).json()['evidence']) == 2
    for window in (-1,604801):
        assert client.get('/graph',params={'window':window},headers=operator_headers()).status_code == 422
    assert client.get('/graph?window=0').status_code == 401


def test_history_cap_is_exact_and_returns_newest_without_cross_resource_edges():
    resource = history_fixture(1001)
    result = graph(0,resource)
    assert result['truncated'] is True and result['returned_effects'] == 1000
    # Identical timestamps have deterministic resource/version tie-breaking.
    assert [r['version'] for r in result['evidence']] == list(range(2,1002))
    assert all(r['resource']==resource for r in result['evidence'])
    assert not any(e['inferred'] for e in result['edges'])
    with engine.begin() as c:
        c.execute(text("UPDATE effects SET observed_at=now()-interval '20 days' WHERE resource=:r AND version=1"), {'r':resource})
    assert graph(604800,resource)['truncated'] is False  # Exactly 1000 is not truncated.
    assert graph(0,'missing-'+resource)['evidence'] == []
