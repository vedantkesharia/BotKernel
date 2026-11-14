set -euo pipefail
cd /opt/botkernel
test ! -e backups/final-acceptance-20261114/final-demo.json
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python - <<'PY'
import httpx,os
from sqlalchemy import text
from botkernel.core import engine
from botkernel.security import operator_headers
assert os.environ['BEDROCK_ENABLED']=='false' and os.environ['AI_ACTION_EXECUTION_ENABLED']=='false'
with httpx.Client(base_url='http://api:8000',headers=operator_headers(),timeout=10) as c:
 row=next(x for x in c.get('/telemetry').raise_for_status().json() if x['id']=='aws-accept-cost-ade1070aa59e')
 assert row['capacity']==3 and row['version']==2 and row['total_allocation']==18 and row['quota_capacity']==20
 assert not row['pending_action'] and not row['controller_hold'] and row['controller_status'] is None
with engine.begin() as c:
 assert c.execute(text("SELECT COUNT(*) FROM actions WHERE state='RESERVED'")).scalar()==0
 assert c.execute(text("SELECT COUNT(*) FROM actions WHERE idempotency_key LIKE 'final-20261114-01:%'")).scalar()==0
print('Confirmed complete quota trajectory: 18,17,19,18,20,18,20,18,20; all <=20')
PY
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T -e DEMO_RUN_ID=final-20261114-01 -e DEMO_RESOURCE=aws-accept-cost-ade1070aa59e -e DEMO_TIMEOUT_SECONDS=180 -e BOTKERNEL_API_URL=http://api:8000 api python -m botkernel.live_demo > backups/final-acceptance-20261114/final-demo.json
cat backups/final-acceptance-20261114/final-demo.json