# BotKernel Demo Environment Readiness and Recording Guide

Latest continuation: [AWS_DEMO_READY.md](AWS_DEMO_READY.md) is the current startup, approval, private-tunnel and rehearsal checklist. AWS identity lookup now fails with expired login, so all current cloud state and browser access are UNKNOWN, regardless of historical observations below. No fresh oscillation run or final dataset was created. Do not invoke `botkernel.live_demo --help`: it has no CLI parser and would execute the demo.

**Checked:** 2026-11-13
**Scope:** Read-only runtime discovery, UI/data audit, and recording preparation.
**Result:** The existing local console is usable, but a fresh end-to-end recording is **not ready**. No containers, services, AWS resources, Kubernetes resources, or application data were changed in this audit.

## Readiness summary

- The authenticated local dashboard at `http://127.0.0.1:5173` proxies to API `http://127.0.0.1:18680`; health and readiness return `ok` and `ready`. PostgreSQL, Redis, and Kafka connectivity were verified through the running local acceptance stack.
- The current dashboard data is historical: 9 registered identities, no recent heartbeats or saved decision snapshots, 22 successful ledger actions, one `VERIFIED` incident with two interventions and one recurrence, six completed deterministic investigation reports, and 20 saved simulator runs.
- The selected Effect Graph window has no recent committed effects. This is consistent with the time-bounded graph query and historical actions; the incident selector highlights evidence but does not expand the graph window.
- Docker Desktop has an 8,139,706,368-byte memory limit (about 7.58 GiB). Five active Kafka brokers use about 4 GiB in the observed sample, and several older worker containers are restarting. The repository recommends 6 GiB free for core Kubernetes services and 8 GiB free when agents and observability are enabled. Starting another stack is not safe with the current capacity and running projects.
- Prometheus, Grafana, Jaeger, and the OTel Collector are stopped. The local metrics token is not configured in `.env`, and `.secrets\metrics.token` is absent.
- EC2 is stopped; SSM port forwarding is unavailable because the Session Manager plugin is missing and no managed-node record is present. Kubernetes context `docker-desktop` refuses connections; Helm is not installed.
- No fresh live-demo run, manifest, or new experiment was created. No real Bedrock inference was run.
- An operator credential appeared in the IDE selection during preparation. Treat it as exposed and rotate it before recording. Do not copy it into this guide, a terminal transcript, a URL, or the recording.

## 1. Actual runtime and port map

All current host bindings listed below are loopback-only. A missing host port means the service is only reachable inside its Docker network. Do not infer cloud availability from a local listener.

