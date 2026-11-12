# Bedrock acceptance preparation

Status: **local preparation only**. No AWS identity, EC2, billing, IAM, Bedrock profile, pricing, or live inference was queried for this work. The previous EC2 runtime window expired; actual instance state is **UNKNOWN**. Do not treat any CLI examples below as authorization.

## Existing integration and remaining acceptance gap

`botkernel.bedrock.BedrockConverse` already makes one bounded Converse request, validates strict Pydantic response schemas, records the provider/model and returned token usage, reserves the shared Redis budget before a request, and fails closed if that reservation is unavailable. It configures one SDK attempt. It does not silently select deterministic reasoning after a Bedrock error.

The Cost and Performance StateGraphs use actual `/telemetry`, validate role direction/capacity/evidence and persist decision provenance in their role checkpoint SQLite database. With `AI_ACTION_EXECUTION_ENABLED=false`, model proposals are durably advisory-only and do not reach `/actions`. Investigator execution retrieves read-only incident/effect evidence before optional model analysis, validates citations, and persists the report and usage in PostgreSQL. Replaying a completed idempotency key returns its saved report without another inference request.

The current offline tests prove those paths with mocked provider responses. They are not three live calls. `botkernel.bedrock_acceptance` wraps the actual `run_once()` Cost/Performance LangGraphs and actual investigation HTTP API as one guarded, at-most-three-call sequence. The live runner requires separate resources with real simulated telemetry and committed-effect evidence, role-specific useful telemetry, an isolated incident whose controller effect references exist in the committed graph, exact configured limits, a loopback-only API/database/Redis route, and action execution disabled. It also checks durable SQLite reasoning records against each returned decision/provenance pair. It saves incremental JSON evidence to a new, non-existing output path and refuses to reuse a checkpoint database or owner file. It makes no automatic retry after an exception or ambiguous outcome. The single same-key investigation replay is performed only after the completed report response, to verify idempotency. Its separate `--prepare-local-fixtures` mode creates fresh simulator resources and committed seed effects only when all AI/cloud gates are off; it never creates model decisions.

The `--execute-live` mode is intentionally not being executed in this session. Its switch and `BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED=true` are additional software guardrails, **not user authorization**. In particular, do not set `BEDROCK_ENABLED` or `BEDROCK_SPEND_AUTHORIZED` based only on repository instructions.

## Local profile route, prepared but not run

The local overlay `compose.bedrock-acceptance.yaml` binds only PostgreSQL and Redis to loopback. The normal Compose API port is also loopback-bound. Run the runner on the host (not inside application containers), so Boto3 uses the host's configured credential chain/profile without mounting AWS credentials into containers:

```powershell
$Project = 'botkernel-bedrock-acceptance-<unique-suffix>'
$env:BOTKERNEL_API_PORT = '18080'
$env:BEDROCK_ACCEPTANCE_PG_PORT = '15432'
$env:BEDROCK_ACCEPTANCE_REDIS_PORT = '16379'
docker compose -p $Project -f compose.yaml -f compose.bedrock-acceptance.yaml --profile stability up --build -d postgres redis kafka init api publisher worker recovery controller
Invoke-RestMethod http://127.0.0.1:18080/ready
```

Use an isolated, fresh Compose project and unique local resource names. First create the Cost/Performance acceptance resources and commit at least one simulator effect per resource through the regular gateway/outbox/Kafka/worker path. The Cost resource must have capacity above 3. The Performance resource must have simulated p95 latency above 80 ms and capacity at most 17. Neither may have pending actions or a controller hold. Produce the incident on a third resource through the existing bounded local controller demo, then verify its committed effect links remain in the one-hour graph window. Do not reuse a shared development database or alter an existing cloud incident. Resource IDs and the incident ID are explicit runner inputs; the runner never fabricates model decisions or prepares fixture effects.

Once the isolated stack is ready, use the local-only fixture mode. It refuses non-loopback API/database/Redis endpoints, verifies the API still reports mock cloud/no infrastructure remediation, creates two fresh resources, then submits one low-risk seed action per resource through the real API and waits for one outbox, receipt and committed effect each. It does not invoke a model.

```powershell
$env:BOTKERNEL_API_URL = 'http://127.0.0.1:18080'
$env:DATABASE_URL = 'postgresql+psycopg://botkernel:local@127.0.0.1:15432/botkernel'
$env:REDIS_URL = 'redis://127.0.0.1:16379'
$FixtureRun = [guid]::NewGuid().ToString()
python -m botkernel.bedrock_acceptance --prepare-local-fixtures `
  --api-url $env:BOTKERNEL_API_URL `
  --output "benchmarks\results\bedrock-acceptance\fixtures-$FixtureRun.json"
$env:DEMO_RESOURCE = 'service-b'
docker compose -p $Project -f compose.yaml -f compose.bedrock-acceptance.yaml --profile stability --profile demo run --rm -e DEMO_RESOURCE=service-b live-demo
```

