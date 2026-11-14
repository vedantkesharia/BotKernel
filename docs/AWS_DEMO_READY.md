# AWS demo readiness — 2026-11-13

This is a readiness record, not a live-deployment certificate. Latest read-only discovery after owner login verified the intended account and the existing EC2 instance STOPPED. No AWS mutation or inference was performed. Historical deployment evidence is in IMPLEMENTATION_WALKTHROUGH.md and the private handoff. Existing frontend edits were preserved.

## Latest authorized read-only discovery after login

### Latest approved execution: IAM complete, safely stopped at fixture-quota blocker

The owner approved a NEW targeted IAM plan. Complete JSON review passed exactly two creates/no other mutations, unchanged four-ARN InvokeModel permissions and attachment to the existing runtime role. Applied ONLY `bedrock-iam-only-20261114.tfplan`, SHA256 `EA95442DF355F8C78988D49EBB85E8D74A347DB316AA5B58365B62C3078F8EA8`, with state locking. Result: 2 added, 0 changed, 0 destroyed. Policy ARN is `arn:aws:iam::<verified-account>:policy/botkernel-demo-bedrock-invoke`, policy ID `ANPA5JQBCXV25QWQDIMCI`; attachment ID is `botkernel-demo-runtime/<policy-arn>`. Read-back policy and all four resource-specific IAM simulations passed. Normal Terraform apply advanced state serial to 21. No manual state edits, EC2 replacement or association configuration changes occurred. The older broad plan remains REJECTED.

EC2 start request: **2026-11-14 01:47:00.544 UTC**; original maximum stop deadline: **05:47:00.544 UTC**. EC2 health waiter passed and SSM was Online (agent 3.3.5700.0). Official workstation plugin 1.2.896.0 is installed. Actual SSM Run Command connectivity succeeded; no browser port-forward was opened. Host has 7,779 MiB RAM, 6,885 MiB available in the initial snapshot, x86_64, 96 GiB disk free, Compose v5.6.0. This is not loaded core/monitoring headroom proof.

Quiesced API and started only the existing PostgreSQL/Redis services for backup (Kafka/API had auto-started on host boot; all agents/executors remained stopped). Created root-only `/opt/botkernel/backups/ready-20261114-01/`: PostgreSQL custom dump, checkpoint tar, and prior runtime/Compose copies. Dump archive listing passed (NOT a new restore drill). SHA256: postgres.dump `7271858f2af54e66b3ab867b3fdd2877731f63e4759d376eb1083cd10ce137b3`; checkpoints.tar `182c7b600fee6866671ea1d80f0a9e317da30b519eaa3415d56ef6708ed24b4c`.

Live DB snapshot: schema 0009, 9 SUCCEEDED actions, 9 effects, 1 report, quota **20**, allocated **13**, no nonterminal actions. ORIGINAL runtime Redis current UTC key `botkernel:bedrock-budget:20261114` was absent; no counter was created/reset and historical stores were untouched. Host runtime images match the historical freeze digests above, and inference/action flags were false.

BLOCKER: only **7 quota units** are available. The reviewed three capacity-4 fixture definitions plus positive seed headroom require 13. Per owner instructions, no quota/config workaround or fixture creation was attempted. Stopped every deployment container, confirmed `docker ps` empty and all inference/action flags false, then stopped the same EC2 instance. **STOPPED VERIFIED 2026-11-14 01:52:01.339 UTC**, with retained EBS attached/delete-on-termination=false. Approximate start-request-to-stop-verification compute+IPv4 arithmetic is $0.0084; actual billing and variable charges remain unknown. Four-hour limit was met comfortably.

No new images were built/pushed/deployed; no credentials rotated; no fixture action/incident/report, model call, monitoring profile or final recording scenario was executed. All cloud browser URLs remain unavailable because EC2 is stopped. Local test suites were not repeated. Model call count remains ZERO. Live acceptance is incomplete.

### Proposed smaller fixtures — requires owner approval before execution

Without changing the quota or any existing resource, initialize new Cost/Performance/incident resources at **1/2/1** (four units total), under the same quota lock and no-pending-work gate. Proposed six gateway actions: Cost **1 -> 4** (+3); Performance **2 -> 1** (-1); incident **1 -> 2 -> 1 -> 2 -> 1**, alternating Performance/Cost fixture actors. Maximum extra allocation including initial definitions is seven units: total allocation never exceeds 20. Cost ends at 4 with downscale headroom; Performance ends at 1 with fixed-simulator workload 6 and a genuine modeled latency signal. The separate incident still has four committed nonzero effects, two actors and three reversals for normal controller detection. No direct effect/incident inserts, threshold/quota changes, final recurrence run or paid-action execution.

