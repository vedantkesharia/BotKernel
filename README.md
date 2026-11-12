# BotKernel

**Evidence-driven coordination and reliability for independently operating agents.**

BotKernel is a distributed AgentOps platform for detecting and containing harmful interactions between autonomous agents sharing infrastructure. It combines durable action execution, a deterministic Collective Stability Controller, evidence-grounded incident investigation, and an operator dashboard. Unlike a chatbot or agent-framework demo, its core contribution is controlling shared-system side effects and retaining evidence across asynchronous execution.

> **Implementation status:** Local PostgreSQL/Kafka execution, simulator, stability controller, deterministic agents/investigator, and dashboard are implemented. Bedrock integration exists behind explicit gates, but live inference has not been verified. AWS state may be stale or unknown. Do not infer cloud deployment readiness from historical notes.

## Architecture

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 24, "rankSpacing": 35, "padding": 15, "subGraphTitleMargin": {"top": 8, "bottom": 20}}}}%%
flowchart TB
  classDef service fill:#f8fafc,stroke:#64748b,color:#0f172a,stroke-width:1.2px;
  classDef datastore fill:#eff6ff,stroke:#64748b,color:#0f172a,stroke-width:1.2px;
  classDef control fill:#f5f3ff,stroke:#8b7cc8,color:#1e1b4b,stroke-width:1.2px;
  classDef optional fill:#f9fafb,stroke:#9ca3af,color:#374151,stroke-dasharray:4 4;
  classDef ui fill:#f0fdfa,stroke:#5f9e96,color:#134e4a,stroke-width:1.2px;
  classDef infra fill:#fff7ed,stroke:#c49a78,color:#431407,stroke-width:1.2px;

  subgraph L1["Agent Reasoning Layer"]
    TEL["Simulator Telemetry<br/>(via API)"]:::service
    BED["Bedrock<br/>(optional)"]:::optional
    REDIS["Redis<br/>(advisory)"]:::optional
    COST["Cost Agent<br/>(LangGraph)"]:::service
    PERF["Performance Agent<br/>(LangGraph)"]:::service
    TEL --> COST & PERF
    BED -.-> COST & PERF
    REDIS -.-> COST & PERF
  end

  subgraph L2["Durable Execution Layer"]
    API["FastAPI Gateway"]:::service
    PG["PostgreSQL<br/>ledger · reservations · outbox"]:::datastore
    PUB["Outbox Publisher"]:::service
    KAFKA["Kafka<br/>at-least-once"]:::datastore
    WORK["Execution Workers"]:::service
    SIM["Simulator Effects"]:::service
    REC["Recovery<br/>Service"]:::service
    API --> PG --> PUB --> KAFKA --> WORK --> SIM
    REC --> PG
  end

  subgraph L3["Stability & Investigation Layer"]
    EFFECTS["Committed Effects<br/>(PostgreSQL)"]:::datastore
    GRAPH["Committed-Effect Graph"]:::control
    CTRL["Collective Stability Controller"]:::control
    INC["Incidents<br/>(PostgreSQL)"]:::datastore
    HOLD["Resource Holds<br/>(gateway-enforced)"]:::control
    INV["Incident Investigator<br/>(LangGraph)"]:::control
    RPT["Persisted Reports<br/>(PostgreSQL)"]:::datastore
    EFFECTS --> GRAPH --> CTRL --> INC
    CTRL --> HOLD
    EFFECTS -. evidence .-> INV
    INC -. on demand .-> INV
    INV --> RPT
  end

  subgraph L4["Operator Experience & Observability"]
    READ["FastAPI<br/>read endpoints"]:::service
    DASH["React Operations Dashboard<br/>API-backed"]:::ui
    EXP["Experiment Lab"]:::ui
    OBS["Prometheus · Grafana<br/>OpenTelemetry · Jaeger"]:::ui
    READ --> DASH
    DASH --- EXP
    EXP ~~~ OBS
  end

  subgraph L5["Deployment / Platform"]
    CMP["Local Docker Compose"]:::infra
    K8S["Local Kubernetes Helm<br/>(runtime unverified)"]:::infra
    TF["Terraform"]:::infra
    AWS["Private AWS Demo<br/>(current state unknown)"]:::infra
    RUN["BotKernel Services<br/>(deployment targets)"]:::service
    CMP ~~~ K8S ~~~ TF
    TF -. provisions .-> AWS
    CMP -. deploys .-> RUN
    K8S -. deploys .-> RUN
    AWS -. deploys .-> RUN
  end

  COST --> API
  PERF --> API
  SIM --> EFFECTS
  WORK -->|commit| EFFECTS
  GRAPH --> READ
  INC --> READ
  RPT --> READ
  CTRL -. telemetry .-> OBS
  OBS ~~~ CMP

  style L1 fill:#f8fafc,stroke:#cbd5e1,color:#334155
  style L2 fill:#f8fafc,stroke:#cbd5e1,color:#334155
  style L3 fill:#faf8ff,stroke:#d6cee8,color:#334155
  style L4 fill:#f5fbfa,stroke:#c5ded9,color:#334155
  style L5 fill:#fffbf6,stroke:#e6d5c6,color:#334155
