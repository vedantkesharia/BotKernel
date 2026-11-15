# Benchmark audit: latest study (2026-11-14)

[Engineering results](ENGINEERING_RESULTS.md) is authoritative for new numbers; [Benchmarks](BENCHMARKS.md) provides reproducible commands and the full evidence index. This addendum covers the complete latest study and retains the original audit below as historical evidence.

## Scope and findings

- **Execution:** all 18 predeclared interleaved runs, three repeats for each 24/1, 48/4 and 80/8 workload at 200/20 ms publisher polling. All 912 measured actions and 78 warmups completed with one published outbox, receipt and effect each; resource versions matched effect counts. Medians are across run-level percentiles, not pooled action distributions or confidence intervals.
- **Tradeoffs:** 24/1 throughput 4.717 to 10.465 effects/s and completion p95 259.402 to 120.842 ms; 48/4 throughput 14.762 to 25.205 and completion p95 382.406 to 222.237 ms. At **eight clients**, throughput regressed 12.723 to 12.337 (**-3.03%**), completion p95 worsened 815.305 to 927.094 ms (**+13.71%**), and admission p95 worsened 235.936 to 279.838 ms (**+18.61%**). Admission p95 also worsened at one client. The default remains 200 ms; the evidence does not support universal improvement.
- **Durability:** all five fault actions completed with five unique effects and zero unresolved actions: three receipt-crash/duplicate repeats, one publisher ACK-before-commit crash and one publisher pause. Worker recovery times were 6.035/6.045/6.132 s; publisher crash/pause 4.687/5.405 s. Different timing boundaries prevent a comparative recovery-speed claim. Kafka remains at-least-once; simulator receipts do not prove universal exactly-once external effects.
- **Controller:** all 10 seeds, eight scenarios and three policies (240 virtual runs, 120 ticks each), with identical input digests across policies. Oscillation reversals/interventions improved 47/7 to 15/2, while modeled p95 worsened 154.573 to 264.283 ms, throughput fell 0.658 to 0.308, tick false-positive occupancy rose 0.178 to 0.800, and outside-truth onsets rose 0 to 10. Collective avoided basic's 10 outside-truth onsets each in simultaneous_resources and temporary_spike; healthy scaling had no alarms. All 24 groups are retained. Episode fragmentation, outside-truth onsets and tick occupancy have different denominators; null denominators remain null. Virtual outputs are separate from PostgreSQL/Kafka measurements.

## Measurement and provenance qualifications

All six stages cover 912/912 measured actions, but **37 negative outbox deltas were retained**. Outbox wait is a span-boundary proxy: committed work may be observed before the enclosing admission span ends, and cross-process wall clocks can be noisy. Dispatch-start-to-consume includes producer/broker/consumer scheduling, not pure network latency. Worker execution includes finalization; overlapping stage percentiles cannot be summed.

Lag was known in **415/448 samples**, unknown in 33; telemetry reported zero errors. Unknown offsets were not imputed as zero. Maximum known lag at 80/8 rose 6 to 7. A sampled backlog highwater is not continuous observation or an independent post-load drain-duration measurement.

These are **three short repeats**, measurement windows 1.800-6.900 s, with 24-80 measured actions per run and unstable p99 estimates. Shared PostgreSQL/Kafka and competing host workloads remained; Node/SVG/browser review overlapped later measurements. Alternating order reduces order bias but cannot remove host drift. Results support bounded local tuning observations, not a capacity limit, production sizing or a unique causal bottleneck. Historical 2.7-3.6 effects/s measurements are not matched comparisons.

Pooled sampled median publisher CPU rose 2.64% to 13.39% of one core. Sparse Docker samples include startup/warmup/end periods and exclude the client and other host processes. CPU/RAM samples and sampled maxima are **not absolute peaks**, time-weighted workload averages or CPU cost/effect. Ten simulator seeds are not ten independently calibrated workloads; near-deterministic trajectories and persistent containment limit generalization.

Recorded source hashes of worker/core/api/observability/real_benchmark/benchmark_runtime were identical across all 18 runs; benchmark_analysis also matched. The full source manifest was not identical: unimported benchmark_failures.py appeared after the first five chronological runs, and real_benchmark_recovery.py changed across the first five, next seven and final six runs. These fault helpers are outside the measured throughput import path; do not describe every repository file as unchanged. Per-run manifests retain exact hashes.

## Evidence and reproduction