This design is documented only, NOT executed. Ask owner to approve the lower-footprint fixture definitions and resuming within the remaining original 05:47 UTC operating window; do not assume an extension or restart automatically. Revalidate quota/health on resume and stop if the bound no longer holds. IAM is already complete; do not reapply either old plan. The separate EC2 public-IP drift remains unresolved and must not be fixed as part of readiness.

### Approved operation paused at pre-start gate

The owner approved the bounded operation, with an explicit stop for any unexpected Terraform diff. The official Amazon-signed SSM plugin was installed and verified as 1.2.896.0 before EC2 startup. However, saved plan `infra/terraform/bedrock-ready-20261114.tfplan` proposes THREE creates and ONE destroy: the two intended IAM creates PLUS EC2 replacement. JSON review identifies only `associate_public_ip_address` as the replacement trigger (refreshed false versus configured true). The instance is stopped with no current public IPv4; its subnet still has MapPublicIpOnLaunch=true. Whether this is stopped-instance/provider refresh behavior or durable configuration drift is not established. Do not apply this plan or modify the instance to satisfy it.

Rejected plan SHA-256: `0365440EEB74AB2A4C6181A66341AAD776ACBCE23384166E7A83E3D498A6BB9A`. Terraform state serial remains 18. EC2 was rechecked STOPPED. No IAM change, image build/push, cloud container start, fixture action or Bedrock request occurred. The four-hour compute window has NOT started. Existing retained-resource charges continue independently.

The proposed next decision is owner approval to generate a NEW IAM-only targeted saved plan for `aws_iam_policy.bedrock_invoke` and `aws_iam_role_policy_attachment.bedrock_invoke`, with unchanged reviewed four-ARN permissions and existing inputs. Apply only if its reviewed JSON contains exactly those two creates, zero changes and zero destroys; reject all other diffs. This would leave the unrelated EC2 association configuration/state untouched. No targeted plan has been run yet; the original broad approval does not override the explicit unexpected-diff stop condition.

- EC2 `i-0b30b3106988f698e`: stopped, m7i-flex.large, us-east-2a, AL2023 AMI `ami-03081c3f9c48b414e`. Encrypted 100-GiB gp3 `vol-01bd47406f4f88f00`, 3,000 IOPS/125 MiB/s, retained on termination. IMDSv2 required, hop limit 2. Security group `sg-0f4047472ed74b0db` has zero ingress and HTTPS-only egress. Existing subnet routes outbound through the existing internet gateway.
- SSM has no managed-node record while stopped. Plugin is not on the workstation PATH. The runtime role has AmazonSSMManagedInstanceCore plus scoped ECR-pull/CloudWatch-write permissions. Real EC2 start/stop DryRun checks both returned DryRunOperation (authorized, NOT executed).
- Initial IAM simulation without `aws:RequestedRegion` returned Organizations denies. Repeating with the actual us-east-2 request context returned ALLOWED for operator StartSession, ECR authentication/push and IAM policy creation/attachment. This is not a verified session. The account is an Organizations member; parent/SCP inspection was denied. Do not treat the earlier context-free simulations as established effective denials or bypass restrictions.
- Nova Micro profile is ACTIVE, and model agreement/entitlement/authorization/region availability are AVAILABLE/AUTHORIZED. Destinations are us-east-1/us-east-2/us-west-2. Runtime `bedrock:InvokeModel` is currently implicitly denied. Supplying the proposed policy to simulation, without attaching it, allows the profile and all three foundation-model ARNs in the Ohio context. Actual runtime inference is still unverified.
- Both ECR repositories are private, encrypted AES256, immutable tags, scan-on-push. Latest recorded release is `freeze-70f62eb-d80809e5`: backend `sha256:48bebad6e6a80042a68b83f012b5592433bf184797cce9e54ed723c00c9b0df8`, dashboard `sha256:e494d59f19255fe768baa82791e0751620c1782897a8947d2da6d573bb26f784`. Those match the historical deployment record. They predate the current SDK diagnostics/acceptance/configuration fixes. Exact files currently staged on the stopped host cannot be read through SSM yet; inspect before overwriting or deploying.
- `/botkernel/demo` exists, retains logs 30 days and reports 3,604,161 stored bytes. Latest stream events are historical November 12 events; no current log delivery is claimed.
- Local Terraform state serial 18 tracks 15 managed resources. No refresh/plan/apply or state edit was performed. No current terraform.tfvars exists; reconstruct nonsecret plan inputs from verified instance/account data and existing definitions after approval, not by changing state.
- Pricing API (us-east-1 pricing endpoint, products filtered to Ohio): EC2 $0.09576/hour; gp3 $0.08/GB-month; IPv4 $0.005/hour. Nova Micro On-demand input $0.000035/1K tokens and output $0.00014/1K tokens. The output product description misleadingly says input; its inferenceType and output usage product identify it as output. No billing/credit balance was queried or assumed.

