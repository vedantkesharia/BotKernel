import httpx
import json
import sys
from types import SimpleNamespace

import pytest

from botkernel.real_benchmark import _request, percentile
from botkernel.benchmark_analysis import analyze, main as analyze_main, STAGES
from botkernel.benchmark_runtime import JsonlSpanExporter, require_owned_database, validate_environment


def test_percentiles_interpolate_and_handle_empty_samples():
    assert percentile([], 95) is None
    assert percentile([30, 10, 20], 50) == 20
    assert percentile([10, 20], 95) == 19.5


def test_request_observes_committed_terminal_state():
    def handle(request):
        if request.method == "POST":
            return httpx.Response(202, json={"id": "action-1"})
        return httpx.Response(200, json={"state": "SUCCEEDED"})

    with httpx.Client(base_url="http://benchmark", transport=httpx.MockTransport(handle)) as client:
        row = _request(client, "agent", "resource", 0, 2, "run", "key")
    assert row["action_id"] == "action-1"
    assert row["state"] == "SUCCEEDED"
    assert row["completion_ms"] >= row["admission_ms"] >= 0


def test_rejected_action_has_no_completion_or_action_id():
    with httpx.Client(
        base_url="http://benchmark",
        transport=httpx.MockTransport(lambda request: httpx.Response(409, text="conflict")),
    ) as client:
        row = _request(client, "agent", "resource", 0, 2, "run", "key")
    assert row["state"] == "REJECTED"
    assert row["action_id"] is None
    assert row["completion_ms"] is None


DB = "bk_benchmark_012345abcdef"
TRACE = "1" * 32


@pytest.mark.parametrize("database", ["botkernel", "bk_benchmark", DB + "0", DB + "\n",
                                      "bk_benchmark_012345ABCDEf", "bk_benchmark_../bad"])
def test_owned_database_guard_rejects_other_names(monkeypatch, database):
    monkeypatch.setenv("BOTKERNEL_BENCHMARK_OWNED", "true")
    with pytest.raises(RuntimeError):
        require_owned_database(database)


def test_ownership_is_explicit_and_legacy_is_opt_in(monkeypatch):
    monkeypatch.delenv("BOTKERNEL_BENCHMARK_OWNED", raising=False)
    with pytest.raises(RuntimeError):
        require_owned_database(DB)
    monkeypatch.setenv("BOTKERNEL_BENCHMARK_OWNED", "true")
    require_owned_database(DB)
    require_owned_database("bk_benchmark", allow_legacy=True)


def _safe_environment(monkeypatch):
    monkeypatch.setenv("BOTKERNEL_BENCHMARK_API_URL", "http://bkpubbench-012345abcdef-api:8000")
    monkeypatch.setenv("BOTKERNEL_BENCHMARK_OWNED", "true")
    monkeypatch.setenv("CLOUD_MODE", "mock")
    for key in ("AWS_DEPLOY_ALLOWED", "BEDROCK_ENABLED", "BEDROCK_SPEND_AUTHORIZED", "AI_ACTION_EXECUTION_ENABLED"):
        monkeypatch.setenv(key, "false")
    for key in ("AGENT_PROVIDER", "INVESTIGATOR_PROVIDER"):
        monkeypatch.setenv(key, "deterministic_mock")
    for key in ("KAFKA_TOPIC", "KAFKA_CONSUMER_GROUP"):
        monkeypatch.setenv(key, "bkpubbench_012345abcdef")


@pytest.mark.parametrize("key,value", [("BEDROCK_ENABLED", "true"), ("BEDROCK_SPEND_AUTHORIZED", "true"),
                                      ("AWS_DEPLOY_ALLOWED", "true"), ("AI_ACTION_EXECUTION_ENABLED", "true"),
                                      ("CLOUD_MODE", "aws"), ("AGENT_PROVIDER", "bedrock"),
                                      ("INVESTIGATOR_PROVIDER", "bedrock"), ("KAFKA_TOPIC", "actions"),
                                      ("KAFKA_CONSUMER_GROUP", "executors")])
