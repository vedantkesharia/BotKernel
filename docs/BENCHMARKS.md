# Benchmarks: latest measured study (2026-11-14)

[Engineering results](ENGINEERING_RESULTS.md) is authoritative for the latest numbers and definitions. This page provides reproduction commands and an evidence index; older reports below remain explicitly historical.

## Latest measured outcomes

The predeclared interleaved study includes **all 18 runs**: 24 actions/1 client, 48/4 and 80/8, three repeats at both 200 ms and opt-in 20 ms publisher polling. **912 measured actions + 78 warmups = 990 successful unique simulator effects**, each with one published outbox row, receipt and effect, and consistent resource versions. All submissions returned HTTP 202; no measured rejection, failure, escalation or timeout occurred.

Each cell below is the median of three run-level results. Throughput is confirmed effects/s; latency is milliseconds. All distributions and min/max remain in the curated evidence.

| Actions / clients | Poll ms | Effects/s | Admission p50 / p95 / p99 | Completion p50 / p95 / p99 |
|---|---:|---:|---|---|
| 24 / 1 | 200 | 4.717 | 22.701 / 37.984 / 46.403 | 206.695 / 259.402 / 263.407 |
| 24 / 1 | 20 | 10.465 | 22.868 / 41.191 / 43.311 | 94.001 / 120.842 / 179.294 |
| 48 / 4 | 200 | 14.762 | 40.681 / 84.312 / 122.283 | 264.682 / 382.406 / 428.108 |
| 48 / 4 | 20 | 25.205 | 40.991 / 69.303 / 80.103 | 138.318 / 222.237 / 240.569 |
| 80 / 8 | 200 | 12.723 | 133.707 / 235.936 / 271.375 | 626.129 / 815.305 / 865.320 |
| 80 / 8 | 20 | 12.337 | 137.079 / 279.838 / 345.965 | 601.699 / 927.094 / 994.559 |

At 24/1 and 48/4, throughput increased 121.86% and 70.74%. At **80/8 it decreased 3.03%**, completion p95 increased **13.71%**, and admission p95 increased **18.61%**. Admission p95 also worsened at 24/1. Faster polling is workload-specific; the default remains 200 ms. The 48/4 20 ms throughput range was 15.722-26.661 effects/s.

The separate **five fault cases** comprise three receipt-before-finalization crashes with duplicate injection (6.035 / 6.045 / 6.132 s), one publisher ACK-before-outbox-commit crash (4.687 s), and one publisher pause (5.405 s after restart launch). All five actions completed with five unique effects and zero unresolved actions. Timing boundaries differ; these are simulator-specific idempotency observations under at-least-once delivery.

The virtual controller study includes **10 seeds x 8 scenarios x 3 policies = 240 runs**, each 120 ticks, with matched input digests across policies. Collective versus basic reduced oscillation reversals 47 to 15 and interventions 7 to 2, but modeled p95 worsened 154.573 to 264.283 ms, logical throughput fell 0.658 to 0.308 actions/virtual s, and tick false-positive occupancy rose 0.178 to 0.800. Collective had 10 outside-truth oscillation onsets versus basic's zero; it avoided basic's 10 each in simultaneous_resources and temporary_spike. Healthy scaling had no alarms. See all 24 scenario/policy groups rather than selecting favorable cases. These are model outputs, not service throughput.

## Limits that accompany the results

- All six correlated stages cover 912/912 measured actions. Outbox wait is a span-boundary proxy with **37 retained negative deltas**, not an exact commit-to-dispatch measurement. Dispatch includes scheduling; worker execution includes finalization, so stage percentiles overlap and must not be added.
- Consumer lag is known for **415/448 samples**; 33 unknown offsets stay unknown. Backlog sampling had zero errors. Maximum known lag at 80/8 rose 6 to 7 despite a lower sampled outbox backlog.
- Measurement windows were **1.800-6.900 s**, with only three repeats per cell and unstable p99 estimates. Existing containers shared the host and PostgreSQL/Kafka; Node/SVG/browser review overlapped later measurements. Interleaving reduces order bias, not host confounding. This is not a capacity-limit experiment or proof of a unique causal bottleneck.
- Publisher pooled sampled median CPU rose **2.64% to 13.39% of one core**. Sparse Docker CPU/RAM samples include startup/warmup/end periods, omit client/other host processes, and are neither absolute peaks nor CPU cost per effect.
- Historical **2.7-3.6 effects/s** runs used a different protocol/environment and are not matched baselines. Ten simulator seeds do not establish ten independent workload calibrations or universal controller superiority. Episode precision penalizes fragmentation and differs from out-of-truth onset counts and tick occupancy.

## Curated evidence

