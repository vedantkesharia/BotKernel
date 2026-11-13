# Bedrock acceptance

## Bounded live attempt (2026-11-12)

The approved operator profile was verified against the intended project account in `us-east-2`. The `us.amazon.nova-micro-v1:0` inference profile and backing model were ACTIVE; current Ohio rates were checked at $0.000035/1,000 input and $0.00014/1,000 output tokens. IAM simulation allowed the operator profile and relevant destination models, but the EC2 role did not have Bedrock permission; no IAM changes were made. Simulation is not proof of effective authorization.

The existing harness was invoked once against isolated, real PostgreSQL/Kafka fixtures using transient operator credentials. The Cost case reserved 1,812 application-estimated tokens, then recorded `FAILED_OR_OUTCOME_UNKNOWN` / `bedrock_client_error`. No Converse response, model usage or precise underlying AWS error was captured; whether AWS received or charged the request is unknown. The harness stopped before Performance and Investigator, and no retry was made. This is **not** successful live inference. Preserve the existing reservation and evidence; a further paid experiment requires fresh authorization and must not automatically retry the ambiguous request.

The intended bounds were at most three calls, one SDK attempt per case, 512 output tokens per call, 20,000 application-estimated total tokens and a proposed $0.01 budget. Redis and application limits are not AWS billing caps. AI-driven action execution remained disabled. The deployed API's Bedrock, spending and action gates are disabled; the private EC2 instance was stopped after a separate deterministic demo.

## Offline diagnosis and next-call proposal

The original temporary SDK archive contained Boto3/Botocore but omitted the `python-dateutil` dependency, which was also absent from the target container. An offline reconstruction of that archive and environment, with network transport blocked, reproduced `ModuleNotFoundError: dateutil`; the old provider masked its initialization error as `bedrock_client_error`. Do not reuse the incomplete archive helper. This is a strong client-side explanation, not proof of the original exception: no exception was preserved, so the historical request and any charge remain unknown. The archived Botocore supported Converse; the original process used frozen credentials from the verified host identity and the intended region/profile ID. Effective IAM/model access, DNS/TLS and remote behavior were not proven by this reconstruction.

The provider now preserves the client initialization category and emits allowlisted diagnostics without request content or credentials; ambiguous Converse failures remain unknown. The investigator acceptance HTTP deadline also accommodates the bounded worker deadline and termination grace. Current offline tests use the configured Nova Micro profile and mocked Botocore responses; they do not prove live model output or account access. The deployed EC2 image predates these diagnostic changes.

For a separately authorized **new** experiment, use a complete compatible Boto3/Botocore installation with all dependencies, including a credential provider compatible with the selected login method. Keep Nova Micro as the first candidate; Nova Lite and Nova 2 Lite account access, permissions, pricing and contract compliance have not been verified, and changing models does not address the SDK defect. Recheck identity, effective permissions, pricing and network readiness. Preserve the earlier 1,812-token reservation and all evidence; account for its daily call and token limits without clearing counters or reusing its idempotency key. A remaining daily allowance may be insufficient for three calls.

The exact proposed runner command and gates are the `--execute-live` block below, with fresh fixtures, checkpoint and output paths; **do not execute without explicit new paid-inference authorization**. It permits at most three intended calls, one per workflow, 512 output tokens each, 20,000 estimated tokens per day and no automatic retries or model-driven actions. At the historical rates above, 20,000 all-output tokens estimate $0.0028; a three-call split with 1,536 output and 18,464 estimated input tokens estimates $0.0008613. The proposed $0.01 ceiling is not an AWS billing cap, actual usage may differ, and rates must be rechecked.

The host runner and a supervised child independently resolved the `botkernel-dev` login provider, refreshed credentials, constructed the regional Bedrock client and matched the previously verified account through read-only STS. Python 3.12.10, Boto3/Botocore 1.44.2, python-dateutil 2.9.0.post0 and awscrt 0.38.0 were verified in a complete isolated host environment. A real host HTTP API and its supervised Investigator worker then completed all three workflows against mocked Converse responses with AWS HTTP transport blocked; each process independently resolved and checked unexpired login credentials. The offline test suppressed SDK credential refresh after the separate refresh check to guarantee no AWS endpoint was contacted during those workflows. Mock token usage is not live usage. The API and worker used the same isolated Redis budget, persisted the reasoning and report, and made no model-driven actions.