## Consolidated proposed approval scope — still NOT authorized

Use the existing instance, networks, retained storage, role, ECR repositories and log group only. Build/push exactly two linux/amd64 images with fresh immutable tag `ready-20261114-01`, record their registry digests, and deploy by digest. Do not replace or delete either historical release. Preserve the pre-existing unstaged frontend work in the release; do not commit it.

IAM: use existing Terraform `enable_bedrock_invoke`/`bedrock_model_arns` configuration to prepare and inspect a saved plan. Authorization must expressly permit applying it ONLY if it contains exactly two creates: `aws_iam_policy.bedrock_invoke[0]` and `aws_iam_role_policy_attachment.bedrock_invoke[0]`, zero changes and zero destroys. Stop for any other diff. Attach only to botkernel-demo-runtime; Action is only bedrock:InvokeModel and resources are the verified Ohio system inference profile plus Nova Micro foundation models in us-east-1/us-east-2/us-west-2. No infrastructure-remediation permissions. The reviewed four-ARN policy was simulated from ignored `infra/deploy/nova-micro-readonly-simulation.json`; it was not applied.

Before starting the four-hour window, install/verify the official Windows SSM plugin with owner Administrator interaction. Then start the existing instance, verify SSM/role/health, back up existing PostgreSQL/checkpoints and record old host image/configuration identities. Deploy current Compose/Nginx/runtime fixes, rotate the exposed operator credential privately and align metrics secrets. Start core services with deterministic/spend/action defaults off; no unrelated restarts or volume deletion. Validate monitoring sequentially against measured headroom, without resizing. Run each independent deterministic agent at most once AFTER paid acceptance on suitable reviewed resources, at most two additional gateway actions; valid no-ops/rejections are acceptable.

For this acceptance window explicitly start ONLY `postgres redis kafka-volume-init kafka init api publisher worker recovery controller dashboard` with `docker compose --env-file runtime.env -f compose.aws-demo.yaml up -d` followed by that service list. Do not run the general start helper at this stage: it also starts both agent services. Leave agents stopped throughout paid acceptance. Restore deterministic providers and both Bedrock gates false before intentionally starting their one-cycle services afterward.

### Isolated evidence preparation, not the final recording scenario

After approval and live read-only inventory, create three uniquely named acceptance-only simulator resource definitions at capacity 4/version 0. Do this transactionally under the quota lock only if existing capacity plus pending positive reservations leaves at least 13 units of headroom; otherwise STOP without quota/threshold changes. Mirror only their initial simulator resource state; never insert action, outbox, receipt, effect or incident rows directly. Record initial definitions as fixture setup, not executed effects. Never overwrite an existing resource.

Through authenticated gateway and real publisher/Kafka/worker only, submit at most SIX logical fixture actions with fixed payloads/keys and observed versions:

| Resource | Gateway capacities in order | Purpose |
|---|---|---|
| New acceptance Cost resource | 4 -> 5 | One real committed effect; downscale headroom |
| New acceptance Performance resource | 4 -> 3 | One real committed effect; actual modeled scale-up signal |
| New acceptance incident resource | 4 -> 3 -> 5 -> 3 -> 5, alternating Cost/Performance fixture actors | Four genuine committed effects, cross-agent reversals, controller-created incident |

The first two rows each describe one action. Wait for ledger SUCCEEDED and verify one outbox/receipt/effect and one version increment per action. Stop on any unexpected rejection/uncertainty; reconcile with the SAME key, never create a replacement logical action. Let the real controller detect the isolated incident; do not insert an incident or change detector settings. Stop at initial detection; do not drive verification/recurrence, resolve incidents, or run `live_demo`. Label fixture actor identities as deterministic test actors, not autonomous model reasoning. Require no HOLD/pending work on the two role resources, validate telemetry and all graph references, and save a unique acceptance-fixture manifest.

