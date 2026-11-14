set -euo pipefail
cd /opt/botkernel
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python - <<'PY'
import os,json,uuid,redis,httpx
from datetime import datetime,timezone
from pathlib import Path
from botkernel.core import engine
from botkernel.security import operator_headers
from botkernel.bedrock_acceptance import _resource_snapshot,_require_usage
p=Path('/app/benchmarks/results/bedrock-final-investigator-02.json')
assert not p.exists(), 'Do not repeat an existing attempt'
key='bedrock-final-investigator:'+str(uuid.uuid4())
result={'status':'PREPARED','runtime':'aws-demo','provider':'bedrock','model_id':'us.amazon.nova-micro-v1:0','region':'us-east-2','idempotency_key':key,'action_execution_enabled':False}
def save(): p.write_text(json.dumps(result,indent=2))
save()
assert os.environ['AI_ACTION_EXECUTION_ENABLED']=='false'
r=redis.Redis.from_url(os.environ['REDIS_URL'])
daily='botkernel:bedrock-budget:'+datetime.now(timezone.utc).strftime('%Y%m%d')
calls,tokens=map(int,r.hmget(daily,'calls','reserved_tokens'))
assert calls==4 and tokens==13876, 'Usage changed; review before new invocation'
before=_resource_snapshot(engine,'aws-accept-incident-ade1070aa59e')
try:
 with httpx.Client(base_url='http://api:8000',headers=operator_headers(),timeout=75) as c:
  result['status']='REQUEST_ATTEMPTED';save()
  response=c.post('/incidents/2/investigations',json={'idempotency_key':key,'provider':'bedrock'})
  response.raise_for_status();row=response.json();result['investigation_id']=row['id'];result['report_status']=row['status'];save()
  assert row['status']=='COMPLETE', 'Investigator did not complete; inspect diagnostics'
  report=row['report'];assert report['ai_analysis']['status']=='COMPLETE'
  _require_usage(report['usage'],expected_invocations=1)
  stored=c.get('/investigations/'+row['id']).raise_for_status().json()
  assert stored['report']==report
  after=_resource_snapshot(engine,'aws-accept-incident-ade1070aa59e');assert after==before
  result.update(status='PASSED',usage=report['usage'],ai_analysis=report['ai_analysis'],effect_count=len(report['effects']),operational_state_unchanged=True,persisted_get_matched_post=True)
except Exception as error:
 result['status']='FAILED_OR_OUTCOME_UNKNOWN';result['error_type']=type(error).__name__;save();raise
save();print(json.dumps(result))
print('BUDGET',{k.decode():v.decode() for k,v in r.hgetall(daily).items()})
PY