The tested Windows virtual-environment launcher introduced an intermediate parent process, causing the Investigator's parent guard to fail. Launching the API with the actual base Python executable and the trusted virtual environment's site-packages on `PYTHONPATH` preserved the direct parent/child relationship and existing supervisor. Do not bypass the guard or Job Object. The existing Kafka broker advertises a Docker-only hostname and caused host `/ready` to return 503. A subsequent offline run with a separate loopback Kafka broker returned `/ready` 200 and passed all three mocked workflows. Its test-only Redis and Kafka containers were stopped afterward; fixture effects were committed directly through the simulator, not through Kafka. A running host-reachable Kafka listener and an actual `/ready` 200 remain prerequisites for live acceptance.

The historical Redis DB 15 currently contains **one call and 1,812 reserved tokens** for 2026-11-12 UTC. With a three-call daily cap, only two calls remain. The acceptance runner now reads that shared daily counter and refuses to start unless all three call slots and at least three output-token allocations remain; it never clears the counter. This preflight is not a reservation: concurrent users can still consume the allowance later, and per-call atomic reservations remain authoritative. Before any authorized run, verify the host API and runner use the same original Redis server and DB 15; a fresh Redis server or database would incorrectly omit the historical reservation. Do not reset counters or use a new store to bypass the limit. The current experiment is blocked until a sufficient legitimate allowance and healthy Kafka are available; recheck credentials, effective authorization, network and prices at that time.

The remaining sections describe historical preparation and offline validation. Their earlier statements about unknown cloud state or approval describe those earlier sessions, not the attempt above. Examples are not authorization for new cloud changes or inference.

## Existing integration and remaining acceptance gap

`botkernel.bedrock.BedrockConverse` already makes one bounded Converse request, validates strict Pydantic response schemas, records the provider/model and returned token usage, reserves the shared Redis budget before a request, and fails closed if that reservation is unavailable. It configures one SDK attempt. It does not silently select deterministic reasoning after a Bedrock error.

The Cost and Performance StateGraphs use actual `/telemetry`, validate role direction/capacity/evidence and persist decision provenance in their role checkpoint SQLite database. With `AI_ACTION_EXECUTION_ENABLED=false`, model proposals are durably advisory-only and do not reach `/actions`. Investigator execution retrieves read-only incident/effect evidence before optional model analysis, validates citations, and persists the report and usage in PostgreSQL. Replaying a completed idempotency key returns its saved report without another inference request.

The current offline tests prove those paths with mocked provider responses. They are not three live calls. `botkernel.bedrock_acceptance` wraps the actual `run_once()` Cost/Performance LangGraphs and actual investigation HTTP API as one guarded, at-most-three-call sequence. The live runner requires separate resources with real simulated telemetry and committed-effect evidence, role-specific useful telemetry, an isolated incident whose controller effect references exist in the committed graph, exact configured limits, a loopback-only API/database/Redis route, and action execution disabled. It also checks durable SQLite reasoning records against each returned decision/provenance pair. It saves incremental JSON evidence to a new, non-existing output path and refuses to reuse a checkpoint database or owner file. It makes no automatic retry after an exception or ambiguous outcome. The single same-key investigation replay is performed only after the completed report response, to verify idempotency. Its separate `--prepare-local-fixtures` mode creates fresh simulator resources and committed seed effects only when all AI/cloud gates are off; it never creates model decisions.

The `--execute-live` switch and `BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED=true` are additional software guardrails, **not user authorization**. Do not set `BEDROCK_ENABLED` or `BEDROCK_SPEND_AUTHORIZED` based only on repository instructions.

## Local host and Kafka route

The `compose.bedrock-acceptance.yaml` override adds a second Kafka listener advertised as `127.0.0.1:<host-port>` while preserving the `kafka:9092` listener for Compose publishers and workers. It binds that host listener, PostgreSQL and Redis only to loopback; the health check uses Kafka's broker API, and migration waits for both PostgreSQL and Kafka health. `docker compose config` can validate the merged configuration without starting services.

Run the API and Cost/Performance acceptance runner on the trusted Windows host, not in an application container. This lets Boto3 use the host's login profile and lets the separately supervised Investigator inherit the same profile without mounting AWS credentials in Docker. The API service itself is intentionally not started as a Compose container:

