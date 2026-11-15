# Observability

Prometheus, three provisioned Grafana dashboards, OpenTelemetry through the Collector to Jaeger, and structured logs observe the real gateway/PostgreSQL/Kafka pipeline. Simulator capacity and latency remain modeled values. See [source](../botkernel/observability.py), [configuration](../observability) and [worker](../botkernel/worker.py).

## Recorded AWS verification

On November 14, 2026, the private AWS deployment showed **5/5 Prometheus targets UP**, a committed-effects gauge of **24**, and real series in System Overview, Distributed Execution Pipeline and Collective Reliability. One Jaeger trace contained **14 spans across API, publisher and worker**. Matching CloudWatch events recorded admission, publication and handling. This is bounded workflow evidence, not a throughput or capacity benchmark.

The deployment was stopped and tunnels closed after acceptance. Saved telemetry is historical, not current health. Prometheus runtime storage and Jaeger traces were ephemeral; restart does not guarantee those series or traces survive. CloudWatch logs were retained, with applicable storage charges. See [public validation evidence](VALIDATION.md).

## Metrics contracts

| Signal | Meaning and limitation |
|---|---|
| `botkernel_http_requests_total`, `botkernel_http_duration_seconds` | Bounded route/method/status-class requests and durations; metrics requests exclude themselves. |
| `botkernel_action_admissions_total` | Best-effort process outcomes; resets at restart and can miss a post-commit crash. PostgreSQL remains authoritative. |
| `botkernel_operations_total`, `botkernel_operation_duration_seconds` | Process attempts for publish, delivery, recovery sweeps and controller ticks; attempts are not unique effects. |
| `botkernel_actions`, `botkernel_incidents` | Current database state gauges; absent states may have no series. |
| `botkernel_outbox_backlog`, `botkernel_committed_effects`, `botkernel_dead_letters`, `botkernel_execution_attempts`, `botkernel_interventions`, `botkernel_recurrences` | PostgreSQL snapshot gauges; they can decrease under retention. |
| `botkernel_incident_transitions_total` | Derived from durable transition rows committed with lifecycle changes. |
| `botkernel_database_scrape_success` | Collection failure indicator; failure does not fabricate zero-valued state. |

Only the API exports shared database totals. Its read-only repeatable-read collector has a dedicated bounded pool and connection, lock and statement timeouts. Process CPU/memory metrics describe instrumented processes, not host totals. Consumer lag and multi-process API metric aggregation remain unimplemented. Scrape availability alone does not prove worker progress.

## Traces and logs

Migration `0006` persists normalized W3C context with admission/outbox data. The publisher restores context and injects Kafka headers; consumer processing follows the asynchronous publish span. Missing or malformed context starts a new trace without rejecting work. Recovery links original context; independently scheduled controller traces link contributing actions rather than claiming synchronous parentage.

The parent-based sampler uses `BOTKERNEL_TRACE_SAMPLE_RATIO` (default `1.0`). Bounded asynchronous export can lose spans without affecting database commits, Kafka offsets or simulator effects. Kafka remains at least once; ambiguous effects require reconciliation against durable evidence.

JSON logs emit bounded allowlisted fields and omit authorization headers, request bodies and arbitrary extras. Transition logs/spans follow the PostgreSQL commit; durable rows remain authoritative if a process exits before emission. Logs/traces do not replace the ledger or constitute a comprehensive audit system.

## Private operation

The Compose `observability` profile supplies monitoring services. Keep UI bindings on loopback and background exporters inside the private network. Operator, agent and metrics credentials must be distinct; the metrics credential permits only `/metrics`. Local API configuration accepts the metrics token while Prometheus reads its configured secret file; AWS mounts that file into the API as well. See [security](../botkernel/security.py) and [Compose configuration](../compose.yaml).

Retain restrictive credential-file permissions and supplied container hardening. Dashboards can be empty before traffic. Folder labels identify the deployment; only simulator resource latency/capacity and Experiment Lab outputs are modeled. Request, process and durable-ledger metrics are real instrumentation. Future AWS startup requires specific approval. Fresh monitoring claims require fresh scrape, dashboard and trace checks. See [roadmap](ROADMAP.md) for storage, restore and availability limits.

## Initial read-only AWS inspection (November 15)

This section records the initial paused-service inspection. The later approved deployment/activity and shutdown are recorded below; initial pending-release and target-status observations are historical.

Read-only inspection confirmed Grafana datasource UID `prometheus` is a provisioned proxy at `http://prometheus:9090`. Querying through Grafana's datasource proxy returned the same **24 committed effects** as the EC2 Prometheus. The old folder/title suffix `local simulation` is misleading deployment labeling, not evidence of a Windows datasource or fake series.

