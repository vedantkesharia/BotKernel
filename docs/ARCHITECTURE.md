# Architecture

## Local-first system

Independent Cost and Performance agent processes observe simulator telemetry and submit proposals only through FastAPI admission. PostgreSQL owns quotas, resource reservations, the action ledger, the transactional outbox, committed effects, incidents, investigation reports and durable heartbeat timestamps. The publisher sends outbox events to Kafka; workers execute idempotent simulated effects and reconcile ledger state. A recovery worker retries bounded work and escalates ambiguous or exhausted actions. Redis contains disposable heartbeat and inference-budget hints; it is not the correctness authority.

The gateway serializes quota admission and idempotency with PostgreSQL advisory transaction locks. It reserves resource capacity and writes the action/outbox in one transaction. Workers check simulator receipts before replaying effects. Finalization takes the quota lock before changing capacity. The global admission lock is intentionally simple but limits throughput; no production throughput claim is made. Migrations 0001-0008 define the current schema; the root `schema.sql` remains a legacy reference.

The Collective Stability Controller reads committed effects and resource-specific reversal evidence, uses hysteresis and a sustained verification window, applies bounded temporary holds, reopens on recurrence and escalates after its intervention budget. Incident evidence retains initial and latest detection snapshots for reconstruction. The seeded comparison harness is a simulation, not production telemetry or a PostgreSQL/Kafka benchmark; do not claim controller superiority from it.

Cost and Performance agents use separate LangGraph processes and role-specific SQLite checkpoints. The investigator uses deterministic, read-only PostgreSQL evidence collection; optional Bedrock hypotheses are labeled separately from verified facts and deterministic inferences. Neither agent nor investigator has direct database, Kafka, infrastructure or remediation tools. Any agent proposal still goes through the gateway and deterministic controller.

The investigator uses idempotent PostgreSQL report claims, a fenced lease and a bounded pool of session advisory slots. Evidence statements have a five-second timeout. Session loss can release an advisory slot while Python computation continues, and the graph has no hard cancellation/whole-request deadline; fencing prevents a stale owner from finalizing but does not stop that computation.

## Local observability

The optional local Compose profile provides Prometheus, provisioned Grafana, an OpenTelemetry Collector and Jaeger. W3C trace context is persisted through the outbox and Kafka headers. Admission counters are process-local best-effort metrics; ledger and incident data in PostgreSQL remain authoritative. Monitoring storage is local and is not a production retention or access-control design. See [OBSERVABILITY.md](OBSERVABILITY.md).

## AWS single-host deployment model

Terraform and Compose describe an optional private, single-host AWS demonstration using EC2, ECR, CloudWatch Logs and SSM. No live cloud state is asserted here. Runtime credentials belong in host-only secret files or an instance role, never in source or images. Keep application ports private; operator routes are unauthenticated and require a separate access-control design before any public exposure. Review [the Terraform guide](../infra/terraform/README.md) for deployment prerequisites and approval gates. This design is not highly available; backup/restore has not been verified, and cloud storage and runtime can incur charges.

## Runtime limitations

- The API and operator mutation routes have no browser authentication. Loopback and SSM are a private-demo boundary, not a public security model.
- The Compose broker is a single-node Kafka and the database is a single-host PostgreSQL instance; there is no HA or managed failover.
- The deployment container set, Docker Compose installation on AL2023, image build, runtime startup and AWS IAM behavior are not validated against a live EC2 instance.
- No AWS resources, credentials, Bedrock requests or paid services have been accessed in this workspace.
