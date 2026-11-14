set -euo pipefail
cd /opt/botkernel
python3 - <<'PY'
from pathlib import Path
p=Path('runtime.env');env=dict(l.split('=',1) for l in p.read_text().splitlines() if '=' in l and not l.startswith('#'))
env.update(BEDROCK_ENABLED='false',BEDROCK_SPEND_AUTHORIZED='false',AI_ACTION_EXECUTION_ENABLED='false',AGENT_PROVIDER='deterministic_mock',INVESTIGATOR_PROVIDER='deterministic_mock')
p.write_text(''.join(k+'='+v+chr(10) for k,v in env.items()));p.chmod(0o600)
PY
docker compose --env-file runtime.env -f compose.aws-demo.yaml up -d --no-deps --force-recreate api
for n in $(seq 1 30); do if curl -fsS http://127.0.0.1:8080/api/ready >/dev/null; then break; fi; sleep 2; done
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python - <<'PY'
import httpx,json,os,sqlite3
from botkernel.security import operator_headers
assert all(os.environ.get(k)=='false' for k in ('BEDROCK_ENABLED','BEDROCK_SPEND_AUTHORIZED','AI_ACTION_EXECUTION_ENABLED'))
with httpx.Client(base_url='http://api:8000',headers=operator_headers()) as c:
 print('RESOURCES',json.dumps(c.get('/resources').raise_for_status().json()))
p='/app/benchmarks/results/bedrock-final-20261114-01.sqlite'
with sqlite3.connect(p) as db:
 print('CHECKPOINT_THREADS',db.execute('SELECT DISTINCT thread_id FROM checkpoints').fetchall())
 print('REASONING',db.execute('SELECT run_id,status FROM agent_reasoning').fetchall())
PY