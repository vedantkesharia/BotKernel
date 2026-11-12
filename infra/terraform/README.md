# AWS single-host demo foundation

This is an un-applied Terraform foundation for an isolated, nonproduction portfolio demo. It targets one Amazon Linux 2023 EC2 host running Docker Compose; PostgreSQL, single-node Kafka, Redis, workers, agents and the dashboard remain local containers on persistent encrypted EBS. It is not HA or a production database/broker design.

## Resources and defaults

- One VPC, one subnet with an Internet Gateway default route, one route table and one instance security group.
- One configurable EC2 instance (default `t3.large`) with IMDSv2 required and a 100-GiB gp3 encrypted root/data volume.
- No security-group ingress rules. Egress is restricted to TCP 443 for SSM, ECR, CloudWatch Logs, package updates and optional Bedrock.
- A runtime-only instance profile: SSM managed-node access, ECR pull for the two project repositories and CloudWatch write access to one log group. The optional Bedrock policy is separate and grants only `bedrock:InvokeModel` on explicitly supplied foundation-model/inference-profile ARNs. It is off by default. This is not an infrastructure-administration role.
- Two private ECR repositories (backend and dashboard), immutable tags, push scanning and deletion protection.
- A CloudWatch log group with bounded retention (30 days by default). No custom metrics, Container Insights, load balancer, NAT Gateway, RDS, managed Kafka, or EKS is created.

The public-routing subnet and public IPv4 are used only for outbound HTTPS (SSM agent, ECR, logs and optional inference); ingress is empty. The private dashboard/API is exposed only on the host loopback by the deployment Compose file and is accessed through an IAM-authorized SSM port-forward. This avoids NAT Gateway and interface endpoint hourly costs but retains the public IPv4 charge and requires careful outbound egress control. PostgreSQL, Kafka, Redis and worker ports are never published. The deployment identity needs narrowly scoped SSM session permissions; the EC2 role is not the deployment identity.

## Local static validation

No AWS credentials are needed for formatting, initialization of the provider plugin, or `terraform validate`. Do not run `plan`, `apply`, `destroy`, `refresh`, or credential-dependent commands as part of local validation. Terraform state and `.terraform/` are ignored; never commit state or local `*.tfvars`.

```powershell
Set-Location infra\terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

`terraform init` downloads the HashiCorp provider from the Terraform Registry; it does not call AWS. An actual plan requires a separately approved deployment session, a reviewed account/region, a current AL2023 AMI ID, and a real local ignored `.tfvars` file. `terraform.tfvars.example` contains placeholders and is not deployable.

## Future authorized workflow

1. Select the dedicated AWS account and region and verify quotas, AMI ID, EC2/EBS/ECR/CloudWatch/IPv4 costs, SSM reachability and all image/model support. Keep the Bedrock permission disabled unless separately approved.
2. Copy `terraform.tfvars.example` to ignored `terraform.tfvars`, replace placeholders locally, review `terraform plan` and the generated IAM/network policy, then obtain explicit deployment approval before any apply.
3. Use a human deployment identity kept outside this runtime role. The human identity should be limited to the approved Terraform resource set and SSM `StartSession`/port-forward access to the resulting instance; the EC2 role must not administer infrastructure.
4. Locally build tagged backend and dashboard images with `scripts\build-aws-demo.ps1`; inspect them and scan findings. A future, separately approved image-push step must authenticate with the operator's short-lived AWS identity and push to the two private ECR outputs. Never put credentials in the images or frontend bundle.
5. Connect through SSM, copy `compose.aws-demo.yaml` and the runtime config to `/opt/botkernel`, create the two host-only secret files with `sudo scripts/create-aws-demo-secrets.sh`, install/verify Docker Compose v2 using the current [official Linux instructions](https://docs.docker.com/compose/install/linux/), then run `scripts/start-aws-demo.sh` with the required Docker/AWS permissions. The AL2023 bootstrap installs Docker Engine only; Compose plugin availability is not assumed. The helper rejects duplicate or unsafe mode flags and validates Compose before ECR login, but is a template and has not been run on EC2.
6. On the operator workstation, after separately approved provisioning and IAM authorization, run:

   ```sh
   aws ssm start-session --target <instance-id> --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}' --region <approved-region>
   ```

   Visit `http://127.0.0.1:8080`. Dashboard requests go through its private Nginx `/api/` proxy to FastAPI. No API port is published on the host. SSM port-forwarding payloads are not logged like shell sessions; audit session start/stop metadata through CloudTrail and do not treat it as command-content auditing.