```

LangGraph Cost and Performance agents submit proposals through the FastAPI gateway, which records reservations and an outbox in PostgreSQL's authoritative ledger. Kafka delivers events at least once to workers that apply simulator effects; the recovery service retries or reconciles work, and PostgreSQL persists effects, incidents and investigation reports. The PostgreSQL boxes show logical views of the same database. The committed-effect graph and deterministic Collective Stability Controller detect harmful interactions and apply resource holds; the LangGraph Investigator examines evidence on demand. The React dashboard and Experiment Lab access operational data through the API. Redis is advisory, and Bedrock reasoning is optional and unverified live. Prometheus, Grafana, OpenTelemetry and Jaeger provide observability. Docker Compose supports local operation; the local Helm/Kubernetes chart is runtime-unverified, and Terraform describes a private AWS demo whose current state is unknown. See [architecture details](docs/ARCHITECTURE.md).

## Execution and recovery

1. Agents observe simulator telemetry and produce a proposal (deterministic by default).
2. FastAPI validates role, resource and capacity constraints; PostgreSQL atomically commits admission, reservation, ledger and outbox state.
3. The publisher emits outbox events to Kafka; workers execute the simulated effect and persist receipts/effects.
4. The controller analyzes committed cross-agent effects, applies targeted interventions, monitors sustained recovery, and persists incident lifecycle transitions.
5. The investigator retrieves persisted evidence before optional analysis and saves a validated report. Reports are advisory; investigation does not remediate resources.
6. The dashboard renders API-backed operations, graph, incidents and experiments.

## Capabilities and limits

| Area | Implemented behavior | Qualification |
|---|---|---|
| Durable execution | PostgreSQL ledger, quota/reservation admission, transactional outbox, Kafka workers, recovery | Simulator effects; at-least-once delivery, not universal exactly-once |
| Agents | Independent LangGraph Cost and Performance workflows | Deterministic providers are default; model proposals remain advisory when action execution is disabled |
| Stability | Committed-effect graph, directional reversal evidence, selective holds, recovery verification and recurrence handling | Deterministic controller; evaluated in simulation, not production-scale proof |
| Investigation | Evidence retrieval, citation validation, persisted reports and idempotent request handling | Deterministic by default; live Bedrock inference unverified |
| Dashboard | Landing, Mission Control, Agent Fleet, Effect Graph, Investigations, Experiment Lab | Single-operator bearer authentication; keep private/loopback |
| Observability | Prometheus/Grafana and OpenTelemetry/Jaeger integrations | See [observability notes](docs/OBSERVABILITY.md) for scope |
| Deployment | Docker Compose, Terraform/private AWS assets and local Kubernetes Helm templates | Historical AWS state is not a current-state assertion; Kubernetes runtime is unverified |

## Evaluation

BotKernel includes seeded discrete-event controller comparisons and a PostgreSQL/Kafka real-system benchmark. Simulation metrics describe modeled scenarios, not production detection accuracy. Real-system numbers are single-host observations and must be read with their workload, uncertainty, and limitations in [BENCHMARKS.md](docs/BENCHMARKS.md) and [BENCHMARK_AUDIT.md](docs/BENCHMARK_AUDIT.md). Do not compare simulated throughput with measured database/Kafka throughput.

The retained local PostgreSQL/Kafka runs measured 25 actions at concurrency 1, 50 at concurrency 5, and 100 at concurrency 10. Observed committed-effect throughput ranged from **2.704 to 3.585 effects/s**; admission p95 ranged from **175 to 1,915 ms**, and completion p95 from **538 to 4,382 ms**. These are single-host measurements; the benchmark does not measure stage latency, consumer lag, or peak CPU/memory. See the saved run reports for exact methodology and caveats.

## Technology choices

| Technology | Role |
|---|---|
| Python / FastAPI | Admission API, workers, controller and evidence services |
| LangGraph | Stateful Cost/Performance agent and investigator workflows |
| PostgreSQL | Authoritative ledger, reservations, outbox, effects and reports |
| Kafka | Asynchronous at-least-once event delivery |
| Redis | Advisory coordination and budget state |
| React / TypeScript | Operations dashboard and Experiment Lab |
| Docker Compose | Reproducible local multi-service environment |
| Terraform / AWS | Optional private single-host deployment; current cloud state unknown |
| Prometheus, Grafana, OpenTelemetry, Jaeger | Metrics, dashboards, traces and trace inspection |

## Quick start

Prerequisites: Docker Desktop with Linux containers (or Docker Engine/Compose), Python 3.12 for host tools, and Node.js/npm for the dashboard.

PowerShell (from repository root):

```powershell
$env:BOTKERNEL_API_PORT = '18003'
$env:BOTKERNEL_OPERATOR_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:BOTKERNEL_AGENT_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose -p botkernel-local up --build -d postgres redis kafka init api publisher worker recovery controller
Invoke-RestMethod http://127.0.0.1:18003/ready
```

Keep both generated credentials private and retain them for the lifetime of the stack. The gateway checks for at least 43 printable ASCII characters but cannot verify randomness; generate each token independently using a cryptographically secure generator. To enter the operator credential in the console, copy it securely from the first terminal, for example with `Set-Clipboard -Value $env:BOTKERNEL_OPERATOR_TOKEN`, and clear the clipboard afterward. These PowerShell variables are process-local; use an ignored `.env` or another secure secret source for persistence. Regenerating them requires recreating the API and agent containers with the same updated values.

Then in another terminal:

```powershell
Set-Location apps/dashboard
npm ci
$env:BOTKERNEL_API_TARGET = 'http://127.0.0.1:18003'
npm run dev
```

Open the Vite URL (normally `http://127.0.0.1:5173`). For a bounded Kafka/controller/investigation walkthrough, use `.\scripts\run-live-demo.ps1` from the repository root in an isolated local stack; it writes local demo state. Stop services without deleting volumes:

```powershell
docker compose -p botkernel-local down
```

The dashboard setup is covered in [the dashboard guide](apps/dashboard/README.md); the root Compose files and CI workflow define backend startup and test commands.

## Tests and CI

The project has PostgreSQL/Kafka integration tests, controller/evaluation tests, dashboard Vitest tests, a TypeScript/Vite build, Playwright Chromium tests, and mocked/offline Bedrock acceptance tests. See [CI](.github/workflows/ci.yml), [LangGraph](docs/LANGGRAPH.md), and [Bedrock acceptance](docs/BEDROCK_ACCEPTANCE.md). Local results are not GitHub Actions results; check Actions after an approved publication. CI must remain independent of AWS credentials and paid inference.

## Deployment and optional AI

Local Docker Compose is the supported evaluation path. Terraform and deployment assets target a private AWS demonstration; review [Terraform documentation](infra/terraform/README.md) before any use. Cloud resources can incur charges. Bedrock is optional and disabled by default; live use requires separate authorization, fresh identity/permission/pricing checks, and explicit spend approval. Application token limits are not hard billing caps.

## Security and known limitations

- `AI_ACTION_EXECUTION_ENABLED=false`, `BEDROCK_ENABLED=false`, and spend authorization is disabled by default.
- PostgreSQL is authoritative; Redis is advisory; Kafka is at-least-once.
- Simulator idempotency does not establish exactly-once behavior for arbitrary external side effects.
- Operational API routes require a configured high-entropy operator bearer token; agents use a separate restricted token. `/health` and `/ready` are public. Missing or invalid authentication configuration fails closed.
- The API accepts `BOTKERNEL_OPERATOR_TOKEN` and optional `BOTKERNEL_AGENT_TOKEN`, or their respective `_FILE` alternatives; do not set both forms for one credential. Restrict secret-file permissions. The private AWS Compose template mounts files only into the services that need them.
- The console retains its token only in memory; reload requires sign-in. Tokens have no automatic expiry: sign-out clears local state, not the server credential, so rotate the token to revoke it. The shared agent token is not per-agent identity and permits simulator action submission. Use TLS on any non-loopback connection and keep the API private; authentication is not a public-exposure boundary. Prometheus uses a separate read-only metrics token supplied through a secret file; see [observability setup](docs/OBSERVABILITY.md).
- The Helm chart references externally created operator and agent Secrets; its metrics Secret is optional. Helm templates were validated but not deployed. AWS-demo changes are not deployed or runtime-validated.
- Local simulations are not proof of multi-host production reliability.
- Live Bedrock invocation and current AWS deployment state are unverified.
- Investigations run in supervised processes with a bounded timeout; advisory slots do not guarantee a distributed concurrency cap across database partitions. Backup/restore remains unverified.

## Project documentation

- [Architecture](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md) · [Collective Stability algorithm](docs/COLLECTIVE_STABILITY_ALGORITHM.md)
- [LangGraph and providers](docs/LANGGRAPH.md) · [Bedrock acceptance](docs/BEDROCK_ACCEPTANCE.md)
- [Benchmarks](docs/BENCHMARKS.md) · [Benchmark audit](docs/BENCHMARK_AUDIT.md) · [Portfolio walkthrough](docs/PORTFOLIO.md)
- [Implementation walkthrough](docs/IMPLEMENTATION_WALKTHROUGH.md) · [Local Kubernetes chart (not runtime-validated)](infra/kubernetes/README.md)

## Rights

Copyright © 2026 Vedant Kesharia. All rights reserved.

This repository is publicly available for portfolio review. No general license is granted for copying, modification, redistribution or commercial use without prior written permission, subject to applicable law and GitHub's terms.