```powershell
$Project = 'botkernel-bedrock-acceptance-<unique-suffix>'
$env:BOTKERNEL_API_PORT = '18080'
$env:BEDROCK_ACCEPTANCE_PG_PORT = '15432'
$env:BEDROCK_ACCEPTANCE_REDIS_PORT = '16379'
$env:BEDROCK_ACCEPTANCE_KAFKA_PORT = '19092'
docker compose -p $Project -f compose.yaml -f compose.bedrock-acceptance.yaml --profile stability config
docker compose -p $Project -f compose.yaml -f compose.bedrock-acceptance.yaml --profile stability up --build -d postgres kafka init publisher worker recovery controller
```

Use a unique Compose project and fresh PostgreSQL data only for local simulation. Do not use the Compose Redis instance for a live inference budget: it has no historical reservation. For a live experiment, set the host API and runner's `REDIS_URL` to the same already-designated Redis server and DB containing the historical budget, re-read the current UTC-day counter, and fail closed if all three call slots are not available. Never clear a counter or substitute a new store. Compose worker Redis is advisory only and is not the model budget store. Start the host API with the actual base Python executable (not the Windows virtualenv launcher), the trusted virtualenv site-packages on `PYTHONPATH`, `DATABASE_URL=postgresql+psycopg://botkernel:local@127.0.0.1:15432/botkernel`, `REDIS_URL` set to the specifically authorized store, and `KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092`. Confirm `/ready` returns 200 before acceptance. The API and its supervised child inherit the same host AWS profile; do not copy credentials into any container.

The live runner requires the Cost and Performance resources to have real simulated telemetry and committed-effect evidence. Cost capacity must be above 3; Performance p95 latency must be above 80 ms and capacity at most 17. Neither can have pending actions or a controller hold. It also requires a distinct incident with committed controller-effect evidence in the one-hour graph window. Prepare these through the regular gateway/outbox/Kafka/worker/controller path with all AI gates disabled. Never alter an existing cloud incident. Resource and incident IDs must be explicit inputs; the acceptance runner does not fabricate model decisions or fixtures.

For offline deterministic setup only, start the host API with every AI gate off. Use the actual base Python executable (not the Windows virtualenv launcher), and expose the trusted virtualenv packages without copying credentials into containers:

```powershell
$VenvPython = Join-Path $PWD '.venv-bedrock\Scripts\python.exe'
$BasePython = & $VenvPython -c "import sys; from pathlib import Path; print(Path(sys.base_prefix) / 'python3.12.exe')"
$env:PYTHONPATH = "$PWD;$PWD\.venv-bedrock\Lib\site-packages"
$env:PYTHONNOUSERSITE = '1'
$env:DATABASE_URL = 'postgresql+psycopg://botkernel:local@127.0.0.1:15432/botkernel'
$env:REDIS_URL = 'redis://127.0.0.1:16379'
$env:KAFKA_BOOTSTRAP_SERVERS = '127.0.0.1:19092'
$env:BOTKERNEL_API_URL = 'http://127.0.0.1:18080'
$env:CLOUD_MODE = 'mock'
$env:AWS_DEPLOY_ALLOWED = 'false'
$env:AI_ACTION_EXECUTION_ENABLED = 'false'
$env:BEDROCK_ENABLED = 'false'
$env:BEDROCK_SPEND_AUTHORIZED = 'false'
$env:AGENT_PROVIDER = 'deterministic_mock'
$env:INVESTIGATOR_PROVIDER = 'deterministic_mock'
$env:BOTKERNEL_OPERATOR_TOKEN = (Get-Content '<private-operator-token-file>' -Raw).Trim()
$env:BOTKERNEL_AGENT_TOKEN = (Get-Content '<private-agent-token-file>' -Raw).Trim()
$ApiProc = Start-Process -FilePath $BasePython -ArgumentList @('-m','uvicorn','botkernel.api:app','--host','127.0.0.1','--port','18080') -PassThru -NoNewWindow
```

Wait for `http://127.0.0.1:18080/ready` to return 200. The fixture mode refuses non-loopback API/database/Redis endpoints, verifies the API reports mock cloud/no infrastructure remediation, creates two fresh resources, then submits one low-risk seed action per resource through the real API and waits for one outbox, receipt and committed effect each. It never invokes a model. The isolated Compose Redis in this example is for offline setup only:

```powershell
$env:BOTKERNEL_API_URL = 'http://127.0.0.1:18080'
$env:KAFKA_BOOTSTRAP_SERVERS = '127.0.0.1:19092'
$FixtureRun = [guid]::NewGuid().ToString()
python -m botkernel.bedrock_acceptance --prepare-local-fixtures `
  --api-url $env:BOTKERNEL_API_URL `
  --output "benchmarks\results\bedrock-acceptance\fixtures-$FixtureRun.json"
$env:DEMO_RESOURCE = 'service-b'
python -m botkernel.live_demo
```

Set the operator/agent variables from private files only within the trusted local shell. The host-run demo exercises local PostgreSQL admission/outbox, Kafka, worker receipts and controller lifecycle without inference. Record the fixture and incident IDs, then stop only the API process started above and the isolated Compose project without `-v`. Before any separately approved inference, configure the host API and runner to use the exact pre-existing model-budget store; the fresh offline Redis is never eligible for live inference.

For a verified host profile, set `BEDROCK_PROFILE=botkernel-dev` only in the separately authorized host acceptance process; Boto3 uses that profile independently in both the host process and supervised child. If an owner-approved credential chain is used instead, leave the profile unset. This procedure does not mount credentials in Compose or persist them in images, environment files, logs or acceptance output.

## Proposed host command, not authorized

Once the Kafka and budget blockers are resolved, use an isolated virtual environment with the optional login dependencies. This installation and the command below are local; no AWS credentials are copied into an image or tracked file.

```powershell
python -m venv .venv-bedrock
$VenvPython = Join-Path $PWD '.venv-bedrock\Scripts\python.exe'
& $VenvPython -m pip install '.[aws-login]'
$BasePython = & $VenvPython -c "import sys; from pathlib import Path; print(Path(sys.base_prefix) / 'python3.12.exe')"
$env:PYTHONPATH = "$PWD;$PWD\.venv-bedrock\Lib\site-packages"
$env:PYTHONNOUSERSITE = '1'
```

In the same private PowerShell process, configure loopback `DATABASE_URL`, the **existing** budget store `REDIS_URL` (DB 15), a host-reachable `KAFKA_BOOTSTRAP_SERVERS`, `BOTKERNEL_API_URL`, and private operator and agent tokens. Prepare fresh Cost/Performance resources and a distinct incident with the gates disabled through the regular gateway/outbox/Kafka/worker/controller path. Verify all processes use the same database and budget store, the login profile is unexpired and matches the expected account, the exact profile/model and permissions remain valid, and fresh pricing is acceptable. The run must not be started unless the actual API `/ready` returns 200. No new approval is conveyed by these instructions.

Only after explicit approval of the new paid experiment, set the reviewed gates before starting the host API, then run once with fresh resource IDs and a fresh output filename. The two role cycles run locally in the host process; they do not start continuous agent containers. The API's cloud and AI-action gates remain mock/false. A model may correctly choose `NO_OP`; this is an accepted decision if provenance and evidence validate.