The live API, PostgreSQL, Kafka, Redis, dashboard, Grafana, Prometheus, Collector and Jaeger were running. Publisher/worker/recovery/controller and both agents were intentionally stopped. Gates were `CLOUD_MODE=mock`, with AWS deployment, Bedrock, spending and AI execution disabled. Retained database values: allocation/quota20/20; 24 succeeded actions, receipts/effects24; unpublished outboxes0, unresolved actions0, outstanding reservations0. Live incident state was **two VERIFIED, one ESCALATED**; screenshot observations are not substituted for the current API values.

All three live Grafana UIDs were browser-accessible. Proposed source titles are **System Overview**, **Distributed Execution Pipeline**, **Collective Stability**, with the `BotKernel -` prefix; their UIDs are unchanged. The reviewed source separates folders via Grafana provisioning environment substitution: AWS `BotKernel / AWS Demo`, local `BotKernel / Local`. The running AWS files still need an approved update. [Grafana provisioning contract](https://grafana.com/docs/grafana/latest/administration/provisioning/).

Existing queries were retained; latency expressions are multiplied by1000 and use Grafana unit `ms`. New descriptions distinguish database totals from process counters and explain stopped-service No data. The additional panels use existing API admission/process metrics, not invented telemetry. All25 expressions were parsed successfully by the actual AWS Prometheus, including expressions that correctly returned no series.

### Demonstration queries

Enter these in Prometheus Query and choose Table for current values. Source is `botkernel/observability.py` unless noted; rate windows need enough retained samples.

| Measure | Exact PromQL | Expected meaning |
|---|---|---|
| Target availability | `up` | Prometheus scrape state per instance: gateway1, four background0 while intentionally stopped |
| Healthy targets by job | `sum by (job) (up)` | gateway1/background0; not a count of successful actions |
| API request rate | `sum(rate(botkernel_http_requests_total[5m]))` | Real HTTP responses/sec; safe GETs can populate it |
| API request p95 in ms | `1000 * histogram_quantile(0.95, sum by (le) (rate(botkernel_http_duration_seconds_bucket[5m])))` | Histogram estimate over actual requests; No data/NaN with no observations is not zero latency |
| HTTP 5xx fraction | `sum(rate(botkernel_http_requests_total{category="5xx"}[5m])) / clamp_min(sum(rate(botkernel_http_requests_total[5m])), 0.000000001)` | Includes genuine startup/readiness failures; fraction, not percent multiplied by100 |
| Retained committed effects | `botkernel_committed_effects` |24 durable effect rows at inspection; not24effects/sec |
| Ledger outcomes | `botkernel_actions` |24 SUCCEEDED at inspection, grouped by state |
| Unpublished outbox | `botkernel_outbox_backlog` |0 at inspection; not Kafka consumer lag |
| Execution attempts | `botkernel_execution_attempts` |24 persisted attempts; attempts are not unique effects |
| Dead letters | `botkernel_dead_letters` |0 persisted rows at inspection |
| Database collection success | `botkernel_database_scrape_success` |1 proves current gauge collection; absence/failure must not become a healthy zero |
| Process operations | `sum by (operation,outcome) (rate(botkernel_operations_total[5m]))` |Publication/delivery/recovery/controller attempts. No series is expected with those processes stopped |
| Incident states | `botkernel_incidents` |Current retained state counts, not incident arrival rate |
| Recorded transitions | `botkernel_incident_transitions_total` |Lifetime database transition counts by detected/hold/verification/recurrence/escalation |
| Interventions / recurrences | `botkernel_interventions` / `botkernel_recurrences` |Two separate queries: durable sums6/3 at inspection |
| API resident memory | `process_resident_memory_bytes{job="gateway"}` |Python-process RSS bytes, not EC2 host/container memory |
| API process CPU | `rate(process_cpu_seconds_total{job="gateway"}[5m])` |CPU cores consumed by that process, not host utilization |

No Kafka consumer-lag exporter, per-effect reversal counter or time-aware active-hold gauge was found. Those panels are omitted. Inspect reversals in the graph and exact holds in the incident/telemetry APIs; status counts alone do not determine whether a timed HOLD has expired.

Prometheus scrapes every5seconds. The **running** retention is1day, not the7days in repository Compose. Its TSDB command points to `/tmp/botkernel-prometheus`, whereas the named volume is at `/prometheus`: this is a container-recreation retention risk. Keep the current container while updating Grafana; a TSDB backup/migration and retention change need separate approval. A wide Grafana range cannot recover absent samples, and process restarts reset counters even when durable database gauges survive.

### Current Jaeger workflow

The live v3 discovery endpoint `/api/v3/services` listed `botkernel-api` and `jaeger`. The legacy `/api/services` returned404; that does not mean the Collector is disconnected. An authenticated, sampled GET `/resources` produced a trace retrievable by ID with five actual spans: `fastapi.dependencies`, `fastapi.endpoint`, `fastapi.serialization`, `GET /resources`, `http.server`. Browser trace view also loaded successfully.

Select service `botkernel-api`, a recent lookback (15minutes), then Find Traces; alternatively open `/trace/<private-current-trace-id>`. Read-only API calls prove current ingestion but do not create outbox/Kafka/worker spans. The Collector receives OTLP and exports to `jaeger:4317`; actual API environment points at `http://otel-collector:4318`. The inspected Jaeger command has no explicit durable backend, and current service discovery does not show historical publisher/worker traces. Treat default in-memory traces as ephemeral. [Jaeger v3 API](https://www.jaegertracing.io/docs/2.dev/architecture/apis/).

After separately approved execution, verify actual span relationships and links, rather than assuming one continuous synchronous trace. Preserve sanitized trace evidence before a restart. No live execution was resumed for this inspection.

CloudWatch read-only inspection also returned100 recent existing events across two application streams, including98 structured `http_access` events. Only sanitized event categories/timestamps were retained for this inspection; no log bodies or credentials are published. These are current read-request logs, not newly executed action evidence. The direct Prometheus browser forward became unavailable late in the review, while Grafana's datasource proxy continued to query all five live target series; reopen the forward before recording.

## Approved AWS dry demo and retained evidence (November 15)

The new backend/dashboard and Grafana provisioning were subsequently deployed and verified. The folder is **BotKernel / AWS Demo**, with exactly three existing UIDs: `botkernel-system` (System Overview), `botkernel-execution` (Distributed Execution Pipeline), and `botkernel-collective` (Collective Stability), all with the BotKernel title prefix. Histogram latency panels now multiply seconds by1,000 and display `ms`. Browser inspection showed real plots, descriptions and readable legends; datasource UID `prometheus` remained a proxy to the EC2 Compose service `http://prometheus:9090`.

An execution preflight refused to start four old containers with stale Bedrock enable/spend flags. With separate owner approval those four containers were recreated using the tested backend and all inference/action gates false. Prometheus and all stateful/tracing containers were not recreated. All five scrape targets became UP. The API and four background services therefore supplied actual deployment metrics, not virtual benchmark measurements.

Exactly two approved simulator actions completed:5 ->4 ->5, resource versions10 ->11 ->12, allocation20 ->19 ->20 against quota20. Each had one execution attempt, published outbox, receipt and effect. Durable effects/attempts increased24 ->25 ->26, while backlog/dead letters remained0. New API admission outcomes recorded2 accepted; worker process metrics recorded2 successful publications and2 deliveries. Controller/recovery sweeps were live process operations, not extra logical actions. Existing incident states stayed two VERIFIED/one ESCALATED; there was no incident resolution or new model invocation.

Both action traces were retrieved in Jaeger and opened in the browser: **15 spans each across API, publisher and worker**, including PostgreSQL reservation/outbox, Kafka publication/consumption, simulator receipt and finalization. The sampled caller's parent span was not exported, so Jaeger showed **Incomplete**. The application spans were present; do not insert a synthetic root or describe this as lossless complete tracing. A future instrumented caller should export its real parent span. CloudWatch returned exactly six correlated structured events: admission, publication and handling for each action, using the actual `action.id` field. Private action/trace identifiers and sanitized exports remain outside public documentation.

Before shutdown all13 approved services had zero restarts/OOM, and final database verification found26 successful actions, published outboxes, receipts and effects, with zero unresolved work/reservations/unpublished outboxes. Hashes of the original24 action/outbox/receipt/effect records and saved reports/operator decisions were unchanged. All application services were stopped gracefully. AWS confirmed EC2 **stopped at23:09:09 UTC**, ahead of the01:00 UTC deadline.

### Metrics and trace retention after shutdown

The actual Prometheus TSDB was in a128MiB tmpfs, not its named data volume. A bounded SIGSTOP of the Prometheus process allowed an in-container archive of the frozen TSDB/WAL to retained EBS, followed by SIGCONT and graceful shutdown. Four files totaling2,830,197 bytes and archive/file SHA-256 manifests were preserved in the protected release backups. Docker archive-copy had returned an empty view of the tmpfs; the live WAL remained intact and was preserved by the corrected method.

This is a crash-consistent archive, not a completed restore test. An existing-container restart creates a fresh tmpfs; historical series are not restored automatically. A separately approved mount/restore correction is needed to query those archived samples again. The existing named volume and other application volumes were retained. Jaeger in-memory traces were exported before shutdown but are not expected to survive the restart. For recording, clearly identify archived evidence, or obtain fresh approval for new actions/current traces; never replay the completed dry-run keys or replace missing samples with benchmark figures.
