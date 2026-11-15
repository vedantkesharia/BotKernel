# Architecture

[Full system diagram](assets/botkernel-system-architecture.svg) | [Asset audit](ARCHITECTURE_ASSET_AUDIT.md) | [Validation](VALIDATION.md)

## Boundaries and deployment

BotKernel is a local-first AgentOps simulator. The verified AWS deployment is a single EC2 host running Docker Compose, private ECR images, retained encrypted EBS, an IAM instance role, SSM access and CloudWatch logging. It is not HA, Kubernetes or EKS. Its November14acceptance was bounded and the instance stopped afterward. Local Compose and the separate Helm chart are alternative runtimes; Kubernetes runtime acceptance passed in a separate local kind cluster: seven committed effects, contention/idempotency, persistence and rollout checks. EKS was not deployed.

Nginx serves React/Vite assets and proxies `/api` to FastAPI over the private container network. AWS browser access uses an encrypted SSM tunnel to EC2 loopback HTTP, not an implemented Nginx TLS terminator. Operational routes require an operator bearer credential; a separate restricted agent credential and metrics credential have narrower purposes. Health/readiness are public checks. The browser retains its operator token in memory only. Shared static credentials are not per-user/per-agent identity, expiry or production RBAC.

## Agent decision and proposal lifecycle

`botkernel/lang_agents.py` builds independent Cost and Performance StateGraphs. Observe/analyze/propose/submit/reconcile stages use stable role threads and separate role-specific SQLite checkpoint files in the independent runtime. Synchronous durability saves reasoning and immutable canonical request/fingerprint/idempotency identity before networking. An additive local proposal table records submission/reconciliation attempts, retry deadlines, authoritative action identity/outcome and terminal review states.

Local Linux advisory ownership locks prevent cooperating writers from advancing one checkpoint simultaneously. Writable runtime entrypoints enforce ownership; Studio mutation is restricted. This is a tested local-filesystem guarantee, not distributed fencing or support for arbitrary network filesystems.

Default reasoning is deterministic. Optional Bedrock Converse (`botkernel/bedrock.py`) obtains EC2 role credentials through the standard SDK chain. Strict Pydantic contracts, role direction, capacity bounds, resource/evidence validation and provenance gates apply before the common submission boundary. `AI_ACTION_EXECUTION_ENABLED=false` prevents every model-originated action from reaching the gateway. Advisory proposals are never mislabeled executed. No model can change controller policy or mutate AWS infrastructure.

Ambiguous requests retain original proposal identity. Accepted actions reconcile by authoritative lookup instead of repeated POST. Persistent backoff and bounded attempts pause unresolved work for review; local retry exhaustion does not prove an external effect failed. Model calls use one SDK attempt, no automatic model fallback and no automatic ambiguous-call retries. Reports/checkpoints retain provider, requested model/profile, returned usage/request ID where available. Input-byte estimates and Redis reservations are application limits, not billing guarantees.

## Admission and transactional outbox

`botkernel/api.py` validates requests and authentication. `botkernel/core.py` serializes idempotency, locks quota before resource, verifies expected version and existing reservation, then enforces policy, dependencies, deadline and selective controller holds. PostgreSQL commits action/reservation and outbox in one transaction. A reused key with a different payload fails closed; a model cannot escape that conflict with a fresh key for the same uncertain operation.

Alembic **0009** is the current schema. Startup checks migration compatibility/drift rather than silently repairing unknown operational history. PostgreSQL owns quotas, versions, action states, receipts, committed effects, incidents, transitions and reports.

The publisher is a separate process in `botkernel/worker.py`. It reads unpublished rows with `FOR UPDATE SKIP LOCKED`, waits for Kafka acknowledgement and marks publication inside the transaction. Death after broker ACK but before transaction commit can publish a duplicate. Kafka remains **at-least-once**, despite producer idempotence. The single-node KRaft broker has no HA; the implementation uses an action topic, not a separate recovery/retry-topic architecture.

`OUTBOX_POLL_INTERVAL_SECONDS` preserves the200msdefault and permits bounded opt-in tuning; it does not weaken publication or transaction rules. `KAFKA_CONSUMER_GROUP` defaults to `executors` and allows isolated test groups. The [matched measurements](ENGINEERING_RESULTS.md) show both benefits and adverse high-concurrency/CPU tradeoffs.

## Worker, simulator and reconciliation

Workers consume action IDs with trace context. Execution holds a per-action PostgreSQL session advisory lock across transactions. The simulator capacity change and receipt commit atomically. Finalization then takes the authoritative quota lock, writes an immutable committed-effect row and advances resource version/action state in a separate transaction.

A crash after receipt but before finalization leaves a reconcilable state: external simulator capacity changed, receipt present, ledger version/effect not yet advanced. Replay checks receipt and external state before repeating anything. Unknown external divergence escalates and preserves reservation; absence of a receipt plus a known expired/exhausted operation can fail safely. Recovery uses the same guarded execution path. Kafka offsets commit after handling; malformed/unknown messages enter the dead-letter ledger.

This is simulator-specific idempotency, not universal exactly-once computation or external execution. Receipts and version constraints cannot make an arbitrary remote API atomic.

## Collective stability and investigation

`botkernel/stability.py` derives directional reversals from committed effects. Detection uses multiple changes/agents, reversal count, modeled harmful latency and a bounded score. Holds are resource-specific scale-down restrictions, not global pauses; safe scale-up still faces quota/version policy. Sustained samples/verification and hysteresis govern recovery. Recurrence reopens containment; a bounded intervention budget escalates persistent harm. Operator review actions are authenticated and durably recorded; model output cannot release a hold.

The Investigator StateGraph retrieves committed incident/effect evidence, correlates reversals and produces verified facts, deterministic inferences and explicitly labeled hypotheses. A supervised subprocess has bounded execution and cancellation; database leases/concurrency slots fence stale completions. Optional Bedrock analysis must satisfy the exact schema and cite supplied evidence. It has no mutation tools. The service persists the validated report in PostgreSQL and serves idempotent retrieval; read-only evidence gathering does not mean report persistence is absent.

Redis stores advisory heartbeats/decision snapshots. Its shared atomic model call/token guard intentionally fails closed if unavailable, but it is not the execution ledger and loss/reset can remove budget history. Redis must never be reset or switched merely to obtain inference allowance.

## Evidence and telemetry

Trace context crosses admission, outbox and Kafka boundaries. OpenTelemetry spans cover reservation/outbox, publication/consumption, simulator receipt and finalization. Prometheus exports request/operation metrics and durable database gauges; Grafana visualizes them; Jaeger retrieves traces; CloudWatch stores structured AWS logs. Counters reset with processes; durable gauges and recorded rows have different semantics. Trace/metrics retention depends on configured storage and may be ephemeral.

[Real benchmarks](BENCHMARKS.md) execute HTTP/PostgreSQL/Kafka with monotonic client timing, stage spans and sampled resource/offset telemetry. [Controller comparisons](ENGINEERING_RESULTS.md#controller-stability-and-tradeoffs) are seeded virtual simulations. Their modeled latency/throughput and alarm labels must never be presented as real backend performance.

## Known limits

Single-host storage/broker/database, a globally serialized quota path, one worker in measured workloads, local-only checkpoint ownership, shared credentials, incomplete disaster-recovery restore proof and untested multi-node Kubernetes behavior remain explicit limits. Bounded historical AWS acceptance does not establish current cloud availability or general production readiness.
