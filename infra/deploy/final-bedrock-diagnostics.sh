set -euo pipefail
cd /opt/botkernel
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python - <<'PY'
import json,os,redis,httpx
from pathlib import Path
from botkernel.security import operator_headers
p=Path('/app/benchmarks/results/bedrock-final-20261114-01.json')
record=json.loads(p.read_text());print('ACCEPTANCE',json.dumps(record))
with httpx.Client(base_url='http://api:8000',headers=operator_headers(),timeout=10) as c:
 rs=c.get('/incidents/2/investigations').raise_for_status().json()
 for x in rs:
  if x.get('provider')=='bedrock':
   report=c.get('/investigations/'+str(x['id'])).raise_for_status().json()
   print('REPORT',json.dumps(report))
r=redis.Redis.from_url(os.environ['REDIS_URL']);print('BUDGET',{k.decode():v.decode() for k,v in r.hgetall('botkernel:bedrock-budget:20261114').items()})
PY