def test_runtime_rejects_cloud_and_shared_transport(monkeypatch, key, value):
    _safe_environment(monkeypatch)
    validate_environment(DB)
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        validate_environment(DB)


def _raw(carrier=None):
    return {"samples": [{"phase": "measured", "action_id": "a"},
                        {"phase": "warmup", "action_id": "warmup"}],
            "summary": {"authoritative_rows": [{"id": "a", "trace_context": carrier or {
                "traceparent": f"00-{TRACE}-{'a' * 16}-01"}}]}}


def _span(stage, number, start, end, action=None, parent=None, trace=TRACE):
    return {"name": STAGES[stage], "trace_id": trace, "span_id": f"{number:016x}",
            "parent_span_id": parent, "start_time_ns": start * 1_000_000,
            "end_time_ns": end * 1_000_000,
            "attributes": {"action.id": action} if action is not None else {}}


def test_analysis_joins_nested_trace_and_reports_correct_stage_definitions():
    spans = [_span("reserve", 1, 10, 20, parent="a" * 16),
             _span("load", 2, 25, 50, "a"), _span("publish", 3, 30, 45, "a"),
             _span("consume", 4, 40, 90, "a", parent=f"{3:016x}"),
             _span("execute", 5, 42, 80, "a"), _span("finalize", 6, 70, 79, "a"),
             _span("execute", 7, 0, 999, "warmup")]
    result = analyze(_raw(), spans)
    for metric, value in (("outbox_wait_ms", 5), ("dispatch_start_to_consume_ms", 10),
                          ("publication_ms", 15), ("worker_execute_ms", 38), ("finalization_ms", 9)):
        assert result["metrics"][metric] == {"n": 1, "missing_actions": 0, "negative_count": 0,
                                             "p50": value, "p95": value, "p99": value}
    assert "not pure Kafka networking" in result["definitions"]["dispatch_start_to_consume_ms"]
    assert result["backlog_telemetry"] is None


def test_negative_cross_process_deltas_are_retained_and_missing_coverage_reported():
    result = analyze(_raw(), [_span("reserve", 1, 10, 30), _span("load", 2, 20, 25, "a"),
                              _span("publish", 3, 30, 40, "a"), _span("consume", 4, 29, 45, "a")])
    assert result["metrics"]["outbox_wait_ms"]["p50"] == -10
    assert result["metrics"]["outbox_wait_ms"]["negative_count"] == 1
    assert result["metrics"]["dispatch_start_to_consume_ms"]["negative_count"] == 1
    assert result["metrics"]["worker_execute_ms"]["missing_actions"] == 1
    assert result["metrics"]["worker_execute_ms"]["p50"] is None


def test_malformed_provenance_and_span_records_remain_visible(tmp_path):
    raw = _raw({"traceparent": "invalid"})
    raw_path, spans_path, output = (tmp_path / name for name in ("raw.json", "spans.jsonl", "analysis.json"))
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    spans_path.write_text('broken-json\n' + json.dumps(_span("reserve", 1, 1, 2)) + '\n' +
                          json.dumps({"name": "malformed"}) + '\n', encoding="utf-8")
    analyze_main(["--raw", str(raw_path), "--spans", str(spans_path), "--output", str(output)])
    result = json.loads(output.read_text())
    assert result["invalid_or_missing_trace_context"] == 1
    assert result["invalid_spans"] == 1
    assert result["malformed_jsonl_lines"] == 1
    assert result["metrics"]["outbox_wait_ms"]["n"] == 0
    assert json.loads(raw_path.read_text()) == raw
    with pytest.raises(FileExistsError):
        analyze_main(["--raw", str(raw_path), "--spans", str(spans_path), "--output", str(output)])


def test_action_id_join_can_cross_traces_and_duplicate_records_do_not_inflate_n():
    execute = _span("execute", 1, 1, 3, "a", trace="2" * 32)
    result = analyze(_raw(), [execute, execute])
    assert result["metrics"]["worker_execute_ms"]["n"] == 1
    assert result["duplicate_span_records"] == 1