This makes all three acceptance cases ready within the one-hour evidence window, while leaving final-recording resources/history untouched. The fixture data is retained and clearly labeled acceptance-only. Run the existing three-case harness once from EC2 using its role; at most three intended Converse calls, one attempt each, max 512 output tokens/call, 20,000 application-estimated daily tokens in the ORIGINAL runtime Redis store, no fallback, no action execution. Read current UTC counters first; never reset or switch stores. At the verified rates, 18,464 input plus 1,536 output tokens cost ~$0.0008613; the requested $0.01 target allows uncertainty and is not a billing cap. Stop on the first failed/ambiguous case. No repeated paid attempt is included in this approval.

Operate for at most FOUR HOURS FROM START, or stop earlier on completion/failure. Compute is $0.38304, IPv4 ~$0.02; retained gp3 accrues ~$0.04444 over four hours using a 720-hour month. Known subtotal ~$0.4475 plus ECR/log/transfer/tax and model charges. Incremental start-dependent compute/IPv4 subtotal ~$0.4030; EBS already accrues while stopped. Proposed planning allowance is $1 total variable operational cost for this bounded session, not a guaranteed ceiling. Stop if unforeseen services/costs are needed; no credits assumed. Disable inference gates, quiesce only this deployment, preserve volumes and evidence, stop the existing EC2 instance and wait for stopped state. No automatic stop is configured; approval must include this stop operation and the owner must know the UTC deadline.

## Executed local validation

- Focused mocked provider/acceptance: `docker compose -p bk-final-regression run --build --rm --no-deps tests pytest -q -ra tests/test_bedrock.py tests/test_bedrock_acceptance.py`: 56 passed, one LangGraph warning. This preceded the final secret-precedence regression.
- Final rebuilt source: `docker compose -p bk-final-regression run --build --rm --no-deps tests pytest -q -ra`: 199 passed, 1 skipped, 1 warning, 254.53 seconds, exit 0 including teardown. The skipped live-Prometheus test requires a Prometheus binary. A preceding full run before the last secret-precedence fix passed 198, skipped 1, in 182.30 seconds; it is not a second final-source run.
- Python compileall, installed dependency check, bash syntax checks, both Compose configurations and explicit disabled-gate/bounded-agent/private-port assertions passed.
- Terraform fmt/validate passed without plan/apply. Helm strict lint and three profile renders passed; no cluster installation. Nginx `-t` passed in an isolated local image with networking disabled.
- Frontend TypeScript/Vite build passed (existing >500-kB chunk advisory); Vitest 6 passed. AWS Playwright was not run because there is no authenticated cloud access/tunnel. No screenshots were generated in this readiness task.

No cloud resource start/stop, IAM change, image push, model call, budget reset or fresh demo was performed. Current AWS charges/credits are unknown. The only attempted account operation was STS identity discovery; it failed at proxy access in the sandbox and then at expired login outside it. Read-only discovery must resume after owner login before a concrete cloud-change approval can be finalized.

Files changed in this readiness continuation: `botkernel/bedrock_acceptance.py`, `tests/test_bedrock_acceptance.py`, `compose.aws-demo.yaml`, `infra/deploy/runtime.env.example`, `scripts/start-aws-demo.sh`, `apps/dashboard/deploy.nginx.conf`, this document, `docs/BEDROCK_ACCEPTANCE.md`, `docs/DEMO_RECORDING_GUIDE.md`, `docs/OBSERVABILITY.md`, `docs/IMPLEMENTATION_WALKTHROUGH.md`, `infra/terraform/README.md`, `infra/kubernetes/README.md`, and the ignored/private `docs/PROJECT_HANDOFF.md`. Pre-existing `OrchestrationDemo.tsx`, `landing-refinements.css` and `e2e/landing.spec.ts` edits were preserved and not changed in this task. Nothing was staged, committed or pushed.

## Immediate prerequisite

Owner login refresh and STS account match are now complete. The reference read-only commands below remain useful for rechecks; do not start EC2 until the consolidated operating approval is granted. The earlier runtime matrix describes the previous blocked discovery: latest confirmed EC2 state is stopped, so no EC2-hosted container is currently running. Browser tunnels remain unavailable/unverified.

