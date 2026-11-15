# Roadmap

BotKernel's local-first execution and stability workflows are implemented with bounded runtime evidence. PostgreSQL owns correctness, Redis is advisory, Kafka delivery is at least once, and ambiguous external effects require reconciliation. The private AWS demo was verified on November 14, 2026, then stopped. See [validation](VALIDATION.md) and [engineering results](ENGINEERING_RESULTS.md).

| Area | Actual status | Remaining boundary |
|---|---|---|
| Execution foundation | Gateway, migrations, outbox, worker receipts, recovery and replay exercised with PostgreSQL/Kafka | General external adapters need outcome inspection/fencing; simulator receipts do not establish arbitrary external exactly-once effects. |
| Stability controller | Selective holds, sustained verification, recurrence, bounded escalation and operator lifecycle exercised | Production telemetry and threshold calibration; simulator comparisons do not prove superiority. |
| LangGraph and investigator | Independent deterministic agents, durable proposals/reconciliation, read-only reports, supervised deadlines and stale-worker fencing | Cross-host ownership, partition-time computation limits and human review/release workflow. |
| Bedrock | Genuine advisory decisions and saved report verified; one validation failure retained among four new calls | Inference/action gates remain off; schema compliance does not prove recommendation optimality. |
| Dashboard and monitoring | Landing plus five private console views verified against AWS; five scrape targets, three dashboards, 14-span trace and CloudWatch correlation | Shared bearer credentials are not public multi-user authorization; stopped/ephemeral telemetry is historical. |
| Validation | Current local backend: 255 passed, 1 skipped; frontend build and 6 unit tests passed. Historical AWS browser smoke passed | Earlier local run retained: 214 passed, 7 failed, 1 skipped under memory pressure. The earlier AWS backend result was 221 passed/1 skipped; current local results are separately recorded in validation. |
| Kubernetes | Helm lint/render/YAML checks passed; local Kubernetes disabled/stopped | No installed release, pod/PVC, workflow, rollout or runtime acceptance. |
| Recovery/availability | Backups created and integrity checked | Restore drill unverified; single-host services and one broker do not provide HA. |

## Next acceptance work

1. Arrange sufficient local resources and enable the cluster before following the [Kubernetes runtime procedure](../infra/kubernetes/README.md). Preserve existing workloads and data; record runtime separately from static Helm checks.
2. Restore PostgreSQL and agent/investigation checkpoints into an isolated environment and verify state and replay. Backup integrity alone does not prove recoverability.
3. Expand broker failover, retention, schema upgrade and cross-host recovery evidence before availability claims. Finish and validate foundation acceptance before subsequent capabilities.
4. Extend measured workloads and episode-level evaluation without adjusting ground truth to favor the controller. The 18-run polling study now records stage coverage, consumer lag and sampled resources; replicate longer on a quiet host and distinguish modeled from measured metrics.

Saved acceptance needs no additional paid inference. Fresh recording or action replay requires operating/quota review; historical telemetry must not appear as live. See [Bedrock contracts](BEDROCK_ACCEPTANCE.md), [benchmarks](BENCHMARKS.md) and [documentation index](DOCS_INDEX.md).
