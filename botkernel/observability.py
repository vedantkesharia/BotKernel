"""Bounded operational metrics, tracing, and structured logging."""
import json
import logging
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock

from opentelemetry import context as otel_context
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanLimits, TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace import Link, SpanKind, Status, StatusCode
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from sqlalchemy import create_engine, text


REQUESTS = Counter("botkernel_http_requests_total", "HTTP responses", ["route", "method", "category"])
DURATION = Histogram("botkernel_http_duration_seconds", "HTTP duration", ["route", "method"])
OPERATIONS = Counter("botkernel_operations_total", "Process operations, not durable effects", ["operation", "outcome"])
OP_DURATION = Histogram("botkernel_operation_duration_seconds", "Process operation duration", ["operation"])
ADMISSIONS = Counter(
    "botkernel_action_admissions_total",
    "Best-effort API admission outcomes; process-local and reset on restart",
    ["outcome"],
)

ADMISSION_OUTCOMES = frozenset({
    "accepted",
    "validation_rejected",
    "resource_conflict",
    "quota_rejected",
    "policy_rejected",
    "dependency_failure",
    "unexpected_error",
})
_TRACE_KEYS = frozenset({"traceparent", "tracestate"})
_TRACEPARENT = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
_CONFIG_LOCK = Lock()
_TELEMETRY_CONFIGURED = False
_LOGGING_CONFIGURED = False
_PROPAGATOR = TraceContextTextMapPropagator()
_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "botkernel")
_ATTRIBUTE_ALLOWLIST = frozenset({
    "action.id",
    "incident.id",
    "messaging.destination",
    "messaging.kafka.partition",
    "messaging.kafka.offset",
    "botkernel.outcome",
    "db.system",
    "db.operation",
    "http.route",
    "http.request.method",
    "http.response.status_code",
})


def configure_telemetry(service_name=None):
    """Configure bounded asynchronous OTLP export once per process."""
    global _TELEMETRY_CONFIGURED, _SERVICE_NAME
    with _CONFIG_LOCK:
        if _TELEMETRY_CONFIGURED:
            return
        _SERVICE_NAME = service_name or os.getenv("OTEL_SERVICE_NAME", "botkernel")
        resource = Resource.create({"service.name": _SERVICE_NAME})
        sample_ratio = float(os.getenv("BOTKERNEL_TRACE_SAMPLE_RATIO", "1.0"))
        if not 0 <= sample_ratio <= 1:
            raise ValueError("BOTKERNEL_TRACE_SAMPLE_RATIO must be between 0 and 1")
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(TraceIdRatioBased(sample_ratio)),
            span_limits=SpanLimits(max_attributes=32, max_events=16, max_links=32),
        )
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip().rstrip("/")
        if endpoint:
            trace_endpoint = endpoint if endpoint.endswith("/v1/traces") else endpoint + "/v1/traces"
            exporter = OTLPSpanExporter(endpoint=trace_endpoint, timeout=2)
            provider.add_span_processor(BatchSpanProcessor(
                exporter,
                max_queue_size=2048,
                max_export_batch_size=256,
                schedule_delay_millis=500,
                export_timeout_millis=2000,
            ))
        trace.set_tracer_provider(provider)
        propagate.set_global_textmap(_PROPAGATOR)
        _TELEMETRY_CONFIGURED = True


def _tracer():
    configure_telemetry()
    return trace.get_tracer("botkernel")


