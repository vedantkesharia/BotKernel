# LangGraph agents and investigations

Cost and Performance run independent typed `observe -> analyze -> submit` StateGraphs with separate SQLite checkpoints. They read simulator telemetry through FastAPI and mutate operational state only through `/actions`. PostgreSQL owns correctness, Kafka delivery is at least once, and Redis is advisory. Agents have no direct infrastructure or remediation tools.

## Provider and submission safety

[Agent source](../botkernel/lang_agents.py) accepts `deterministic_mock`, `bedrock` and `ollama_local`; unknown providers fail instead of falling back. Deterministic reasoning is the default. [Bedrock decisions](../botkernel/bedrock.py) use strict typed contracts with unknown fields forbidden. Submission revalidates every provider's checkpointed output against provider/model provenance, observed resource/version/capacity, role identity, decision/delta consistency and evidence. Model deltas are bounded to three units; Cost cannot increase capacity and Performance cannot decrease it.

Model proposals are checked against current hold/pending-action policy. With `AI_ACTION_EXECUTION_ENABLED=false`, proposals are durably advisory and are not submitted. Persisted advisory or policy-blocked proposals cannot become executable merely by changing a flag. `NO_OP` performs no submission. Enabled execution still requires gateway version, quota, dependency, idempotency and containment checks.

## Durable proposal lifecycle

The checkpoint stores workflow state, canonical proposal payload, fingerprint and stable idempotency key before HTTP submission. States include `PREPARED`, `SUBMITTING`, `OUTCOME_UNKNOWN`, `ACCEPTED`, `ADVISORY_ONLY`, `POLICY_BLOCKED` and `REVIEW_REQUIRED`. Bounded retries reconcile the existing proposal with the gateway rather than create replacement actions. Uncertain or exhausted outcomes require review; there is no automated review-release workflow.

A cooperating local-file lock limits advancement of one checkpoint; it is not distributed fencing. SQLite stores workflow evidence; PostgreSQL ledger state and simulator receipts determine action outcomes. Checkpoint volumes persist across container restarts, but cross-host ownership and disaster restore remain unverified.

## Read-only investigator

[Investigator source](../botkernel/investigator.py) gathers bounded evidence in read-only PostgreSQL transactions, separating `VERIFIED_FACT`, `DETERMINISTIC_INFERENCE` and `HYPOTHESIS` findings. Optional Bedrock analysis adds supported hypotheses and advisory recommendations; it cannot rewrite deterministic findings or execute remediation. Citations are validated against supplied facts. Insufficient evidence can abstain before inference.

The [API contract](../botkernel/api.py) permits only `deterministic_mock` or `bedrock` for investigations; an unsupported configured provider returns unavailable. The [service](../botkernel/investigation_service.py) persists reports and request fingerprints in PostgreSQL. Identical completed requests replay saved reports; conflicting idempotency reuse is rejected. Report statuses are `RUNNING`, `COMPLETE`, `INSUFFICIENT_EVIDENCE` and `FAILED`.

Session advisory-lock slots bound admission under normal connectivity. A supervised child has a hard execution deadline and termination grace; lease ownership fences stale finalization. Evidence queries also have statement timeouts. Database session loss may release a slot before its process stops, so this is not a strict distributed computation cap during partitions. A terminated model request may already have incurred a charge and is not automatically retried.

## Authentication and defaults

Private operator APIs require a configured bearer credential; agents use a separate scoped credential. The dashboard token lives only in memory. Retain loopback/private networking: shared-token authentication is not public multi-user authorization. See [dashboard usage](../apps/dashboard/README.md).

Agent and Investigator providers default to `deterministic_mock`. `BEDROCK_ENABLED`, `BEDROCK_SPEND_AUTHORIZED`, `AI_ACTION_EXECUTION_ENABLED` and `AWS_DEPLOY_ALLOWED` default to `false`; cloud mode is `mock`. Bedrock uses one bounded SDK attempt without model-error fallback. Redis guards allow 12 calls/day, 80,000 estimated tokens/day and 1,024 output tokens/call; they are not billing caps.

November 14 acceptance covered advisory Cost/Performance `NO_OP` decisions and a saved Investigator report across four new model calls, including one retained validation failure. Two independent deterministic agent processes were also verified. AWS is stopped. See [Bedrock acceptance](BEDROCK_ACCEPTANCE.md) and [validation](VALIDATION.md); recorded results do not authorize repeated inference or actions.
