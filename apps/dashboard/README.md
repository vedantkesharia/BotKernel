# BotKernel dashboard

The React 19/Vite dashboard reads operational state from the local FastAPI service; it contains no fabricated telemetry.

## Routes

- `/` - product landing page; it makes no operator API requests.
- `/app` - API-backed Mission Control.
- `/app/agents` - registered agents and ledger activity.
- `/app/graph` - observed and inferred effect relationships from `/graph`.
- `/app/incidents` - incident evidence, lifecycle, saved reports and state-gated local acknowledgement/resolution.
- `/app/experiments` - bounded seeded comparisons, saved runs, charts and exports.

Legacy `/agents`, `/graph`, `/incidents` and `/experiments` URLs redirect to `/app/...`, preserving query strings used for evidence navigation.

## Local development

Start an explicitly named local stack from the repository root in PowerShell:

```powershell
$env:BOTKERNEL_API_PORT='18019'
$env:BOTKERNEL_OPERATOR_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:BOTKERNEL_AGENT_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose -p botkernel-neutral-review up --build -d postgres redis kafka init api publisher worker recovery controller
Invoke-RestMethod http://127.0.0.1:18019/ready
Invoke-RestMethod http://127.0.0.1:18019/experiments -Headers @{ Authorization = "Bearer $env:BOTKERNEL_OPERATOR_TOKEN" }
```

Then, from `apps/dashboard` in another terminal:

```powershell
npm ci
$env:BOTKERNEL_API_TARGET='http://127.0.0.1:18019'
npm run dev
```

Open `http://127.0.0.1:5173` after Vite starts; if that port is in use, use the URL Vite prints. Vite requires an explicit `BOTKERNEL_API_TARGET` during development. This prevents a stale API container on port 8000 from silently serving `/ready` while returning 404 for `/experiments`. Both API checks above must return successfully. To create real graph and incident data, run `docker compose -p botkernel-neutral-review exec -T api python -m botkernel.live_demo` from the root. The bounded driver uses two registered identities but is one process and modifies this project's local demo data. Stop with `docker compose -p botkernel-neutral-review down`; do not add `-v` because that deletes its named volumes. The review stack is currently stopped, with its volumes retained.

`npm test` runs Vitest unit tests, `npm run build` runs TypeScript and Vite, and `npm run test:e2e` runs Chromium tests against the selected backend. Browser tests require Chromium (`npx playwright install chromium`) and a populated local API. Screenshots of all five routes at 1440x900, 1280x800 and 390x844 are saved under Git-ignored `visual-review/`.

Compose mounts the host `benchmarks/results` directory into the API. A bounded healthy-scaling run was written to that directory, and `/experiments/{id}` returned it after API container recreation. Browser tests also generate real simulator runs in this directory; keep them separate from operational performance benchmarks.

Experiment runs use the deterministic discrete-event harness, not a PostgreSQL/Kafka performance test. Results and limitations are documented in `../../docs/BENCHMARKS.md`. Playwright coverage includes desktop and mobile layouts, a real API-backed experiment, graph node/edge selection and filtering, incident evidence, mobile navigation, and API error/input-validation states. Set `BOTKERNEL_OPERATOR_TOKEN` in the Playwright process to the isolated API's credential. Keep the API private despite authentication.

The dashboard uses configured shadcn/ui primitives, Motion, Recharts and XYFlow. The public landing is separate from the authenticated API-backed console and uses an illustrative architecture diagram, not fabricated live metrics. Mission Control derives readiness from `/health` and `/ready`, shows authoritative simulator allocation and recent ledger records, and does not claim throughput or actual AWS utilization. Investigations preserve evidence classifications and link actions into the Effect Graph. The lab's precision, recall, F1 and false-positive rate remain tick-level alarm occupancy, not episode-level incident metrics. Measured infrastructure performance charts remain future work. See `../../docs/BENCHMARK_AUDIT.md`.

Investigation requests now reserve one of two default PostgreSQL session advisory-lock slots (`INVESTIGATION_MAX_CONCURRENT`, 1..16; configure consistently across instances). A new request gets HTTP 503 when no slot is free; duplicate requests reuse their record. The claim transaction commits before graph execution, while a dedicated pooled database connection holds the session lock; normal release and connection invalidation on release errors are implemented. A database disconnect releases locks even if Python computation continues; the lease fences finalization but does not terminate computation. This is not a hard global computation bound under lost database sessions and a hung live owner may retain a slot until its connection dies. The existing five-second SQL statement limit is not a whole-graph timeout.

The existing Investigations page includes an API-backed saved-report panel, Analyze Incident, retry-stable session-storage keys, status/classification display and graph evidence links. The landing page and investigation-to-graph flow have repeatable Chromium coverage against the current local API. Visual checks cover 1440x900, 1280x800 and 390x844. A local E2E run created and retrieved a persisted report for a genuine Kafka/controller incident. Bedrock was not invoked.

The Agent Fleet displays actual persisted provider/model provenance, latest structured decision, evidence, gateway approval and authoritative action/effect status when available. Investigations can explicitly request optional Bedrock analysis after deterministic evidence gathering; hypotheses are labeled, evidence links are validated, and recommendations are advisory. Mission Control reads `/health` and `/ready`, labels resources and telemetry as simulator data, and does not claim cloud utilization. Bedrock is disabled by default and was not live-verified; see `../../docs/LANGGRAPH.md`.

## Private AWS demo (deployed)

The deployment image is built from `Dockerfile.deploy` and served by Nginx with `/api/` proxied to FastAPI on the private Compose network. PostgreSQL, Kafka, Redis and the direct API have no host-published ports. The updated authentication has not been deployed or verified in AWS; do not expose this deployment to the public internet or a shared tunnel. Follow [`../../infra/terraform/README.md`](../../infra/terraform/README.md) for the generic deployment design and prerequisites; no current cloud resource state is asserted.