| Service | Runtime | Container/internal port | Host/browser port | Exact URL | Status | API/data source | Required for video? |
|---|---|---:|---:|---|---|---|---|
| Primary React/Vite dashboard | Windows / Vite | 5173 | `127.0.0.1:5173` | `http://127.0.0.1:5173/` | Running; `/api/health` and `/api/ready` return 200. Its `.env` target is `http://127.0.0.1:18680`. | Vite proxy to the primary local API | Yes, for the current local console |
| Secondary React/Vite dashboard | Windows / Vite | 5189 | `127.0.0.1:5189` | `http://127.0.0.1:5189/` | Running, but appears to be a historical test UI. Its `/api/actions` response has the same four rows as API `18089`; the Vite process target itself was not directly observable. Do not use as the primary recording UI. | Likely API `18089`; inferred from matching response, not confirmed from process configuration | No |
| Primary local FastAPI | Docker, `botkernel-bedrock-e2e-90f2ff90` | `api:8000` | `127.0.0.1:18680` | `http://127.0.0.1:18680/health` and `/ready` | Running; health `ok`, readiness `ready` | PostgreSQL, Kafka, Redis; `.env` gates remain mock/disabled | Yes, for the current console |
| Secondary local FastAPI | Docker, `botkernel-bedrock-ui` | `api:8000` | `127.0.0.1:18580` | `http://127.0.0.1:18580/health` and `/ready` | Running and ready; separate test data | Its PostgreSQL at `15432`, Redis at `16390`, Kafka internal only | No |
| Test FastAPI | Docker, `botkernel-current-tests-run-9901d25de978` | `api:8000` | `127.0.0.1:18089` | `http://127.0.0.1:18089/health` and `/ready` | Running and ready; four action rows | Historical/current-test data; no published database ports | No |
| Not-ready test FastAPI | Docker, `botkernel-bedrock-e2e` | `api:8000` | `127.0.0.1:18088` | `http://127.0.0.1:18088/health` | Health `ok`, readiness unavailable; port is occupied | Test stack; PostgreSQL, Redis, and Kafka are internal | No |
| Primary PostgreSQL | Docker, primary local stack | `postgres:5432` | `127.0.0.1:15443` | `127.0.0.1:15443` | Container healthy; API readiness verifies database connectivity | Durable actions, effects, resources, incidents, transitions, and investigation reports | Yes, for the current local pipeline |
| Secondary PostgreSQL | Docker, `botkernel-bedrock-ui` | `postgres:5432` | `127.0.0.1:15432` | `127.0.0.1:15432` | Container healthy; separate test data | Historical test database | No |
| Primary Redis | Docker, primary local stack | `redis:6379` | `127.0.0.1:16391` | `127.0.0.1:16391` | Running; advisory status cache connectivity was checked | Latest decision snapshots; Redis is not authoritative for action outcomes | Yes, for the current local UI |
| Secondary Redis | Docker, `botkernel-bedrock-ui` | `redis:6379` | `127.0.0.1:16390` | `127.0.0.1:16390` | Running; separate test stack | Advisory cache | No |
| Kafka brokers | Docker, five active local stacks | `kafka:9092` (KRaft controller `9093`) | No host port; `19092` is free | Internal advertised address `kafka:9092` | Broker connectivity verified for the primary API. The acceptance Compose file describes a host listener, but the running primary container does not publish it. | Transactional outbox publisher and execution workers | Yes, for the local pipeline proof |
| Publisher, worker, recovery, controller | Docker | Metrics exporter `9100` internally when enabled | No host port | Compose service names on the private network | Primary and secondary acceptance services are running. Several older unrelated projects have restart loops. | Kafka/outbox, action ledger, recovery, controller | Yes, for the local pipeline proof |
| Cost and Performance agents | No active process/container found | N/A | N/A | N/A | Not running. Registered identities and ledger actions do not prove active independent agents. | Would use the agent gateway if deliberately enabled | Optional; do not imply they are currently running |
| Local Nginx dashboard | Docker/Windows | Expected container `8080` | Host `8080` is free | No local URL | No local Nginx/dashboard container is running | None | No |
| AWS dashboard Nginx | EC2 Docker | Container port `8080`; EC2 host loopback `127.0.0.1:8080` | No Windows listener currently | EC2-side expected URL: `http://127.0.0.1:8080/app` | EC2 is stopped. Port 8080 is supported by the deployment Compose/Nginx configuration and prior host-loopback verification, but is not live-reachable now. | Private Nginx proxy to EC2 FastAPI on internal `api:8000` | Optional; blocked |
| AWS SSM forward | Windows to EC2 | Remote port `8080` | Proposed local port `18090` (verified free) | If later approved and connected: `http://127.0.0.1:18090/app` | Not running; SSM plugin missing, no managed-node record, EC2 stopped. Local `18088` is already occupied by a test API. | IAM-authorized SSM port forward; no public ingress | Optional; blocked |
| Prometheus | Docker profile `observability` | `9090` | `127.0.0.1:19090` (free) | `http://127.0.0.1:19090` | Stopped. Metrics-only token missing from `.env` and `.secrets\metrics.token` is absent. | Scrapes `api:8000` and publisher/worker/recovery/controller exporters on private networks | Yes, only for the observability chapter |
| Grafana | Docker profile `observability` | `3000` | `127.0.0.1:13000` (free) | `http://127.0.0.1:13000` | Stopped. Compose config provides loopback-only anonymous read-only Viewer access; this is not operator-authenticated Grafana. | Prometheus; existing System, Execution, and Collective dashboards | Yes, only for the observability chapter |
| OTel Collector | Docker profile `observability` | OTLP gRPC `4317`, HTTP `4318` | No host port | Internal endpoint for a future demo: `http://otel-collector:4318` | Stopped; current API has no configured OTLP endpoint | Receives API/worker spans and exports to Jaeger | Yes, only for a trace chapter |
| Jaeger | Docker profile `observability` | UI `16686` | `127.0.0.1:16686` (free) | `http://127.0.0.1:16686` | Stopped; no current trace is retrievable | Receives OTel Collector exports | Yes, only for a trace chapter |
| Kubernetes dashboard service | Kubernetes | Documented service `dashboard:8080` | Future `kubectl` forward `18080` | If deployed: `http://127.0.0.1:18080/app` | No cluster connection, pods, service, or port-forward verified | Helm chart service; not the public landing page | Optional; unavailable |

