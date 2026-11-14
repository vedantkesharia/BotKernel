set -euo pipefail
cd /opt/botkernel
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python - <<'PY'
import os,json,time,httpx
from pathlib import Path
from sqlalchemy import text
from botkernel.core import engine
from botkernel.security import operator_headers
from botkernel.live_demo import _wait_for_action
p=Path('/app/benchmarks/results/final-demo-quota-release-20261114.json');assert not p.exists()
resource='aws-accept-cost-ade1070aa59e';key='final-20261114:quota-release:cost'
with httpx.Client(base_url='http://api:8000',headers=operator_headers(),timeout=15) as c:
 assert os.environ['BEDROCK_ENABLED']=='false' and os.environ['AI_ACTION_EXECUTION_ENABLED']=='false'
 rows=c.get('/telemetry').raise_for_status().json();row=next(x for x in rows if x['id']==resource)
 assert row['capacity']==4 and row['total_allocation']==19 and row['quota_capacity']==20
 assert not row['pending_action'] and not row['controller_hold'] and row['controller_status'] is None
 with engine.begin() as db:
  assert db.execute(text("SELECT COUNT(*) FROM actions WHERE state='RESERVED'")).scalar()==0
  assert db.execute(text('SELECT COUNT(*) FROM actions WHERE idempotency_key=:key'),{'key':key}).scalar()==0
 c.post('/agents/cost-demo').raise_for_status()
 request={'agent':'cost-demo','workflow':'approved-demo-quota-release','idempotency_key':key,'resource':resource,'expected_version':row['version'],'capacity':3}
 result={'status':'PREPARED','request':request};p.write_text(json.dumps(result))
 result['status']='POST_ATTEMPTED';p.write_text(json.dumps(result))
 response=c.post('/actions',json=request);response.raise_for_status();action=response.json()['id'];result['action_id']=action;p.write_text(json.dumps(result))
 _wait_for_action(c,action,time.monotonic()+60)
 after=next(x for x in c.get('/telemetry').raise_for_status().json() if x['id']==resource)
 assert after['capacity']==3 and after['version']==row['version']+1 and after['total_allocation']==18
 result.update(status='SUCCEEDED',after=after);p.write_text(json.dumps(result));print(json.dumps(result))
PY