Record the two fixture resource IDs from the JSON and the `incident_id` printed by the deterministic live-demo. The incident demo uses the third resource `service-b`; it exercises real local PostgreSQL admission/outbox, Kafka, worker receipts and controller lifecycle. Run the host Python environment with repository dependencies already installed. Before any future inference approval, confirm the local API, database and Redis URLs refer only to this isolated project.

For a verified host profile, set `BEDROCK_PROFILE=botkernel-dev` in the later acceptance process; Boto3 uses that profile only inside the host process. If the owner instead approves another host credential chain, leave the profile unset. The profile name and credential availability have not been inspected. This path does not copy credentials into Compose, images, environment artifacts, or output reports.

Only after the distinct live-acceptance approval described below, set the exact reviewed gates and run once with fresh resource IDs and a fresh output filename. The two role cycles run locally in the host process; they do not start continuous agent containers. The API's cloud and AI-action gates remain mock/false. A model may correctly choose `NO_OP`; this is an accepted decision if provenance and evidence validate.

```powershell
$env:CLOUD_MODE = 'mock'
$env:AWS_DEPLOY_ALLOWED = 'false'
$env:AI_ACTION_EXECUTION_ENABLED = 'false'
$env:BEDROCK_ENABLED = 'true'
$env:BEDROCK_SPEND_AUTHORIZED = 'true'
$env:AGENT_PROVIDER = 'bedrock'
$env:INVESTIGATOR_PROVIDER = 'bedrock'
$env:BEDROCK_MODEL_ID = 'us.amazon.nova-micro-v1:0'
$env:BEDROCK_REGION = 'us-east-2'
$env:BEDROCK_MAX_OUTPUT_TOKENS = '512'
$env:BEDROCK_MAX_CALLS_PER_RUN = '1'
$env:BEDROCK_MAX_CALLS_PER_DAY = '3'
$env:MAX_BEDROCK_TOKENS_PER_DAY = '20000'
$env:BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED = 'true'
$AcceptanceRun = [guid]::NewGuid().ToString()
$env:BOTKERNEL_AGENT_CHECKPOINTS = (Join-Path $PWD ".local-bedrock-acceptance\$AcceptanceRun\checkpoints.sqlite")
python -m botkernel.bedrock_acceptance --execute-live `
  --api-url $env:BOTKERNEL_API_URL `
  --cost-resource '<isolated-cost-resource>' `
  --performance-resource '<isolated-performance-resource>' `
  --incident-id <verified-local-incident-id> `
  --output "benchmarks\results\bedrock-acceptance\$AcceptanceRun.json"