Other verified listeners: host ports `8000`, `8080`, `19090`, `19092`, `13000`, and `16686` are free; `5173`, `5189`, `18088`, `18089`, `18580`, and `18680` are occupied as listed above. `18090` is free and was selected as the future SSM local port. The active containers include several historical test projects; they were not stopped, restarted, or deleted. `bk-final-regression` and `botkernel-current` have internal-only PostgreSQL/Kafka/Redis containers. Older `botkernel-investigation-proof`, `botkernel-langgraph-validation`, `botkernel-observe`, `botkernel-trace-verification`, `botkernel-ui-review`, and `botkernel-live` projects include worker restart loops. These are development/test stacks, not the current dashboard's backing project and not proof of a production deployment. The primary Kafka container advertises only `kafka:9092`, not `127.0.0.1:19092`.

### AWS boundary and cost

The private EC2 instance is stopped, type `m7i-flex.large`, in the intended `us-east-2` region. Read-only AWS calls used profile `botkernel-dev` with an explicit `--region us-east-2`; its configured default region is `us-east-1`, so keep the explicit region. A read-only pricing lookup found an Ohio Linux On-Demand rate of about **$0.09576/hour** while running. Compute is not accruing while the instance is stopped, but this is not a billing query: the retained 100-GiB encrypted gp3 volume and other retained resources can still incur charges. No instance start, SSM session, Bedrock call, IAM change, Terraform operation, or public-ingress change was made.

If the owner separately approves a future start and SSM becomes available, use the free local port rather than occupied `18088`:

```powershell
aws ssm start-session --profile botkernel-dev --region us-east-2 `
  --target '<owner-approved-instance-id>' `
  --document-name AWS-StartPortForwardingSession `
  --parameters '{"portNumber":["8080"],"localPortNumber":["18090"]}'
```

This is a future command template only; it was not run. Its prerequisites are a running, SSM-managed instance, the Session Manager plugin, and owner approval to incur compute cost. The EC2-side URL is `http://127.0.0.1:8080`; the Windows-side URL would be `http://127.0.0.1:18090`. No account ID, instance ID, or credential is included here.

### Kubernetes boundary

`kubectl` is installed and the selected `docker-desktop` context exists, but its API endpoint refuses connections. No pods, services, namespace, resource usage, or Helm release could be verified. Helm is unavailable, so no chart render was performed in this session. The chart and README are present; that is not evidence of a running deployment.

The chart README recommends at least 6 GiB free and 4 CPU cores for core services, or 8 GiB free and 6 cores when agents and observability are enabled, plus 8 GiB persistent storage. The current Docker engine has less than 8 GiB total memory before accounting for running containers. Do not create a cluster or install the chart automatically. For a later owner-approved local cluster, follow `infra\kubernetes\README.md`, create its database/operator/agent secrets from private files, and use the documented command:

```powershell
helm upgrade --install botkernel infra\kubernetes\botkernel `
  --kube-context docker-desktop --namespace botkernel-demo --create-namespace `
  --wait --wait-for-jobs --timeout 15m
```

Only after rollout checks pass should the documented dashboard forward be opened:

```powershell
kubectl --context docker-desktop -n botkernel-demo port-forward svc/dashboard 18080:8080
```

Neither command was run. Do not show a chart, service, or port-forward as a live Kubernetes deployment until a real cluster and pods have been verified.

## 2. Authenticated console pages and actual data

All five authenticated pages rendered in the browser audit without page errors or mutation requests. The page navigation was read-only. The dashboard footer labels resource telemetry as simulated.

