# Local Kubernetes simulator

2026-11-13: Helm 3.17.3 was downloaded to temporary storage and verified against its published SHA-256. Strict lint and default/agent/observability renders passed. The configured docker-desktop API refused a direct connection; no release, pods or PVCs were created. Static readiness is green; runtime acceptance remains pending. See [AWS_DEMO_READY.md](../../docs/AWS_DEMO_READY.md) for the separate EC2 Compose status; it is not Kubernetes proof.

This is the existing Helm deployment for a **private local simulator**, not a production or cloud Kubernetes deployment. It provides PostgreSQL, single-node Kafka, Redis, a migration Job, FastAPI, publisher, worker, recovery, controller and dashboard. Optional Cost and Performance agents have separate single-writer SQLite PVCs. Optional Prometheus, Grafana, OpenTelemetry Collector and Jaeger use the project's current dashboards and trace path. Nothing in this guide was installed into a Kubernetes cluster during this implementation.

All services are ClusterIP; the stateful service names are headless ClusterIP Services for stable pod identity. Kafka advertises `kafka:9092`, reachable by in-cluster clients. The API becomes ready only after Alembic revision `0009` and Kafka metadata access succeed. Background and agent pods wait for the API readiness endpoint. The chart creates a no-permission ServiceAccount and disables service-account token mounting. There is no Ingress, NodePort, LoadBalancer or NetworkPolicy; service privacy relies on a dedicated namespace and local cluster. NetworkPolicies are intentionally omitted because enforcement depends on the selected CNI.

## Prerequisites and offline checks

Use an existing local Docker Desktop Kubernetes or uniquely named `kind` cluster. Never create an EKS cluster or install into an unfamiliar/shared context. Reserve at least **6 GiB free memory and 4 CPU cores for core services**, or **8 GiB and 6 cores when agents and observability are enabled**, plus **8 GiB of persistent storage**. These are conservative setup recommendations based on chart requests/limits, not measured working-set benchmarks. Check current Docker and cluster workloads before proceeding.

From the repository root in PowerShell:

```powershell
helm lint --strict infra\kubernetes\botkernel
helm template botkernel infra\kubernetes\botkernel | Out-Null
helm template botkernel infra\kubernetes\botkernel --set agents.enabled=true | Out-Null
helm template botkernel infra\kubernetes\botkernel --set observability.enabled=true | Out-Null
kubectl config current-context
kubectl get nodes
```

Proceed only when the current context is a local context (`kind-*` or `docker-desktop`) and its node is the intended local cluster. Pass that exact context explicitly to all later commands. The chart defaults keep all Bedrock and AI-action gates disabled, use deterministic agent providers and keep every service private.

## Create a fresh private deployment

Choose a unique release, local cluster context and **new** namespace. The database, operator and agent credentials must be independent random values, at least 43 printable ASCII characters. Create password/token files outside the repository with restrictive local permissions and no trailing newline. Build `database-url` for user/database `botkernel`, host `postgres`, port `5432`, and the same password as `postgres-password`; URL-encode password characters. Do not put secret contents in chart values or command text.

Build and load the current images:

```powershell
$ClusterName = '<your-local-kind-cluster>'
$Context = "kind-$ClusterName"
$Namespace = 'botkernel-acceptance-<unique-suffix>'
docker build -f Dockerfile.deploy -t botkernel-api:local .
docker build -f apps\dashboard\Dockerfile.deploy -t botkernel-dashboard:local apps\dashboard
kind load docker-image botkernel-api:local botkernel-dashboard:local --name $ClusterName
```

For Docker Desktop Kubernetes, omit `kind load`; the cluster shares Docker Desktop's local image store. Create the namespace and required Secrets from private files:

```powershell
$Context = '<kind-cluster-context-or-docker-desktop>'
$Namespace = 'botkernel-acceptance-<unique-suffix>'
$DatabasePasswordFile = '<private-password-file>'
$DatabaseUrlFile = '<private-url-file>'
$OperatorTokenFile = '<private-operator-token-file>'
$AgentTokenFile = '<private-agent-token-file>'
$CurrentContext = kubectl config current-context
if ($CurrentContext -ne $Context) { throw "Switch to the explicitly selected local context first." }
$ApiServer = kubectl config view --minify --context $Context -o jsonpath='{.clusters[0].cluster.server}'
$ApiHost = ([uri]$ApiServer).DnsSafeHost
$IsKindLocal = ($Context -like 'kind-*') -and ($ApiHost -in @('127.0.0.1', 'localhost', '::1'))
$IsDockerDesktopLocal = ($Context -eq 'docker-desktop') -and ($ApiHost -eq 'kubernetes.docker.internal')
if (-not ($IsKindLocal -or $IsDockerDesktopLocal)) { throw "Refusing non-local Kubernetes API endpoint: $ApiHost" }
kubectl --context $Context create namespace $Namespace
kubectl --context $Context -n $Namespace create secret generic botkernel-database `
  "--from-file=postgres-password=$DatabasePasswordFile" `
  "--from-file=database-url=$DatabaseUrlFile"
kubectl --context $Context -n $Namespace create secret generic botkernel-operator `
  "--from-file=operator-token=$OperatorTokenFile"
kubectl --context $Context -n $Namespace create secret generic botkernel-agent `
  "--from-file=agent-token=$AgentTokenFile"
helm upgrade --install botkernel infra\kubernetes\botkernel `
  --kube-context $Context --namespace $Namespace --wait --wait-for-jobs --timeout 15m
```

To run the deterministic Cost and Performance processes, opt in only after confirming the dedicated database is disposable simulation state. Their default targets are distinct (`service-a` and `service-b`); the chart rejects equal targets. Add `--set agents.enabled=true` to the Helm command. These agents can submit simulator actions; they have no direct infrastructure-remediation path.

Check the migration and workload state before using the dashboard:

```powershell
kubectl --context $Context -n $Namespace get jobs,pods,services,pvc
$Migration = kubectl --context $Context -n $Namespace get jobs -o name |
  Where-Object { $_ -like 'job.batch/botkernel-migrate-*' } |
  Select-Object -Last 1
if (-not $Migration) { throw 'Migration Job is missing.' }
kubectl --context $Context -n $Namespace wait --for=condition=complete $Migration --timeout=10m
kubectl --context $Context -n $Namespace rollout status statefulset/botkernel-postgres --timeout=10m
kubectl --context $Context -n $Namespace rollout status statefulset/botkernel-kafka --timeout=10m
kubectl --context $Context -n $Namespace rollout status statefulset/botkernel-redis --timeout=10m
foreach ($Deployment in @('api','publisher','worker','recovery','controller','dashboard')) {
  kubectl --context $Context -n $Namespace rollout status "deployment/botkernel-$Deployment" --timeout=10m
}
```

If `agents.enabled=true`, also wait for both role-specific deployments:

```powershell
foreach ($Deployment in @('cost','performance')) {
  kubectl --context $Context -n $Namespace rollout status "deployment/botkernel-$Deployment" --timeout=10m
}
```

In a separate terminal, run and leave open `kubectl --context $Context -n $Namespace port-forward svc/dashboard 18080:8080`. Then `http://127.0.0.1:18080/api/ready` must report ready. Sign in to `/app` using the private operator credential; the agent credential is separate. The dashboard's API proxy stays on loopback through `kubectl port-forward`.

Run the bounded deterministic controller and investigation demo from the repository root while the port-forward is active. Set the token from the private file without echoing it, and keep it only in this PowerShell process:

```powershell
$env:BOTKERNEL_OPERATOR_TOKEN = (Get-Content '<private-operator-token-file>' -Raw).Trim()
$env:BOTKERNEL_API_URL = 'http://127.0.0.1:18080/api'
python -m botkernel.live_demo
Remove-Item Env:\BOTKERNEL_OPERATOR_TOKEN
Remove-Item Env:\BOTKERNEL_API_URL
```

The demo exercises authenticated gateway actions, outbox/Kafka/worker effects, controller lifecycle, evidence graph and persisted deterministic investigation. It does not invoke Bedrock. Confirm persisted records and broker/topic state directly:

```powershell
kubectl --context $Context -n $Namespace exec statefulset/botkernel-postgres -- `
  psql -U botkernel -d botkernel -c "SELECT state,count(*) FROM actions GROUP BY state ORDER BY state"