7. Verify `/health`, `/ready`, PostgreSQL/Kafka/Redis health, simulated telemetry labeling, worker heartbeats, and persisted checkpoints. Back up PostgreSQL and export any needed Kafka, SQLite checkpoint, investigation, benchmark and observability artifacts before upgrades or teardown.

The runtime config points Docker's `awslogs` driver to the Terraform-created log group. Browser/operator endpoints have no application authentication; their safety boundary is IAM-authorized SSM access and loopback-only host binding. This is acceptable only for a private single-operator portfolio demo. Do not expose it through a public IP, load balancer, public DNS or a shared tunnel. A public product needs authentication/authorization, CSRF protections, TLS, audit controls and a separate review before exposure.

## Superseded historical cost model (t3.xlarge; do not use for current planning)

The known-priced subtotal assumes one 730-hour month, continuous `t3.xlarge` Linux On-Demand use at the AWS T3 page's displayed `$0.1670/hour`, 100 GiB gp3 at the EBS page's `$0.08/GiB-month` example rate, one in-use public IPv4 at `$0.005/hour`, and 2 GiB total private ECR storage at `$0.10/GiB-month`. This yields **$133.76/month before taxes, logs, transfer, snapshots, and other variable charges**:

| Component | Calculation | Estimate |
|---|---:|---:|
| EC2 `t3.xlarge` | 730 × $0.1670 | $121.91 |
| gp3 volume | 100 × $0.08 | $8.00 |
| Public IPv4 | 730 × $0.005 | $3.65 |
| ECR | 2 GiB × $0.10 | $0.20 |
| **Known-priced subtotal** |  | **$133.76/month** |

Rates and regional applicability must be rechecked in the AWS Pricing Calculator before deployment; the above is a lower-bound subtotal, not a quote or a complete monthly estimate. CloudWatch ingestion/storage, Bedrock, taxes, internet egress, additional ECR storage, snapshots/backups, CloudWatch queries/custom metrics, and any CPU-credit usage are excluded. CloudWatch pricing depends on region, log class, ingestion, retention and query volume; no log rate is asserted here. The instance is configured in Standard CPU-credit mode to avoid Unlimited surplus-credit charges (sustained work may instead be throttled). Stop or terminate compute when not demonstrating; EBS volumes, snapshots, ECR and retained logs continue to incur storage charges. A teardown must preserve or explicitly export the EBS data before any deletion.