```powershell
$env:CLOUD_MODE = 'mock'
$env:AWS_DEPLOY_ALLOWED = 'false'
$env:AI_ACTION_EXECUTION_ENABLED = 'false'
$env:BEDROCK_ENABLED = 'true'
$env:BEDROCK_SPEND_AUTHORIZED = 'true'
$env:AGENT_PROVIDER = 'bedrock'
$env:INVESTIGATOR_PROVIDER = 'bedrock'
$env:BEDROCK_PROFILE = 'botkernel-dev'
$env:BEDROCK_MODEL_ID = 'us.amazon.nova-micro-v1:0'
$env:BEDROCK_REGION = 'us-east-2'
$env:BEDROCK_MAX_OUTPUT_TOKENS = '512'
$env:BEDROCK_MAX_CALLS_PER_RUN = '1'
$env:BEDROCK_MAX_CALLS_PER_DAY = '3'
$env:MAX_BEDROCK_TOKENS_PER_DAY = '20000'
$env:BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED = 'true'
$env:BOTKERNEL_API_URL = 'http://127.0.0.1:18080'
$AcceptanceRun = [guid]::NewGuid().ToString()
$env:BOTKERNEL_AGENT_CHECKPOINTS = (Join-Path $PWD ".local-bedrock-acceptance\$AcceptanceRun\checkpoints.sqlite")
$ApiProc = Start-Process -FilePath $BasePython -ArgumentList @('-m','uvicorn','botkernel.api:app','--host','127.0.0.1','--port','18080') -PassThru -NoNewWindow
try {
  $ready = $false
  $deadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $deadline) {
    if ($ApiProc.HasExited) { throw 'Host API exited before readiness' }
    try {
      $response = Invoke-RestMethod -Uri "$env:BOTKERNEL_API_URL/ready" -TimeoutSec 3 -ErrorAction Stop
      if ($response.status -eq 'ready') { $ready = $true; break }
    } catch { Start-Sleep -Seconds 1 }
  }
  if (-not $ready) { throw 'Host API did not become ready; no inference attempted' }
  & $BasePython -m botkernel.bedrock_acceptance --execute-live `
    --api-url $env:BOTKERNEL_API_URL `
    --cost-resource '<isolated-cost-resource>' `
    --performance-resource '<isolated-performance-resource>' `
    --incident-id <verified-local-incident-id> `
    --output "benchmarks\results\bedrock-acceptance\$AcceptanceRun.json"
} finally {
  if (Get-Process -Id $ApiProc.Id -ErrorAction SilentlyContinue) { Stop-Process -Id $ApiProc.Id }
  $env:BEDROCK_ENABLED = 'false'
  $env:BEDROCK_SPEND_AUTHORIZED = 'false'
  $env:AI_ACTION_EXECUTION_ENABLED = 'false'
  $env:AGENT_PROVIDER = 'deterministic_mock'
  $env:INVESTIGATOR_PROVIDER = 'deterministic_mock'
}
```

The checkpoint path and output path must be new; the harness refuses to reuse or overwrite them. The application and Redis counters are safeguards, not hard billing caps. If a call errors, the outcome is uncertain, usage is missing, a case fails, or the saved output reports failure, stop. Do not rerun with a new run ID. Investigate the existing SQLite `agent_reasoning`, proposal and PostgreSQL investigation report records first. The harness itself only replays the investigator request after it receives a completed response, using the exact same key.

The `finally` block stops only the API process it started and disables this shell's inference gates. Retain all checkpoints and output. Stop separately owned local services only after confirming their identity and lack of other users; never delete volumes.

## Historical Bedrock/profile and spend preflight reference

Before a future authorized experiment, recheck the owner-confirmed account, profile, model, permissions and pricing. Stop if the target differs, a query is denied, or support is ambiguous. These commands do not call `Converse` or mutate resources.

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

The model candidate is system-defined inference profile `us.amazon.nova-micro-v1:0`, source region `us-east-2`. The 2026-11-12 profile and model checks and operator IAM simulation are described above; effective authorization and the ambiguous Cost error remain unresolved. A cross-region profile may require permission to invoke both the profile ARN and destination foundation-model ARNs.

At the 2026-11-12 checked rates, a 20,000-token all-output bound would be `$0.0028`; three 512-output-token caps leave at most 18,464 estimated input tokens, about `$0.0008613` under that token split. These estimates assume those rates apply and actual tokens fit the application estimate. The proposed `$0.01` experiment ceiling is not a verified cost or a hard AWS limit. Recheck pricing for future approval; an AWS Budget alert is not a billing cap.

## Historical private EC2 integration preparation

Previously published deployment images may not contain current source. Any future deployment would need locally rebuilt backend and dashboard images, followed by separately approved immutable-tag publication and deployment. No cloud operation is authorized by this preparation.

The instance profile route avoids copying long-lived credentials into containers, but current role permissions, metadata reachability from the runtime, egress and Nova profile destinations need read-only verification. An authorized cloud acceptance must keep continuous LangGraph agent services stopped or deterministic, then run each Cost/Performance process for one cycle only; never set `AGENT_PROVIDER=bedrock` while agents run indefinitely. Keep the API, agents and investigator on mock cloud mode with `AI_ACTION_EXECUTION_ENABLED=false`. The investigator request uses the real API and a fresh key only once; any network ambiguity stops the run.

Before inference, create a complete incident through the running local controller in the isolated AWS demo only after all infrastructure/update approvals. Verify its controller transitions, resource-specific effect ledger and graph evidence. Then run one Cost cycle, one Performance cycle and one investigator API request. Capture the CloudWatch application logs, exact action/effect/receipt/outbox records, agent checkpoint provenance, investigation report/provider/model/usage and the pre/post operational-state query results. No model proposal may be admitted or mutate a resource.

Rollback preparation: before service changes, capture the current immutable image tags/digests, Compose config with secrets redacted, service health, latest PostgreSQL backup status, and checkpoint/report/artifact inventory. If any inference ambiguity or service regression occurs, set all Bedrock/spend/action gates false, restore deterministic providers, stop only the acceptance agent processes, and return to the last approved image/config. Preserve EBS, Docker volumes, PostgreSQL, Kafka, SQLite checkpoints, incidents, reports and benchmark evidence. Do not run `down -v`, delete images/data, stop/start/terminate EC2, change IAM, or perform rollback operations without their own explicit approval.

## Approval checkpoints for any future acceptance

1. **Read-only AWS preflight approval:** identity/account, current EC2 state/instance profile, recent Cost Explorer cost, Nova inference-profile/model metadata, and exact-principal IAM simulation above. No model invocation, IAM change, image push, Terraform, EC2 change, or service operation is included.
2. **Separate paid-inference approval:** only after the read-only results and current pricing are reviewed, explicitly approve any future bounded experiment with action execution disabled. The earlier approval does not authorize retries or additional calls. Application limits are not a hard billing cap.

Do not treat unrelated full-suite or browser resource limitations as a reason to require another full stack before a separately approved, safely isolated bounded test.

## Follow-up validation (2026-11-12)

The current-source local API image was rebuilt for the isolated browser project `botkernel-bedrock-e2e-90f2ff90`; `/ready` returned `ready`. The serial Chromium suite passed **19/19** against `http://127.0.0.1:18680`, covering desktop/mobile graph controls, incident evidence links, model/provider/usage labels, visual viewport checks, horizontal overflow, and experiment history. A first run overlapped backend test execution and had two failures (an API 503 and experiment history still loading); rerunning after backend testing completed passed without source changes.

