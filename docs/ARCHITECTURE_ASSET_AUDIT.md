> Historical audit of the previous hand-authored SVG. The owner supplied a new architecture PNG afterward; the current SVG is a faithful pixel-boundary vector conversion of that image, not the earlier audited reconstruction. The earlier geometry counts and original PNG hash below do not describe the replacement asset.

# Architecture asset audit

Original, code-native [SVG](assets/botkernel-system-architecture.svg), reviewed against the existing [PNG](assets/botkernel-system-architecture.png) and implementation on 2026-11-14. The PNG is preserved as supplied; the SVG is a separate corrected asset.

| PNG discrepancy / ambiguity | SVG correction and implementation reference |
| --- | --- |
| PostgreSQL appears to publish directly to Kafka; publisher absent | Separate outbox publisher: locks rows, waits for broker ACK, then marks published. Duplicate window is explicit. `botkernel/worker.py` (`publish`), `compose.yaml` publisher service. |
| Kafka lists recovery/retry topics | Action execution topic only; single-node KRaft, at-least-once delivery. Recovery sweeps ledger records, reconciles receipts/state and reuses guarded execution. `botkernel/worker.py` (`consume`), `botkernel/core.py` (`_execute_with_lock`, `sweep`). |
| Redis omitted | Advisory heartbeats/decision snapshots; inference call/token reservations fail closed when the counter is unavailable. PostgreSQL remains authoritative for admission. `botkernel/api.py` (`register`, `agents`, `publish_agent_decision`), `botkernel/lang_agents.py` (`publish_reasoning`), `botkernel/bedrock.py` (`BedrockConverse._reserve_daily_budget`). |
| SQLite checkpoints lead into Bedrock | Separate Cost/Performance role checkpoints; model calls originate in LangGraph reasoning nodes. SQLite holds checkpoint/proposal state. Optional Nova Micro uses Converse and the EC2 IAM role, advisory only. `botkernel/lang_agents.py` (`build_agent`, nested `analyze`), `compose.yaml` role checkpoint paths, `botkernel/bedrock.py` (`BedrockConverse._runtime`), `infra/terraform/iam.tf`. |
| Nginx claims TLS termination | Private AWS access is browser -> SSM tunnel -> loopback HTTP. Nginx serves static assets and proxies `/api`; bearer authentication is enforced by FastAPI. `apps/dashboard/deploy.nginx.conf`, `compose.aws-demo.yaml` dashboard ports, `botkernel/security.py` (`authorize`), `botkernel/api.py` application dependencies. |
| Results look like a separate datastore / generic exactly-once effects | Return path explicitly targets the same PostgreSQL. Receipt + simulator effect commit together; finalization is a separate transaction updating effects, versions and action state. Idempotency is simulator-specific. `botkernel/core.py` (`_admit`, `_execute`, `_execute_with_lock`); offset handling in `botkernel/worker.py` (`consume`). |
| Controller / investigator boundaries need precision | Committed effect graph drives deterministic resource holds, sustained verification, recurrence and bounded escalation. Investigator reads evidence; service persists schema/citation-validated reports; optional Bedrock never remediates. `botkernel/stability.py` (`graph`, `_advance_state`), `botkernel/investigator.py` (`load`, `ai_assist`), `botkernel/investigation_service.py` (`start`). |
| Deployment badges could imply a currently running AWS demo or Kubernetes acceptance | Historical bounded AWS run verified 2026-11-14; EC2 now stopped. Local Compose is distinct. Recorded Kubernetes status: disabled, about 1.2 GiB free; static checks do not establish runtime acceptance. `infra/kubernetes/README.md` documents the runtime acceptance boundary. |

Supporting infrastructure references: `botkernel/observability.py`, `observability/`, `compose.aws-demo.yaml` (Prometheus/Grafana, OTel/Collector/Jaeger and CloudWatch logs); `infra/terraform/compute.tf`, `iam.tf`, `images.tf` (EC2, encrypted EBS, IAM/SSM, ECR). Deployment status describes historical verification, not a fresh operational check. No performance numbers are implied.

SVG validation:

- Existing PNG inspected visually. SHA-256 before and after: `7ADB4959BA339E16AFBD12D41AED27B86317334BD1D71C04A2C3B18DF2E147D8` (unchanged).
- SVG parsed as XML; accessible title/description and `1800 1660` viewBox present. No embedded raster, script, foreignObject, external fonts or external resource dependencies.
- Existing Playwright/Chromium rendered the final SVG locally at 900 x 830. All 118 text elements fit the canvas; automated text-pair geometry checks found zero overlaps; browser parser errors: zero. The rendered PNG was manually inspected for layout and arrow routing. Owner approval of the final visual remains part of publication review.
- XML IDs and marker/pattern references, source paths and scoped whitespace checks passed. No tools were installed. No builds, application tests, benchmarks, cloud operations or model requests were run for the asset review; historical application results were not rerun.
- Final audit polish checked for plain ASCII and confirmed the SVG hash unchanged. This document edit did not rerun rendering or application validation.
