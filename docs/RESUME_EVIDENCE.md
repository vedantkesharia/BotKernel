# Resume evidence

Use these claims with their stated scope. Simulator capacity is not AWS autoscaling; transport is at least once; neither deployment is HA. Historical AWS acceptance is a bounded run, not a continuously hosted production system.

## Five bullet candidates

1. **Built a PostgreSQL transactional-outbox and Kafka execution plane; verified 990 unique simulator effects across 18 bounded runs, with one receipt/effect per action and consistent resource versions.**
2. **Validated concurrent quota admission and idempotency in Kubernetes: 32 authenticated requests at up to eight concurrent clients produced seven unique effects, 15 idempotent duplicate responses and ten policy/conflict rejections without leaked reservations.**
3. **Instrumented 912 actions across six distributed stages and introduced opt-in publisher tuning, reducing single-client median run-level completion p95 from 259 to 121 ms while documenting higher polling CPU cost and an eight-client tail regression.**
4. **Deployed and corrected a Helm-based local Kubernetes runtime; verified queued-worker recovery in 7.66 seconds, PostgreSQL persistence across an 8.48-second pod restart, and seven durable effects after rollouts, alongside five isolated crash/duplicate fault cases.**
5. **Integrated independent LangGraph workflows with Amazon Bedrock Converse, validating real Cost, Performance and Investigator outputs with persisted provenance, strict schema/citation checks and advisory-only model execution.**

## Numbers, support and limits

| Bullet | Exact support | Reproduction / evidence | Engineering meaning and claim boundary |
|---|---|---|---|
| 1 | 912 measured + 78 warmups = 990 actions; 18 runs; 3 repeats/cell | [Execution summary](../benchmarks/curated/2026-11-14/execution-summary.json); `python scripts/run-shared-benchmarks.py --execute --actions 24 48 80 --concurrency 1 4 8 --repeats 3 --poll-seconds .2 --compare-poll-seconds .02 --label matched-poll` | HTTP, outbox, Kafka, receipts and effects were real. Short shared-host runs do not establish peak/sustained capacity or arbitrary exactly-once side effects. |
| 2 | 32 requests: 22 accepted responses, 10 rejections; 7 logical actions and 15 duplicate responses; peak configured concurrency 8 | [Kubernetes request/snapshot evidence](../benchmarks/curated/kubernetes-2026-11-15/summary.json); `scripts/kubernetes-runtime-check.py` phases in [runtime guide](KUBERNETES_ACCEPTANCE.md) | Four competing positive reservations admitted one; observed allocation 12 + pending 2 = quota 14. Eight simultaneous first-use requests shared one key/ID. Four concurrent downscales respected a real hold. One small dataset does not prove arbitrary concurrency levels. |
| 3 | Completion p95 259.402 -> 120.842 ms, **53.415% lower**, at 24 actions/1 client; 3 runs per condition | [Latency distributions and stage boundaries](ENGINEERING_RESULTS.md); same matched benchmark command as bullet 1 | Admission p95 worsened at one client; publisher CPU increased. At 80 actions/8 clients, completion p95 worsened **13.711%**. Default remains 200 ms. No production SLO or globally faster configuration claim. |
| 4 | Resume-to-verified 7.656 s; PostgreSQL delete-to-Ready 8.484 s; later worker rollout 2.734 s; Helm upgrade 15.469 s | [Kubernetes evidence](../benchmarks/curated/kubernetes-2026-11-15/); [five fault cases](../benchmarks/curated/2026-11-14/fault-summary.json) | Six effects present before PostgreSQL restart persisted; the seventh was created afterward. Dependency restarts and an initial 503 occurred. Core kind runtime only; no EKS, multi-node resilience, zero downtime or full restore claim. |
| 5 | Three successful real workflows across four new requests, including one retained Investigator validation failure before correction | [Bedrock acceptance](BEDROCK_ACCEPTANCE.md), [historical validation](VALIDATION.md), `botkernel/bedrock_acceptance.py` | Cost/Performance returned NO_OP. The successful Investigator hypotheses list was empty. Integration/provenance is proven; model optimality or autonomous infrastructure action is not. Do not rerun paid calls without approval. |

## Best selections by role

- **Backend/distributed systems:** bullets 1, 2 and 3. Explain quota lock ordering, transactional outbox replay windows and why faster polling exposes downstream contention.
- **Infrastructure/cloud:** bullets 4, 2 and 5. Explain kind versus EC2 Compose, PVC persistence, probe-induced restarts, private SSM access, IAM role credentials and bounded cloud shutdown.
- **AI engineering:** bullets 5, 1 and 2. Explain durable LangGraph checkpoints, provider-independent submission gates, strict evidence references and why deterministic admission remains authoritative.

For coordination-focused interviews, add the separately measured controller result: **240 virtual scenario-policy runs across ten seeds**; basic-to-collective oscillation reversals **47 -> 15** (68.09% lower), but modeled p95 **154.57 -> 264.28 ms**, lower modeled throughput and worse false-positive occupancy. These are simulator comparisons, not Kafka/HTTP measurements. [All tradeoffs](ENGINEERING_RESULTS.md#controller-stability-and-tradeoffs).

The next valuable performance experiment is a longer predeclared replication on a quiet host, followed by PostgreSQL/quota/worker profiling. Do not replace the recorded results with targets or imply causality from a stage correlation alone.