| Page | Reads/data source | Current vs historical | Safe on-camera interaction and expected result |
|---|---|---|---|
| Mission Control `/app` | `/health`, `/ready`, `/agents`, `/actions`, `/resources`, `/incidents`. PostgreSQL supplies registry, action ledger, resource, and incident state; readiness checks PostgreSQL/Kafka; Redis is advisory. | Health/readiness are current probes. Ledger and incident counts are persisted history. Resource values are simulator state, not live cloud telemetry. Current API: 9 identities, 22 actions (all `SUCCEEDED`), 1 verified incident, 0 active incidents. | Show the connection/readiness pill, resource allocation, action ledger, and incident summary. Refresh and page navigation are reads; do not use incident mutation controls. |
| Agent Fleet `/app/agents` | `/agents` and `/actions`; identity/heartbeat rows are PostgreSQL-backed, latest decision snapshots come from Redis. Heartbeat freshness is 30 seconds. | The 9 identities are registered, but there are 0 recent heartbeats and 0 saved decision snapshots. The 22 action rows are history, not proof of running agent processes. | Search/filter and select an identity. It should show stale heartbeat/no decision snapshot and ledger history. A future live-demo actor is driven by one script, not an independent LangGraph process. |
| Effect Graph `/app/graph` | `/graph?window=...` and `/incidents`; committed effects are PostgreSQL-backed and relationships are derived from effect ordering/reversals. API accepts 1-3600 seconds; UI offers 5/15/60-minute windows. | The 60-second and 1-hour graph queries both returned 0 nodes, edges, and effects. The selected incident is historical. The incident selector highlights evidence; it does not filter or expand the graph node set. This is consistent with no committed effects in the selected recent window, not proof that the ledger has no history. | Select the 60-minute window, optionally choose the incident and inspect the empty-state explanation. After a fresh bounded run, expect recent effect nodes/edges only if the API returns them; verify the graph before recording. |
| Investigations `/app/incidents` | `/incidents`, `/actions`, `/incidents/{id}/investigations`; incidents, ledger, and saved reports are PostgreSQL-backed. | One persisted `VERIFIED` incident has 2 interventions, 1 recurrence, and 19 healthy samples; there are 0 currently active incidents. Six reports are `COMPLETE`, all `deterministic_mock`, with 96 findings total. No completed Bedrock report/model metadata exists. | Select the saved incident/report and expand findings/evidence. `Analyze Incident`, acknowledge, and resolve are mutations; do not click them on existing data. |
| Experiment Lab `/app/experiments` | `GET /experiments` and `GET /experiments/{run_id}` load local `benchmarks/results` artifacts, not PostgreSQL/Kafka. `POST /experiments` writes new simulator result files. | 20 saved runs exist. The latest displayed run is an oscillation comparison with seeds `17,23,41` and 120 virtual seconds. Results are deterministic simulator output; no database or Kafka workload is generated. | Select a saved run and inspect the three-mode chart/summary. Do not click Run during the recording; it creates new raw JSON/CSV artifacts and is not a live system test. |

The experiment harness compares independent agents, per-resource locks with a fixed cooldown, and the Collective Stability Controller against the same seeded schedule. It writes `raw.json`, `summary.csv`, `ticks.csv`, `effects.csv`, and `report.md`. Its synthetic workload/latency assumptions are not production telemetry. No experiment was rerun for this audit.

### Truthful interpretation of the screenshot observations

- **22 succeeded actions, zero recent heartbeats, nine registered identities:** consistent. Action rows persist in PostgreSQL; heartbeat health is only true for the last 30 seconds. No active Cost/Performance containers were found.
- **One incident recorded, zero active:** consistent. The incident is historical and verified, not an active alert.
- **Fleet has stale heartbeats and no saved decisions:** consistent with no running agent processes and no recent Redis decision snapshots; do not present registry rows as live agents.
- **Empty Effect Graph at 60 minutes:** consistent with its time filter when no committed effects fall in the last hour. The API maximum is one hour; an incident selection only highlights linked evidence.
- **Verified incident with two interventions and one recurrence:** a persisted lifecycle record, not a bug or currently active incident.
- **Saved deterministic findings and an oscillation three-seed run:** stored evidence, not current model inference or a live database/Kafka evaluation.

