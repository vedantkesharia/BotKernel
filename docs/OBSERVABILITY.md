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

Retain restrictive credential-file permissions and supplied container hardening. Dashboards can be empty before traffic; simulation labels describe the workload even when AWS hosts it. Future AWS startup requires specific approval. Fresh monitoring claims require fresh scrape, dashboard and trace checks. See [roadmap](ROADMAP.md) for storage, restore and availability limits.
