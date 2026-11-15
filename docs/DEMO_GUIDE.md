# AWS dry demonstration and recording

Use only a private, owner-approved operating session. November 14 distributed/Bedrock acceptance and the November 15 two-action dry demo are recorded evidence, not an always-on service. The latest run finished with **26 committed effects**, no unresolved actions and AWS-confirmed **stopped** EC2 at 23:09:09 UTC. This guide does not authorize another startup, action, incident decision or model call. Keep the next approved stop deadline visible privately.

## Private browser tabs

| View | Address |
|---|---|
| Landing | `http://127.0.0.1:18090/` |
| Mission Control | `http://127.0.0.1:18090/app` |
| Agent Fleet | `http://127.0.0.1:18090/app/agents` |
| Effect Graph | `http://127.0.0.1:18090/app/graph` |
| Investigations | `http://127.0.0.1:18090/app/incidents` |
| Experiment Lab | `http://127.0.0.1:18090/app/experiments` |
| Grafana | `http://127.0.0.1:13000` |
| Prometheus | `http://127.0.0.1:19090` |
| Jaeger | `http://127.0.0.1:16686` |

These are browser-side SSM forwards to EC2 loopback ports 8080, 13000, 19090 and 16686 respectively, not local development services. They work only while the actual tunnels and approved host run. Never expose public ingress to replace a tunnel. Sign in before recording, keep credentials out of screenshots and avoid terminals containing private environment files.

For an approved running session, set `BOTKERNEL_INSTANCE_ID` privately to the existing instance. Check each local port is free before opening a replacement tunnel; preserve any working tunnel. Run each command in its own PowerShell terminal:

```powershell
aws ssm start-session --profile botkernel-dev --region us-east-2 --target $env:BOTKERNEL_INSTANCE_ID --document-name AWS-StartPortForwardingSession --parameters "portNumber=8080,localPortNumber=18090"
aws ssm start-session --profile botkernel-dev --region us-east-2 --target $env:BOTKERNEL_INSTANCE_ID --document-name AWS-StartPortForwardingSession --parameters "portNumber=13000,localPortNumber=13000"
aws ssm start-session --profile botkernel-dev --region us-east-2 --target $env:BOTKERNEL_INSTANCE_ID --document-name AWS-StartPortForwardingSession --parameters "portNumber=19090,localPortNumber=19090"
aws ssm start-session --profile botkernel-dev --region us-east-2 --target $env:BOTKERNEL_INSTANCE_ID --document-name AWS-StartPortForwardingSession --parameters "portNumber=16686,localPortNumber=16686"
```

All four forwards were verified during the approved dry demo. They are unavailable after EC2 shutdown; do not present these addresses as continuously hosted services. The official Session Manager plugin must also be available in the terminal's PATH.

## Click-by-click walkthrough