def test_exporter_emits_only_allowed_fields_and_never_overwrites(tmp_path):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    path = tmp_path / "telemetry" / "api.jsonl"
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(path, "api")))
    with provider.get_tracer("test").start_as_current_span("botkernel.action.execute") as span:
        span.set_attributes({"action.id": "a", "http.route": "/actions", "messaging.kafka.offset": 2,
                             "request.body": "secret-body", "authorization": "secret-token"})
        span.add_event("secret-event", {"body": "secret-body"})
    provider.shutdown()
    serialized = path.read_text()
    row = json.loads(serialized)
    assert "secret" not in serialized
    assert row["attributes"] == {"action.id": "a", "http.route": "/actions", "messaging.kafka.offset": 2}
    assert row["start_time_ns"] <= row["end_time_ns"]
    assert len(row["trace_id"]) == 32 and len(row["span_id"]) == 16
    with pytest.raises(FileExistsError):
        JsonlSpanExporter(path, "publisher")


def test_fresh_database_rule_still_rejects_existing_actions(monkeypatch):
    from botkernel import real_benchmark as benchmark
    monkeypatch.setenv("BOTKERNEL_BENCHMARK_OWNED", "true")
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query):
            assert str(query) == "SELECT count(*) FROM actions"
            return SimpleNamespace(scalar_one=lambda: 1)
    monkeypatch.setattr(benchmark, "engine", SimpleNamespace(url=SimpleNamespace(database=DB), begin=Connection))
    with pytest.raises(RuntimeError, match="not fresh"):
        benchmark.run(1, 1, 0, "unused")


def test_sampler_unknown_commits_stay_null_and_database_errors_are_recorded(monkeypatch):
    from botkernel import real_benchmark as benchmark
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "bkpubbench_012345abcdef")
    monkeypatch.setenv("KAFKA_TOPIC", "bkpubbench_012345abcdef")
    sampler = benchmark.BacklogSampler()
    class Consumer:
        def __init__(self, config):
            assert config["enable.auto.commit"] is False
        def list_topics(self, **kwargs):
            return SimpleNamespace(topics={"bkpubbench_012345abcdef": SimpleNamespace(error=None, partitions={0: None, 1: None})})
        def committed(self, partitions, **kwargs):
            sampler.stop_event.set()
            return [SimpleNamespace(partition=p, offset=-1001, error=None) for p in (0, 1)]
        def get_watermark_offsets(self, partition, **kwargs):
            return (0, 4) if partition.partition == 0 else (0, 0)
        def close(self):
            pass
    def unavailable(*args, **kwargs):
        raise RuntimeError("secret database details")
    monkeypatch.setattr(benchmark, "create_engine", unavailable)
    monkeypatch.setitem(sys.modules, "confluent_kafka", SimpleNamespace(
        Consumer=Consumer, TopicPartition=lambda topic, p: SimpleNamespace(partition=p)))
    sampler.thread.start()
    sampler.thread.join(timeout=2)
    result = sampler.stop()
    assert result["coverage"]["consumer_lag"] == 0
    assert result["highwaters"]["consumer_lag"] is None
    assert result["samples"][0]["partitions"] == [
        {"partition": 0, "low": 0, "high": 4, "committed": None, "lag": None},
        {"partition": 1, "low": 0, "high": 0, "committed": None, "lag": 0}]
    assert result["errors"] == [{"stage": "database_setup", "type": "RuntimeError"}]
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize('url', ['https://example.com:8000', 'http://api:8000',
    'http://bkpubbench-012345abcdef-api:8000/other', 'http://user:secret@bkpubbench-012345abcdef-api:8000'])
def test_benchmark_api_cannot_target_unrelated_services(monkeypatch, url):
    from botkernel.benchmark_runtime import benchmark_api_url
    monkeypatch.setenv('BOTKERNEL_BENCHMARK_API_URL', url)
    with pytest.raises(RuntimeError): benchmark_api_url(DB)