```powershell
aws sts get-caller-identity --profile botkernel-dev --region us-east-2 --query Account --output text
aws ec2 describe-instances --profile botkernel-dev --region us-east-2 --instance-ids i-0b30b3106988f698e --query 'Reservations[].Instances[].{State:State.Name,Type:InstanceType,Launch:LaunchTime,Profile:IamInstanceProfile.Arn,Volumes:BlockDeviceMappings,Groups:SecurityGroups,Metadata:MetadataOptions}'
aws ssm describe-instance-information --profile botkernel-dev --region us-east-2
aws ecr describe-images --profile botkernel-dev --region us-east-2 --repository-name botkernel-demo-backend
aws ecr describe-images --profile botkernel-dev --region us-east-2 --repository-name botkernel-demo-dashboard
aws logs describe-log-groups --profile botkernel-dev --region us-east-2 --log-group-name-prefix /botkernel/
aws bedrock get-inference-profile --profile botkernel-dev --region us-east-2 --inference-profile-identifier us.amazon.nova-micro-v1:0
```

Use instance volume/group/profile results for `describe-volumes`, `describe-security-groups`, `get-instance-profile`, role attached/inline-policy inspection and exact-role IAM simulation. Verify no ingress, encrypted retained gp3, SSM core permissions, ECR pull/log write permissions, and narrowly scoped `bedrock:InvokeModel` on the actual inference profile AND every destination foundation-model ARN. Simulation alone does not establish SCP authorization. Do not edit Terraform state or apply IAM as a diagnostic.

## Runtime matrix

All rows below are implemented; running/verified AWS columns refer to THIS session.

| Service | Implemented | Running on AWS | Verified | Private port | Blocker |
|---|---|---|---|---|---|
| React/Nginx | Yes | Unknown | No | 8080 | Expired AWS login; image freshness unknown |
| FastAPI | Yes | Unknown | No | api:8000 | Same; auth rotation requires approved restart |
| PostgreSQL | Yes | Unknown | No | postgres:5432 | Same; preserve existing volume |
| Kafka | Yes | Unknown | No | kafka:9092 | Same; preserve existing volume |
| Redis | Yes | Unknown | No | redis:6379 | Same; preserve budgets/AOF |
| Publisher | Yes | Unknown | No | internal metrics 9100 | Same |
| Worker | Yes | Unknown | No | internal metrics 9100 | Same |
| Recovery | Yes | Unknown | No | internal metrics 9100 | Same |
| Controller | Yes | Unknown | No | internal metrics 9100 | Same |
| Cost Agent | Yes | Unknown | No | None | Bounded one-cycle process; checkpoint evidence required |
| Performance Agent | Yes | Unknown | No | None | Same |
| Investigator | Yes | API child on demand | No | API route | Supervisor/image/IAM live verification |
| Bedrock | Yes | No successful inference established | No | HTTPS outbound | Approval, IAM, budget, valid fixtures |
| Prometheus | Yes | Unknown | No | 19090 | Capacity and scrape verification |
| Grafana | Yes | Unknown | No | 13000 | Capacity and datasource verification |
| Jaeger/Collector | Yes | Unknown | No | 16686 / internal 4318 | Capacity and actual trace retrieval |
| CloudWatch | Yes | Unknown | Historical only | AWS Console | Fresh log delivery unknown |

GREEN: local static configuration where checks passed in the handoff. YELLOW: deployed application, monitoring, SSM, Helm runtime and all live model cases. RED: expired login prevents account discovery; Session Manager plugin is not on PATH; configured local Kubernetes API refuses connections.

## Approval package — not authorization

After successful identity and permission discovery, obtain ONE explicit operating approval covering the exact immutable image digests, existing instance, deployment/config and credential rotation, narrowly scoped IAM diff if needed, SSM sessions, capacity-gated monitoring, three Bedrock calls, and stopping EC2 at an agreed UTC deadline. Do not approve unknown IAM or image diffs generically.

Historical compute estimate: $0.09576/hour; four hours ~$0.383 compute plus ~$0.02 IPv4, prorated retained 100-GiB storage, ECR/logging/transfer, and proposed <=$0.01 incremental inference target. This is NOT a freshly verified quote, billing limit, or credit balance. Recheck Ohio pricing before approval. Retained EBS, ECR and logs incur charges after stopping. No automatic stop is installed. Record launch/start time and the owner-approved stop deadline.

## After approval: startup and private access

```powershell
aws ec2 start-instances --profile botkernel-dev --region us-east-2 --instance-ids i-0b30b3106988f698e
aws ec2 wait instance-status-ok --profile botkernel-dev --region us-east-2 --instance-ids i-0b30b3106988f698e
aws ssm describe-instance-information --profile botkernel-dev --region us-east-2
aws ssm start-session --profile botkernel-dev --region us-east-2 --target i-0b30b3106988f698e
```