| Step | Click / input | Observe and explain | Evidence kind |
|---|---|---|---|
| 1 | Open `/`, then Launch Console | The orchestration illustration describes the architecture; it is not production telemetry | Illustrative |
| 2 | Sign in privately; open `/app` | API connection, action outcomes, allocations and incident summary. Explain that PostgreSQL owns correctness | Live read of retained database |
| 3 | Open `/app/agents`; select an identity | Distinguish completed bounded processes, cached Redis decisions, PostgreSQL outcomes and actual provider/model usage. Cost/Performance Bedrock acceptance returned advisory NO_OP | Historical provenance; no model invocation |
| 4 | Inspect recent action records and resource versions | Admission created an action/outbox; Kafka carried its ID; receipt and finalization recorded one simulator effect. Effects are not EC2 resizing | Historical real execution over simulated resources |
| 5 | Open `/app/graph`; choose Last 7 days, then a resource/incident and an action node | Inspect committed effects and inferred reversal edges, then source/target evidence. All history returns the newest 1,000 effects at most; heed truncation notices | Historical committed evidence |
| 6 | Open `/app/incidents`; select the newest VERIFIED incident with two interventions, one recurrence and 21 healthy samples | Show lifecycle and selective containment. Preserve its state. Do not click Resolve/Acknowledge | Historical deterministic control |
| 7 | Read the saved report and evidence classification | Verified facts, deterministic inferences and hypotheses remain distinct. The selected VERIFIED incident's saved report is deterministic; inspect the existing historical Bedrock report separately using the operator's private evidence manifest | Persisted reports; no Analyze click |
| 8 | Open `/app/experiments`; select a saved comparison/scenario | Compare independent/basic/collective results and unfavorable latency/false-positive tradeoffs. Do not generate another experiment merely for the recording | Modeled virtual results |
| 9 | Grafana: open UID `botkernel-system`, choose Last 15 minutes and 10-second refresh | Actual API request rate, p95 in milliseconds, error fraction, scrape health and process metrics where available. Folder is BotKernel / AWS Demo | Live monitoring when running |
| 10 | Grafana: UID `botkernel-execution` | Retained effects/attempts ended at26 with zero backlog/dead letters. Saved dry-run plots show24 ->25 ->26 and real publication/delivery events. New process rates require current traffic | Live scrape of historical rows; archived dry-run time series |
| 11 | Grafana: UID `botkernel-collective` | Show current incident-state counts, durable interventions/recurrences and transitions. Do not narrate lifetime sums as new events | Live scrape of retained controller evidence |
| 12 | Prometheus Query: enter `up`, select Table; repeat `sum by (job) (up)` | The dry run verified5/5 UP: gateway1/background4. Stopped services legitimately become DOWN. Use the exact queries in [observability](OBSERVABILITY.md) | Live scrape status when running |
| 13 | Jaeger: select `botkernel-api`, Last 15 minutes, Find Traces; use a current action trace from the private manifest | Both dry actions produced15 spans across API/publisher/worker. The unexported caller parent causes an Incomplete marker. Historical exports are saved; in-memory traces do not survive shutdown | Actual distributed trace, current or explicitly archived |
| 14 | In the owner's private SSM terminal run `docker compose --env-file runtime.env -f compose.aws-demo.yaml ps -a` from `/opt/botkernel` | Show actual EC2 services and explain which roles are approved to run. Hide registry/account identifiers before recording. Never display tokens or environment-file contents | Live AWS Docker evidence |
| 15 | End within the approved window; quiesce approved work, close owned tunnels, stop the approved application and existing EC2, verify `stopped` | Preserve volumes, database, Kafka, Redis, reports and checkpoints; retained EBS/ECR/log charges continue | Authorized operating procedure |

The deployed backend/dashboard passed actual AWS historical-graph acceptance: Last hour / Last24 hours each returned the two new effects; Last7 days (default) / All history returned all26 at the dry-run checkpoint. These are observed windows, not permanent counts. All history is capped at the newest1,000 effects with a truncation notice. Choose Last7 days or All history for later recordings; never alter evidence timestamps. The telemetry endpoint's eight-effects-per-resource limit does not define the graph's evidence set.

Do not confuse the deterministic driver, two independent LangGraph processes and sequential advisory Bedrock acceptance. No paid model test needs repeating for this dry run. The successful Investigator returned an empty hypotheses list; do not invent findings. Preserve existing VERIFIED and ESCALATED incidents.

## Verified bounded activity - do not replay

The owner explicitly approved this completed simulator-only trajectory after checking allocation/quota20/20, no reservations/holds on the selected resource, no unresolved actions and no unpublished outboxes:

1. An initial safety check refused to start four old containers whose Bedrock enable/spend flags were still true. With separate owner approval, only those four roles were recreated using the tested backend and all inference/action gates false. No model request occurred.
2. Two uniquely registered scripted identities submitted exactly one gateway POST each. These were not independently reasoning LLM agents.
3. Downscale5 ->4: resource version10 ->11, allocation20 ->19, effects/receipts24 ->25.
4. Restore4 ->5: version11 ->12, allocation19 ->20, effects/receipts25 ->26.
5. Each action returned202, completed in one attempt and had one published outbox, one receipt and one effect. The original24 action/outbox/receipt/effect records and reports/operator decisions remained unchanged. Final unresolved/reservations/unpublished counts were zero.

