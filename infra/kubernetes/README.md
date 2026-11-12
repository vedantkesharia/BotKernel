# Local Kubernetes simulator

This Helm chart is an **unverified local deployment**, not a production or cloud Kubernetes configuration. It has not been run end to end. It keeps Compose unchanged and deploys a single PostgreSQL, Kafka and Redis with PVCs, a migration Job, API, publisher, worker, recovery, controller and dashboard. Optional Cost and Performance agent deployments use separate checkpoint PVCs and `Recreate` rollout strategy. Agents are disabled by default because deterministic agents can submit simulator actions.

The chart uses fixed service names, so install only one release per dedicated namespace. All Services are ClusterIP: do not create an Ingress, NodePort or public forwarding. Operator routes are unauthenticated. Bedrock, cloud remediation and model action execution are fixed off in the chart. The `databaseSecret` must already exist with `postgres-password` and `database-url` keys. The URL must address `postgres` and its password must match the password key; URL-encode special characters. Kubernetes Secrets are not encrypted automatically; never commit them.

## Preparation, not executed here

Use Docker, kind, kubectl and Helm in a local environment with enough free memory after existing workloads. A complete isolated cluster requires additional memory for the kind control plane, broker, database and application processes; the resource requests in the chart alone are not a measured working-set bound. Check Docker Desktop availability and existing containers before creating a cluster. No cloud credentials are needed.

Build the two existing application images, then create a uniquely named kind cluster and dedicated namespace after checking host capacity:

```powershell
docker build -f Dockerfile.deploy -t botkernel-api:local .
docker build -f apps\dashboard\Dockerfile.deploy -t botkernel-dashboard:local apps\dashboard
kind create cluster --name <unique-cluster>
kind load docker-image botkernel-api:local botkernel-dashboard:local --name <unique-cluster>
kubectl --context kind-<unique-cluster> create namespace <unique-namespace>
```

Create a new database password file and a matching database URL file in a private location outside the repository. Do not copy real credentials into chart values, shell history, manifests or screenshots. Create the Kubernetes Secret from those files:

```powershell
kubectl --context kind-<unique-cluster> -n <unique-namespace> create secret generic botkernel-database `
  --from-file=postgres-password=<private-password-file> `
  --from-file=database-url=<private-url-file>
helm lint infra\kubernetes\botkernel
helm template botkernel infra\kubernetes\botkernel --set agents.enabled=true
helm install botkernel infra\kubernetes\botkernel --kube-context kind-<unique-cluster> `
  --namespace <unique-namespace> --set agents.enabled=true
kubectl --context kind-<unique-cluster> -n <unique-namespace> get pods,jobs,pvc
kubectl --context kind-<unique-cluster> -n <unique-namespace> port-forward svc/dashboard 18080:8080
```

The migration Job waits for PostgreSQL and runs existing Alembic initialization. API `/ready` remains unavailable until migration and Kafka succeed; workers and agents wait for API readiness before starting. Kafka readiness is a TCP check, not proof of broker or application correctness. Worker processes restart on exit but have no independent application-health probe. Do not assume the Job or dependent services succeeded: inspect the Job, logs and API readiness explicitly.

For acceptance, separately demonstrate a committed action, controller incident, saved investigation, worker restart and persistent-state recovery. Those checks have **not** been run against Kubernetes. StatefulSet PVCs are retained by Kubernetes by default; standalone checkpoint/experiment PVCs use Helm's keep policy. Do not delete the namespace, cluster, claims or volumes until their data and ownership have been reviewed. The chart does not implement backup/restore, HA, public access controls or coordinated cross-system snapshots.