[Execution CSV](../benchmarks/curated/2026-11-14/execution-summary.csv) and [full execution JSON](../benchmarks/curated/2026-11-14/execution-summary.json) retain every run, distributions, min/max, stage coverage and `evidence_dir` references to compressed raw samples/spans and sanitized resource samples. [Five-fault summary](../benchmarks/curated/2026-11-14/fault-summary.json), [24-group controller CSV](../benchmarks/curated/2026-11-14/controller-summary.csv), [full controller summary](../benchmarks/curated/2026-11-14/controller-summary.json) and [SHA-256 manifest](../benchmarks/curated/2026-11-14/SHA256.json) support review without cherry picking. [Reproduction commands](BENCHMARKS.md#reproduction-commands) distinguish local real-system runs, virtual evaluation and offline export; the fixed five-case recovery matrix uses the exact executed `--actions 1` selector. Fresh-clone infrastructure/image startup, host `pip install -e .` (including confluent-kafka dependencies) and optional matplotlib/numpy export prerequisites are documented there. None were executed for this documentation update.

## Historical audit retained below

Everything below is the preserved earlier audit. Dates, then-missing measurements, requirements and UI-session statements refer to those historical sessions. Episode follow-ups and latest real-system measurements above must be read separately from the original three-seed audit.

---

# Benchmark and controller audit ? 2026-11-07

This is a targeted source and artifact audit. It does not rerun or alter the saved benchmark. Original evidence is retained in `benchmarks/results/88b0aa07-e4bb-40b9-9bab-e11d9fdf33f0/`.

## Verified definitions in evaluation.py
`_harmful_intervals` declares scenario windows before detection. Oscillation, overlapping remediation, and worker failure are labeled harmful from tick 0 to `duration-45`; cascade begins at tick 15; recurrence has two intervals. These labels depend on a scenario schedule, not measured harmful effects or realized application state. `build_schedule` uses the same seed/scenario schedule for all three modes and hashes it. Exogenous load and noise are equivalent across modes, while state and subsequent agent actions diverge due to interventions. This is a fair comparison of policies under shared inputs, but state-dependent outcomes are not equivalent samples.

Confusion counts in `simulate` are **per virtual tick**. The `alarm_active` flag remains true throughout a basic cooldown or collective `HOLD`/`VERIFYING`/`ESCALATED` state. Thus a controller that keeps an incident active after the predeclared harmful interval accumulates false-positive ticks even if no new false alarm occurred. Precision and FPR describe alarm occupancy versus scheduled windows, not episode-level incident classification. They cannot alone establish detector trigger quality. `unnecessary_interventions` instead counts intervention *starts* outside a scheduled harmful interval; this is a different denominator. There is no explicit episode-level false alarm count in the persisted summary.

The saved oscillation report says collective vs basic: 15 vs 47 modeled reversals and 2 vs 7 interventions, but precision .633 vs .886, FPR .800 vs .178, logical throughput .308 vs .658 actions per virtual second, and modeled application p95 264.063 vs 154.713 ms. These are adverse as well as favorable outcomes; no superiority claim is justified. A 20-second hold and sustained verification can suppress actions while leaving modeled latency high, explaining a plausible throughput/latency tradeoff. The exact contribution of hold duration to those results needs per-tick analysis; this audit does not assign causality from aggregate metrics.

## Production fidelity
The collective mode calls the production `stability.analysis` scoring function on virtual effects. Its surrounding lifecycle is separately modeled in `_advance_collective`, so it is not an end-to-end execution of PostgreSQL incident transitions, Kafka, outbox, or recovery. Basic mode uses two high-latency samples and fixed cooldown. The benchmark's action throughput and application p95 are simulator outputs, not actual service latency or PostgreSQL/Kafka throughput. Confidence intervals over only three seeds often collapse because policies produce identical outcomes.

## Required follow-up
1. Add per-episode trigger precision/recall and false-alarm episodes alongside existing tick occupancy metrics. Preserve old metrics with explicit names so historical reports remain interpretable.
2. Report alarm onset/clear times and scheduled interval boundaries; separate persistent alarm occupancy after a harmful window from new triggers.
3. Validate labels with independently specified action/telemetry criteria and sensitivity tests for interval end times; do not derive labels from a detector's output.
4. Vary seeds and workload intensity/duration. Retain raw per-tick evidence and report each seed before intervals.
5. Keep real PostgreSQL/Kafka admission/dispatch/CPU/memory measurements in a separately named experiment.

No thresholds, labels, or artifacts from the original seeded evaluation run were changed in this UI-focused session. The browser suite and one manual persistence check created additional one-seed virtual simulation runs, which are distinct from the audited run and not service-performance benchmarks.

The Experiment Lab had a separate presentation bug: the API groups `time_series` records by mode, while the chart merged rows by tick and retained insertion order. Recharts therefore received virtual ticks out of order. The UI now sorts merged rows by tick. Series entrance animation also caused partial curves in immediate screenshots and React duplicate-key warnings; it is disabled for these operational charts. The persisted benchmark artifacts and evaluation calculations were not changed.

## Follow-up UI session

The neutral Experiment Lab explicitly labels its existing precision, recall, F1 and false-positive rate as tick-level alarm occupancy, not incident-trigger metrics. Its mobile chart labels the virtual-time axis separately from the legend.

## Episode analysis follow-up (2026-11-11)

The separate five-seed run documented in `BENCHMARKS.md` adds one-to-one overlap matching, detection and observed-clear delays, unmatched-alert and missed-episode counts, onset-outside-truth counts, and modeled containment duration. No controller threshold or original ground-truth label changed. Repeated alerts within one harmful interval are unmatched under this metric, even when their onset falls inside truth; they must not be presented as out-of-truth triggers. An alarm carried across two disjoint truth episodes can match only one. Boundary-censored alert clear times remain unavailable. This changes neither the historical occupancy metrics nor their interpretation.

For oscillation, basic has more fragmented matched-window alerts but fewer onsets outside truth than collective; collective also keeps containment active longer and has worse modeled latency and logical throughput. These observations support methodology and tradeoff explanations, not a causal attribution to hold duration alone. The real PostgreSQL/Kafka results are separate measurements under `benchmarks/results/real-system/`, not improvements in this simulated policy.

## Measured-source versus final-source provenance

All 18 performance runs used identical hashes for worker, core, API, observability, benchmark client and benchmark wrapper. The final worker/core/API/observability still match those measured hashes. After measurements, the client and wrapper gained a fail-closed private API URL guard; no workload, timing, sampling or exporter logic changed. In-memory reversal of only that guard reproduced both recorded hashes byte-for-byte (`real_benchmark.py`: `258627bd70f4da8eaf4f8cf41cbd105c14d25fcbe6ee708c6a2cff03811a9704`; `benchmark_runtime.py`: `cb68d583ae406c492703c9d77947cf9077ab258ed94b3df0372c790f22ad6f5c`). The final 255-test regression includes the guard. Do not describe the measurements as byte-identical final-source measurements or rewrite their source metadata.