- [Execution summary CSV](../benchmarks/curated/2026-11-14/execution-summary.csv), [full distributions and metadata](../benchmarks/curated/2026-11-14/execution-summary.json), and [polling tradeoff chart](../benchmarks/curated/2026-11-14/polling-tradeoff.svg). Each run's `evidence_dir` links compressed raw samples, role spans, derived analysis and sanitized Docker samples.
- [All five fault snapshots and handling events](../benchmarks/curated/2026-11-14/fault-summary.json).
- [All 24 controller groups CSV](../benchmarks/curated/2026-11-14/controller-summary.csv) and [full ten-seed controller summary](../benchmarks/curated/2026-11-14/controller-summary.json), with per-seed evidence under [controller](../benchmarks/curated/2026-11-14/controller/).
- [SHA-256 evidence manifest](../benchmarks/curated/2026-11-14/SHA256.json) and [methodology audit](BENCHMARK_AUDIT.md).

## Reproduction commands

Run from the repository root. These are prospective commands, not validation executed by this documentation update. Real-system commands require the existing local `bk-final-regression` PostgreSQL/Kafka/Redis infrastructure and `bk-final-regression-tests:latest` image with the current benchmark modules. The runner creates new benchmark databases, topics/groups and app containers on that shared infrastructure; it does not reproduce an identical host load. No AWS or paid API is needed.

For a fresh clone, use Python 3.12+ and Docker Desktop with Linux containers/Compose. In a host virtual environment, install the project if needed for `botkernel.evaluation`. The project dependencies include `confluent-kafka>=2.6,<3` (including `confluent_kafka.admin`), Psycopg, SQLAlchemy, HTTPX and tracing libraries; the Dockerfile installs the same project dependencies in the benchmark image. No separate Kafka Python package is needed. Use an interpreter/platform with a compatible confluent-kafka wheel; source builds require librdkafka and compiler prerequisites.

```powershell
# Optional host environment setup, if project dependencies are not already installed.
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .

# Fresh-clone local infrastructure and benchmark image; no application/test startup.
docker compose -p bk-final-regression -f compose.yaml up -d --wait postgres redis kafka
docker build -t bk-final-regression-tests:latest .

# Confirm broker readiness before launching the runner; retry if Kafka is still starting.
docker compose -p bk-final-regression -f compose.yaml exec -T kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server kafka:9092
```

Compose also runs the Kafka volume-permission initializer. PostgreSQL has a healthcheck; Kafka readiness is checked separately above. Reuse an existing compatible project rather than resetting its data; these commands retain volumes. The runner uses the `bk-final-regression_default` network and expects the standard PostgreSQL credentials from `compose.yaml`. Its memory guard requires at least 650 MiB available before each run; more headroom is advisable. Fresh-clone results will not reproduce the original competing host load.

```powershell
# All 18 throughput runs; order reverses in the second repeat.
python -B scripts/run-shared-benchmarks.py --execute --infrastructure-project bk-final-regression --image bk-final-regression-tests:latest --actions 24 48 80 --concurrency 1 4 8 --repeats 3 --poll-seconds 0.2 --compare-poll-seconds 0.02 --label matched-poll

# Exact executed selector: --actions 1 still runs all five fixed recovery cases.
python -B scripts/run-shared-benchmarks.py --execute --recovery --infrastructure-project bk-final-regression --image bk-final-regression-tests:latest --actions 1 --concurrency 1 --repeats 1 --poll-seconds 0.2 --label fault-matrix

# Two predeclared five-seed blocks; all eight scenarios and three policies by default.
python -B -m botkernel.evaluation --seeds 1103 1201 1301 1409 1511 --duration 120 --output benchmarks/results
python -B -m botkernel.evaluation --seeds 1601 1709 1801 1901 2003 --duration 120 --output benchmarks/results
```

Each invocation creates fresh UUID-named evidence. For offline stage analysis of one run, use its raw JSON and three exported role files; choose a new output path (exclusive creation preserves earlier analysis):

```powershell
python -B -m botkernel.benchmark_analysis --raw <run-dir>/<uuid>/raw.json --spans <run-dir>/telemetry/api.jsonl <run-dir>/telemetry/publisher.jsonl <run-dir>/telemetry/worker.jsonl --output <new-analysis.json>
```

The offline stage analyzer uses only the standard library. The curated exporter also generates an SVG with **optional host packages `matplotlib` and `numpy`**; they are not declared project dependencies. Install them in the host environment only if needed before export:

```powershell
python -m pip install matplotlib numpy
```

Replace angle-bracket placeholders before execution. To curate all completed sessions, substitute the new comparison/fault session directories and two evaluation UUID directories; `--output` must not exist:

```powershell
python -B scripts/export-engineering-results.py --comparison <comparison-session> --faults <fault-session> --controllers <seed-block-1-dir> <seed-block-2-dir> --output <new-curated-dir>
```

## Historical reports retained below

Everything below this divider is the preserved earlier report, including its then-current commands, numbers, unavailable metrics and follow-up status. References to "current" or "current run" below describe that historical session only. They do not supersede the latest study or imply that historical follow-ups remain unimplemented.

---

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
