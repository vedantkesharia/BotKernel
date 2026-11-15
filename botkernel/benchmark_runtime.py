"""Opt-in local benchmark wrapper; never initializes or migrates a database."""
import argparse
import json
import os
from pathlib import Path
import re
import runpy
from threading import Lock
from urllib.parse import urlsplit

from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult


OWNED_DATABASE = re.compile(r"bk_benchmark_[0-9a-f]{12}")
SPAN_ATTRIBUTES = frozenset({
    "action.id", "http.route", "messaging.destination",
    "messaging.kafka.partition", "messaging.kafka.offset",
})


def require_owned_database(database, *, allow_legacy=False):
    if os.getenv("BOTKERNEL_BENCHMARK_OWNED") != "true" or not (
        OWNED_DATABASE.fullmatch(database or "") or (allow_legacy and database == "bk_benchmark")
    ):
        raise RuntimeError("A dedicated benchmark-owned database is required")


def benchmark_api_url(database):
    value = os.getenv("BOTKERNEL_BENCHMARK_API_URL", "http://api:8000")
    url = urlsplit(value)
    expected = "api" if database == "bk_benchmark" else "bkpubbench-" + database.removeprefix("bk_benchmark_") + "-api"
    if (url.scheme != "http" or url.hostname != expected or url.port != 8000
            or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment):
        raise RuntimeError("Benchmark API must be the exact private owned runtime")
    return value


def validate_environment(database):
    require_owned_database(database)
    benchmark_api_url(database)
    for key in ("AWS_DEPLOY_ALLOWED", "BEDROCK_ENABLED", "BEDROCK_SPEND_AUTHORIZED",
                "AI_ACTION_EXECUTION_ENABLED"):
        if os.getenv(key, "false").strip().lower() != "false":
            raise RuntimeError(f"Benchmark requires {key}=false")
    if os.getenv("CLOUD_MODE", "mock") != "mock":
        raise RuntimeError("Benchmark requires CLOUD_MODE=mock")
    for key in ("AGENT_PROVIDER", "INVESTIGATOR_PROVIDER"):
        if os.getenv(key, "deterministic_mock") != "deterministic_mock":
            raise RuntimeError(f"Benchmark requires {key}=deterministic_mock")
    for key in ("KAFKA_TOPIC", "KAFKA_CONSUMER_GROUP"):
        value = os.getenv(key, "")
        if not (re.fullmatch(re.escape(database) + r"(?:_[a-z0-9_-]+)?", value)
                or value == "bkpubbench_" + database.removeprefix("bk_benchmark_")):
            raise RuntimeError(f"Benchmark requires unique owned {key} with the database run suffix")


class JsonlSpanExporter(SpanExporter):
    """Strict field allowlist; no events, resources, exception or request payloads."""

    def __init__(self, path, role):
        self.role = role
        self._lock = Lock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation preserves earlier runs and rejects shared role files.
        self._file = Path(path).open("x", encoding="utf-8")

    def export(self, spans):
        try:
            with self._lock:
                for span in spans:
                    self._file.write(json.dumps({
                        "role": self.role, "name": span.name,
                        "trace_id": format(span.context.trace_id, "032x"),
                        "span_id": format(span.context.span_id, "016x"),
                        "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                        "start_time_ns": span.start_time, "end_time_ns": span.end_time,
                        "attributes": {k: v for k, v in (span.attributes or {}).items()
                                       if k in SPAN_ATTRIBUTES and type(v) in (str, int, float, bool)},
                    }, separators=(",", ":")) + "\n")
                self._file.flush()
            return SpanExportResult.SUCCESS
        except (OSError, ValueError):
            return SpanExportResult.FAILURE

    def shutdown(self):
        with self._lock:
            self._file.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=("api", "publisher", "worker"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    from sqlalchemy.engine import make_url
    from botkernel.core import database_url_from_environment
    validate_environment(make_url(database_url_from_environment()).database)
    path = os.getenv("BENCHMARK_SPAN_FILE")
    if not path:
        parser.error("BENCHMARK_SPAN_FILE must name a new, distinct file for each role")
    from botkernel.observability import configure_telemetry
    configure_telemetry(f"botkernel-benchmark-{args.role}")
    provider = trace.get_tracer_provider()
    provider.add_span_processor(BatchSpanProcessor(
        JsonlSpanExporter(path, args.role), max_queue_size=2048,
        max_export_batch_size=256, schedule_delay_millis=100,
        export_timeout_millis=2000,
    ))
    try:
        if args.role == "api":
            import uvicorn
            uvicorn.run("botkernel.api:app", host=args.host, port=args.port)
        else:
            os.environ["ROLE"] = args.role
            runpy.run_module("botkernel.worker", run_name="__main__")
    finally:
        provider.force_flush(timeout_millis=5000)
        provider.shutdown()


if __name__ == "__main__":
    main()