@contextmanager
def traced_span(name, attributes=None, parent_context=None, links=None, kind=SpanKind.INTERNAL):
    safe_attributes = {
        key: value
        for key, value in (attributes or {}).items()
        if key in _ATTRIBUTE_ALLOWLIST and isinstance(value, (str, bool, int, float))
    }
    with _tracer().start_as_current_span(
        name,
        context=parent_context,
        links=links,
        kind=kind,
        attributes=safe_attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except Exception:
            span.set_status(Status(StatusCode.ERROR))
            raise


def _clean_carrier(carrier):
    if not isinstance(carrier, dict):
        return {}
    clean = {}
    for key in _TRACE_KEYS:
        value = carrier.get(key)
        if isinstance(value, bytes):
            try:
                value = value.decode("ascii")
            except UnicodeDecodeError:
                continue
        if not isinstance(value, str):
            continue
        if len(value) > (55 if key == "traceparent" else 512):
            continue
        if any(ord(char) < 0x20 or ord(char) > 0x7E for char in value):
            continue
        clean[key] = value
    parent = clean.get("traceparent", "")
    if not _TRACEPARENT.fullmatch(parent):
        return {}
    if parent[3:35] == "0" * 32 or parent[36:52] == "0" * 16:
        return {}
    return clean


def normalize_trace_context(carrier):
    """Validate W3C context and return only canonical traceparent/tracestate."""
    clean = _clean_carrier(carrier)
    if not clean:
        return None
    extracted = _PROPAGATOR.extract(clean)
    span_context = trace.get_current_span(extracted).get_span_context()
    if not span_context.is_valid:
        return None
    normalized = {}
    _PROPAGATOR.inject(normalized, context=extracted)
    return {key: normalized[key] for key in _TRACE_KEYS if key in normalized}


def capture_trace_context():
    carrier = {}
    _PROPAGATOR.inject(carrier)
    return normalize_trace_context(carrier)


def extract_trace_context(carrier):
    normalized = normalize_trace_context(carrier)
    return _PROPAGATOR.extract(normalized) if normalized else otel_context.Context()


def trace_context_from_kafka(headers):
    carrier = {}
    for key, value in headers or ():
        if key in _TRACE_KEYS:
            carrier[key] = value
    return extract_trace_context(carrier)


def span_links_from_carriers(carriers, limit=32):
    links = []
    seen = set()
    for carrier in carriers:
        normalized = normalize_trace_context(carrier or {})
        if not normalized:
            continue
        context = _PROPAGATOR.extract(normalized)
        span_context = trace.get_current_span(context).get_span_context()
        key = (span_context.trace_id, span_context.span_id)
        if key in seen:
            continue
        seen.add(key)
        links.append(Link(span_context))
        if len(links) >= limit:
            break
    return links


def _current_ids():
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return {}
    return {
        "trace_id": format(span_context.trace_id, "032x"),
        "span_id": format(span_context.span_id, "016x"),
    }


class JsonLogFormatter(logging.Formatter):
    """Emit a strict allowlist; arbitrary message bodies and extras are omitted."""

    def format(self, record):
        event = getattr(record, "event", None)
        if record.name == "uvicorn.access" and isinstance(record.args, tuple) and len(record.args) >= 5:
            event = "http_access"
        if not isinstance(event, str) or not event:
            event = "log_message"
        result = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "severity": record.levelname,
            "service": _SERVICE_NAME,
            "component": record.name[:80],
            "event": event[:100],
        }
        result.update(_current_ids())
        for key in _ATTRIBUTE_ALLOWLIST:
            value = getattr(record, key.replace(".", "_"), None)
            if isinstance(value, (str, bool, int, float)):
                result[key] = value
        if event in {"bedrock_failure", "investigation_bedrock_failure"}:
            diagnostics = getattr(record, "bedrock_diagnostics", None)
            if isinstance(diagnostics, dict):
                safe = {}
                for key in ("category", "stage", "exception_type", "missing_module", "aws_error_code",
                            "request_id", "boto3_version", "botocore_version", "timeout"):
                    value = diagnostics.get(key)
                    if value is None or (isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value)):
                        safe[key] = value
                status = diagnostics.get("http_status")
                if status is None or (type(status) is int and 100 <= status <= 599):
                    safe["http_status"] = status
                for key in ("response_received", "remote_outcome_unknown"):
                    if type(diagnostics.get(key)) is bool:
                        safe[key] = diagnostics[key]
                result["bedrock"] = safe
        if event == "http_access":
            method = record.args[1]
            status = record.args[4]
            if isinstance(method, str) and method in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                result["http.request.method"] = method
            if isinstance(status, int):
                result["http.response.status_code"] = status
        return json.dumps(result, separators=(",", ":"), ensure_ascii=True)


def configure_logging(service_name=None):
    global _LOGGING_CONFIGURED, _SERVICE_NAME
    if service_name:
        _SERVICE_NAME = service_name
    root = logging.getLogger()
    if not _LOGGING_CONFIGURED:
        existing_json = False
        for handler in root.handlers:
            handler.setFormatter(JsonLogFormatter())
            existing_json = existing_json or getattr(handler, "_botkernel_json", False)
        if not existing_json:
            handler = logging.StreamHandler()
            handler.setFormatter(JsonLogFormatter())
            handler._botkernel_json = True
            root.addHandler(handler)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            for handler in logging.getLogger(name).handlers:
                handler.setFormatter(JsonLogFormatter())
        root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        _LOGGING_CONFIGURED = True


