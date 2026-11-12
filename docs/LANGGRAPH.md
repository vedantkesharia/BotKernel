# LangGraph agents and Bedrock

## Verified local incident investigation walkthrough (2026-11-10)

The bounded `botkernel.live_demo` now continues past controller recurrence to invoke the real `/incidents/{id}/investigations` endpoint with `provider=deterministic_mock`, retrieve the persisted report, repeat the identical idempotency request and verify every cited action against both the gateway ledger and the Effect Graph. The script remains one deterministic driver with two registered identities; it is not the independent Cost/Performance LangGraph service demo. It produces eight gateway actions through PostgreSQL outbox, Kafka and worker receipts, and reports actual incident/report/effect IDs. On the verified isolated `botkernel-bedrock-e2e` project, incident 2 produced eight `SUCCEEDED` ledger actions, eight published outbox rows, eight receipts, eight effects (versions 5–12), one detected/recurrent incident with two interventions, and a COMPLETE deterministic investigation. Its report contained eight VERIFIED_FACT findings, seven DETERMINISTIC_INFERENCE reversals and one uncertain HYPOTHESIS. Exact IDs and evidence are in the latest private project handoff.

Repeat locally with `.\scripts\run-live-demo.ps1`; see [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md) for resource checks, dashboard connection and non-destructive cleanup. It creates a new local Compose project, so first inspect Docker resource pressure. No cloud request or Bedrock inference is part of this path.

## Independent Cost and Performance agents

The Cost and Performance processes each run a typed StateGraph (`observe -> analyze -> submit`) with a role-specific SQLite checkpoint. They read API telemetry, produce a structured proposal and submit only through the existing FastAPI `/actions` gateway. Deterministic mock reasoning is the default; optional Bedrock reasoning does not bypass gateway admission or the Collective Stability Controller. The agents have no direct SQL, Kafka, infrastructure or remediation tools.

Per-role checkpoints retain workflow state and proposal identity; they are not authoritative action state. Submission records preserve the canonical payload and idempotency key before HTTP submission, use bounded retry/reconciliation attempts and pause uncertain outcomes in `REVIEW_REQUIRED`. A cooperating local-file ownership lock limits concurrent advancement of one checkpoint, but is not distributed fencing. The PostgreSQL ledger and simulator receipt remain authoritative. The operator has no automated review-release workflow.

For local deterministic verification, follow the isolated commands in this guide's repository history or the root README and use a distinct Compose project name and free loopback port. Do not remove named volumes to stop a project. The AWS-demo Compose mounts `agent_checkpoints` persistently at `/var/lib/botkernel/checkpoints`; Cost and Performance use different SQLite files. Checkpoint restore is local-disk behavior and has not been tested on EBS or after EC2 recreation.

Example local deterministic startup (from the repository root in PowerShell):

```powershell
$env:BOTKERNEL_API_PORT='18029'
$env:AGENT_INTERVAL_SECONDS='8'
$env:AGENT_MAX_RUNS='3'
docker compose -p botkernel-langgraph --profile langgraph up --build -d postgres redis kafka init api publisher worker recovery langgraph-cost langgraph-performance
Invoke-RestMethod http://127.0.0.1:18029/ready
docker compose -p botkernel-langgraph --profile langgraph logs --tail 50 langgraph-cost langgraph-performance
docker compose -p botkernel-langgraph --profile langgraph down
```

Use an unused port/project name and retain volumes; do not add `-v`. This runs deterministic local agents only, not Bedrock.

## Incident investigations

The investigator first gathers bounded evidence using read-only PostgreSQL transactions, then classifies verified facts, deterministic inferences and evidence gaps. Bedrock, when explicitly selected and separately authorized, may add only evidence-grounded `HYPOTHESIS` findings and advisory recommendations. It cannot alter the deterministic findings or execute remediation. Evidence links are validated against the supplied facts and link into the dashboard Effect Graph.

Reports are idempotently persisted in PostgreSQL and expose provider/model provenance and bounded error status. Session advisory slots constrain admission under normal connectivity; evidence queries have a five-second statement timeout. A supervised process executes each graph with a configurable hard deadline and termination grace; stale workers are fenced from finalizing reports. Session loss can release a slot while its process continues, so this is not a strict distributed concurrency cap during a partition. A terminated Bedrock invocation may have incurred a charge and is never automatically retried.

