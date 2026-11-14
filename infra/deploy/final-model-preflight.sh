set -euo pipefail
cd /opt/botkernel
docker logout 913756568949.dkr.ecr.us-east-2.amazonaws.com
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python - <<'PY'
import os,json,redis,boto3
from datetime import datetime,timezone
from sqlalchemy import text
from botkernel.core import engine
from botkernel.security import operator_headers
from botkernel.bedrock_acceptance import validate_agent_observation
import httpx
print('credential_method',boto3.Session().get_credentials().method)
r=redis.Redis.from_url(os.environ['REDIS_URL'])
key='botkernel:bedrock-budget:'+datetime.now(timezone.utc).strftime('%Y%m%d')
print('BUDGET',json.dumps({k.decode():v.decode() for k,v in r.hgetall(key).items()}))
with engine.begin() as c:
 for query in ['SELECT version_num FROM alembic_version','SELECT SUM(capacity) FROM resources','SELECT COUNT(*) FROM effects','SELECT COUNT(*) FROM actions WHERE state=\'RESERVED\'']:
  print(query,c.execute(text(query)).scalar())
with httpx.Client(base_url='http://api:8000',headers=operator_headers(),timeout=15) as c:
 print('ready',c.get('/ready').raise_for_status().json())
 rows=c.get('/telemetry').raise_for_status().json()
 for role in ('cost','performance'):
  row=next(x for x in rows if x['id']=='aws-accept-'+role+'-ade1070aa59e')
  validate_agent_observation(role,row)
  print('TELEMETRY',json.dumps(row))
 incident=next(x for x in c.get('/incidents').raise_for_status().json() if x['id']==2)
 print('INCIDENT',json.dumps({'id':2,'state':incident['status'],'resource':incident['resource'],'evidence':incident['evidence']['origin']}))
PY