set -euo pipefail
cd /opt/botkernel
# These separate, bounded deterministic processes use safe no-op telemetry and NEW files.
docker compose --env-file runtime.env -f compose.aws-demo.yaml run --rm --no-deps -e AGENT_PROVIDER=deterministic_mock -e BOTKERNEL_AGENT_RESOURCE=service-a -e BOTKERNEL_AGENT_CHECKPOINTS=/var/lib/botkernel/checkpoints/cost-final-20261114.sqlite langgraph-cost python -c 'import json;from botkernel.lang_agents import run_once; r=run_once("cost"); print(json.dumps(r,default=str)); assert r["outcome"]["decision"]=="no_change"' > /opt/botkernel/backups/final-acceptance-20261114/cost-process.json &
cost_pid=$!
docker compose --env-file runtime.env -f compose.aws-demo.yaml run --rm --no-deps -e AGENT_PROVIDER=deterministic_mock -e BOTKERNEL_AGENT_RESOURCE=bk-cloud-demo-70f62eb -e BOTKERNEL_AGENT_CHECKPOINTS=/var/lib/botkernel/checkpoints/performance-final-20261114.sqlite langgraph-performance python -c 'import json;from botkernel.lang_agents import run_once; r=run_once("performance"); print(json.dumps(r,default=str)); assert r["outcome"]["decision"]=="no_change"' > /opt/botkernel/backups/final-acceptance-20261114/performance-process.json &
performance_pid=$!
wait "$cost_pid"; echo 'Cost process exit0'
wait "$performance_pid"; echo 'Performance process exit0'
python3 - <<'PY'
import json
from pathlib import Path
for role in ['cost','performance']:
 r=json.loads(Path('backups/final-acceptance-20261114/'+role+'-process.json').read_text())
 print(role,json.dumps({k:r.get(k) for k in ['agent','run_id','outcome','provider','ai_provenance']}))
PY