```

The checkpoint path and output path must be new; the harness refuses to reuse or overwrite them. The application and Redis counters are safeguards, not hard billing caps. If a call errors, the outcome is uncertain, usage is missing, a case fails, or the saved output reports failure, stop. Do not rerun with a new run ID. Investigate the existing SQLite `agent_reasoning`, proposal and PostgreSQL investigation report records first. The harness itself only replays the investigator request after it receives a completed response, using the exact same key.

After an approved local run, restore all inference gates and providers to disabled/deterministic defaults, retain checkpoint/report/output artifacts, and stop only the isolated project without `-v`:

```powershell
$env:BEDROCK_ENABLED = 'false'
$env:BEDROCK_SPEND_AUTHORIZED = 'false'
$env:AI_ACTION_EXECUTION_ENABLED = 'false'
$env:AGENT_PROVIDER = 'deterministic_mock'
$env:INVESTIGATOR_PROVIDER = 'deterministic_mock'
docker compose -p $Project -f compose.yaml -f compose.bedrock-acceptance.yaml --profile stability stop
```

Do not use the project name above unless it is the exact project started in the current authorized local session. Stopping is not cleanup; volumes are retained.

## Bedrock/profile and spend preflight (AWS commands, not run)

Approval requested **first** for a read-only AWS inspection session only. Stop if the profile/account differs from the owner-confirmed target, if a query is denied, or if profile/model/IAM support is ambiguous. These commands do not call `Converse` or mutate resources. The expected historical profile name is `botkernel-dev`; it has not been checked.

```powershell
$ProfileName = 'botkernel-dev'
$Region = 'us-east-2'
aws sts get-caller-identity --profile $ProfileName --region $Region --query '{Account:Account,Arn:Arn}' --output json
aws ec2 describe-instances --profile $ProfileName --region $Region --instance-ids '<owner-approved-instance-id>' --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,Type:InstanceType,Launch:LaunchTime,Profile:IamInstanceProfile.Arn,Volumes:BlockDeviceMappings[].Ebs.VolumeId}' --output json
$End = (Get-Date).ToString('yyyy-MM-dd')
$Start = (Get-Date).AddDays(-30).ToString('yyyy-MM-dd')
aws ce get-cost-and-usage --profile $ProfileName --region us-east-1 --time-period "Start=$Start,End=$End" --granularity DAILY --metrics UnblendedCost --output json
aws bedrock list-inference-profiles --profile $ProfileName --region $Region --type-equals SYSTEM_DEFINED --query 'inferenceProfileSummaries[?inferenceProfileId==`us.amazon.nova-micro-v1:0`].{Id:inferenceProfileId,Status:status,Type:type}' --output json
aws bedrock get-inference-profile --profile $ProfileName --region $Region --inference-profile-identifier us.amazon.nova-micro-v1:0 --output json
aws bedrock get-foundation-model --profile $ProfileName --region $Region --model-identifier amazon.nova-micro-v1:0 --output json
```

Before any permission decision, use the profile response to identify the exact inference-profile ARN and every destination foundation-model ARN/region. Then, only with approval and the actual owner-confirmed principal ARN:

```powershell
aws iam simulate-principal-policy --profile $ProfileName --region $Region `
  --policy-source-arn '<owner-confirmed-principal-arn>' `
  --action-names bedrock:InvokeModel `
  --resource-arns '<exact-inference-profile-arn>' '<each-required-destination-model-arn>' `
  --output json
```

For the EC2 role route, inspect the attached instance profile and role policy read-only, then simulate that exact role ARN against the same reviewed resource list. Terraform `infra/terraform/iam.tf` defaults the separate Bedrock policy off. If approved, it must be scoped to the inference profile and required destination models; do not broaden it to `Resource: "*"`. IAM simulation does not establish effective authorization through SCPs, permissions boundaries, endpoint policies or all service-specific conditions. Do not modify IAM in this phase.

The model candidate is system-defined inference profile `us.amazon.nova-micro-v1:0`, source region `us-east-2`. Its active state, regional availability, routing destinations, account entitlement and effective `bedrock:InvokeModel` permission are all **unknown**. A cross-region profile may require permission to invoke both the profile ARN and destination foundation-model ARNs. Verify this against the current profile response and AWS's current regional inference documentation before approval.

No current pricing was checked. The earlier handoff cited an Ohio Nova Micro price example of `$0.000035/1K` input and `$0.00014/1K` output tokens, but those are historical references, not a verified current quote. At those illustrative rates, a 20,000-token all-output bound would be `$0.0028`; three 512-output-token caps leave at most 18,464 estimated input tokens, about `$0.0008613` under that token split. These estimates assume the rates remain applicable and actual tokens fit the application estimate; neither is established. The proposed `$0.01` experiment ceiling is a request only, not a verified cost nor a hard AWS limit. Obtain current official regional/profile pricing and calculate a conservative estimate before requesting paid-call approval. Do not rely on an AWS Budget alert as a billing cap.

## Private EC2 integration preparation (not run)

Previously published deployment images may not contain current source. Any future deployment would need locally rebuilt backend and dashboard images, followed by separately approved immutable-tag publication and deployment. No cloud operation is authorized by this preparation.

The instance profile route avoids copying long-lived credentials into containers, but current role permissions, metadata reachability from the runtime, egress and Nova profile destinations need read-only verification. An authorized cloud acceptance must keep continuous LangGraph agent services stopped or deterministic, then run each Cost/Performance process for one cycle only; never set `AGENT_PROVIDER=bedrock` while agents run indefinitely. Keep the API, agents and investigator on mock cloud mode with `AI_ACTION_EXECUTION_ENABLED=false`. The investigator request uses the real API and a fresh key only once; any network ambiguity stops the run.

Before inference, create a complete incident through the running local controller in the isolated AWS demo only after all infrastructure/update approvals. Verify its controller transitions, resource-specific effect ledger and graph evidence. Then run one Cost cycle, one Performance cycle and one investigator API request. Capture the CloudWatch application logs, exact action/effect/receipt/outbox records, agent checkpoint provenance, investigation report/provider/model/usage and the pre/post operational-state query results. No model proposal may be admitted or mutate a resource.

Rollback preparation: before service changes, capture the current immutable image tags/digests, Compose config with secrets redacted, service health, latest PostgreSQL backup status, and checkpoint/report/artifact inventory. If any inference ambiguity or service regression occurs, set all Bedrock/spend/action gates false, restore deterministic providers, stop only the acceptance agent processes, and return to the last approved image/config. Preserve EBS, Docker volumes, PostgreSQL, Kafka, SQLite checkpoints, incidents, reports and benchmark evidence. Do not run `down -v`, delete images/data, stop/start/terminate EC2, change IAM, or perform rollback operations without their own explicit approval.

## Approval checkpoint

1. **Read-only AWS preflight approval:** identity/account, current EC2 state/instance profile, recent Cost Explorer cost, Nova inference-profile/model metadata, and exact-principal IAM simulation above. No model invocation, IAM change, image push, Terraform, EC2 change, or service operation is included.
2. **Separate paid-inference approval:** only after the read-only results and current pricing are reviewed, approve at most three intended invocations (Cost, Performance, Investigator), each at most 512 generated tokens, total application-estimated tokens at most 20,000, proposed spend ceiling `$0.01`, action execution disabled. This limit is not a hard billing cap. The profile and account access are currently unverified, so the cost estimate is not yet ready for approval.

Live acceptance is **not ready to begin** until a clean current-source local API/browser regression, isolated evidence fixtures, AWS identity/profile and price/permission preflight, safe credential route, and explicit paid-call approval are complete.

## Follow-up validation (2026-11-12)

The current-source local API image was rebuilt for the isolated browser project `botkernel-bedrock-e2e-90f2ff90`; `/ready` returned `ready`. The serial Chromium suite passed **19/19** against `http://127.0.0.1:18680`, covering desktop/mobile graph controls, incident evidence links, model/provider/usage labels, visual viewport checks, horizontal overflow, and experiment history. A first run overlapped backend test execution and had two failures (an API 503 and experiment history still loading); rerunning after backend testing completed passed without source changes.

