# Collective Stability evaluation

## Reproduce the current run

The harness is a seeded discrete-event **simulation**, not a database or Kafka performance benchmark. From the repository root:

```powershell
python -m botkernel.evaluation --seeds 17 23 41 --scenarios oscillation healthy_scaling simultaneous_resources overlapping_remediation cascade recurrence temporary_spike worker_failure --duration 120 --output benchmarks\results
```

## Separate real-system benchmark (initial measurements)

`scripts\run-real-benchmark.ps1` creates a uniquely named local Compose project with its own PostgreSQL database, Kafka broker/topic, Redis, API, publisher and worker. It retains all volumes and prints a command to stop only that project. From the repository root:

```powershell
.\scripts\run-real-benchmark.ps1 -Actions 25 -Concurrency 1 -Warmup 1
.\scripts\run-real-benchmark.ps1 -Actions 50 -Concurrency 5 -Warmup 1
.\scripts\run-real-benchmark.ps1 -Actions 100 -Concurrency 10 -Warmup 1
.\scripts\run-real-benchmark.ps1 -Actions 25 -Concurrency 1 -Warmup 1 -Recovery
```

Each client owns one freshly created test resource; capacities alternate between 1 and 2, and the isolated database quota is set to 40. Warmups precede a synchronization barrier. Admission and completion use the client's monotonic clock; completion includes 50 ms polling. Throughput divides unique confirmed measured effects by elapsed time from the first measured submission to the last observed outcome. PostgreSQL ledger, outbox, receipt and effect rows are checked; the later runs additionally verify resource versions against effect counts. These are closed-loop samples from a heavily shared Docker Desktop host, not a capacity limit or production benchmark.

| Actions / clients | Admission p50 / p95 / p99 ms | Completion p50 / p95 / p99 ms | Confirmed effects/s |
|---|---|---|---:|
| 25 / 1 | 68.961 / 174.987 / 287.572 | 378.607 / 538.205 / 730.854 | 2.704 |
| 50 / 5 | 269.282 / 665.516 / 892.288 | 1312.721 / 2212.026 / 2379.237 | 3.585 |
| 100 / 10 | 568.209 / 1914.957 / 3033.013 | 3067.288 / 4382.264 / 5429.639 | 3.090 |

These are single runs, not statistically representative comparisons. All measured actions succeeded and each had one receipt and effect with a published outbox. Raw JSON, CSV and per-run reports are in `benchmarks/results/real-system/` under run IDs `65a08540-fb16-4637-b2e9-95bd314a909a`, `0d481657-cf8c-4c4a-89fc-36ec0f2f86af`, and `ad2c84bc-3c6a-4dae-bc5d-4072e9367038`. The first run preceded the added resource-version cross-check. Three other Kafka instances and many pre-existing services were running concurrently; no workload isolation or peak resource monitoring was performed.

The local environment was Docker Engine 29.9.2, Compose 5.6.1, Linux WSL2 x86_64, Python 3.12.16, PostgreSQL 16.15 and Kafka image `apache/kafka:3.9.0`. After the 100-action run, a single `docker stats` snapshot showed API 76.21 MiB / 0.34% CPU, worker 50.18 MiB / 0.99%, Kafka 320.3 MiB / 13.27%, and PostgreSQL 66.31 MiB / 37.49%; these are post-run instantaneous observations, not measured peaks. Publication, delivery and worker timings, consumer lag, and workload CPU/memory remain unavailable, not zero.

The separate recovery run `08dc5256-6d01-44f8-b4b5-c6600db277c9` stopped only the benchmark project worker, started a worker configured to exit after the simulator receipt, published one deliberate duplicate after its exit, and started a replacement worker. Before recovery PostgreSQL showed DISPATCHED, one receipt, no effect and version 0. It reached SUCCEEDED in 6.474 seconds after observing the crash; the replacement logged two handled deliveries, while the database retained one receipt, one effect and version 1. This is a single simulator-specific fault case, not a general exactly-once claim. The optional `-Recovery` sequence above automates the same test in a fresh benchmark project; the shown result was run through the equivalent explicit Compose commands.

The current full run is `benchmarks/results/88b0aa07-e4bb-40b9-9bab-e11d9fdf33f0/`. It includes `raw.json`, `summary.csv`, `ticks.csv`, `effects.csv`, and a generated `report.md`. Re-running creates a new UUID-named directory and does not overwrite prior raw evidence. The Experiment Lab exposes bounded single-scenario runs through `POST /experiments` and lists persisted runs from `GET /experiments`.

## Comparison design

Each seed/scenario schedule is generated once and replayed against all three modes. Initial capacities, per-resource admission serialization, action quotas, workloads, virtual duration, and random input jitter are held constant. Ground-truth intervals are declared in the scenario schedule before the detector runs.