The focused LangGraph module passed **44 tests**, and its checkpoint persistence test passed alone. The full isolated PostgreSQL/Kafka suite was not green in this continuation: two normal-order attempts each produced **138 passed, 10 failed**, all in `test_lang_agents.py` at observer resource lookup (`StopIteration`); explicitly setting `BOTKERNEL_AGENT_RESOURCE=service-a` did not resolve it. Reordering the full suite produced **144 passed, 4 failed** in core tests due to resource reservation/quota assumptions. The full suite therefore exhibits order-sensitive shared test state and must be fixed and rerun twice before claiming current complete-backend acceptance. The earlier November 11 full-suite result is historical and does not override these failures.

The focused three-case mocked acceptance harness had previously passed **10 tests**; these prove the actual integration paths with mocked inference, not live model behavior. In the current full-suite attempts, the acceptance tests were among the passing tests.

At the time of this earlier validation, no AWS or live inference checks had been run; see the 2026-11-12 bounded-attempt status above for the later results. The application limits are not AWS billing caps.

## Final bounded local validation

The Cost/Performance acceptance runner now restores `BOTKERNEL_AGENT_RESOURCE` after each invocation; the focused harness and downstream graph regression passed **11 tests**. An earlier full-suite attempt reported **132 passed, 15 failed** before the final harness fix. After that fix, the complete isolated PostgreSQL/Kafka suite passed twice (**148 passed** each run, one LangGraph deprecation warning). Those full runs were before the final experiment-history performance correction.

The experiment history endpoint now reads a compact `history.json` for new runs and reconstructs legacy history from `report.md` and `summary.csv`, avoiding large `raw.json` tick payloads. Its focused evaluation tests passed **12/12**. A fresh API image was ready; its 20-run history request took 4.19 seconds. The latest full dashboard suite before that correction was **18/19**, failing only the experiment visual wait. After setting that single content wait to 15 seconds, the targeted desktop/laptop/mobile Chromium visual test passed **1/1**. The full backend and browser suites were not rerun after the history change.

At the time of this earlier local validation, no AWS or live inference checks had been run; see the bounded-attempt status above for the later results.
