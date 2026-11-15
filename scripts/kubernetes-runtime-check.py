"""Bounded acceptance INSIDE a fresh, dedicated Kubernetes API pod.

Stream this file to `kubectl exec -i ... -- env
BOTKERNEL_K8S_ACCEPTANCE=true python - prepare|verify|replay|snapshot`.
Stop worker/recovery before prepare; resume them before verify. Never target
development or AWS data. Credentials come from the pod's existing environment.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
from sqlalchemy import text
from botkernel.core import engine

assert os.getenv('BOTKERNEL_K8S_ACCEPTANCE') == 'true'
assert os.getenv('KUBERNETES_SERVICE_HOST')
assert os.getenv('CLOUD_MODE') == 'mock'
for flag in ('AWS_DEPLOY_ALLOWED', 'BEDROCK_ENABLED', 'BEDROCK_SPEND_AUTHORIZED', 'AI_ACTION_EXECUTION_ENABLED'):
    assert os.getenv(flag, 'false').lower() == 'false', flag
HEADERS = {'Authorization': 'Bearer ' + os.environ['BOTKERNEL_OPERATOR_TOKEN']}
PREFIX = 'k8s-contention-'


def snapshot():
    with engine.connect() as c:
        actions = [dict(r) for r in c.execute(text("""
          SELECT a.id::text,a.state,a.resource,a.idempotency_key,
            (SELECT count(*) FROM outbox o WHERE o.action_id=a.id AND o.published) published,
            (SELECT count(*) FROM receipts r WHERE r.action_id=a.id) receipts,
            (SELECT count(*) FROM effects e WHERE e.action_id=a.id) effects
          FROM actions a ORDER BY a.created_at"""
        )).mappings()]
        resources = [dict(r) for r in c.execute(text('SELECT * FROM resources ORDER BY id')).mappings()]
        allocation = c.execute(text('SELECT sum(capacity) FROM resources')).scalar_one()
        pending = c.execute(text("SELECT coalesce(sum(greatest(delta,0)),0) FROM actions WHERE state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN','ESCALATED')")).scalar_one()
        quota = c.execute(text('SELECT capacity FROM quota WHERE id=1')).scalar_one()
        revision = c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    assert allocation + pending <= quota
    return dict(actions=actions, resources=resources, allocation=allocation, pending=pending, quota=quota, migration=revision)


def proposal(i):
    return dict(agent=PREFIX+str(i), workflow='kubernetes-acceptance',
                idempotency_key=PREFIX+str(i),resource=PREFIX+str(i),expected_version=0,capacity=3)


def batch(payloads):
    gate = Barrier(len(payloads))
    def submit(payload):
        with httpx.Client(base_url='http://127.0.0.1:8000',headers=HEADERS,timeout=20) as client:
            gate.wait(timeout=10)
            start=time.monotonic(); r=client.post('/actions',json=payload)
            return dict(status=r.status_code, response=r.json(), latency_ms=(time.monotonic()-start)*1000)
    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        return list(pool.map(submit,payloads))


def prepare():
    with engine.begin() as c:
        c.execute(text('SELECT id FROM quota WHERE id=1 FOR UPDATE'))
        assert c.execute(text('SELECT count(*) FROM actions')).scalar_one()==0, 'Fresh namespace data required'
        assert c.execute(text('SELECT sum(capacity) FROM resources')).scalar_one()==8
        c.execute(text('UPDATE quota SET capacity=14 WHERE id=1'))
        for i in range(4):
            resource=PREFIX+str(i)
            c.execute(text('INSERT INTO agents(id) VALUES(:id)'),dict(id=resource))
            c.execute(text('INSERT INTO resources(id,capacity) VALUES(:id,1)'),dict(id=resource))
            c.execute(text('INSERT INTO external_resources(id,capacity) VALUES(:id,1)'),dict(id=resource))
    competition=batch([proposal(i) for i in range(4)])
    assert sorted(r['status'] for r in competition)==[202,409,409,409],competition
    winner=next(i for i,r in enumerate(competition) if r['status']==202)
    replays=batch([proposal(winner)]*8)
    aid=competition[winner]['response']['id']
    assert all(r['status']==202 and r['response']['id']==aid for r in replays)
    bad=proposal(winner);bad['capacity']=2
    changed=batch([bad])[0];assert changed['status']==409
    state=snapshot();assert len(state['actions'])==1 and state['pending']==2 and state['allocation']==12
    assert state['actions'][0]['effects']==state['actions'][0]['receipts']==0
    return dict(competition=competition,duplicate_requests=replays,changed_payload=changed,pending_state=state)


def verify():
    start=time.monotonic()
    while time.monotonic()-start<90:
        state=snapshot()
        if state['actions'] and all(a['state']=='SUCCEEDED' for a in state['actions']):break
        time.sleep(.2)
    assert len(state['actions'])==1 and state['pending']==0 and state['allocation']==14
    action=state['actions'][0]
    assert action['state']=='SUCCEEDED' and action['published']==action['receipts']==action['effects']==1,state
    resource=next(r for r in state['resources'] if r['id']==action['resource'])
    assert resource['version']==1 and resource['capacity']==3
    i=int(action['resource'].removeprefix(PREFIX))
    stale=proposal(i);stale['idempotency_key']+='-stale'
    policy=proposal(i);policy.update(expected_version=1,risk='high',idempotency_key=PREFIX+'policy')
    failures=batch([stale,policy]);assert all(r['status']==409 for r in failures)
    return dict(completion_observation_seconds=time.monotonic()-start,rejections=failures,state=state)


def replay():
    from confluent_kafka import Producer
    state=snapshot();assert state['actions']
    aid=state['actions'][0]['id'];p=Producer({'bootstrap.servers':'kafka:9092','enable.idempotence':True})
    errors=[]
    p.produce('actions',key=aid,value=aid,callback=lambda err,msg:errors.append(str(err)) if err else None)
    assert p.flush(15)==0 and not errors
    return dict(acknowledged_duplicate_action=aid,state_before=state)


def controller():
    state=snapshot();action=state['actions'][0];resource=action['resource'];outcomes=[]
    for step,capacity in enumerate((1,3,1,3)):
        current=next(r for r in snapshot()['resources'] if r['id']==resource)
        payload=proposal(step);payload.update(resource=resource,capacity=capacity,
                    expected_version=current['version'],idempotency_key=PREFIX+'controller-'+str(step))
        result=batch([payload])[0];assert result['status']==202,result
        aid=result['response']['id'];deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            row=next(a for a in snapshot()['actions'] if a['id']==aid)
            if row['state']=='SUCCEEDED':break
            time.sleep(.2)
        assert row['state']=='SUCCEEDED';outcomes.append(result)
    deadline=time.monotonic()+20;incident=None
    while time.monotonic()<deadline:
        with engine.connect() as c:
            row=c.execute(text("SELECT id,status,resource FROM incidents WHERE resource=:r ORDER BY id DESC LIMIT 1"),{'r':resource}).mappings().first()
        if row and row['status'] in ('HOLD','VERIFYING'):incident=dict(row);break
        time.sleep(.5)
    assert incident,'Controller did not create containment from committed reversals'
    current=next(r for r in snapshot()['resources'] if r['id']==resource)
    blocked=[]
    for i in range(4):
        payload=proposal(i);payload.update(resource=resource,expected_version=current['version'],capacity=2,idempotency_key=PREFIX+'hold-'+str(i));blocked.append(payload)
    holds=batch(blocked);assert all(r['status']==409 and 'containment' in r['response']['detail'] for r in holds),holds
    other=next(r for r in snapshot()['resources'] if r['id'].startswith(PREFIX) and r['id']!=resource)
    payload=proposal(0);payload.update(resource=other['id'],expected_version=other['version'],capacity=other['capacity'],idempotency_key=PREFIX+'unrelated')
    unrelated=batch([payload])[0];assert unrelated['status']==202
    return dict(transitions=outcomes,incident=incident,held_concurrent_rejections=holds,unrelated_admission=unrelated,state=snapshot())


def first_key():
    state=snapshot()
    target=next(r for r in state['resources'] if r['id'].startswith(PREFIX) and r['version']==0)
    payload=proposal(0);payload.update(resource=target['id'],capacity=target['capacity'],
        expected_version=0,idempotency_key=PREFIX+'simultaneous-first-key')
    assert not any(a['idempotency_key']==payload['idempotency_key'] for a in state['actions'])
    results=batch([payload]*8)
    assert all(r['status']==202 for r in results)
    assert len({r['response']['id'] for r in results})==1
    return dict(requests=results,state=snapshot())


phase=sys.argv[1]
result={'phase':phase,'utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        'result':{'prepare':prepare,'verify':verify,'replay':replay,'snapshot':snapshot,'controller':controller,'first-key':first_key}[phase]()}
print(json.dumps(result,default=str))
