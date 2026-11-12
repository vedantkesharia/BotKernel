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