The focused LangGraph module passed **44 tests**, and its checkpoint persistence test passed alone. The full isolated PostgreSQL/Kafka suite was not green in this continuation: two normal-order attempts each produced **138 passed, 10 failed**, all in `test_lang_agents.py` at observer resource lookup (`StopIteration`); explicitly setting `BOTKERNEL_AGENT_RESOURCE=service-a` did not resolve it. Reordering the full suite produced **144 passed, 4 failed** in core tests due to resource reservation/quota assumptions. The full suite therefore exhibits order-sensitive shared test state and must be fixed and rerun twice before claiming current complete-backend acceptance. The earlier November 11 full-suite result is historical and does not override these failures.

The focused three-case mocked acceptance harness had previously passed **10 tests**; these prove the actual integration paths with mocked inference, not live model behavior. In the current full-suite attempts, the acceptance tests were among the passing tests.

No AWS identity, EC2, billing, IAM, Bedrock, or pricing check was run. No live inference, cloud change, or persistent-data cleanup occurred. The candidate profile and proposed 3-call / 512-output-token / 20,000-estimated-token / $0.01 experiment bounds remain unverified application limits, not AWS billing caps. Current AWS state, permissions, cross-region destinations, credential route, and pricing are **UNKNOWN**. Do not execute the listed read-only preflight or any inference until the corresponding separate authorization is given. Keep all inference, cloud-deployment, and AI-action gates disabled.

## Final bounded local validation

The Cost/Performance acceptance runner now restores `BOTKERNEL_AGENT_RESOURCE` after each invocation; the focused harness and downstream graph regression passed **11 tests**. An earlier full-suite attempt reported **132 passed, 15 failed** before the final harness fix. After that fix, the complete isolated PostgreSQL/Kafka suite passed twice (**148 passed** each run, one LangGraph deprecation warning). Those full runs were before the final experiment-history performance correction.

The experiment history endpoint now reads a compact `history.json` for new runs and reconstructs legacy history from `report.md` and `summary.csv`, avoiding large `raw.json` tick payloads. Its focused evaluation tests passed **12/12**. A fresh API image was ready; its 20-run history request took 4.19 seconds. The latest full dashboard suite before that correction was **18/19**, failing only the experiment visual wait. After setting that single content wait to 15 seconds, the targeted desktop/laptop/mobile Chromium visual test passed **1/1**. The full backend and browser suites were not rerun after the history change.

No AWS identity, EC2, billing, IAM, Bedrock, or pricing query was made. No live inference, cloud change, or data/volume cleanup occurred. AWS state and permissions remain **UNKNOWN**. The approval checkpoints and all disabled cloud, spend and AI-action gates above remain unchanged.
