set -euo pipefail
cd /opt/botkernel
python3 - <<'PY'
from pathlib import Path
p=Path('runtime.env');env=dict(l.split('=',1) for l in p.read_text().splitlines() if '=' in l and not l.startswith('#'))
env['BOTKERNEL_API_IMAGE']='913756568949.dkr.ecr.us-east-2.amazonaws.com/botkernel-demo-backend@sha256:08a005d680faf5da82ab6d6562e1ba6977b3684b93f3201c8b58bada47a180a1'
assert env['AI_ACTION_EXECUTION_ENABLED']=='false'
p.write_text(''.join(k+'='+v+chr(10) for k,v in env.items()));p.chmod(0o600)
PY
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 913756568949.dkr.ecr.us-east-2.amazonaws.com
docker compose --env-file runtime.env -f compose.aws-demo.yaml pull api
docker logout 913756568949.dkr.ecr.us-east-2.amazonaws.com
docker compose --env-file runtime.env -f compose.aws-demo.yaml up -d init api publisher worker recovery controller
for n in $(seq 1 30); do if curl -fsS http://127.0.0.1:8080/api/ready >/dev/null; then break; fi; sleep 2; done
curl -fsS http://127.0.0.1:8080/api/ready