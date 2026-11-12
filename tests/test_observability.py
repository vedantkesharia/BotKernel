from botkernel.security import operator_headers
import json
import logging

from fastapi.testclient import TestClient
from botkernel.api import app
from botkernel.core import engine
from botkernel.observability import (
    ADMISSIONS,
    DurableCollector,
    JsonLogFormatter,
    REQUESTS,
    extract_trace_context,
    normalize_trace_context,
    span_links_from_carriers,
    traced_span,
)
from opentelemetry import trace


def test_scrapes_do_not_count_themselves():
    client = TestClient(app, headers=operator_headers())
    before = list(REQUESTS.collect())[0].samples
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "botkernel_database_scrape_success 1.0" in response.text
    assert list(REQUESTS.collect())[0].samples == before
    assert "botkernel_committed_effects" in response.text


def test_bounded_unknown_routes():
    client = TestClient(app, headers=operator_headers())
    client.get("/unknown-private-value")
    body = client.get("/metrics").text
    assert 'route="unmatched"' in body
    assert "unknown-private-value" not in body


def test_database_failure_does_not_raise_from_collector():
    class Broken:
        def begin(self):
            raise RuntimeError("private failure details")
    metrics = list(DurableCollector(Broken()).collect())
    assert len(metrics) == 1
    assert metrics[0].samples[0].value == 0
    assert "private" not in str(metrics)


def test_durable_effect_metric_matches_authority():
    from sqlalchemy import text
    with engine.connect() as c:
        count = c.execute(text("SELECT count(*) FROM effects")).scalar_one()
    values = {m.name: m.samples[0].value for m in DurableCollector(engine).collect() if m.samples}
    assert values["botkernel_committed_effects"] == count


def test_trace_context_is_w3c_validated_and_bounded():
    carrier = {
        "traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        "tracestate": "vendor=value",
        "baggage": "secret=ignored",
    }
    normalized = normalize_trace_context(carrier)
    assert normalized == {key: carrier[key] for key in ("traceparent", "tracestate")}
    assert normalize_trace_context({"traceparent": "malformed"}) is None
    assert normalize_trace_context({
        "traceparent": "00-00000000000000000000000000000000-0123456789abcdef-01",
    }) is None
    context = extract_trace_context({"traceparent": b"\xff"})
    assert not trace.get_current_span(context).get_span_context().is_valid
    assert len(span_links_from_carriers([carrier, carrier])) == 1


def test_json_logs_correlate_trace_without_emitting_payload_or_secrets():
    formatter = JsonLogFormatter()
    with traced_span("test.log.correlation"):
        record = logging.LogRecord(
            "botkernel.api",
            logging.INFO,
            __file__,
            1,
            "Authorization: bearer secret request body",
            (),
            None,
        )
        record.event = "action_admitted"
        record.action_id = "action-safe"
        record.authorization = "bearer secret"
        record.request_body = {"private": "payload"}
        output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["event"] == "action_admitted"
    assert parsed["action.id"] == "action-safe"
    assert len(parsed["trace_id"]) == 32
    assert len(parsed["span_id"]) == 16
    assert "secret" not in output
    assert "payload" not in output


def test_http_access_logs_are_json_without_raw_paths():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/actions/private-id", "1.1", 200),
        None,
    )
    parsed = json.loads(JsonLogFormatter().format(record))
    assert parsed["event"] == "http_access"
    assert parsed["http.request.method"] == "GET"
    assert parsed["http.response.status_code"] == 200
    assert "private-id" not in json.dumps(parsed)


def test_invalid_action_request_counts_validation_rejection():
    client = TestClient(app, headers=operator_headers())
    before = client.get("/metrics").text
    response = client.post("/actions", json={})
    assert response.status_code == 422
    after = client.get("/metrics").text
    assert "botkernel_action_admissions_total" in after
    assert 'outcome="validation_rejected"' in after
    assert before != after


def test_admission_outcomes_use_fixed_labels_and_commit_after_admission():
    import uuid
    from sqlalchemy import text

    client = TestClient(app, headers=operator_headers())
    suffix = uuid.uuid4().hex
    agent = "metrics-agent-" + suffix
    resource = "metrics-resource-" + suffix
    quota_resource = "metrics-quota-resource-" + suffix
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO agents(id) VALUES(:id)"), {"id": agent})
        connection.execute(
            text("INSERT INTO resources(id,capacity) VALUES(:id,1)"), {"id": resource}
        )
        connection.execute(
            text("INSERT INTO external_resources(id,capacity) VALUES(:id,1)"), {"id": resource}
        )
        connection.execute(
            text("INSERT INTO resources(id,capacity) VALUES(:id,1)"), {"id": quota_resource}
        )
        connection.execute(
            text("INSERT INTO external_resources(id,capacity) VALUES(:id,1)"), {"id": quota_resource}
        )

    def count(outcome):
        return sum(
            sample.value
            for family in ADMISSIONS.collect()
            for sample in family.samples
            if sample.name == "botkernel_action_admissions_total"
            and sample.labels.get("outcome") == outcome
        )

    def submit(**overrides):
        body = {
            "agent": agent,
            "workflow": "metrics-test",
            "idempotency_key": suffix + "-" + uuid.uuid4().hex,
            "resource": resource,
            "expected_version": 0,
            "capacity": 1,
        }
        body.update(overrides)
        return client.post("/actions", json=body)

    expected_statuses = {
        "accepted": 202,
        "resource_conflict": 409,
        "quota_rejected": 409,
        "policy_rejected": 409,
        "dependency_failure": 409,
        "validation_rejected": 409,
    }
    with engine.begin() as connection:
        connection.execute(text("UPDATE quota SET capacity=greatest(capacity,(SELECT coalesce(sum(capacity),0) FROM resources)+(SELECT coalesce(sum(greatest(delta,0)),0) FROM actions WHERE state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN','ESCALATED'))+10) WHERE id=1"))
    initial = {outcome: count(outcome) for outcome in expected_statuses}
    assert submit().status_code == 202
    assert submit(expected_version=1).status_code == 409
    assert submit(risk="high").status_code == 409
    assert submit(dependencies=["00000000-0000-0000-0000-000000000001"]).status_code == 409
    assert submit(deadline="2000-01-01T00:00:00Z").status_code == 409

    with engine.begin() as connection:
        original_quota = connection.execute(
            text("SELECT capacity FROM quota WHERE id=1 FOR UPDATE")
        ).scalar_one()
        connection.execute(text("UPDATE quota SET capacity=1 WHERE id=1"))
    try:
        assert submit(
            resource=quota_resource,
            idempotency_key=suffix + "-quota",
        ).status_code == 409
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE quota SET capacity=:capacity WHERE id=1"),
                {"capacity": original_quota},
            )

    for outcome, status in expected_statuses.items():
        assert count(outcome) == initial[outcome] + 1, (outcome, status)
