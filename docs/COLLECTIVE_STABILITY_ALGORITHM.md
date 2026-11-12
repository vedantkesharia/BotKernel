# Collective stability controller v0.3

Implemented in `botkernel/stability.py` and migrations `0003`–`0005`. This is a deterministic engineering controller for the local simulator, not a learned causal model or a claim of optimal thresholds.

## Evidence and detection
Each successful action writes exactly one committed `effects` row in the same transaction that advances the durable resource version. The row contains action, agent, resource, before/after capacity, synthetic latency, and observation time; the action and `(resource, version)` constraints make replay unable to create duplicate evidence. Graph construction orders by version and emits observed `agent -> action -> resource` relationships plus explicitly inferred cross-agent `REVERSED_DIRECTION` links.

For non-zero changes in a resource observation window, `k` is the count of adjacent, cross-agent, opposite-direction pairs and `D` is one when a committed effect has latency above 100 ms. `S = .7 min(1, k/3) + .3D`. Detection requires at least four changes, two agents, three reversals, degradation, and `S >= .8`. This rejects monotone healthy scaling. The defaults are configurable with `STABILITY_WINDOW_SECONDS`, `STABILITY_HOLD_SECONDS`, `STABILITY_VERIFICATION_SECONDS`, `STABILITY_VERIFICATION_SAMPLES`, and `STABILITY_MAX_INTERVENTIONS`.

## Incident lifecycle and containment
`HOLD` blocks only new scale-downs on the affected resource; scale-up and all unrelated resources remain admissible. A hold is created or renewed under the existing quota/resource lock order, so its admission decision is atomic with gateway admission and action finalization. Window scans run before this short mutation transaction; the controller does not hold a global lock while traversing effects.

At hold expiry, the resource enters `VERIFYING` only when newly observed effects since the intervention are not harmful and current modeled latency is at or below 100 ms. It becomes `VERIFIED` only after the configured elapsed verification window and at least three controller samples. While verified, new qualifying reversals reopen the same incident and reapply containment. Each incident allows two automatic interventions; continued harmful behavior then becomes `ESCALATED`, requiring review instead of an endless hold/recovery loop. Evidence stores action IDs, participating agents, reversal pairs, the score, correlation caveat, and a bounded lifecycle transition history.

## Local operator workflow
Migration `0005` adds idempotent operator-action records and `RESOLVED`. `POST /incidents/{id}/acknowledge` accepts an escalated incident; `POST /incidents/{id}/resolve` accepts only a verified incident. Both require a bounded reason and idempotency key. The API locks quota, resource, and incident in the controller's existing lock order; duplicate identical requests replay successfully, while conflicting key reuse or invalid state transitions return 409. A resolved incident remains in history, and later detection creates a new incident rather than reusing the resolved row.

These are local-development controls, not authenticated identity or production authorization. Reasons and idempotency keys must be nonblank after trimming. No proposed recovery-action approval queue currently exists. The dashboard presents acknowledgement/resolution only in allowed states and labels the lack of identity authentication.

## Evaluation evidence
The first full three-mode seeded run and raw files are documented in `docs/BENCHMARKS.md`. It did not establish superiority: collective mode reduced modeled oscillations in the oscillation scenario but had substantially more false alarms and lower modeled throughput than the basic policy. This is evidence about the current deterministic simulator, not real system performance.

The later five-seed follow-up additionally scores matched alarm episodes and separately counts onsets outside scheduled harm. Its one-to-one overlap metric penalizes repeated alarms within one harmful window; it is not the same quantity as false-positive tick occupancy. The collective mode showed fewer fragmented alarms than basic in oscillation but one outside-truth onset, longer containment and worse modeled latency/throughput. No detection or intervention thresholds were changed. See `BENCHMARKS.md` for exact definitions and limitations.

## Limits
Latency remains the fixed local formula `40 + 160 max(0, workload/capacity - 1)` and is not production telemetry. There are no service-dependency telemetry inputs, adaptive workload baselines, or production-calibrated thresholds. The simulation's small seed set, simplified policies, modeled latency, and uneven scenario semantics limit inference; see `docs/BENCHMARKS.md`. The 60-second evidence window needs calibration for real workloads.
