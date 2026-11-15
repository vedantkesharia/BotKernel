# Architecture diagram reference

The primary [SVG blueprint](assets/botkernel-system-architecture.svg) uses native vector shapes and editable text. The owner-supplied PNG is retained as an earlier reference; its annotations are not the authoritative description of the implemented topology.

| Diagram responsibility | Implementation |
|---|---|
| Independent workflows and checkpoints | `botkernel/lang_agents.py`; separate Cost/Performance SQLite paths |
| Optional advisory model provider | `botkernel/bedrock.py`; Converse, strict validation and Redis budget reservations |
| Authenticated admission | `botkernel/api.py`, `botkernel/security.py`, `botkernel/core.py`; policy, holds, quota, versions and idempotency |
| Atomic action and outbox | PostgreSQL transaction in `core._admit` |
| Separate publisher and Kafka workers | `botkernel/worker.py`; broker acknowledgement before publication mark, at-least-once replay |
| Receipts, committed effects and reconciliation | `botkernel/core.py`; simulator receipt transaction and separate finalization in the same PostgreSQL |
| Collective controller | `botkernel/stability.py`; committed-effect evidence, selective containment, verification, recurrence and escalation |
| Read-only investigation | `botkernel/investigator.py`, `botkernel/investigation_service.py`; validated evidence and persisted reports |
| Operator console and telemetry | `apps/dashboard/`, `botkernel/observability.py`, `observability/` |
| Separate runtime choices | `compose.yaml`, `compose.aws-demo.yaml`, `infra/terraform/`, `infra/kubernetes/` |

The blueprint contains no temporary resource identifiers, acceptance badges or deployment dates. Source semantics distinguish model advice from deterministic admission/control, simulated effects from infrastructure mutation, and single-host EC2 Compose from local kind Kubernetes. EKS and HA are not implied.

For executed runtime checks and measured limitations, see [validation](VALIDATION.md), [Kubernetes acceptance](KUBERNETES_ACCEPTANCE.md) and [engineering results](ENGINEERING_RESULTS.md).
