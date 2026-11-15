# Demonstrating BotKernel

BotKernel has a completed, bounded AWS acceptance run and an independent local-first simulator. The AWS host is normally stopped; no public service is promised. Do not repeat paid calls or historical driver actions merely to inspect saved proof.

## Local walkthrough

1. Follow [local setup](LOCAL_SETUP.md), select an unused loopback API port and sign in privately. Never record bearer credentials.
2. Open `/app`: inspect API readiness, authoritative outcomes, resource versions and controller status. A disconnected API is unknown, not an empty healthy deployment.
3. Open `/app/agents`: select an identity and distinguish cached Redis decisions from PostgreSQL action outcomes. Workflow-definition stages do not claim recorded stage-level execution. A completed bounded run is not a crashed heartbeat.
4. Open `/app/graph`: choose the actual resource and a window no greater than one hour. Inspect committed-action nodes, effect references and cross-agent reversal edges. Empty recent history is valid; never rewrite timestamps.
5. Open `/app/incidents`: select the actual incident, inspect HOLD/verification/recurrence/escalation transitions, citations and persisted report. Deterministic facts/inferences and model hypotheses remain separate. An empty hypotheses array must not be narrated as generated findings.
6. Open `/app/experiments`: compare the same scenario and seeds across the three policies. These latency/throughput values are virtual, not HTTP/Kafka performance. Show unfavorable tradeoffs too.

The public `/` animation is illustrative. Real execution is shown by an authenticated admission followed by a durable outbox row, Kafka delivery, simulator receipt, committed effect and version change. [Architecture](ARCHITECTURE.md).

## Bounded real-system reproduction

Use the isolated benchmark/fault harness rather than operating against an arbitrary development database:

```powershell
# Requires existing isolated PostgreSQL/Kafka/Redis test infrastructure and enough memory.
# Creates only NEW benchmark-owned databases, topics/groups and temporary application containers.
python scripts/run-shared-benchmarks.py --execute --actions 24 --concurrency 1 --repeats 1 --label walkthrough
python scripts/run-shared-benchmarks.py --execute --recovery --actions 1 --concurrency 1 --repeats 1 --label recovery-walkthrough
```

Review [prerequisites, safety and full reproduction commands](BENCHMARKS.md) first. Inspect the emitted result directory: raw action outcomes, database invariants, allowlisted spans, backlog/lag samples and Docker samples. The fault matrix deliberately crashes only its own processes; an acknowledged duplicate must still yield one simulator effect and version increment.

For the controller story, use the existing `scripts/run-live-demo.ps1` and `botkernel.live_demo` only after reviewing their implementation and target state. The eight-action scenario is a deterministic driver presenting two actor identities, not two independently reasoning LLM processes. It writes real simulator actions. Do not execute it as a read-only health check or use `--help` without inspecting CLI behavior.

## Historical private AWS demonstration

The November 14 acceptance already proved the distributed driver, independent deterministic agents, genuine Bedrock advisory outputs, persisted investigation, browser access and monitoring. [Validation](VALIDATION.md) records its scope. The final recorded allocation was full; blindly replaying the driver is unsafe. A fresh recording requires new operating authorization and a reviewed quota/hold/version trajectory. Never reset quota, incidents or effects to manufacture a clean screen.

With an explicitly approved existing-instance operating window and SSM access, private browser forwarding uses this shape:

```powershell
$InstanceId = '<owner-verified-existing-instance>'
$Profile = '<owner-profile>'
aws ssm start-session --profile $Profile --region us-east-2 --target $InstanceId `
  --document-name AWS-StartPortForwardingSession `
  --parameters '{"portNumber":["8080"],"localPortNumber":["18090"]}'
```

Verify the local port is free first. The dashboard routes are `http://127.0.0.1:18090/` and `/app`, `/app/agents`, `/app/graph`, `/app/incidents`, `/app/experiments`. They are unavailable while the host is stopped or the tunnel is absent. Sign in before recording; do not show tokens or private runtime files.

Monitoring used separate private forwards: local/host Grafana `13000/13000`, Prometheus `19090/19090`, Jaeger `16686/16686`. These are historical mappings, not current availability. Inspect actual memory before enabling monitoring, check Prometheus targets, use System/Execution/Collective dashboards and retrieve a real action-correlated trace. CloudWatch is an AWS Console view, not a local proxy. Do not expose ports publicly if SSM is unavailable.

## Recording order and truthful narration

Show landing, Mission Control, Agent Fleet, Effect Graph, incident/report, Experiment Lab, Grafana, Prometheus, Jaeger, CloudWatch and EC2 Compose status. Use one manifest of actual action/incident/report/trace IDs kept privately. Hide account identifiers, credentials and unrelated stacks. Show Nova Micro usage/provider only for actual returned results; the successful Cost/Performance decisions were NO_OP, and no model action executed.

Keep the authorized stop deadline visible privately. Disable inference/action gates, stop only the approved application services without deleting volumes, stop the existing EC2 instance and verify `stopped`. Retained EBS/ECR/log charges continue. [AWS deployment guide](../infra/terraform/README.md).

Kubernetes is a separate local deployment and may be shown as live only after actual pods, PVCs, readiness, a distributed action and restart checks pass. Static Helm render success is not a Kubernetes demonstration. [Runtime procedure](../infra/kubernetes/README.md).


The separate local kind core runtime has now passed acceptance. Its private dashboard was verified at `http://127.0.0.1:18080/app`; see [exact current access and evidence](KUBERNETES_ACCEPTANCE.md). This is local Kubernetes, separate from EC2 Compose.