The operations console uses an externally configured operator bearer credential. The local Compose API binds to loopback; the AWS demo additionally exposes only the loopback-bound dashboard, which proxies API requests over the private container network. Do not expose it to untrusted networks.

## Optional Bedrock Converse provider (offline implementation)

`botkernel.bedrock.BedrockConverse` uses the Boto3 Bedrock Runtime `Converse` operation lazily, without tools. It applies configured SDK timeouts and one SDK attempt, bounds requests/output, validates strict structured response contracts, classifies sanitized errors and records returned model/token provenance. Cost/Performance proposals remain advisory unless a separate action-execution setting is enabled; the deployment runtime hard-codes mock cloud mode and remediation off. Investigator analysis occurs only after deterministic evidence collection. There is no automatic model-error fallback.

All gates are off by default:

```text
AGENT_PROVIDER=deterministic_mock
INVESTIGATOR_PROVIDER=deterministic_mock
BEDROCK_ENABLED=false
BEDROCK_SPEND_AUTHORIZED=false
AI_ACTION_EXECUTION_ENABLED=false
CLOUD_MODE=mock
AWS_DEPLOY_ALLOWED=false
```

Changing the provider alone does not permit a request. `BEDROCK_ENABLED=true` and `BEDROCK_SPEND_AUTHORIZED=true` are both required; the latter runtime flag is not itself spend approval. A shared Redis reservation limits estimated daily calls/tokens and fails closed if unavailable. These local limits are not an AWS billing cap, and response usage is only known after a successful call. The Terraform Bedrock policy is a separate optional attachment restricted to explicitly configured model/profile ARNs; the EC2 role does not receive Bedrock access by default.

No AWS account/profile was inspected, no model or region is selected, and no live Converse request has been made. Before any live test, establish and approve:

1. The AWS account/profile identity without printing or sharing credentials, and the exact region.
2. The model or inference-profile ID, regional Converse support and the required `bedrock:InvokeModel` resource ARNs (including backing model ARNs where required).
3. Current official model-specific input/output prices for that region and inference tier.
4. The prompt/input token estimate, at most 512 output tokens per call, timeout and expected usage.
5. At most three calls total: one Cost decision, one Performance decision and one evidence-complete investigation (which may abstain before model invocation). The current configured estimated-token budget is 20,000/day, not a guaranteed billing limit.
6. A dollar estimate derived from the exact selected model/region and conservative token estimate, then explicit approval of the maximum additional spend.

No model-specific dollar estimate is responsible until the model, region, account access, token estimate and current price are known. Do not invoke Bedrock before that review. The live test must keep `AI_ACTION_EXECUTION_ENABLED=false`, `CLOUD_MODE=mock`, and `AWS_DEPLOY_ALLOWED=false`; do not provision resources as part of model verification.

After approval, use an environment with an assigned IAM role or otherwise separately approved secure credential chain; do not bake credentials into images, frontend bundles or Compose files. Set the approved model/region, `BEDROCK_MAX_CALLS_PER_RUN=1`, `BEDROCK_MAX_CALLS_PER_DAY=3`, `MAX_BEDROCK_TOKENS_PER_DAY=20000`, `BEDROCK_MAX_OUTPUT_TOKENS=512`, `BEDROCK_REQUEST_TIMEOUT_SECONDS=10`, and `AGENT_MAX_RUNS=1`. Verify actual provider/model provenance and returned usage for Cost and Performance, then submit one evidence-complete investigation. Preserve the idempotency keys and report. If a call errors, abstains or returns `NO_OP`, record that actual result and do not retry beyond the approved call count. This is an acceptance procedure, not a command executed in this session.

The following is a command template for a **future separately approved AWS-demo session**, after applying an explicitly reviewed Bedrock-only IAM policy and placing non-secret settings in a protected acceptance env file. It bypasses the deployment helper intentionally because that helper refuses all inference; it must not be used until the account, region, model, compatibility, price, IAM ARNs, token estimate and dollar ceiling above are approved:

In the authorized Linux SSM shell on the EC2 host:

```sh
runtime_env=/etc/botkernel/runtime.bedrock-acceptance.env
docker compose --env-file "$runtime_env" -f /opt/botkernel/compose.aws-demo.yaml up -d dashboard api publisher worker recovery controller langgraph-cost langgraph-performance
docker compose --env-file "$runtime_env" -f /opt/botkernel/compose.aws-demo.yaml logs --tail 50 langgraph-cost langgraph-performance
```

In the operator's PowerShell session with the separately approved SSM port-forward active:

```powershell
$incidentId = <approved-complete-incident-id>
$body = @{ idempotency_key = [guid]::NewGuid().ToString(); provider = 'bedrock' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/incidents/$incidentId/investigations" -ContentType 'application/json' -Body $body
```

The acceptance env must set `AGENT_PROVIDER=bedrock`, `INVESTIGATOR_PROVIDER=bedrock`, `AGENT_MAX_RUNS=1`, `CLOUD_MODE=mock`, `AWS_DEPLOY_ALLOWED=false`, `AI_ACTION_EXECUTION_ENABLED=false`, `BEDROCK_ENABLED=true`, `BEDROCK_SPEND_AUTHORIZED=true`, `BEDROCK_MODEL_ID=<approved-id>`, `BEDROCK_REGION=<approved-region>`, `BEDROCK_MAX_CALLS_PER_RUN=1`, `BEDROCK_MAX_CALLS_PER_DAY=3`, `MAX_BEDROCK_TOKENS_PER_DAY=20000`, `BEDROCK_MAX_OUTPUT_TOKENS=512`, and `BEDROCK_REQUEST_TIMEOUT_SECONDS=10`. The request assumes the operator has first established the approved SSM port-forward to dashboard port 8080. Agent processes can run one cycle each; the investigation may abstain without a call if evidence is incomplete. This template is not an AWS approval or a dollar cap. After acceptance, explicitly restore the disabled runtime settings and verify the resulting Compose configuration.

Official references: [Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html) documents Converse and its IAM permission; [model cards](https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html) list supported capabilities; [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) varies by provider/model, tier and region.

## Bedrock acceptance preparation — offline integration coverage (2026-11-11)

The default remains deterministic and all Bedrock/action gates remain closed. The agent observer now supports an optional `BOTKERNEL_AGENT_RESOURCE` target (nonblank, at most 100 characters); the default is still `service-a`. This permits isolated provider tests to exercise real API simulator telemetry without reusing a resource that may have a controller hold or pending action.

Offline acceptance tests use fake Bedrock reasoners/Converse responses, not AWS. They execute Cost and Performance LangGraphs against the real local `/telemetry` API, persist SQLite reasoning provenance, and assert `AI_ACTION_EXECUTION_ENABLED=false` prevents gateway submission and operational mutation. A PostgreSQL/Kafka-backed investigation test creates a controller incident through the existing local simulator helpers, invokes the real investigation API with a mocked Converse response, validates citations against the actual committed effects, verifies persisted model/provider/usage fields and confirms duplicate request replay does not make another provider call. Operational resource, action, outbox, receipt, effect, incident, transition and operator-action snapshots remain unchanged by report generation.

The proposed live candidate remains inference profile `us.amazon.nova-micro-v1:0` in `us-east-2`, with one Cost, one Performance and one investigator request, 512 output tokens each, application estimated-token budget 20,000, and maximum call budget configured to 3. These are requested test bounds only. The Redis budget is an application guard, can be lost/reset with Redis state, uses an input-size estimate rather than a tokenizer, and is not an AWS billing cap. Bedrock SDK retries are configured to one total attempt; uncertain Cost/Performance invocations are durably marked and not repeated. A complete investigator report is persisted in PostgreSQL; incomplete evidence abstains before a call.

No AWS identity, Bedrock availability, IAM, model-region support or current pricing was queried in this offline session. The local Compose app containers do not mount the operator's AWS profile, so local-profile execution from inside a container is not currently established; do not copy credentials into images or the repository. The deployed EC2 role is documented as lacking Bedrock permission by default. A separately authorized read-only preflight must settle account/region/model/profile/permission and the safe credential path before any live request. Keep AI action execution disabled for the experiment.

The bounded three-case runner and current local-host credential route are documented in [BEDROCK_ACCEPTANCE.md](BEDROCK_ACCEPTANCE.md). The runner is not executed or authorized by configuration values alone; require separate user approval for AWS reads and, later, paid inference.