@contextmanager
def operation(name):
    started = time.monotonic()
    try:
        yield
    except Exception:
        OPERATIONS.labels(name, "error").inc()
        raise
    else:
        OPERATIONS.labels(name, "success").inc()
    finally:
        OP_DURATION.labels(name).observe(time.monotonic() - started)


class DurableCollector:
    def __init__(self, engine):
        self.engine = engine

    def collect(self):
        try:
            with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
                with connection.begin():
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    connection.execute(text("SET LOCAL statement_timeout = '2000ms'"))
                    connection.execute(text("SET LOCAL lock_timeout = '500ms'"))
                    rows = connection.execute(text("""
                        SELECT 'actions'::text AS metric, state::text AS label, count(*)::bigint AS value
                        FROM actions GROUP BY state
                        UNION ALL
                        SELECT 'incidents', status::text, count(*)::bigint FROM incidents GROUP BY status
                        UNION ALL SELECT 'outbox_backlog', NULL::text, count(*)::bigint FROM outbox WHERE NOT published
                        UNION ALL SELECT 'committed_effects', NULL::text, count(*)::bigint FROM effects
                        UNION ALL SELECT 'dead_letters', NULL::text, count(*)::bigint FROM dead_letters
                        UNION ALL SELECT 'execution_attempts', NULL::text, coalesce(sum(attempts),0)::bigint FROM actions
                        UNION ALL SELECT 'interventions', NULL::text, coalesce(sum(intervention_count),0)::bigint FROM incidents
                        UNION ALL SELECT 'recurrences', NULL::text, coalesce(sum(recurrence_count),0)::bigint FROM incidents
                        UNION ALL SELECT 'incident_transition', transition, count(*)::bigint
                        FROM incident_transitions GROUP BY transition
                    """)).all()
            grouped = {}
            for name, label, value in rows:
                grouped.setdefault(name, []).append((label, value))
            metrics = []
            for name, label in (("actions", "state"), ("incidents", "status")):
                metric = GaugeMetricFamily("botkernel_" + name, "Current durable rows by state", labels=[label])
                for state, count in grouped.get(name, []):
                    metric.add_metric([state], count)
                metrics.append(metric)
            for name in (
                "outbox_backlog",
                "committed_effects",
                "dead_letters",
                "execution_attempts",
                "interventions",
                "recurrences",
            ):
                value = grouped.get(name, [(None, 0)])[0][1]
                metrics.append(GaugeMetricFamily(
                    "botkernel_" + name,
                    "Durable database snapshot; may decrease on retention",
                    value=value,
                ))
            transitions = CounterMetricFamily(
                "botkernel_incident_transitions",
                "Durable incident lifecycle transitions committed in PostgreSQL",
                labels=["transition"],
            )
            for transition, count in grouped.get("incident_transition", []):
                transitions.add_metric([transition], count)
            metrics.extend((transitions, GaugeMetricFamily(
                "botkernel_database_scrape_success",
                "Database snapshot available",
                value=1,
            )))
            yield from metrics
        except Exception:
            yield GaugeMetricFamily(
                "botkernel_database_scrape_success",
                "Database snapshot available",
                value=0,
            )


def _metrics_engine(engine):
    return create_engine(
        engine.url,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.25,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 1},
    )


def install_api(app, engine):
    from fastapi.responses import Response

    configure_telemetry(os.getenv("OTEL_SERVICE_NAME", "botkernel-api"))
    configure_logging(os.getenv("OTEL_SERVICE_NAME", "botkernel-api"))
    registry = CollectorRegistry()
    registry.register(DurableCollector(_metrics_engine(engine)))

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(REGISTRY) + generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def measure(request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        started = time.monotonic()
        status = 500
        try:
            parent_context = extract_trace_context({
                "traceparent": request.headers.get("traceparent"),
                "tracestate": request.headers.get("tracestate"),
            })
            with traced_span(
                "http.server",
                {"http.request.method": request.method},
                parent_context=parent_context,
                kind=SpanKind.SERVER,
            ) as span:
                response = await call_next(request)
                status = response.status_code
                span.set_attribute("http.response.status_code", status)
                route = getattr(request.scope.get("route"), "path", "unmatched")
                if route != "unmatched":
                    span.set_attribute("http.route", route)
                return response
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            method = request.method if request.method in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"} else "OTHER"
            REQUESTS.labels(route, method, str(status // 100) + "xx").inc()
            DURATION.labels(route, method).observe(time.monotonic() - started)
            if route == "/actions":
                if status == 422:
                    ADMISSIONS.labels("validation_rejected").inc()
                elif status >= 500:
                    ADMISSIONS.labels("unexpected_error").inc()
