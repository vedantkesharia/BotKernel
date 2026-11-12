# Implementation walkthrough

## Two-minute pitch

BotKernel coordinates agents that can individually make sensible decisions but jointly destabilize a shared resource. The gateway atomically reserves capacity and writes an action and transactional outbox to PostgreSQL. Kafka distributes execution, workers apply idempotent **simulated** effects, and the controller examines committed evidence for cross-agent reversals. It can contain a resource, observe sustained recovery and record an incident. An investigator builds an evidence-backed report, and the dashboard exposes the operational state. This is a local-first engineering demonstration, not a claim of production-grade exactly-once execution.

## Repository map

| Area | Entry points |
|---|---|
| API / state | `botkernel/api.py`, `botkernel/core.py`, `migrations/versions/` |
| Streaming and recovery | `botkernel/worker.py`, `botkernel/core.py` |
| Agents and provider | `botkernel/lang_agents.py`, `botkernel/bedrock.py`, `botkernel/bedrock_acceptance.py` |
| Stability and investigation | `botkernel/stability.py`, `botkernel/effect_relationships.py`, `botkernel/investigator.py`, `botkernel/investigation_service.py` |
| UI | `apps/dashboard/src/`, `apps/dashboard/e2e/` |
| Evaluation | `botkernel/evaluation.py`, `botkernel/episode_metrics.py`, `botkernel/real_benchmark.py`, `benchmarks/` |
| Deployment | `compose.yaml`, `infra/terraform/`, `infra/kubernetes/`, `observability/` |

## Dashboard and API

`apps/dashboard/src/main.tsx` routes the console and queries `/health`, `/ready`, `/agents`, `/actions`, `/resources` and `/incidents`. The landing page is separate and does not require the operator API.

| Page | React source | Data and interaction |
|---|---|---|
| `/` | `landing.tsx`, `LandingStories.tsx`, `OrchestrationDemo.tsx` | Public product introduction and illustrative interaction |
| `/app` | `overview.tsx` | Shared readiness, agents, actions, resources and incidents |
| `/app/agents` | `fleet.tsx` | Shared agent registry/action data and available decision provenance |
| `/app/graph` | `graph.tsx` | `/graph` with window/resource filters and `/incidents`; inspect nodes, edges and evidence links |
| `/app/incidents` | `incidents.tsx`, `InvestigationReports.tsx` | Incident list, evidence/lifecycle, acknowledge/resolve, and investigation POST/list |
| `/app/experiments` | `experiments.tsx` | `/experiments` create/list, `/experiments/{id}` and artifact downloads for simulated workloads |

`botkernel/api.py` implements these routes plus `/telemetry`, `/agents/{agent}`, `/agents/{agent}/decision`, `/incidents/{id}/investigations` and `/investigations/{id}`. Operator routes require an externally configured bearer credential; keep the API on a private boundary.

## Action lifecycle and consistency

`core.admit()` serializes idempotency/quota admission using PostgreSQL transaction advisory locks, validates quota and resource state, and commits reservation, action and outbox together. Tables include `agents`, `quota`, `resources`, `actions`, `outbox`, `receipts` and simulator resource state; subsequent migrations add committed effects, incident lifecycle and investigation reports.

`worker.publish()` reads unpublished outbox rows under `FOR UPDATE SKIP LOCKED`, publishes to Kafka, waits for broker acknowledgement and then marks the row published. A crash after publication but before the database commit can publish again. `worker.consume()` processes Kafka records and commits offsets after processing. Simulator receipts and resource versions protect replay of that simulated operation; PostgreSQL is authoritative and Kafka is at-least-once. A recovery sweeper handles retryable/ambiguous work and escalation. This is not a generic exactly-once guarantee for external systems: ambiguous external effects must be reconciled.

## Agents, graph and controller

The Cost and Performance agents in `lang_agents.py` use `observe -> analyze -> submit` LangGraph nodes. They read API telemetry, retain workflow/proposal state in role-specific SQLite checkpoints, and submit through the gateway. A local file lock prevents cooperating processes from simultaneously owning a checkpoint; it is not distributed fencing. PostgreSQL remains the source of truth for action outcomes.

