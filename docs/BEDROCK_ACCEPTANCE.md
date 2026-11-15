# Bedrock acceptance

Optional Bedrock Converse reasoning is implemented for Cost, Performance and incident investigation. Genuine inference was verified on November 14, 2026. The private AWS demo was stopped afterward; inference and model-driven action gates were restored to `false`. See [validation](VALIDATION.md) for recorded evidence.

## Implementation contracts

- [Provider](../botkernel/bedrock.py): lazy Boto3 Converse client, one SDK attempt, bounded input/output, strict typed JSON with extra fields forbidden, sanitized diagnostics and returned usage provenance. Invalid responses are not coerced or unwrapped; errors do not trigger model switching or deterministic fallback.
- [Agent graphs](../botkernel/lang_agents.py): telemetry-backed decisions and durable SQLite checkpoints. Submission revalidates provider, provenance, resource/version, role, capacity delta and evidence. Model proposals remain advisory when action execution is disabled; enabled proposals still require gateway admission and controller policy.
- [Investigator](../botkernel/investigator.py): read-only evidence gathering precedes inference. Deterministic findings remain separate from model hypotheses, with validated citations. [Durable execution](../botkernel/investigation_service.py) persists PostgreSQL reports, supervises deadlines and fences stale finalization. Completed idempotent replay does not invoke inference again.
- [Acceptance runner](../botkernel/bedrock_acceptance.py): checks readiness, committed evidence, disabled actions and the original shared budget before a bounded three-case sequence. It saves incremental results and stops on failure. A failed sequence remains failed after a separately tracked successful invocation.

## Actual November 14 results

Requests used IAM role credentials and Nova Micro inference profile `us.amazon.nova-micro-v1:0` with source region `us-east-2`. This identifies the requested profile, not a separately returned destination-region model identity.

| Workflow | Actual result | Input / output tokens |
|---|---|---|
| Cost | Passed; advisory `NO_OP` | 561 / 104 |
| Performance | Passed; advisory `NO_OP` | 557 / 102 |
| Investigator, first response | Returned response failed strict root-schema validation; retained | 1,963 / 430 |
| Investigator, controlled new invocation | Passed; report persisted | 2,113 / 189 |

These are **four new calls**, including the failed response. The corrected Investigator prompt explicitly required the flat eight-field root contract; validation was not weakened. The successful report contained an empty hypotheses array and supported advisory narrative. Schema compliance and `NO_OP` do not prove optimal reasoning; the Performance capacity explanation merits human review. Capacity and latency evidence remains simulator data.

An earlier historical Cost response was lost. Its exact content, failure cause and billing outcome remain unknown. Offline reconstructions and later diagnostics do not recover it. Preserve the original failure, reservations and artifacts; do not replace it with later success.

The sequential Bedrock harness is distinct from the two independent deterministic LangGraph processes also verified in the final run. It does not demonstrate concurrent autonomous Bedrock agents.

## Defaults and budgets

```text
AGENT_PROVIDER=deterministic_mock
INVESTIGATOR_PROVIDER=deterministic_mock
BEDROCK_ENABLED=false
BEDROCK_SPEND_AUTHORIZED=false
AI_ACTION_EXECUTION_ENABLED=false
CLOUD_MODE=mock
AWS_DEPLOY_ALLOWED=false
BEDROCK_MAX_CALLS_PER_RUN=1
BEDROCK_MAX_CALLS_PER_DAY=12
MAX_BEDROCK_TOKENS_PER_DAY=80000
BEDROCK_MAX_OUTPUT_TOKENS=1024
```

Provider selection alone cannot enable inference. Both Bedrock gates are required; software flags do not grant spend approval. Redis atomically reserves estimated input plus maximum output before each SDK attempt and fails closed when unavailable. PostgreSQL owns correctness; this Redis guard is application spend protection, not a durable billing ledger or AWS billing cap. Preserve the original store, UTC-day counters and failed/ambiguous reservations.

Use role credentials or a separately reviewed secure credential chain; never embed credentials in images, frontend bundles or tracked configuration. Ambiguous network/SDK outcomes stop execution without automatic retry. Conclusive validation failures remain evidence; a controlled new invocation needs its own attempt identity and remaining authorized allowance. Future paid operations require specific approval. See [LangGraph contracts](LANGGRAPH.md).