kubectl --context $Context -n $Namespace exec statefulset/botkernel-postgres -- `
  psql -U botkernel -d botkernel -c "SELECT count(*) AS outbox_rows FROM outbox; SELECT count(*) AS receipts FROM receipts; SELECT count(*) AS effects FROM effects; SELECT count(*) AS reports FROM investigation_reports"
kubectl --context $Context -n $Namespace exec statefulset/botkernel-kafka -- `
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
```

## Optional Prometheus, Grafana and Jaeger

Observability is off by default and does not gate core workload startup. Before enabling it, create a metrics Secret containing `metrics-token`, a Grafana admin Secret containing `admin-user` and `admin-password`, and a ConfigMap from the three existing dashboards. Use independent credentials and private files:

```powershell
$MetricsTokenFile = '<private-metrics-token-file>'
$GrafanaUserFile = '<private-grafana-user-file>'
$GrafanaPasswordFile = '<private-grafana-password-file>'
kubectl --context $Context -n $Namespace create secret generic botkernel-metrics `
  "--from-file=metrics-token=$MetricsTokenFile"
kubectl --context $Context -n $Namespace create secret generic botkernel-grafana-admin `
  "--from-file=admin-user=$GrafanaUserFile" `
  "--from-file=admin-password=$GrafanaPasswordFile"
kubectl --context $Context -n $Namespace create configmap botkernel-grafana-dashboards `
  --from-file=observability\dashboards
helm upgrade --install botkernel infra\kubernetes\botkernel `
  --kube-context $Context --namespace $Namespace --reuse-values `
  --set observability.enabled=true --wait --wait-for-jobs --timeout 15m
foreach ($Deployment in @('prometheus','grafana','otel-collector','jaeger')) {
  kubectl --context $Context -n $Namespace rollout status "deployment/botkernel-$Deployment" --timeout=10m
}
```

Prometheus scrapes `/metrics` with the metrics-only bearer credential and scrapes worker exporters over private ClusterIP Services. Grafana provisions the existing Prometheus datasource and dashboard files; its admin password comes only from the Secret. Collector sends OTLP traces to Jaeger. No monitoring UI or OTLP port is published. Port-forward only for a private local review:

```powershell
kubectl --context $Context -n $Namespace port-forward svc/prometheus 19090:9090
kubectl --context $Context -n $Namespace port-forward svc/grafana 13000:3000
kubectl --context $Context -n $Namespace port-forward svc/jaeger 16686:16686
```

Verify Prometheus targets at `http://127.0.0.1:19090/api/v1/targets`, sign in to Grafana at `http://127.0.0.1:13000` and check System Overview, Distributed Execution Pipeline and Collective Reliability, and inspect traces at `http://127.0.0.1:16686`. This runtime validation remains pending. Prometheus/Grafana/Jaeger data is ephemeral in this chart; dashboards are supplied from the repository. Trace export is optional and does not block PostgreSQL/Kafka transactions.

## Bedrock, storage and shutdown boundaries

Helm values expose the existing model, region, provider, request timeout, call and token settings, but `bedrock.enabled` and `bedrock.spendAuthorized` default to false, as does model-driven action execution (fixed off). Do not enable inference in local Kubernetes acceptance. Do not mount an AWS profile or access keys. Future AWS-backed Kubernetes use needs a separately reviewed platform workload identity; this chart does not create EKS, IAM roles, or credentials.

PostgreSQL, Kafka and Redis have persistent StatefulSet claims; each LangGraph role and experiment history has its own persistent claim. StatefulSet claim retention is set to `Retain`, and standalone checkpoint/experiment claims use Helm's keep policy. Redis remains advisory state, not the action ledger. PVCs do not provide backup, restore, HA or a cross-system consistent snapshot. Grafana/Prometheus/Jaeger state is intentionally ephemeral.

To stop workloads while retaining data, use `helm uninstall botkernel --namespace $Namespace --kube-context $Context` only after reviewing ownership. Do not delete the namespace, PVCs or volumes without explicit data-retention approval. Helm uninstall is not a data cleanup or disaster-recovery procedure.

No cluster runtime, authenticated scrape, dashboard, trace or persistent-state recovery has been verified here. Static `helm lint`/rendering is not runtime acceptance.