The graph is derived from committed effects. `effect_relationships.py` identifies reversal relationships only across contiguous versions/capacity boundaries from different agents with opposite directions; these are inferred correlations, not causal proof. `stability.py` scores evidence over a window and updates resource-scoped holds and incident lifecycle state. Verification requires sustained healthy observations; recurrence and bounded intervention escalation are tracked. See [the algorithm](COLLECTIVE_STABILITY_ALGORITHM.md) for precise policy and evaluation caveats.

## Investigation and optional AI

`investigator.py` executes `load_incident -> retrieve_effects -> correlate -> report -> ai_assist`. Deterministic evidence retrieval precedes optional model analysis. Findings distinguish facts and deterministic inferences from hypotheses, and evidence references are validated. `investigation_service.py` manages durable idempotency, claims and lease fencing in PostgreSQL. `investigation_process.py` supervises a fresh `investigation_worker.py` process with its own database connections. The default 30-second execution deadline (1-45 seconds) is followed by a default two-second termination grace (0.1-5 seconds); Linux uses a process group, SIGTERM and SIGKILL, and Windows uses a kill-on-close Job Object. Supervisor death also stops the worker on supported platforms. Evidence queries retain their five-second timeout. Execution timeout finalizes the fenced report as `FAILED/execution_timeout` when PostgreSQL is available; replaying the same key returns it without relaunching. The default two advisory slots are configurable from 1 to 16, but a database partition may release a slot before computation stops, so no strict distributed concurrency guarantee is claimed. Timeout of a Bedrock request is ambiguous and must not trigger an automatic paid retry.

`bedrock.py` implements optional Converse requests with configuration gates, schema validation and returned usage/provenance where available. `bedrock_acceptance.py` prepares the bounded three-case workflow. Live inference remains unverified; model actions and Bedrock spend are disabled by default. Redis stores advisory heartbeat/decision and inference-budget state; it is neither the ledger nor an AWS billing cap.

## Observability and deployment

`observability.py` instruments metrics and trace context; `observability/` contains Prometheus, Grafana, OpenTelemetry Collector and Jaeger configuration. The private AWS templates additionally configure CloudWatch logging; current cloud state is unknown.

Compose is the validated local integration path. `infra/terraform/` describes the private single-host EC2/ECR/SSM deployment. The new [Kubernetes chart](../infra/kubernetes/README.md) is rendered and linted but **not runtime-validated**. Both deployments use a simulator, not live infrastructure remediation. Backup/restore, public operator access and HA are not verified.

## Five-minute design discussion

Explain the tradeoff between a simple serialized PostgreSQL quota lock and admission throughput; follow one action from atomic outbox to possible duplicate Kafka delivery; explain simulator receipts and why arbitrary external effects need reconciliation; show how the controller separates repeated reversals from confirmed causation; then trace a persisted incident into read-only evidence and a fenced report. Finish with the limits: single-host data services, advisory Redis budgets, private-only operator access, partition-sensitive advisory slots, and unverified live Bedrock/Kubernetes acceptance.

## Interview prompts

1. What happens if Kafka acknowledges an outbox event but PostgreSQL rolls back?
2. How do reservations and quota locks prevent conflicting admissions, and where do they reduce throughput?
3. Why is a simulator receipt insufficient for exactly-once behavior against a third-party API?
4. How would you distinguish noisy healthy scaling from repeated harmful feedback?
5. What can a lease fence, and why does it not cancel a running process?
6. How would a consistent PostgreSQL/Kafka/checkpoint backup be coordinated and verified?
7. Why is an application token budget not a cloud billing cap?

See [benchmark methodology](BENCHMARKS.md), [benchmark audit](BENCHMARK_AUDIT.md), [architecture](ARCHITECTURE.md) and [Bedrock acceptance](BEDROCK_ACCEPTANCE.md).