The official Windows Session Manager installer requires Administrator rights. Download only the official installer linked by AWS: https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-windows.html . Verify its signature, install interactively, reopen PowerShell and verify `session-manager-plugin --version`. Installation does not grant `ssm:StartSession`; check effective permissions for the instance and session document, including Organizations restrictions. No public ingress workaround.

On EC2, first inspect existing `/opt/botkernel/runtime.env`, image digests and volume inventory privately. Do not print runtime.env or resolved Compose environment. Back up PostgreSQL and checkpoints before upgrade. The current local files are NOT deployed. Publishing new immutable backend/dashboard images and replacing the staged files requires the reviewed deployment approval.

```bash
cd /opt/botkernel
docker compose version
docker compose --env-file runtime.env -f compose.aws-demo.yaml ps -a
free -m
df -h /var/lib/docker
# runtime.env must retain all cloud/action/spend flags false and AGENT_MAX_RUNS=1.
BOTKERNEL_DEPLOY_APPROVED=true bash scripts/start-aws-demo.sh
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/health',timeout=5).read().decode()); print(urlopen('http://127.0.0.1:8000/ready',timeout=5).read().decode())"
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T postgres pg_isready -U botkernel -d botkernel
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T redis redis-cli ping
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T api python -m alembic current
curl -fsS http://127.0.0.1:8080/healthz
docker stats --no-stream
```

The start helper pulls images and starts services; it must not be used as a read-only health command. It now rejects unbounded agent settings. Verify both agent exit codes, independent SQLite checkpoints and authoritative outcomes; an expected no-op/rejection is not success of an action. Agents are not continuous paid-inference services.

Credential rotation, after approval, on EC2 only: generate a new operator secret without printing it and recreate only API to remount the file. Keep agent and metrics credentials distinct. Store/copy the new token only through the owner's private credential workflow, never on camera or in a command argument. Existing browser sessions will need to sign in again. Do not rotate the database password during this procedure.

```bash
sudo sh -c 'umask 077; openssl rand -hex 32 | tr -d "\n" > /etc/botkernel/secrets/operator_token.next'
sudo mv /etc/botkernel/secrets/operator_token.next /etc/botkernel/secrets/operator_token
# If the metrics file is absent, create it once without displaying it:
sudo sh -c 'test -e /etc/botkernel/secrets/metrics_token || { umask 077; openssl rand -hex 32 | tr -d "\n" > /etc/botkernel/secrets/metrics_token; }'
docker compose --env-file runtime.env -f compose.aws-demo.yaml up -d --no-deps --force-recreate api
```

Check local port availability immediately before each tunnel. Keep each session in its own terminal; do not display credentials while recording:

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 18090,13000,19090,16686 }
aws ssm start-session --profile botkernel-dev --region us-east-2 --target i-0b30b3106988f698e --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8080"],"localPortNumber":["18090"]}'
# Repeat in separate terminals, only for verified running monitoring services:
aws ssm start-session --profile botkernel-dev --region us-east-2 --target i-0b30b3106988f698e --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["13000"],"localPortNumber":["13000"]}'
aws ssm start-session --profile botkernel-dev --region us-east-2 --target i-0b30b3106988f698e --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["19090"],"localPortNumber":["19090"]}'
aws ssm start-session --profile botkernel-dev --region us-east-2 --target i-0b30b3106988f698e --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["16686"],"localPortNumber":["16686"]}'
```

UNAVAILABLE until tunnel verification: `http://127.0.0.1:18090/`, `/app`, `/app/agents`, `/app/graph`, `/app/incidents`, `/app/experiments`; Grafana `http://127.0.0.1:13000`, Prometheus `http://127.0.0.1:19090`, Jaeger `http://127.0.0.1:16686`. These are prospective access routes, not working URLs certified here. AWS Console routes: https://us-east-2.console.aws.amazon.com/ec2/home?region=us-east-2#Instances: ; https://us-east-2.console.aws.amazon.com/cloudwatch/home?region=us-east-2#logsV2:log-groups ; https://us-east-2.console.aws.amazon.com/bedrock/home?region=us-east-2 ; https://us-east-2.console.aws.amazon.com/ecr/repositories?region=us-east-2 . Console access is also unverified.

## Monitoring capacity and proof

Core configured ceilings plus 1,600 MiB optional monitoring leave little OS/startup headroom on 8 GiB. Check actual `free -m`, Docker memory/OOM/restart counts first. Start Prometheus/Grafana first only if there is adequate headroom; add Jaeger/Collector only after measuring remaining headroom. If insufficient, review a sequential demonstration; do not resize automatically.

