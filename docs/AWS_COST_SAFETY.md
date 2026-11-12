# AWS safety
Local Compose development makes no AWS requests and normally incurs no AWS service charges. Terraform and deployment scripts for a private single-host AWS demo exist, and earlier infrastructure/image deployment was reported; its current state is unknown. Environment flags are safety gates, not account spending caps.

Before any cloud operation, obtain explicit approval naming the target, operation, region, price estimate, runtime, resource scope and stop/rollback plan. EKS, MSK, RDS, NAT gateways and always-on load balancers are not part of the current deployment design. AWS Budgets alerts are delayed and are not hard spending caps. Use short-lived credentials/instance roles and least privilege; never log or commit credentials.