Do not alter historical rows to make these screens look populated. A new isolated, bounded demo is the proper way to create recent graph/controller evidence.

## 3. Fresh local demo decision and exact preparation command

`scripts\run-live-demo.ps1` and `botkernel\live_demo.py` were reviewed but **not executed**. The script creates a uniquely named Compose project, chooses a free API port, waits for `/ready`, and runs a bounded demo with an overall 180-second demo timeout and 240-second process bound. The driver registers/acts as `cost-demo` and `performance-demo`, submits eight actions across two oscillation cycles, waits for detection/verification/recurrence, and persists/replays a deterministic investigation. It is one deterministic driver impersonating two registered identities, **not two independent LangGraph processes**.

Do not run it in the current Docker state: starting another broker/database/controller/worker stack risks resource exhaustion, and stopping unrelated historical stacks was not authorized. The current `5173` frontend points to an existing acceptance database, so do not point the fresh demo at it. No dataset or private demo manifest was created.

After the owner has safely resolved Docker capacity and chosen an isolated local run, use a PowerShell terminal at the repository root. Read the operator token from the ignored `.env` without echoing it; set the flags in-process; then run the script once:

```powershell
$operatorLine = Get-Content .env | Where-Object { $_ -match '^BOTKERNEL_OPERATOR_TOKEN=' } | Select-Object -First 1
if (-not $operatorLine) { throw 'Operator credential is missing from ignored .env.' }
$env:BOTKERNEL_OPERATOR_TOKEN = $operatorLine.Substring($operatorLine.IndexOf('=') + 1).Trim().Trim('"').Trim("'")
$env:BOTKERNEL_LIVE_DEMO_PROJECT = 'botkernel-recording-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$env:CLOUD_MODE = 'mock'
$env:AWS_DEPLOY_ALLOWED = 'false'
$env:BEDROCK_ENABLED = 'false'
$env:BEDROCK_SPEND_AUTHORIZED = 'false'
$env:AI_ACTION_EXECUTION_ENABLED = 'false'
$env:AGENT_PROVIDER = 'deterministic_mock'
$env:INVESTIGATOR_PROVIDER = 'deterministic_mock'
try { .\scripts\run-live-demo.ps1 }
finally { Remove-Item Env:\BOTKERNEL_OPERATOR_TOKEN -ErrorAction SilentlyContinue }
```

Run this during preflight, not while exposing the token file or a credential-bearing terminal on camera. Confirm exit code 0, the printed API URL, `Persisted incidents`, action/effect/receipt counts, and that the incident lifecycle and saved report exist before recording. If the run is interrupted or its result is ambiguous, inspect that exact project/database before retrying; do not start a second project blindly. Save any resulting IDs, URLs, actual counts, and timestamp in a private local manifest with no token values. No such run or manifest exists from this audit.

To show the fresh API in a separate dashboard process, first use the exact API URL printed by the script. Port `5174` was verified free during this audit:

```powershell
$env:BOTKERNEL_API_TARGET = 'http://127.0.0.1:<api-port-printed-by-script>'
Set-Location apps\dashboard
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

The fresh dashboard would be `http://127.0.0.1:5174/`; do not change the existing `5173` process or its current data target for the recording.

### Observability prerequisites for that isolated run

Observability was not started. Before a separately approved local observability run, the owner must resolve capacity, create a metrics-only credential in the ignored `.env` and matching `.secrets\metrics.token`, and set:

```text
BOTKERNEL_METRICS_TOKEN=<private metrics-only value>
BOTKERNEL_OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
COMPOSE_PROFILES=observability
```

Do not put the value in this guide or a terminal transcript. The Compose Prometheus service mounts the metrics token file; the API separately needs the matching metrics-only token. The collector endpoint is internal to the Compose network. Loopback Grafana is read-only anonymous by the current Compose configuration; do not expose it on a non-loopback interface.

## 4. Metrics, Grafana, and Jaeger

All observability URLs are currently stopped/free and are only planned URLs until the `observability` profile is started and readiness/targets are verified.

