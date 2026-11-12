# BotKernel local incident-to-investigation demo

This bounded walkthrough uses the existing Docker Compose application and real PostgreSQL/Kafka execution path. The live-demo workload is a deterministic single-process driver registering two identities; it is not a pair of autonomous LangGraph processes. It exercises real gateway admission, outbox publication, Kafka worker effects, controller lifecycle transitions and the read-only investigator.

## Before starting

Check `docker compose ls --all` and Docker memory use. The demo script creates an isolated Compose project with PostgreSQL, Kafka, Redis, API, publisher, worker, recovery and controller services. Do not launch another project if the host is already resource constrained. It uses a new project name and local volumes; it does not connect to AWS or invoke Bedrock.

## Run on Windows PowerShell

From the repository root:

```powershell
$env:BOTKERNEL_LIVE_DEMO_PROJECT = "botkernel-live-demo-$(Get-Random)"
$env:DEMO_RESOURCE = "service-a"
$env:DEMO_TIMEOUT_SECONDS = "180"
.scriptsun-live-demo.ps1
```

The script builds/starts the local stack, waits for `/ready`, runs eight bounded actions, and waits for controller detection, sustained verification, recurrence and selective containment. It then requests an investigation with `provider=deterministic_mock`, GETs the saved report, repeats the same idempotency key and checks every report action against the gateway ledger and current Effect Graph window.

The final JSON includes the actual Compose project run ID, resource, action IDs, incident lifecycle, investigation ID/status/provider, effect timeline, reversals, finding-class counts, graph-reference check and duplicate-request check. A COMPLETE report is deterministic analysis, not LLM reasoning. Investigation recommendations are advisory; no remediation runs.

The output also prints a loopback API URL. In a second terminal, connect the dashboard to that exact API:

```powershell
Set-Location apps/dashboard
$env:BOTKERNEL_API_TARGET = "http://127.0.0.1:<printed-port>"
npm run dev
```

Open the Vite URL. `/` is the product landing page and `/app/incidents` is the investigation console. The incident list and report are backed by the demo PostgreSQL database. The Effect Graph link opens `/app/graph` with the selected action and resource in its query parameters.

## Verify directly

Replace the port and IDs with values printed by the run:

```powershell
Invoke-RestMethod "http://127.0.0.1:<port>/ready"
Invoke-RestMethod "http://127.0.0.1:<port>/incidents/<incident-id>/investigations"
Invoke-RestMethod "http://127.0.0.1:<port>/investigations/<investigation-id>"
Invoke-RestMethod "http://127.0.0.1:<port>/graph?window=3600&resource=<resource-id>"
```

Actions should reach `SUCCEEDED`, with a published outbox event, simulator receipt and one versioned effect per logical action. Controller lifecycle state and investigation reports are separate durable records. The chart and capacity values describe the simulator, not measured EC2 utilization or production latency.

## Stop without deleting evidence

The runner prints the generated project name and this non-destructive command:

```powershell
docker compose -p <printed-project-name> down
```

Do not add `-v`; named PostgreSQL/Kafka/Redis volumes remain for inspection. Keep benchmark exports and local checkpoints. No cloud resources or costs are created by this demo.