Sources checked 2026-11-10: [EC2 T3 pricing and specifications](https://aws.amazon.com/ec2/instance-types/t3/), [EBS pricing](https://aws.amazon.com/ebs/pricing/), [VPC public IPv4 pricing](https://aws.amazon.com/vpc/pricing/), [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/), [ECR pricing](https://aws.amazon.com/ecr/pricing/), and [AWS Pricing Calculator](https://calculator.aws/). These public pricing pages are subject to change. Pricing page ingestion/storage rates were not used in the subtotal.

## Bedrock live acceptance (not executed)

No account access, model authorization or live request has been checked; the EC2 instance state is unknown. The acceptance runner and current preflight/approval procedure are maintained in [BEDROCK_ACCEPTANCE.md](../../docs/BEDROCK_ACCEPTANCE.md). A low-cost candidate for later review is Amazon Nova Micro through `us.amazon.nova-micro-v1:0` in `us-east-2`; exact availability, regional routing, permissions and current price remain unverified. Keep all flags false; Terraform's separate Bedrock policy defaults off.

Before a later live test, present and approve: account/profile identity without credential disclosure; source region and cross-region routing implications; exact inference-profile ID and ARN; current account access/IAM; current input/output rates; request size/token estimates; and a maximum total spend in dollars. Do not use Provisioned Throughput. Authorization to run model calls is separate from Terraform apply approval.

After separate deployment, IAM and inference approvals, run advisory-only tests with `AI_ACTION_EXECUTION_ENABLED=false`, `CLOUD_MODE=mock`, `AWS_DEPLOY_ALLOWED=false`, at most one request each for Cost, Performance and a COMPLETE evidence-backed investigation (3 calls total), 512 output tokens/call, 20,000 estimated input+output tokens/day, and a 10-second timeout. Preserve proposal/report idempotency records. Capture actual model/profile ID, token usage, validated result and provider provenance; if the model correctly returns NO_OP or abstains, do not force an action. A proposed experiment ceiling is $0.01 total, but software budgets and AWS Budgets alerts are not billing caps.

AWS references: [Nova Micro model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-micro.html), [US cross-region inference rules](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html), [AWS Ohio Nova pricing example](https://aws.amazon.com/blogs/machine-learning/effective-cost-optimization-strategies-for-amazon-bedrock/), and [Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html). Public documentation gives $0.000035/1,000 input tokens and $0.00014/1,000 output tokens for Nova Micro in its Ohio example. This would make 20,000 total tokens cost at most about $0.0028 if all were output; the proposed three-call experiment ceiling is $0.01. These estimates do not account for model/profile/account restrictions and are not a billing cap. No live call or account-level access check has occurred.

## State and teardown warning

The encrypted root EBS volume has `delete_on_termination=false`; Docker named volumes therefore survive instance termination but become an unattached billable volume. ECR repositories and the CloudWatch log group have Terraform deletion protection. Before any future destroy, take and verify an encrypted snapshot and/or application-consistent PostgreSQL backup, export Kafka/checkpoints/reports/benchmark outputs, inspect the plan, and retain the data volume, repositories and logs unless their removal is explicitly approved. No backup/restore or cloud deployment has been tested.


## Preflight for the intended Ohio account (commands are for the operator)

The deployment default is `us-east-2`; the Bedrock region is intentionally blank and must be selected separately after model support and price are checked. These read-only commands are prepared for a later user-authorized verification session. They were **not run** here. They use the existing `botkernel-dev` profile and never print credential material:

```powershell
$ProfileName = 'botkernel-dev'
$ExpectedAccount = '<intended-account-id-confirmed-by-owner>'
$InfraRegion = 'us-east-2'
$Identity = aws sts get-caller-identity --profile $ProfileName --query '{Account:Account,Arn:Arn}' --output json | ConvertFrom-Json
if ($Identity.Account -ne $ExpectedAccount) { throw "AWS account mismatch; stop before further calls." }
$Identity | Select-Object Account,Arn
aws configure get region --profile $ProfileName
aws ec2 describe-instance-type-offerings --profile $ProfileName --region $InfraRegion --location-type availability-zone --filters Name=instance-type,Values=t3.large --query 'InstanceTypeOfferings[].Location' --output table
aws service-quotas list-service-quotas --profile $ProfileName --region $InfraRegion --service-code ec2 --query 'Quotas[?contains(QuotaName, `On-Demand`)].{Name:QuotaName,Code:QuotaCode,Value:Value}' --output table
$AmiId = aws ssm get-parameter --profile $ProfileName --region $InfraRegion --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text
aws ec2 describe-images --profile $ProfileName --region $InfraRegion --owners amazon --image-ids $AmiId --query 'Images[].{ImageId:ImageId,Name:Name,Architecture:Architecture,State:State,CreationDate:CreationDate}' --output table
aws bedrock list-foundation-models --profile $ProfileName --region $InfraRegion --by-output-modality TEXT --query 'modelSummaries[].{Id:modelId,Provider:providerName,Input:inputModalities,Output:outputModalities}' --output table
$BedrockRegion = 'us-east-2' # candidate only; needs separate approval
aws bedrock list-inference-profiles --profile $ProfileName --region $BedrockRegion --type-equals SYSTEM_DEFINED --query 'inferenceProfileSummaries[?inferenceProfileId==`us.amazon.nova-micro-v1:0`].{Id:inferenceProfileId,Name:inferenceProfileName,Status:status,Type:type}' --output json
$PrincipalArn = '<owner-approved-operator-principal-arn>'
aws iam simulate-principal-policy --profile $ProfileName --policy-source-arn $PrincipalArn --action-names ec2:RunInstances ec2:CreateVpc ec2:CreateSubnet ec2:CreateInternetGateway ec2:CreateRoute ec2:CreateSecurityGroup ec2:CreateVolume iam:CreateRole iam:PassRole ecr:CreateRepository ecr:GetAuthorizationToken ssm:StartSession logs:CreateLogGroup logs:PutLogEvents --resource-arns '*' --output json
# Only after separate Bedrock approval, substitute the exact reviewed profile ARN.
aws iam simulate-principal-policy --profile $ProfileName --policy-source-arn $PrincipalArn --action-names bedrock:InvokeModel --resource-arns '<exact-approved-inference-profile-arn>' --output json
```

Set `$ExpectedAccount` locally to the owner-confirmed account ID, compare it with the returned Account, and stop on mismatch; do not commit a personal account ID into public source. `aws configure get region` reads local CLI config; explicitly supplied `--region` controls service calls. The SSM public parameter and image description confirm current AL2023 x86_64 AMI metadata, not launch success. Quotas do not prove AZ capacity or IAM access. IAM simulation itself is an AWS API call; the wildcard is only a coarse check. Use a reviewed principal/resource ARN and inspect SCPs, boundaries and conditions. Regional model inventory is not proof of account authorization. The candidate Nova Micro model card documents Converse but not native structured outputs, so application-side Pydantic validation is required. The Ohio geographic profile and IAM need account-specific checks. These commands are approval-gated and have not been run.

Official on-demand price-list lookup can be prepared after selecting exact SKUs/regions. The AWS Price List endpoint is a read-only AWS API and has not been called:

```powershell
aws pricing get-products --profile $ProfileName --region us-east-1 --service-code AmazonEC2 --filters 'Type=TERM_MATCH,Field=location,Value=US East (Ohio)' 'Type=TERM_MATCH,Field=instanceType,Value=t3.large' 'Type=TERM_MATCH,Field=operatingSystem,Value=Linux' 'Type=TERM_MATCH,Field=tenancy,Value=Shared' 'Type=TERM_MATCH,Field=preInstalledSw,Value=NA' 'Type=TERM_MATCH,Field=capacitystatus,Value=Used' --max-results 10 --output json
```

The Price List API's control plane uses `us-east-1` even when filtering a product in Ohio. Inspect the returned On-Demand terms and unit before using a rate; this command is not an account or billing lookup. The exact Ohio EC2 price is not verified until this query is run after approval. Run an equivalent query for EBS, public IPv4 and ECR only after checking each service's catalog schema. Use AWS Pricing Calculator for the final region/service estimate. No command here is authorized to provision or alter resources.

## Current t3.large cost planning estimate (not a quote)

| Type | vCPU | RAM | Published AWS Linux rate (us-east-1 only) | Fit for this stack |
|---|---:|---:|---:|---|
| t3.medium | 2 | 4 GiB | $0.0418/hour | Not enough for the configured core limits plus host overhead. |
| t3.large | 2 | 8 GiB | $0.0835/hour | Initial core-only candidate; peak capacity not yet measured. |
| t3.xlarge | 4 | 16 GiB | $0.1670/hour | Upgrade candidate if memory/CPU monitoring justifies it. |

The AWS T3 price page specifies these rates are for US East (N. Virginia). They are not Ohio quotes; use the approved Ohio Price List lookup before committing cost estimates.

The core stack has 5,312 MiB (5.19 GiB) of Compose memory ceilings, counting the one-shot initializer conservatively. An 8-GiB EC2 host exposes less than 8 GiB to Linux; about 2.4 GiB remains after these container limits for the OS, Docker and cache. Optional Prometheus/Grafana/Jaeger/OTel add 1,600 MiB and must stay disabled on the first host. A read-only local Docker stats snapshot (Docker host reports 7.581 GiB and 12 vCPU) included many separate BotKernel projects: Kafka containers used 677.9, 793.1 and 859.5 MiB, API 115.7 MiB, PostgreSQL 44.1 to 65.4 MiB, Redis 4.6 to 8.4 MiB, and small worker/publisher/controller/recovery services about 39 to 53 MiB each. It did not include active Cost/Performance agent containers or an isolated deployment startup/peak. This supports t3.large as the first bounded core-profile candidate, not as measured peak-safe capacity. Monitor available memory, swap, OOM/restart signals and CPU credits during an approved short run; stop and evaluate t3.xlarge if headroom is poor. t3.medium (4 GiB) is too small for the configured core ceilings plus host overhead.

Planning inputs: `t3.large` about $0.0832/hour (the AWS reference table quotes us-east-1; verify Ohio from the price list before approval), gp3 $0.08/GiB-month, one in-use public IPv4 $0.005/hour, and private ECR $0.10/GiB-month. For a 720-hour month, compute is about $59.90; the known running subtotal is about $71.70 including 100 GiB EBS ($8), public IPv4 ($3.60), and 2 GiB ECR ($0.20). Four hours: EC2 $0.33 + IPv4 $0.02 + prorated EBS about $0.04 = **about $0.39**, or about $0.59 including a full month of ECR storage. Eight hours: about $0.67 + $0.04 + $0.09 = **about $0.80**, or $1.00 with monthly ECR. One day: about $2.00 + $0.12 + $0.26 = **about $2.38**, or $2.58 with monthly ECR. EBS remains billed while the instance is stopped; a stopped instance normally releases its public IPv4 unless an Elastic IP is allocated. Keeping an instance running for eight hours doubles the compute/IPv4 runtime subtotal. A stopped-but-retained host still carries the EBS, ECR, snapshots and logs charges.

CloudWatch log ingestion/storage, data transfer, snapshots, support/tax, and possible surplus CPU credits are excluded. SSM Session Manager itself has no separate fee for this access pattern, but the public IPv4/egress path costs money; private VPC endpoints would add hourly and data-processing charges and are not part of this design. Logging volume and transfer have no measured workload estimate yet. The Nova Micro estimate above is token arithmetic, not an account quote or a billing cap. The approximately $100 credit balance is historical and unverified; do not use it as spending authorization or assume it covers these line items.

Official pricing references (checked 2026-11-10): [EC2 On-Demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/), [T3 instance specifications/pricing](https://aws.amazon.com/ec2/instance-types/t3/), [EBS gp3 pricing](https://aws.amazon.com/ebs/pricing/), [VPC public IPv4 pricing](https://aws.amazon.com/vpc/pricing/), [ECR pricing](https://aws.amazon.com/ecr/pricing/), [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/), [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/), [Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html), [AWS Pricing Calculator](https://calculator.aws/). Rates vary by region and change; the Ohio EC2 estimate above must be verified from the official price list before any plan/apply.

## Operator and EC2 runbook commands

PowerShell operator preparation (no provisioning):

```powershell
$ProfileName = 'botkernel-dev'
$InfraRegion = 'us-east-2'
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
aws sts get-caller-identity --profile $ProfileName --query '{Account:Account,Arn:Arn}' --output json
# Build only local images; does not log in or push.
.\scripts\build-aws-demo.ps1
# Review local Compose using a local copy of runtime.env.example and placeholder secret paths.
docker compose --env-file infra/deploy/runtime.env.example -f compose.aws-demo.yaml config --quiet
```

After separate explicit deployment approval, the future sequence is: create a local ignored tfvars with reviewed account/AMI/region, inspect a saved Terraform plan, obtain approval for its exact resource diff, then apply; push immutable image tags to the Terraform ECR outputs using short-lived credentials; copy the compose/runtime files and host-only secrets to EC2 over SSM; start with `BOTKERNEL_DEPLOY_APPROVED=true sudo -E /opt/botkernel/scripts/start-aws-demo.sh`. No script should be invoked as part of ordinary local development. The current helper validates all cloud/inference/action flags remain false before ECR login and Compose startup.

Linux EC2 checks after a separately approved launch:

```bash
cd /opt/botkernel
sudo docker compose --env-file /opt/botkernel/runtime.env -f /opt/botkernel/compose.aws-demo.yaml ps
sudo docker compose --env-file /opt/botkernel/runtime.env -f /opt/botkernel/compose.aws-demo.yaml logs --tail=100 postgres kafka redis api publisher worker recovery controller
curl --fail http://127.0.0.1:8080/healthz
curl --fail http://127.0.0.1:8080/api/health
curl --fail http://127.0.0.1:8080/api/ready
```

Keep Cost/Performance bounded for a first simulator run by setting `AGENT_MAX_RUNS=1`, reviewing gateway actions, then stop agents. The Compose dashboard is reachable only after an operator starts the documented SSM port forward. For shutdown use `docker compose ... stop` or `down` without `-v`; export/backup data first. The encrypted root EBS volume is intentionally retained on instance termination and remains billable. Never run `destroy` until data preservation is explicitly reviewed.

### Commands reserved for a separately approved deployment

These commands intentionally have **not** been run. `plan` and ECR authentication/push perform AWS API operations and require a separate explicit approval after account/region/cost confirmation. The account number is supplied locally, never written into committed source.

PowerShell operator sequence after approval:

```powershell
$ProfileName = 'botkernel-dev'
$Region = 'us-east-2'
$AccountId = '<owner-confirmed-account-id>'
$Tag = '<immutable-release-tag>'
terraform -chdir=infra/terraform plan -var-file=terraform.tfvars -out=botkernel-demo.tfplan
terraform -chdir=infra/terraform show botkernel-demo.tfplan
# Stop for review/approval of this exact plan before apply.
terraform -chdir=infra/terraform apply botkernel-demo.tfplan
$BackendRepo = terraform -chdir=infra/terraform output -raw backend_repository_url
$DashboardRepo = terraform -chdir=infra/terraform output -raw dashboard_repository_url
aws ecr get-login-password --profile $ProfileName --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"
docker tag botkernel-api:local "$BackendRepo`:$Tag"
docker tag botkernel-dashboard:local "$DashboardRepo`:$Tag"
docker push "$BackendRepo`:$Tag"
docker push "$DashboardRepo`:$Tag"
aws ssm start-session --profile $ProfileName --region $Region --target <instance-id> --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
```

The `apply` step is deliberately shown only to make the future boundary concrete; no approval is granted here. Select the EC2 AMI ID for `us-east-2` only after a region-specific read-only AMI/SSM validation. The selected t3.large has 2 vCPU/8 GiB; t3.medium is 2/4 GiB and t3.xlarge is 4/16 GiB. An xlarge upgrade is the documented fallback, not the initial size. The current terraform example AMI and account ID are placeholders. The existing `scripts/start-aws-demo.sh` requires `BOTKERNEL_DEPLOY_APPROVED=true` and all cloud, Bedrock and AI-action flags false before login/pull/up.

On EC2 over SSM, install/check Compose v2, create secrets only if absent, deploy the two files/runtime config, and start only after all approvals:

```bash
sudo docker compose version
sudo install -d -m 0750 /opt/botkernel
sudo install -m 0644 compose.aws-demo.yaml /opt/botkernel/compose.aws-demo.yaml
sudo install -m 0600 runtime.env /opt/botkernel/runtime.env
sudo BOTKERNEL_SECRET_DIR=/etc/botkernel/secrets bash /opt/botkernel/scripts/create-aws-demo-secrets.sh
sudo BOTKERNEL_DEPLOY_APPROVED=true BOTKERNEL_RUNTIME_ENV_FILE=/opt/botkernel/runtime.env BOTKERNEL_COMPOSE_FILE=/opt/botkernel/compose.aws-demo.yaml bash /opt/botkernel/scripts/start-aws-demo.sh
```

The commands assume the approved operator has already copied artifacts securely and provided the runtime image references. For recovery, inspect `docker compose ps`, health and logs first; do not reset Kafka, PostgreSQL, Redis or checkpoints. For a safe stop, use `docker compose ... stop`; `down` retains named volumes, while Terraform termination retains the encrypted root EBS disk. A full destroy is intentionally not part of this runbook and requires a separate data-export/backup and approval review.

### Deployment status

Static preparation is not a deployment. AWS identity/quota/IAM/model access, an Ohio AMI, image push, EC2 startup, SSM, CloudWatch delivery, Bedrock and restore have not been verified. Publicly reachable host addresses are for outbound traffic only; the security group has no ingress. The dashboard/API remain unauthenticated and are suitable only behind the described single-operator SSM access boundary.