| Surface | Useful panels/queries | What to verify after the bounded run |
|---|---|---|
| Grafana System: `http://127.0.0.1:13000` | API scrape; HTTP requests/sec and p95; Actions by state; Outbox backlog; Worker scrape health; Incidents by status. | API/background scrape targets become `up`; action states reflect the actual eight-action run; outbox backlog may rise during dispatch and should return to zero when drained. |
| Grafana Execution | Transport/recovery operations; committed effects (durable rows); execution attempts; dead letters; outbox backlog. | Committed effects and execution attempts should reflect verified receipts. Do not claim a throughput benchmark from these panels. |
| Grafana Collective | Controller evaluations/sec and p95; incidents by state; durable interventions and recurrences. | Controller evaluations and the incident lifecycle should correspond to the actual new incident. Durable counts are verified from PostgreSQL, not inferred from a chart. |
| Prometheus: `http://127.0.0.1:19090` | `botkernel_committed_effects`; `sum by (status) (botkernel_incidents)`; `botkernel_interventions`; `botkernel_recurrences`; `rate(botkernel_operations_total{operation="controller"}[1m])`. | Confirm targets at `/api/v1/targets` and verify query timestamps/sample values. These metrics are not currently being scraped. |
| Jaeger: `http://127.0.0.1:16686` | Search service `botkernel-api`, lookback last 15 minutes; open `botkernel.http.action_submit`. | A real trace must be retrieved after enabling export. Expand `botkernel.action.admission` and `botkernel.postgresql.reserve_and_outbox`, then check publisher `botkernel.kafka.publish` and worker `botkernel.kafka.consume`, `botkernel.simulator.commit_receipt`, and `botkernel.postgresql.finalize_action`. Kafka context propagation and controller/recovery span links may not form one direct parent-child tree. |

The current API has an empty OTLP endpoint, the observability containers are stopped, and no trace is retrievable now. Earlier handoff validation documented a representative trace, but that historical result is not a currently available trace. Do not claim an end-to-end trace until a new trace is visible in Jaeger. The service names configured in Compose are `botkernel-api`, `botkernel-publisher`, `botkernel-worker`, `botkernel-recovery`, and `botkernel-controller`.

## 5. Bedrock status

Only **Mode A (offline/mock)** is appropriate for this recording: deterministic/mock workflow results and the persisted deterministic investigator reports. The current investigator UI labels these as `DETERMINISTIC_MOCK / NO LLM`. The Agent Fleet UI supports provider/model/usage provenance when a decision snapshot exists; the Investigator UI supports Bedrock model ID and token usage for a completed Bedrock report. Current data has no completed Bedrock decision or report, and there are no current decision snapshots.

The earlier Nova Micro Cost attempt ended ambiguously with `bedrock_client_error`; subsequent mocked workflows do not prove real inference. `BEDROCK_ENABLED`, spending authorization, and AI action execution remain disabled. **Mode B was not run**; do not invoke Bedrock or show mocked output as a real model result.

## 6. No-voice recording storyboard (7:25 target)

Run the bounded demo and validate its data before starting the timed recording. The timed recording shows verified evidence; it does not rerun or mutate the experiment. Keep the operator session authenticated before capture, hide the password field, and never open `.env`, secret files, AWS account pages, credential-bearing process output, or raw environment dumps.

