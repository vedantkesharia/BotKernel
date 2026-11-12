# Local observability

## Local stack

Prometheus, Grafana, the OpenTelemetry Collector and Jaeger are optional Compose-profile services. HTTP host ports bind to loopback; the Collector accepts OTLP only on the private Compose network. The application does not depend on monitoring services for admission or execution. To enable span export, set the OTLP endpoint explicitly; the default is blank and tracing export is disabled.

PowerShell from the repository root:

```powershell
$env:BOTKERNEL_API_PORT='18029'
$env:BOTKERNEL_PROMETHEUS_PORT='19090'
$env:BOTKERNEL_GRAFANA_PORT='13000'
$env:BOTKERNEL_JAEGER_PORT='16686'
$env:BOTKERNEL_OTEL_EXPORTER_OTLP_ENDPOINT='http://otel-collector:4318'
docker compose -p botkernel-observe --profile observability --profile stability up --build -d postgres redis kafka init api publisher worker recovery controller prometheus grafana otel-collector jaeger
Invoke-RestMethod http://127.0.0.1:18029/ready
```

The local API, Prometheus, Grafana and Jaeger UI are at `http://127.0.0.1:18029`, `http://127.0.0.1:19090`, `http://127.0.0.1:13000` and `http://127.0.0.1:16686`. Grafana's provisioned datasource is named `Prometheus` with UID `prometheus`; anonymous Viewer access is only for loopback development. Collector OTLP ports 4317/4318 are not published to the host. Jaeger 2.23.0 is the local trace viewer and uses in-memory storage, so its trace data is lost when the container is recreated. Do not start another project on the same host ports.

Run the isolated PostgreSQL/Kafka suite with:

```powershell
docker compose -p botkernel-observe --profile observability --profile stability run --build --rm --no-deps tests pytest -q
```

Inspect with `docker compose -p botkernel-observe logs --tail 50 api publisher worker recovery controller otel-collector jaeger`. Stop without deleting data using `docker compose -p botkernel-observe --profile observability --profile stability down`; never use `down -v` on development volumes. Prometheus/Grafana state is ephemeral; dashboards are provisioned from `observability/provisioning` and `observability/dashboards`.

## Trace propagation and sampling

The official OpenTelemetry Python API/SDK and OTLP HTTP exporter are used. The application versions resolved in the validated container were 1.45.2; the HTTP transport resolved to 0.66b2. The Collector image is 0.123.0 and Jaeger is 2.23.0. Prometheus and Grafana images are 3.2.1 and 11.6.0. `pyproject.toml` bounds the Python dependencies but does not lock transitive versions.

Migration 0006 adds nullable, shape/length-constrained `outbox.trace_context` and the durable `incident_transitions` table. Admission normalizes W3C `traceparent`/`tracestate` and stores it in the same PostgreSQL transaction as the action and outbox row. The publisher loads that saved context, creates a publish span and injects its context into Kafka headers. A consumer extracts the headers and makes processing a child of that asynchronous publish. Old outbox rows without context and missing or malformed headers start an understandable new trace; invalid propagation data does not reject the action or crash the consumer. Action identity, payload, Kafka delivery semantics and transaction ordering are unchanged.

The recovery sweeper reads the original context from the outbox and adds a span link to recovery execution. Controller evaluations are independently scheduled traces linked to the committed action contexts that supplied their evidence; they are not falsely represented as synchronous child operations. Trace links are bounded and deduplicated.

Spans use a parent-based ratio sampler, defaulting to 1.0 and configurable with `BOTKERNEL_TRACE_SAMPLE_RATIO`. The SDK uses a 2,048-span bounded batch queue, batches up to 256 spans, a 500ms schedule delay and a two-second export timeout. Export is asynchronous; an unavailable Collector may lose spans but does not participate in or block the PostgreSQL transaction, Kafka commit, action admission or simulator effect.

## Structured logs

API, publisher, worker, recovery and controller use JSON logs. The formatter emits timestamp, severity, service/component and a bounded event name; valid trace/span IDs and allowlisted action/incident IDs, outcome, HTTP method/status and Kafka topic/partition/offset are included when available. It omits arbitrary message text, raw request paths/bodies, authorization headers and unrestricted extras. This means exception detail is intentionally not copied into structured events. API access logs use route-free method/status fields.

Logs are process output, not a durable audit log. A log/span for an incident transition is emitted only after its PostgreSQL transaction commits. The durable transition row remains the source of truth if a process exits between commit and log emission.

## Metrics and semantics

- `botkernel_http_requests_total{route,method,category}` and `botkernel_http_duration_seconds{route,method}` describe bounded HTTP route-template/status classes and durations. Unmatched routes collapse to `unmatched`; `/metrics` does not count itself.
- `botkernel_action_admissions_total{outcome}` has the fixed outcomes `accepted`, `validation_rejected`, `resource_conflict`, `quota_rejected`, `policy_rejected`, `dependency_failure` and `unexpected_error`. It is a best-effort process counter, resets at restart, and can undercount if the process exits after PostgreSQL commit but before incrementing. It is not an authoritative admission ledger.
- `botkernel_operations_total{operation,outcome}` and `botkernel_operation_duration_seconds{operation}` count process attempts for publication, delivery, recovery sweeps and controller ticks. They are not durable effects; a recovery sweep is a batch, not a count of individual reconciliations.
- `botkernel_actions{state}` and `botkernel_incidents{status}` are current PostgreSQL state gauges. Absent states have no series.
- `botkernel_outbox_backlog`, `botkernel_committed_effects`, `botkernel_dead_letters`, `botkernel_execution_attempts`, `botkernel_interventions` and `botkernel_recurrences` are database snapshot gauges. They can decrease under retention and should not be treated as monotonically increasing counters.
- `botkernel_incident_transitions_total{transition}` is derived from durable PostgreSQL transition rows, written in the same transaction as the lifecycle change. Replayed/idempotent API requests do not create a second transition unless a state transition commits.
- `botkernel_database_scrape_success` distinguishes a successful snapshot from collection failure. On a database error, the collector emits this failure gauge only rather than fabricating zero-valued state.
- Standard Prometheus process CPU/memory series describe each instrumented process, not the host or whole container.

