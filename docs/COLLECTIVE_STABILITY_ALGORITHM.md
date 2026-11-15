# Collective stability controller v0.3

The deterministic simulator controller is implemented in [stability.py](../botkernel/stability.py) and migrations `0003`–`0005`. It is an engineering policy, not a learned causal model or a claim of optimal thresholds.

## Evidence and detection

Each successful action writes one committed effect with resource version, before/after capacity, synthetic latency and observation time. Unique action and resource/version constraints prevent duplicate evidence on replay. The graph orders by version and emits observed agent/action/resource relationships. Inferred `REVERSED_DIRECTION` edges require contiguous versions and matching capacity boundaries; see [relationship predicate](../botkernel/effect_relationships.py).

The detector counts adjacent nonzero changes in the observation window: `k` is the number of cross-agent opposite-direction pairs, and `D=1` when a committed change has latency above 100 ms. Its score is:

```text
S = 0.7 * min(1, k / 3) + 0.3 * D
```

Detection requires at least four changes, two agents, three reversals, degradation and `S >= 0.8`. This rejects monotone healthy scaling. Detector pair counting and the graph's stricter contiguous-edge predicate are separate contracts.

## Containment and sustained recovery

`HOLD` blocks only new scale-downs on the affected resource; scale-up and unrelated resources remain admissible. Hold mutation uses the existing quota/resource lock order, making admission atomic with gateway decisions and action finalization. Window scanning occurs before the short mutation transaction.

At hold expiry, newly monitored effects must not trigger detection and current modeled latency must be at or below 100 ms before entering `VERIFYING`. The initial healthy sample starts verification; it does **not** establish recovery. `VERIFIED` requires both the elapsed verification window and the configured healthy-sample count. Defaults are a 60-second observation window, 20-second hold, 20-second verification window, three samples and two automatic interventions.

New qualifying reversals after verification reopen the same incident and reapply containment while intervention allowance remains. Harm during verification can also reapply containment. Continued harm after the intervention limit becomes `ESCALATED`; recovery does not loop indefinitely. Evidence retains contributing actions, agents, reversal pairs, score, correlation caveat and lifecycle transitions.

Configuration uses `STABILITY_WINDOW_SECONDS`, `STABILITY_HOLD_SECONDS`, `STABILITY_VERIFICATION_SECONDS`, `STABILITY_VERIFICATION_SAMPLES` and `STABILITY_MAX_INTERVENTIONS`. This documentation does not change thresholds or algorithms.

## Private operator workflow

Migration `0005` adds idempotent operator-action records and `RESOLVED`. `POST /incidents/{id}/acknowledge` accepts an escalated incident; `POST /incidents/{id}/resolve` accepts only a verified incident. Both require an operator bearer credential, bounded nonblank reason and idempotency key. Agent and metrics credentials cannot perform these operations. See [security](../botkernel/security.py) and [API](../botkernel/api.py).

The API locks quota, resource and incident in the established order. Identical requests replay; conflicting key reuse or invalid state returns 409. Resolved incidents remain in history; later detection creates a new incident. The dashboard exposes actions only in allowed states. Keep access private: a shared bearer credential is not a multi-user identity/authorization system. No recovery-action approval queue is implemented.

## Evidence and limits

The original three-mode seeded evaluation did not establish superiority: collective mode reduced modeled oscillations in that scenario but showed more false alarms and lower modeled throughput than basic. The later five-seed follow-up separately scores matched alarm episodes and onsets outside scheduled harm. Fewer fragmented oscillation alarms coexisted with an outside-truth onset, longer containment and worse modeled latency/throughput. No thresholds were changed. See [benchmark definitions](BENCHMARKS.md) and [audit](BENCHMARK_AUDIT.md).

November 14 runtime evidence exercised hold, sustained verification and recurrence; see [validation](VALIDATION.md). This is bounded simulator evidence. Latency uses `40 + 160 * max(0, workload/capacity - 1)`, not production telemetry. Service-dependency inputs, adaptive baselines and production-calibrated thresholds are absent. Small seed sets and simplified policies limit inference.
