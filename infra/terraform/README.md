# AWS single-host demo foundation

This Terraform configuration describes a private, nonproduction Amazon Linux 2023 EC2 host running Docker Compose. PostgreSQL, single-node Kafka, Redis, workers, agents and dashboard use persistent encrypted EBS. It is not an HA database/broker design.

Historical November 14, 2026 acceptance verified the AWS application, all three Bedrock workflows, authenticated browser access and monitoring; the instance was then stopped. Four new model calls included one retained Investigator validation failure. No new AWS infrastructure, Terraform apply, IAM or network changes occurred during that acceptance or this documentation sprint. See [validation](../../docs/VALIDATION.md), [Bedrock acceptance](../../docs/BEDROCK_ACCEPTANCE.md) and [demo guide](../../docs/DEMO_GUIDE.md). Historical shutdown is not a fresh cloud-state check.

## Resources and defaults

- One VPC, subnet, Internet Gateway route, route table and instance security group.
- Configurable EC2 instance, default `m7i-flex.large`, with IMDSv2 and a 100-GiB encrypted gp3 root/data volume.
- No security-group ingress. Egress permits TCP 443 for SSM, ECR, CloudWatch Logs, package updates and optional Bedrock.
- Runtime-only instance profile: SSM managed-node access, project ECR pull and CloudWatch writes. Optional Bedrock permission is a separate attachment, off by default and restricted to supplied model/profile ARNs. The runtime role cannot administer infrastructure.
- Two private ECR repositories with immutable tags, push scanning and deletion protection; a CloudWatch log group with 30-day default retention.
- No load balancer, NAT Gateway, RDS, managed Kafka, EKS, custom metrics or Container Insights.

The subnet's public IPv4 route supports outbound HTTPS; ingress stays empty. Dashboard publication is loopback-only for IAM-authorized SSM forwarding. Its Compose service joins both backend and egress networks because the internal network alone did not publish the loopback port on the observed EC2 runtime. Database, broker, Redis and worker ports are not host-published. The human deployment identity is separate from the EC2 runtime role.

## Local static validation

From the repository root:

```powershell
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
```

These are usage instructions, not checks rerun during this documentation edit. Initialization downloads provider plugins; it does not provision AWS. No AWS credentials are required for these static checks. State, local variable files and provider working directories remain private. The example variable file contains placeholders. `plan`, `refresh`, `apply` and `destroy` are separate cloud operations, not offline validation.

## Authorized deployment procedure

1. Verify the intended account and region privately, current AMI, quotas, permissions, capacity and complete regional cost estimate. Inventory existing resources and drift before planning; do not apply an unrelated saved plan. IAM simulation and model inventory are not proof of effective access.
2. Copy `terraform.tfvars.example` to an ignored local variable file and replace placeholders. Review the exact plan and IAM/network changes before a specifically authorized apply. Keep the optional Bedrock policy disabled unless required and separately reviewed.
3. Build backend/dashboard images locally using [the build helper](../../scripts/build-aws-demo.ps1). Inspect images and scan findings, then publish immutable tags only within the authorized deployment scope. Use short-lived deployment credentials; never bake credentials into images or browser bundles.
4. Connect through SSM. Securely copy [AWS Compose configuration](../../compose.aws-demo.yaml), runtime settings and required helpers to the reviewed host directory. Verify Compose v2; AL2023 bootstrap installs Docker Engine and does not guarantee the Compose plugin. Use [secret creation](../../scripts/create-aws-demo-secrets.sh) only for absent secrets and retain restrictive permissions.
5. Use [the startup helper](../../scripts/start-aws-demo.sh) with the reviewed runtime/configuration paths. It requires the deployment gate and rejects unsafe cloud, Bedrock and model-action settings before login/pull/start. Keep `AGENT_MAX_RUNS=1`; do not enable continuous agents unintentionally.
6. Open a private dashboard tunnel using the intended instance and region supplied locally:

   ```powershell
   aws ssm start-session --target <reviewed-instance-id> --region <reviewed-region> --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
   ```

   Visit `http://127.0.0.1:8080/app`. Nginx proxies `/api/` to FastAPI. Sign in with the operator credential; it lives only in browser memory and is required again after reload. Health endpoints and the dashboard shell do not require operator authentication.
7. Verify readiness, database/broker/Redis health, scoped authentication, checkpoint persistence and simulator labeling. SSM session metadata does not provide command-content auditing for port-forward traffic. Keep access private; do not publish the service through public ingress or shared tunnels.

Deployment examples do not authorize new cloud operations. The local-first runtime remains `CLOUD_MODE=mock` and `AWS_DEPLOY_ALLOWED=false`; these flags restrict application remediation, not Terraform's ability to provision resources.

## Bedrock and monitoring boundaries

Live acceptance used role credentials, Nova Micro profile `us.amazon.nova-micro-v1:0` and source region `us-east-2`. Current defaults disable inference, spending and model-driven actions. Application guards are 12 calls/day, 80,000 estimated tokens/day and 1,024 output tokens/call; they are not AWS billing caps. Preserve unknown historical outcomes and the original shared budget store. Never automatically retry an ambiguous inference request.

The optional monitoring profile was verified on the existing host during the historical run: five targets UP, three Grafana dashboards, a 14-span trace and matching CloudWatch events. It requires fresh capacity and health checks before restart. Configured container ceilings and a bounded memory sample do not establish peak-load capacity. Retain the supplied monitoring hardening and credential permissions. See [observability contracts](../../docs/OBSERVABILITY.md).

## Costs, persistence and shutdown

Recheck current regional EC2, EBS, public IPv4, ECR, CloudWatch, transfer, backup and inference prices before cloud use. Historical estimates are not invoices or current quotes; credits and budget alerts are not guaranteed spending caps. Stopping compute does not eliminate retained EBS, image, log or backup charges.

Back up current PostgreSQL, checkpoints, reports and required broker/benchmark artifacts before upgrades or teardown. November 14 backups were integrity-checked; a complete restore drill remains unverified. PVCs or retained Docker volumes do not establish cross-system recovery or HA.

Quiesce actions and unpublished outbox work before stopping the reviewed Compose services. Close owned tunnels/sessions and verify the instance's stopped state within the authorized operating window. Retain named volumes; do not use `down -v` or terminate resources as routine cleanup.

The root EBS volume has `delete_on_termination=false`; termination retains a billable disk, not a verified recovery environment. ECR repositories and CloudWatch logs have Terraform deletion protection. Any removal requires an explicit data-retention decision and reviewed plan; this runbook does not authorize destroy.