Only the API exports shared database totals, preventing worker-replica summation. The collector uses a dedicated one-connection pool with a 250ms pool-acquisition timeout, one-second PostgreSQL connect timeout, 500ms lock timeout and two-second statement timeout. It reads a read-only repeatable-read snapshot. The query still scans durable tables and should be profiled as retention grows; multi-process API metric aggregation and consumer lag are not implemented. Prometheus scrapes every five seconds with a four-second scrape timeout. `/metrics` is loopback-only in the supplied Compose stack and is not an authenticated public endpoint.

## Grafana

Three provisioned dashboards are available: System Overview, Distributed Execution Pipeline and Collective Reliability. They use the provisioned local Prometheus datasource. Scrape availability is not equivalent to worker progress/readiness; histograms may be empty before requests occur. These charts use actual local service metrics, not discrete-event simulation output.

All three dashboards were browser-reviewed at a desktop viewport with real API and worker data. Panels loaded without browser/query errors or “No data” states during the review. The Prometheus datasource proxy returned an actual committed-effect sample (34 at the final check); all five configured scrape targets—gateway, publisher, worker, recovery and controller—were `up`. This review is not a mobile-layout or production usability certification.

## Verified execution evidence (2026-11-08)

The isolated `botkernel-trace-verification` Compose project used PostgreSQL, Kafka, Redis, API, publisher, worker, recovery, controller, Collector and Jaeger with API port 18039 and Jaeger UI port 16687. Its bounded real gateway/outbox/Kafka/controller demo committed eight actions and demonstrated `HOLD -> VERIFIED -> HOLD`, one recurrence and two interventions.

Jaeger trace `9d0ac2f258bc9241182ecda4fd654935` for action `ab543534-d952-4e66-ad44-e414e8664c99` contained 14 spans across the API, publisher and worker: `http.server`, FastAPI dependency/endpoint/serialization spans, `botkernel.http.action_submit`, `botkernel.action.admission`, `botkernel.postgresql.reserve_and_outbox`, `botkernel.outbox.load`, `botkernel.kafka.publish`, `botkernel.kafka.consume`, `botkernel.action.execute`, `botkernel.postgresql.mark_dispatched`, `botkernel.simulator.commit_receipt` and `botkernel.postgresql.finalize_action`. Publisher and worker JSON log records carried the same trace ID and action ID. Controller `botkernel.stability.resource_evaluation` spans were in separate traces with `FOLLOWS_FROM` links to the action trace.

A second real action (`66dfbe32-821f-4d73-9798-39fecc5065db`) was crashed after its simulator receipt but before ledger finalization. PostgreSQL showed `DISPATCHED`, one receipt and no effect. The recovery worker completed the action; restarting the Kafka worker replayed the event, leaving one receipt, one committed effect and one resource-version increment. The recovery execution trace `dfd04f3f8f64143c3a2aa277a4a6c92e` included `botkernel.recovery.sweep` and `botkernel.action.execute`; that execution span linked with `FOLLOWS_FROM` to origin trace `7f17fe07616d7f4de29a8929c152534b`. Advancing the action's persisted retry deadline to now was used only to avoid waiting through the normal 30-second retry backoff; the recovery process performed the real reconciliation.

With the Collector stopped, a separate gateway action (`95e88d67-e455-4f63-97b9-b14038296d95`) reached `SUCCEEDED` in 0.31 seconds. The Collector was restarted and `/ready` returned 200. This confirms execution independence, not trace retention during an outage.

The complete PostgreSQL/Kafka integration suite passed twice after the final code change: 54 passed in 69.81s and 54 passed in 72.60s. Each run reported one existing Starlette/httpx deprecation warning. The suite includes isolated migration tests, persisted trace-context validation, malformed Kafka trace headers, duplicate delivery/replay and simulator crash recovery. Compose configuration and API readiness were validated.

## Limits and safety

No measured PostgreSQL/Kafka latency, throughput, CPU or memory benchmark was run; simulation results are not backend performance evidence. No frontend files were changed and no React test/build was run. No consumer-lag metric, authenticated operator access, durable trace storage, multi-process API metrics aggregation or production retention policy is claimed. Collector failure can drop telemetry by design. Controller causality is represented by span links because controller evaluations are asynchronous.

The `botkernel-observe` development database retains the task's demo data. Its total resource capacity was restored to 18 against a quota of 20 using a gateway-ledger scale-down; no existing rows or volumes were deleted. The isolated trace-verification stack and its newly created volumes remain running for inspection. Stop either project with `docker compose -p <project> down` and do not add `-v`.

No AWS APIs, credentials, paid inference, Terraform operations or cloud resources were used. No AWS spend occurred.