| Order / duration | Browser URL or terminal | Exact action | Expected screen/result | On-screen caption |
|---|---|---|---|---|
| 1 / 0:25 | `http://127.0.0.1:5174/` | Show the public landing page; click **Launch console**. | Landing page loads, then authenticated console. | `Reliability across autonomous agents` |
| 2 / 0:25 | PowerShell, repo root | Show only `docker compose -p $env:BOTKERNEL_LIVE_DEMO_PROJECT --profile stability --profile demo ps`. | Isolated project services are running; the bounded `live-demo` process exited successfully. Do not show unrelated project stacks. | `Isolated local simulator runtime` |
| 3 / 0:30 | `http://127.0.0.1:5174/app` | Show connected/readiness state, resource allocation, recent ledger, and incident summary. | Fresh local simulator evidence only; resource telemetry remains labeled simulated. | `One operational control surface` |
| 4 / 0:30 | `/app/agents` | Search/select `cost-demo` and `performance-demo`; inspect ledger activity. | Two registered demo actors and their gateway outcomes. State that one driver impersonated the two actors; do not call them independent processes. | `Two actors, one bounded driver` |
| 5 / 0:35 | PowerShell output from the preflight run | Show the already completed script summary and API URL; do not rerun it. | Eight bounded actions, worker receipts/effects, incident lifecycle and persisted investigation, subject to database verification. | `Admitted, executed, reconciled` |
| 6 / 0:35 | PowerShell, repo root | Run the read-only PostgreSQL counts below and show publisher/worker logs from this exact project. | Counts should match the verified run; outbox should be drained and receipts/effects present. | `Outbox to durable effects` |
| 7 / 0:30 | `/app/graph` | Choose 60 minutes; select the new incident; click an evidence node if present. | Recent committed-effect graph and links for the new run. If it is empty, stop and investigate rather than implying data. | `Cross-agent effects, visible` |
| 8 / 0:35 | `/app/incidents` | Select the new incident and show lifecycle/status and intervention/recurrence counts. Do not acknowledge or resolve it. | Persisted HOLD/VERIFYING/VERIFIED/ESCALATED lifecycle consistent with actual run; no fabricated status. | `Containment with verification` |
| 9 / 0:30 | `/app/incidents` report panel | Select the already saved report; expand findings and timeline. Do not click **Analyze Incident**. | Persisted deterministic evidence; advisory only. | `Evidence before hypotheses` |
| 10 / 0:20 | `/app/incidents` report panel | Hold on provider/model provenance. | Clearly reads deterministic/mock and no LLM. No Bedrock inference is claimed. | `Mock reasoning, clearly labeled` |
| 11 / 0:35 | `http://127.0.0.1:13000` | Open System, Execution, then Collective dashboard. | Prometheus targets are up; panels reflect the verified run. | `Operational signals, not theater` |
| 12 / 0:35 | `http://127.0.0.1:16686` | Search `botkernel-api`, last 15 minutes; open a newly retrieved action trace. | Show only spans that actually exist. If no trace appears, stop this chapter and do not claim end-to-end tracing. | `Follow one action trace` |
| 13 / 0:35 | `/app/experiments` | Select the existing oscillation run and compare the three labeled modes. Do not run a new experiment. | Clearly marked simulator-only comparison with seeds and virtual duration. | `One schedule, three strategies` |
| 14 / 0:25 | Optional AWS/Kubernetes tab | Omit while stopped/unavailable. Do not open account identifiers or imply a live cloud/cluster runtime. | Only include after separate owner authorization and fresh health verification. | `Private deployment, separately gated` |
| 15 / 0:20 | Mission Control or landing page | Return to a clean overview and hold. | Local mock mode and simulation boundary remain clear. | `Measured locally, gated by design` |

The timed target including the optional status chapter is about **7 minutes 25 seconds**. The preflight script can take up to its configured process bound; if demonstrating its execution live would exceed the target, run it before recording and show its verified output in scene 5. Never start a second run merely to improve the footage.

Read-only PostgreSQL proof for scene 6 (run in PowerShell from the repository root after the fresh project is verified):

```powershell
docker compose -p $env:BOTKERNEL_LIVE_DEMO_PROJECT --profile stability --profile demo `
  exec -T postgres psql -U botkernel -d botkernel -c `
  "SELECT (SELECT count(*) FROM actions) AS actions, (SELECT count(*) FROM outbox WHERE published) AS published_outbox, (SELECT count(*) FROM receipts) AS receipts, (SELECT count(*) FROM effects) AS committed_effects;"
docker compose -p $env:BOTKERNEL_LIVE_DEMO_PROJECT --profile stability --profile demo `
  exec -T postgres psql -U botkernel -d botkernel -c `
  "SELECT status, intervention_count, recurrence_count FROM incidents ORDER BY opened_at DESC LIMIT 1;"
docker compose -p $env:BOTKERNEL_LIVE_DEMO_PROJECT --profile stability --profile demo `
  logs --since 5m --no-color publisher worker
