set -euo pipefail
cd /opt/botkernel
python3 - <<'PY'
from pathlib import Path
p=Path('runtime.env');env=dict(l.split('=',1) for l in p.read_text().splitlines() if '=' in l and not l.startswith('#'))
env.update(BEDROCK_ENABLED='true',BEDROCK_SPEND_AUTHORIZED='true',AGENT_PROVIDER='bedrock',INVESTIGATOR_PROVIDER='bedrock',BEDROCK_MAX_CALLS_PER_DAY='12',MAX_BEDROCK_TOKENS_PER_DAY='80000',BEDROCK_MAX_OUTPUT_TOKENS='1024',BEDROCK_MAX_CALLS_PER_RUN='1',AI_ACTION_EXECUTION_ENABLED='false',AWS_DEPLOY_ALLOWED='false',CLOUD_MODE='mock')
p.write_text(''.join(k+'='+v+chr(10) for k,v in env.items()));p.chmod(0o600)
PY
docker compose --env-file runtime.env -f compose.aws-demo.yaml up -d --no-deps --force-recreate api
for n in $(seq 1 30); do if curl -fsS http://127.0.0.1:8080/api/ready >/dev/null; then break; fi; sleep 2; done
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T -e BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED=true -e BOTKERNEL_BEDROCK_ACCEPTANCE_RUNTIME=aws-demo -e BOTKERNEL_AGENT_CHECKPOINTS=/app/benchmarks/results/bedrock-final-20261114-01.sqlite api python -m botkernel.bedrock_acceptance --execute-live --api-url http://api:8000 --cost-resource aws-accept-cost-ade1070aa59e --performance-resource aws-accept-performance-ade1070aa59e --incident-id 2 --output /app/benchmarks/results/bedrock-final-20261114-01.json