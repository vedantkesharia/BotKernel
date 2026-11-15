# BotKernel dashboard

The React/Vite dashboard reads operational state from FastAPI. The landing contains an illustrative architecture diagram; console views use API data and label simulator capacity/latency. It does not claim actual cloud utilization or fabricate live metrics.

## Routes and authentication

| Route | View |
|---|---|
| `/` | Public landing; no operator API requests |
| `/app` | Mission Control: health/readiness, allocation and ledger |
| `/app/agents` | Fleet: registration, decisions, provenance and action outcomes |
| `/app/graph` | Effect Graph: committed relationships, inferred reversals, filters and inspection |
| `/app/incidents` | Investigations: lifecycle, evidence and saved reports |
| `/app/experiments` | Deterministic experiments, saved runs, charts and exports |

Legacy `/agents`, `/graph`, `/incidents` and `/experiments` redirect to `/app/...`, preserving query strings. There are six routes: the landing and five console views.

Sign-in validates the operator bearer credential through `/auth/session`. The [API client](src/api.ts) retains it **only in memory**, sends bearer headers with credentials omitted and caching disabled, and clears it on an authenticated 401. Full-page reload requires sign-in again. Investigation session-storage idempotency keys are request identities, not saved credentials. Keep access private; shared-token authentication is not public multi-user authorization.

## Local development

Configure a private stack and distinct operator/agent credentials using the [root README](../../README.md). Confirm its `/ready` endpoint succeeds. From this directory:

```powershell
npm ci
npm run dev
```

Use the URL Vite prints. Server-only `BOTKERNEL_API_TARGET` selects the backend; Vite reads repository environment configuration without exposing operator/agent tokens to browser code. Production Nginx proxies `/api/` over the private Compose network. Never put credentials in frontend build variables.

`npm test` runs Vitest; `npm run build` checks TypeScript and builds Vite; `npm run test:e2e` runs Chromium tests against the selected backend. Browser tests need Chromium, an isolated populated API and its operator credential. Experiments and demo drivers mutate simulator data; retain volumes when stopping the selected stack. These commands are usage instructions, not checks executed during documentation editing.

## Data and action boundaries

Mission Control derives readiness from `/health` and `/ready`; availability does not establish throughput. Fleet shows persisted provenance and authoritative outcomes when available. Graph links distinguish observations from inferences. Incident acknowledgement/resolution is state-gated and requires reasons/idempotency keys. Analysis gathers read-only evidence and saves reports, separating model hypotheses from deterministic findings.

Experiments use a deterministic discrete-event harness. Tick-level alarm occupancy and episode-level matching have different denominators; neither establishes production accuracy. See [benchmarks](../../docs/BENCHMARKS.md) and [audit](../../docs/BENCHMARK_AUDIT.md).

Bedrock and model-driven actions default to disabled. Genuine November 14 acceptance included advisory Cost/Performance `NO_OP` responses and a persisted Investigator report; it did not demonstrate model remediation. The private AWS landing and all five console views passed authenticated browser smoke, including graph inspection and saved usage. AWS is now stopped. Recorded frontend validation passed the build and 6 unit tests, with the existing large-bundle warning. See [validation](../../docs/VALIDATION.md), [LangGraph](../../docs/LANGGRAPH.md) and [Bedrock acceptance](../../docs/BEDROCK_ACCEPTANCE.md).