| Mode | Policy |
|---|---|
| `independent` | No collective alarms or interventions; per-resource serialization and quota safety remain enabled. |
| `basic` | Per-resource serialization, two consecutive latency samples above 100 ms, and a fixed 10-second scale-down cooldown. |
| `collective` | Production `botkernel.stability.analysis` scoring with virtual holds, sustained verification, recurrence handling, and a bounded intervention budget. |

Scenarios cover cost/performance oscillation, healthy scaling, simultaneous independent resources, overlapping remediation, cascading degradation, recurrence, a temporary spike, and execution-worker unavailability.

## Measures and limitations

Raw per-tick records support confusion counts, precision/recall/F1, false-positive rate, detection delay, oscillating changes, interventions, unnecessary interventions, recurrences, sustained stabilization, modeled recovery/escalation time, application-latency percentiles, resource capacities, completed actions, and logical actions per virtual second. The report computes descriptive 95% normal-approximation confidence intervals across the three seeds. With only three seeds these intervals are weak; many controller outcomes are identical across seeds, so several intervals collapse to a point.

Precision, recall, F1 and false-positive rate compare **alarm occupancy per tick** with scheduled harmful intervals, not incident-trigger episodes. A persistent hold after an interval can produce false-positive ticks without another trigger. The separate episode-level metrics below do not replace these historical fields.

The simulator does **not** execute PostgreSQL admission or Kafka dispatch. Admission/dispatch percentiles, CPU, and memory are explicitly null; throughput and application latency are model outputs, not observed service performance. Ground-truth labels, latency formula, thresholds, and scenario transitions are experimental assumptions, not causal proof. Results cannot establish production accuracy or superiority.

## Observed result, not a superiority claim

In the recorded oscillation case, the collective mode reduced modeled cross-agent oscillating changes from 47 (basic) to 15 and used two interventions rather than seven, but had lower precision (0.633 vs. 0.886), a higher false-positive rate (0.800 vs. 0.178), lower logical throughput (0.308 vs. 0.658 actions/virtual-second), and higher modeled application p95 latency (264.063 vs. 154.713 ms). In cascade and recurrence, collective detection metrics were also weaker than the basic policy in this run. Healthy scaling produced no alarms in any mode. These mixed/negative results are retained as-is; they argue for improving calibration and the experiment model before making comparative claims.

## Episode-level follow-up

The independently seeded run `e5c88362-afac-4e2c-ad34-fc957d5920d5` uses seeds 101, 211, 307, 401 and 503, all eight scenarios, 120 ticks and the same three policies. Run `python -m botkernel.evaluation --seeds 101 211 307 401 503 --duration 120 --output benchmarks\results` to create a new run. Existing scenario labels and thresholds are unchanged. Raw ticks, per-seed runs, summaries and report are retained separately from the historical baseline.

Intervals are half-open `[start, stop)`. An alert episode is a maximal contiguous run of the existing global alarm flag; overlapping alerts from different basic-mode resources are unioned. Sorted truth episodes are greedily matched one-to-one to the earliest unmatched overlapping alert. Thus a persistent alert spanning two harmful episodes matches only the first, and a second alert during the same harmful episode is unmatched even if it is not an onset outside truth. We separately report `alert_onsets_outside_truth` and `unmatched_alerts_overlapping_truth`. Delay is zero for an alert already active at truth onset; clear delay is measured from truth end to matched alert end, floored at zero, and null for an alert still active at the run boundary. Precision and recall are null when their denominators are zero; summary means exclude null values. `containment_active_ticks` counts modeled cooldown/hold/verification/escalation ticks, and healthy-latency fraction during harm is descriptive, not causal containment effectiveness.

For oscillation, per-seed mean episode precision/recall was independent n/a/0, basic 0.143/1 and collective 0.333/1. Basic had six unmatched alerts, all overlapping the already matched episode, and zero alert onsets outside truth; collective had two unmatched alerts, including one overlapping truth and one onset outside truth. Basic/collective onset delays were 1/4 ticks and containment lasted 70/98 ticks. Their simulated p95 latency was 154.546/264.610 ms and logical throughput 0.6583/0.3083 actions per virtual second. In recurrence, basic/collective precision was 0.4/1 and recall 1/1; collective onset delay was 6 ticks versus 1.5, and matched-alert clear delay averaged 23.5 ticks. Independent missed both scheduled episodes. Healthy scaling produced no alerts; basic produced one out-of-truth alert during temporary spike whereas collective produced none. Precision here penalizes alarm fragmentation; it is not interchangeable with out-of-truth trigger count or historical tick precision.

These are five seeds per scenario, not five independently calibrated workloads: the schedule and model are simplified and several outcomes are identical across seeds. Differences in false-positive occupancy arise in part from persistent holds outside scheduled labels; fragmented cooldowns also affect episode matching. The longer collective containment coincides with poorer modeled latency and throughput in oscillation, but this comparison does not isolate a causal mechanism. Do not tune thresholds against these samples. Validate ground-truth labels and vary workloads before generalizing.