After approval, set `BOTKERNEL_OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318` and `BOTKERNEL_TRACE_SAMPLE_RATIO=1.0` for the bounded rehearsal (default AWS sampling is 0.1). Restarting affected services needs deployment authorization. Use the same metrics secret file for API and scraper. Verify all five `/api/v1/targets` targets are up, inspect Grafana System/Execution/Collective for real samples, and retrieve an actual Jaeger trace ID linked to an action/outbox/Kafka/worker record. No-data before activity is legitimate. Jaeger uses ephemeral memory; retain sanitized trace evidence before shutdown. CloudWatch must show fresh events, not just historical streams.

```bash
docker compose --env-file runtime.env -f compose.aws-demo.yaml --profile observability up -d prometheus grafana
# Only after headroom measurement:
docker compose --env-file runtime.env -f compose.aws-demo.yaml --profile observability up -d jaeger otel-collector
curl -fsS http://127.0.0.1:19090/api/v1/targets
curl -fsS http://127.0.0.1:16686/api/services
```

## Bedrock acceptance — separately approved, never run automatically

Cost: NOT LIVE-VERIFIED. Performance: NOT LIVE-VERIFIED. Investigator: NOT LIVE-VERIFIED. The historical ambiguous Cost call and its charge remain unknown. Official model documentation supports Converse and `us.amazon.nova-micro-v1:0` from Ohio through geographic routing; strict schema enforcement is performed by BotKernel, not server-side structured-output support. Role permissions must include profile and foundation models in all destinations.

Before enabling any gate, inspect current UTC budget on the EXISTING runtime Redis database and reconcile the historical local DB15 counters separately. Never change stores or reset counters to obtain allowance. Confirm complete SDK imports including dateutil in API and its supervised child and verify role credentials without printing them. No Windows profile files in containers.

The runner requires distinct Cost/Performance simulator resources with role-appropriate telemetry and recent committed evidence, and a THIRD resource's evidence-backed incident whose cited effects appear in the one-hour graph. These are real prerequisites: historical effects may be too old. This task does NOT create a new incident or final recording dataset. Until appropriate fixtures exist, do not spend the first call. Existing `--prepare-local-fixtures` remains local-only and must not be used on AWS to fabricate the recording dataset.

For approved execution, temporarily configure the API/container environment with model/region above, both Bedrock gates true, `AGENT_PROVIDER=bedrock`, `INVESTIGATOR_PROVIDER=bedrock`, max calls/day=3, max tokens/day=20000, max output=512, max calls/run=1, and 10s timeout. Keep `CLOUD_MODE=mock`, `AWS_DEPLOY_ALLOWED=false`, `AI_ACTION_EXECUTION_ENABLED=false`. Continuous agent services must remain stopped or deterministic. Use a new checkpoint/output path; role chains need no AWS_PROFILE/BEDROCK_PROFILE. The new explicit container mode allows only api:8000, postgres and redis endpoints.

```bash
# AFTER exact paid-call/deployment approval and fixture/budget preflight:
run=$(date -u +%Y%m%dT%H%M%SZ)
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T \
  -e BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED=true \
  -e BOTKERNEL_BEDROCK_ACCEPTANCE_RUNTIME=aws-demo \
  -e BOTKERNEL_AGENT_CHECKPOINTS=/app/benchmarks/results/bedrock-$run.sqlite \
  api python -m botkernel.bedrock_acceptance --execute-live --api-url http://api:8000 \
  --cost-resource "$COST_RESOURCE" --performance-resource "$PERFORMANCE_RESOURCE" \
  --incident-id "$INCIDENT_ID" --output /app/benchmarks/results/bedrock-$run.json
```

This runner invokes the two LangGraph workflows sequentially; it is not proof of independent concurrently reasoning Bedrock processes. It validates advisory results, SQLite provenance, PostgreSQL report persistence and operational invariance. Retain JSON/checkpoints. On ANY failure/ambiguity stop, do not rerun with fresh keys. Restore gates false and deterministic providers with the separately authorized restart procedure. Pricing, actual token usage and uncertain charges must be distinguished; $0.01 is an operating target, not an AWS billing cap.

## Rehearsal, later — no fresh scenario executed here

