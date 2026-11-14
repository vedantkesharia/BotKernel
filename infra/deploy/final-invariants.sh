set -euo pipefail
cd /opt/botkernel
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python - <<'PY'
import json,httpx
from sqlalchemy import text
from botkernel.core import engine
from botkernel.security import operator_headers
q="""SELECT a.id::text,a.idempotency_key,a.state,
 (SELECT count(*) FROM outbox o WHERE o.action_id=a.id) outbox_count,
 (SELECT bool_and(published) FROM outbox o WHERE o.action_id=a.id) published,
 (SELECT count(*) FROM receipts r WHERE r.action_id=a.id) receipts,
 (SELECT count(*) FROM effects e WHERE e.action_id=a.id) effects,
 (SELECT trace_context FROM outbox o WHERE o.action_id=a.id LIMIT 1) trace_context
 FROM actions a WHERE a.idempotency_key LIKE 'final-20261114-01:%' OR a.idempotency_key='final-20261114:quota-release:cost' ORDER BY a.created_at"""
with engine.begin() as c:
 rows=[dict(x) for x in c.execute(text(q)).mappings()];assert len(rows)==9
 assert all(x['state']=='SUCCEEDED' and x['outbox_count']==x['receipts']==x['effects']==1 and x['published'] for x in rows)
 print('INVARIANTS',json.dumps(rows))
 print('TOTAL_EFFECTS',c.execute(text('SELECT COUNT(*) FROM effects')).scalar())
 print('RESOURCE',list(c.execute(text("SELECT capacity,version FROM resources WHERE id='aws-accept-cost-ade1070aa59e'")).one()))
with httpx.Client(base_url='http://api:8000',headers=operator_headers(),timeout=15) as c:
 graph=c.get('/graph?window=3600&resource=aws-accept-cost-ade1070aa59e').raise_for_status().json()
 print('GRAPH',json.dumps({'nodes':len(graph['nodes']),'edges':len(graph['edges']),'evidence':len(graph['evidence'])}))
 for i in c.get('/incidents').raise_for_status().json():
  if i['id'] in (2,3): print('INCIDENT',json.dumps({k:i[k] for k in ['id','status','resource','intervention_count','recurrence_count']}))
PY
docker inspect --format '{{.Name}} restarts={{.RestartCount}} oom={{.State.OOMKilled}} state={{.State.Status}}' $(docker compose --env-file runtime.env -f compose.aws-demo.yaml -f compose.metrics-access.yaml --profile observability ps -q)
free -m
docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}'