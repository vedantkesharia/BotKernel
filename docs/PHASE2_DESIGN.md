# Phase 2 implementation design (deferred)

Gate: complete Phase 1 recovery/error policy and acceptance tests first.

## Storage and evidence
Add graph_nodes(id, kind, entity_id) with unique(kind,entity_id), graph_edges(id, source, target, kind, observed_at, action_id, evidence_strength, attributes), telemetry(service_id, observed_at, latency_p95, errors, load), and incidents(id, resource, opened_at, status, score, evidence_ids). Index edges on (source, observed_at) and (target, observed_at). Project ledger events idempotently using a unique source event identifier in one PostgreSQL transaction with consumer deduplication. Add execution timestamps and before/after capacity snapshots before building reversal edges.

Agent REQUESTED action; action MODIFIED resource; resource SUPPORTS service; action REVERSED earlier action; observation MEASURED service. PRECEDED is temporal evidence only. A reversal requires opposite nonzero capacity deltas on the same resource within 60 seconds, not merely adjacent timestamps. Evidence retains source action IDs and telemetry references.

## Detector
For each resource neighborhood use a 60-second event-time window, permit 5 seconds of lateness, and retain 10 minutes for replay. Compute reversal fraction R, repeated-target fraction Q, normalized distinct-agent count A, baseline-relative latency/error degradation D, and normalized dependent-service depth C. Initial hypothesis S=.30R+.15Q+.15A+.25D+.15C; all terms bounded [0,1]. Require at least four successful actions, two agents, two reversals, and sustained telemetry degradation before opening an instability incident at S>=.65 for two samples. These thresholds require calibration, not claims of optimality.

## Containment
Hold only scale-down on the affected resource for 20 seconds when evidence identifies capacity reduction as a likely contributor. Keep unrelated operations admissible. Release below .35 after three healthy samples, limit to two interventions per incident, then escalate. Persist hold policy and check under the same resource/quota admission transaction. Human approval required for future high-risk operations. Avoid no-op action contribution, startup windows, planned workload ramps and single-agent changes as false positives.

## Evaluation
Implement deterministic seeded workload and capacity-to-latency simulation. Run two independent cost/performance processes under identical schedules with: no coordination, locking plus fixed cooldown, and controller. Positive labels describe injected workload intervals and expected harmful loops; include healthy load ramps and benign reversals as negative cases. Measure precision/recall/F1, detection delay, attribution, unnecessary holds, changes avoided and stabilization delay. Export raw events and CSV/JSON reports, repeated seeds and confidence intervals. Do not compare different workloads or include paid inference. First slice: cost/performance oscillation plus a healthy unrelated resource; assert targeted containment and no unrelated holds.

## Recovery integration decision
Build graph evidence from committed effects with stable action IDs and execution timestamps, not Kafka delivery/retry counts. Migration 0002 recovery can finalize via a sweeper outside the normal consumer path; both paths must feed the same future idempotent projection. Escalated holds are safety constraints separate from controller cooldowns. Phase 2 remains deferred until Phase 1 acceptance.

## Implemented v0.1 update
The first slice is now in stability.py and migration 0003; see COLLECTIVE_STABILITY_ALGORITHM.md for actual behavior. Earlier multi-signal weights and multi-sample hysteresis in this document remain planned. Current implementation uses reversal count plus modeled latency, one bounded hold and one verification sample. No baseline evaluation yet.