```

These are inspection queries/log reads. Run them only against the unique demo project, never the existing development or cloud database. Do not record credentials, full environment output, AWS account identifiers, or a token-bearing URL.

### Pause/abort points

- If `/ready` is not ready, stop before submitting actions. Do not start a second stack or switch to an unrelated API.
- If the bounded script exits nonzero, its output is ambiguous, or effect/receipt counts do not match actions, stop recording and inspect that same project. Do not blindly retry.
- If Fleet shows stale actors, say they are registered historical demo identities; do not claim live independent agents.
- If the graph is empty, stop the graph chapter and diagnose the time window/effects.
- If no completed investigator report exists, do not click Analyze during the recording; prepare the deterministic report in preflight and verify persistence first.
- If a Grafana target is down or Jaeger has no trace, omit that claim/chapter. Do not manufacture metrics or traces.
- If the AWS instance is stopped, SSM is unavailable, or Kubernetes cannot be queried, omit those chapters.
- Never enable Bedrock, spending authorization, AWS deployment, or model-driven action execution during this preparation.

## 7. Safe shutdown

No shutdown command was run because no service was started or modified. For a future isolated local demo, preserve data and volumes:

```powershell
docker compose -p $env:BOTKERNEL_LIVE_DEMO_PROJECT --profile stability --profile demo stop
# Optional container/network cleanup while retaining named volumes; never add -v:
docker compose -p $env:BOTKERNEL_LIVE_DEMO_PROJECT --profile stability --profile demo down
```

Do not stop or remove the existing historical test projects to make room without owner approval. For an explicitly approved AWS demo, first quiesce application services over SSM with the documented `sudo docker compose --env-file /opt/botkernel/runtime.env -f /opt/botkernel/compose.aws-demo.yaml stop`; preserve volumes and close the tunnel. Stopping EC2 is a separate owner decision after checking for other sessions/workloads. The EC2 stop command above is only a future template after that approval. Never use `down -v`, delete volumes, or terminate the instance as routine cleanup.

## Final recording-readiness checklist

- **GREEN:** Existing authenticated local console at `http://127.0.0.1:5173`; primary API/PostgreSQL/Kafka/Redis connectivity and health/readiness verified; five pages audited read-only; current historical state explained.
- **YELLOW:** The current console has stale agent heartbeats and an empty recent graph; second Vite is a test UI; Docker contains crowded historical stacks and worker restart loops; a fresh local demo and private manifest do not exist; observability needs a metrics token and trace endpoint; Grafana is anonymous read-only on loopback.
- **RED / BLOCKED:** Do not start a new local stack under the current Docker memory limit; no local Prometheus/Grafana/Jaeger/collector is running; EC2 is stopped and SSM plugin/managed-node access are unavailable; Kubernetes is unreachable and Helm is absent; genuine Bedrock inference is unverified and gated off; rotate the exposed operator credential before recording.

**Bottom line:** A truthful recording can show the existing local console and historical simulator artifacts now, but it cannot yet demonstrate one fresh, consistent live pipeline plus observability. Resolve the Docker capacity/stack ownership decision and the private metrics/credential prerequisites first; AWS, Kubernetes, and paid Bedrock remain separately gated.

## Verified continuation — 2026-11-14

AWS browser smoke passed landing plus /app, /app/agents, /app/graph, /app/incidents, /app/experiments via actual SSM18090->8080; all API checks200, zero pageerrors. Grafana13000 three dashboards, Prometheus19090/targets and Jaeger16686/trace/8bafab00abf74a0da4a6273c72653d3f rendered. These are verified historical URLs, now unavailable: all task-owned tunnels closed and EC2 stopped05:33:39UTC. Operator token is protected in ignored .secrets/aws-console-access/operator.token; never show it. No final eight-action scenario was run. Incident2 is ESCALATED and has no report because Bedrock stopped at failed Cost validation; do not imply live AI completion. Existing effects now exceed1h graph window, so recording needs a separately approved fresh scenario and reviewed quota/holds (fixture allocation19/20). Begin with aws ec2 describe-instances --profile botkernel-dev --region us-east-2 --instance-ids i-0b30b3106988f698e; obtain runtime authorization before start. Use latest AWS_DEMO_READY.md plus PROJECT_HANDOFF.md exact image IDs and commands. Kubernetes remains unavailable; never show chart renders as runtime.