1. Confirm approved deadline, EC2/SSM, auth rotation and Docker health. Open private browser tabs above; sign in without showing tokens.
2. Check Bedrock artifacts for all three actual successful cases. Never label mock provenance real.
3. Show bounded independent deterministic agent exits/checkpoints. Use the existing gateway ledger for action outcomes.
4. Inspect `botkernel/live_demo.py` without invoking it: it has no argument parser, so even `--help` would execute the scenario. During the later approved rehearsal only, use the command below. Select a real registered resource with safe capacity, no pending action/active hold and reviewed quota first. Do NOT use `scripts/run-live-demo.ps1` for AWS: that helper starts a new LOCAL stack.
5. Mission Control: refresh current readiness/actions. Fleet: select the actual identities and inspect decision provider/outcomes.
6. Graph: select the driver's resource and 3600-second window; inspect committed actions, reversal edges and incident highlighting. Only fresh effects will appear.
7. Investigations: select the manifest incident, inspect HOLD/VERIFIED/recurrence transitions and saved evidence. Do not resolve/release during readiness. A new report is an intentional operator action for rehearsal.
8. Grafana: use last 15 minutes and 5-second refresh; inspect actual action, effect, outbox and intervention samples. Jaeger: retrieve a matching trace; record which services/spans exist. CloudWatch: filter the same action/trace and time.
9. Experiment Lab: inspect saved comparison artifacts first. Creating a new experiment is separate virtual simulation work, not measured Kafka performance.
10. Show EC2 Docker `ps -a` and bounded logs. Show Kubernetes only after separate real runtime acceptance. Record silently with no tokens, environment files, account IDs or unrelated local stacks visible.

Exact new incident/action/report/trace IDs and click targets cannot be provided before that deliberate run. Never substitute historical IDs as fresh evidence.

```bash
# LATER REHEARSAL ONLY. Refuse to overwrite the manifest; do not rerun on ambiguity.
run=$(date -u +%Y%m%dT%H%M%SZ)
set -o noclobber
docker compose --env-file runtime.env -f compose.aws-demo.yaml exec -T \
  -e DEMO_RUN_ID="$run" -e DEMO_RESOURCE="$DEMO_RESOURCE" \
  -e DEMO_TIMEOUT_SECONDS=180 -e BOTKERNEL_API_URL=http://api:8000 \
  api python -m botkernel.live_demo > "aws-demo-$run.json"
```

## Kubernetes and shutdown

Configured context is docker-desktop; its API refused a direct connection in this session. No release was installed. Helm runtime acceptance remains pending; follow infra/kubernetes/README.md only after known-context/resource approval. Static lint/render is not live proof.

After review/approval, stop chargeable compute with `aws ec2 stop-instances --profile botkernel-dev --region us-east-2 --instance-ids i-0b30b3106988f698e`, then `aws ec2 wait instance-stopped` with the same arguments. For orderly application shutdown first use `docker compose --env-file runtime.env -f compose.aws-demo.yaml --profile observability stop` on EC2. End only your own SSM sessions. Preserve all named volumes, retained EBS, checkpoints, reports, budgets and images. Do not destroy infrastructure. Confirm stopped state explicitly; retained storage/log charges remain.

## Verified continuation — 2026-11-14

Current live forensics: deployment and private browser smoke verified, but real Bedrock acceptance FAILED at Cost response schema validation. No further model calls permitted without fresh approval. EC2 STOPPED verified 2026-11-14 05:33:39 UTC; all owned tunnels closed. Core/monitoring healthy before shutdown; 5 targets UP, gauge15, real 15-span Jaeger trace 8bafab00abf74a0da4a6273c72653d3f. All five console pages and three Grafana dashboards rendered over actual SSM tunnels. Fixture evidence is older than1h; no fresh graph-interaction claim. Full case/IDs/images/cost/rehearsal details are in the latest PROJECT_HANDOFF.md. Machine-readable evidence: infra/deploy/aws-final-runtime-proof.json and aws-browser-proof.json. Next action is an approved new runtime window after read-only state check; do not rerun Bedrock or fixtures. Monitoring startup must include compose.metrics-access.yaml, preserving token0600/directory0700. Current fixture allocation19/20 requires final-demo quota trajectory review.

## Offline readiness update — 2026-11-14
See latest BEDROCK_ACCEPTANCE.md for strict schema diagnostics, actual JSON Schema prompts, durable historical evidence validation and a new-day3-call approval plan. No AWS operations occurred. Allocation19/20 cannot support the driver's peak+2: minimum proposal is one owner-approved gateway downscale of unheld Cost fixture4->3, then driver on that retained resource3->2->4->3->5 then5->3->5->3->5, peak20. Do Bedrock acceptance on Cost4 BEFORE that optional demo preparation. Existing escalated incident2/effects remain untouched. All changes are local and undeployed.