Use the private manifest to inspect these actual records; do not hardcode operational IDs into public scripts. Do not resubmit the dry-run keys or run the final eight-action driver. Any further activity needs fresh approval, observed versions, new identities/keys and a safe quota trajectory. Stop on a hold, conflict, pending work or ambiguous submission. Never reset quota or clear holds. No new incident was expected from two changes; existing states stayed VERIFIED/ESCALATED/VERIFIED, and no incident was resolved.

Each actual trace includes admission/reservation, outbox loading, Kafka publication/consumption, simulator receipt and finalization. The supplied sampled caller-parent IDs were not exported, so Jaeger labels the traces Incomplete; do not insert invented root spans to hide that. A future approved instrumented caller should export its real parent span. CloudWatch retained three matching admission/publication/handling events per action. Live inference stayed disabled throughout.

## Verified release and safe operation

The immutable release `demo-polish-20261115-01` was built, pushed and deployed by verified digest. It is now used and must never be overwritten. The approved release contained:

- Backend: bounded historical graph query and validation; no schema migration.
- Dashboard: incident sizing/tooltip/textarea/focus fixes and graph controls.
- Provisioning: neutral dashboard titles, millisecond latency units, descriptions/legends and environment-specific folders. Datasource UID and dashboard UIDs stay the same.
- AWS Compose: Grafana receives `BOTKERNEL_GRAFANA_FOLDER=BotKernel / AWS Demo`; local Compose uses `BotKernel / Local`.

Only the two application images were pushed. API/dashboard/Grafana were recreated first; the four execution roles were recreated only after the separate safety-correction approval. Prometheus, PostgreSQL, Kafka, Redis, Collector and Jaeger retained their container IDs throughout deployment. Protected pre/post database/config backups and rollback references are on retained EBS. An early transfer-script failure was rolled back before new values were applied; the corrected attempt was separately approved and verified. No migration, IAM, Terraform or networking change occurred.

For a future approved recording window, start existing containers deliberately after EC2/SSM is ready. Do not rebuild or redeploy this release just to show it. In a private SSM terminal:

```bash
cd /opt/botkernel
# Start existing data containers; wait for their health before the application.
docker compose --env-file runtime.env -f compose.aws-demo.yaml start postgres redis kafka
docker compose --env-file runtime.env -f compose.aws-demo.yaml ps -a
# After all three dependencies are healthy, start only approved application/monitoring services.
docker compose --env-file runtime.env -f compose.aws-demo.yaml --profile observability start api dashboard prometheus grafana jaeger otel-collector
curl -fsS http://127.0.0.1:8080/api/ready
```

Before starting execution roles, inspect actual stored environment gates, image digests, unresolved ledger/outbox, holds and reservations. Include the reviewed `compose.metrics-access.yaml` and `compose.dry-roles-safe.yaml` overrides in any future approved configuration-changing operation. Never use a broad `up` helper that silently recreates Prometheus or starts optional agents. Do not start old optional agent containers with unreviewed stored environments. Reusing dashboard UIDs preserved exactly three dashboards; the empty legacy folder is not a duplicate dashboard.

Rollback restores the saved configuration and prior backend/dashboard digests, then recreates only the same approved services. No database restore/reset is required for this read-only API/UI change. Keep inference and action gates false throughout.

**Prometheus preservation:** its deployed override writes a one-day TSDB to tmpfs `/tmp/botkernel-prometheus`, while the named volume is at `/prometheus`. Before shutdown, the real TSDB/WAL was archived from a bounded frozen process onto retained EBS: four files/2,830,197 bytes, with SHA-256 manifests. Docker archive-copy did not expose the tmpfs, so an in-container archive was required. The snapshot is crash-consistent; a full restore drill has not been performed. Starting the existing container creates a fresh tmpfs and does not automatically restore that archive. Persistent-mount correction/restore requires separate approval; never claim saved24 ->26 plots reappear automatically. Jaeger also has ephemeral storage: preserve exports, and distinguish archived traces from current live data.

## Local development and separate Kubernetes proof

Use [local setup](LOCAL_SETUP.md), [benchmarks](BENCHMARKS.md) and [kind acceptance](KUBERNETES_ACCEPTANCE.md). The new UI was checked against a separate API with PostgreSQL read-only transactions over retained local data, not fabricated AWS results. Core kind acceptance is separate from this EC2 Compose demonstration; EKS was not deployed.
