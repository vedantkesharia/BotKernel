"""Fail closed on incompatible legacy schemas and critical execution invariants."""

import re

from sqlalchemy import inspect, text


BASE_COLUMNS = {
    "agents": {"id": "text", "heartbeat": "timestamp with time zone"},
    "quota": {"id": "integer", "capacity": "integer"},
    "resources": {"id": "text", "capacity": "integer", "version": "integer"},
    "external_resources": {"id": "text", "capacity": "integer"},
    "actions": {
        "id": "uuid", "idempotency_key": "text", "agent": "text", "resource": "text",
        "payload": "jsonb", "delta": "integer", "state": "text",
        "created_at": "timestamp with time zone",
    },
    "outbox": {"id": "bigint", "action_id": "uuid", "published": "boolean"},
    "receipts": {"action_id": "uuid"},
}
HEAD_COLUMNS = {
    **BASE_COLUMNS,
    "outbox": {**BASE_COLUMNS["outbox"], "trace_context": "jsonb"},
    "investigation_reports": {"id":"uuid", "incident_id":"bigint", "idempotency_key":"text", "request_fingerprint":"text", "status":"text", "provider":"text", "report":"jsonb", "error_category":"text", "created_at":"timestamp with time zone", "completed_at":"timestamp with time zone", "lease_token":"uuid", "lease_until":"timestamp with time zone"},
    "incident_transitions": {
        "id": "bigint", "incident_id": "bigint", "transition": "text",
        "occurred_at": "timestamp with time zone", "score": "double precision",
    },
    "actions": {
        **BASE_COLUMNS["actions"], "attempts": "integer",
        "next_attempt": "timestamp with time zone", "last_error": "text",
    },
    "dead_letters": {"topic": "text", "partition_id": "integer", "offset_id": "bigint", "reason": "text"},
    "effects": {
        "action_id": "uuid", "resource": "text", "agent": "text", "version": "integer",
        "before_capacity": "integer", "after_capacity": "integer",
        "latency": "double precision", "observed_at": "timestamp with time zone",
    },
    "incidents": {
        "id": "bigint", "resource": "text", "score": "double precision", "evidence": "jsonb",
        "status": "text", "opened_at": "timestamp with time zone", "hold_until": "timestamp with time zone",
        "verified_at": "timestamp with time zone", "intervention_count": "integer",
        "recurrence_count": "integer", "verification_started_at": "timestamp with time zone",
        "monitor_started_at": "timestamp with time zone", "healthy_samples": "integer",
        "last_score": "double precision", "last_observed_at": "timestamp with time zone",
        "escalated_at": "timestamp with time zone", "reopened_at": "timestamp with time zone",
        "resolved_at": "timestamp with time zone",
    },
    "incident_operator_actions": {
        "id": "bigint", "incident_id": "bigint", "action": "text", "idempotency_key": "text",
        "reason": "text", "actor": "text", "created_at": "timestamp with time zone",
    },
}
NULLABLE = {
    *(("investigation_reports", name) for name in ("report", "error_category", "completed_at", "lease_token", "lease_until")),
    ("actions", "last_error"),
    ("outbox", "trace_context"),
    ("incident_transitions", "score"),
    *(("incidents", name) for name in (
        "verified_at", "verification_started_at", "last_score", "last_observed_at",
        "escalated_at", "reopened_at", "resolved_at",
    )),
}
DEFAULTS = {
    ("agents", "heartbeat"): "now()", ("resources", "version"): "0",
    ("actions", "created_at"): "now()", ("outbox", "id"): "nextval(",
    ("outbox", "published"): "false",
}
HEAD_DEFAULTS = {
    ("actions", "attempts"): "0", ("actions", "next_attempt"): "now()",
    ("effects", "observed_at"): "now()", ("incidents", "id"): "nextval(",
    ("incidents", "status"): "'HOLD'::text", ("incidents", "opened_at"): "now()",
    ("incidents", "hold_until"): "(now() + '00:00:20'::interval)",
    ("incidents", "intervention_count"): "1", ("incidents", "recurrence_count"): "0",
    ("incidents", "monitor_started_at"): "now()", ("incidents", "healthy_samples"): "0",
    ("incident_operator_actions", "id"): "nextval(",
    ("incident_operator_actions", "actor"): "'local-console'::text",
    ("incident_operator_actions", "created_at"): "now()",
    ("incident_transitions", "id"): "nextval(",
    ("incident_transitions", "occurred_at"): "now()",
}
PRIMARY_KEYS = {
    "agents": ["id"], "quota": ["id"], "resources": ["id"], "external_resources": ["id"],
    "actions": ["id"], "outbox": ["id"], "receipts": ["action_id"],
    "dead_letters": ["topic", "partition_id", "offset_id"], "effects": ["action_id"],
    "incidents": ["id"], "incident_operator_actions": ["id"], "investigation_reports": ["id"],
}
FOREIGN_KEYS = {
    "actions": [(["agent"], "agents", ["id"]), (["resource"], "resources", ["id"])],
    "outbox": [(["action_id"], "actions", ["id"])],
    "receipts": [(["action_id"], "actions", ["id"])],
    "effects": [(["action_id"], "actions", ["id"])],
    "incident_operator_actions": [(["incident_id"], "incidents", ["id"])],
    "investigation_reports": [(["incident_id"], "incidents", ["id"])],
}
LEGACY_GUARD = """BEGIN
IF OLD.state <> NEW.state AND NOT ((OLD.state='RESERVED' AND NEW.state='DISPATCHED')
 OR (OLD.state='DISPATCHED' AND NEW.state IN ('SUCCEEDED','OUTCOME_UNKNOWN'))
 OR (OLD.state='OUTCOME_UNKNOWN' AND NEW.state='DISPATCHED'))
 THEN RAISE EXCEPTION 'illegal transition'; END IF;
RETURN NEW; END"""
HEAD_GUARD = """BEGIN
IF OLD.state <> NEW.state AND NOT (
 (OLD.state='RESERVED' AND NEW.state IN ('DISPATCHED','FAILED','ESCALATED')) OR
 (OLD.state='DISPATCHED' AND NEW.state IN ('SUCCEEDED','OUTCOME_UNKNOWN','FAILED','ESCALATED')) OR
 (OLD.state='OUTCOME_UNKNOWN' AND NEW.state IN ('DISPATCHED','FAILED','ESCALATED')))
 THEN RAISE EXCEPTION 'illegal transition'; END IF;
RETURN NEW; END"""


def _compact(value):
    return re.sub(r"\s+", "", value).lower()


def _fail(detail):
    raise RuntimeError(f"Incompatible BotKernel schema: {detail}; restore or migrate explicitly")


def validate_schema(connection, *, legacy):
    """Validate a supported legacy snapshot or selected safety invariants at head."""
    expected = BASE_COLUMNS if legacy else HEAD_COLUMNS
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if legacy and not (tables & BASE_COLUMNS.keys()):
        return
    missing = set(expected) - tables
    if missing:
        _fail("missing tables " + ", ".join(sorted(missing)))
    rows = connection.execute(text(
        "SELECT table_name,column_name,data_type,is_nullable,column_default "
        "FROM information_schema.columns WHERE table_schema=current_schema()"
    )).mappings()
    columns = {(r["table_name"], r["column_name"]): r for r in rows}
    for table, names in expected.items():
        for name, kind in names.items():
            column = columns.get((table, name))
            if not column or column["data_type"] != kind:
                _fail(f"missing or incompatible column {table}.{name}")
            nullable = (table, name) in NULLABLE
            if (column["is_nullable"] == "YES") != nullable:
                _fail(f"incompatible nullability on {table}.{name}")
            default = (DEFAULTS if legacy else {**DEFAULTS, **HEAD_DEFAULTS}).get((table, name))
            if default is not None:
                actual = column["column_default"] or ""
                if (default == "nextval(" and not actual.startswith(default)) or (
                    default != "nextval(" and actual != default
                ):
                    _fail(f"missing or incompatible default on {table}.{name}")
        if table in PRIMARY_KEYS and inspector.get_pk_constraint(table)["constrained_columns"] != PRIMARY_KEYS[table]:
            _fail(f"missing or incompatible primary key on {table}")
        foreign_keys = inspector.get_foreign_keys(table)
        for local, target, remote in FOREIGN_KEYS.get(table, []):
            if not any(fk["constrained_columns"] == local and fk["referred_table"] == target
                       and fk["referred_columns"] == remote for fk in foreign_keys):
                _fail(f"missing foreign key on {table}.{local[0]}")
    if not legacy:
        if inspector.get_pk_constraint("incident_transitions")["constrained_columns"] != ["id"]:
            _fail("missing or incompatible primary key on incident_transitions")
        if not any(
            fk["constrained_columns"] == ["incident_id"]
            and fk["referred_table"] == "incidents"
            and fk["referred_columns"] == ["id"]
            for fk in inspector.get_foreign_keys("incident_transitions")
        ):
            _fail("missing foreign key on incident_transitions.incident_id")

    unique = {"actions": [["idempotency_key"]]}
    if not legacy:
        unique.update({"effects": [["resource", "version"]],
                       "incident_operator_actions": [["incident_id", "idempotency_key"]]})
    for table, requirements in unique.items():
        constraints = inspector.get_unique_constraints(table)
        for required in requirements:
            if not any(item["column_names"] == required for item in constraints):
                _fail(f"missing unique constraint on {table}({','.join(required)})")

    states = "'reserved','dispatched','outcome_unknown','succeeded'"
    reserved = "'reserved','dispatched','outcome_unknown'"
    if not legacy:
        states += ",'failed','escalated'"
        reserved += ",'escalated'"
    checks = connection.execute(text(
        "SELECT t.relname,c.conname,pg_get_constraintdef(c.oid) AS definition "
        "FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
        "JOIN pg_namespace n ON n.oid=t.relnamespace "
        "WHERE n.nspname=current_schema() AND c.convalidated"
    )).mappings()
    definitions = {(row["relname"], row["conname"]): _compact(row["definition"]).replace("::text", "") for row in checks}
    expected_checks = {
        ("actions", "actions_state_check"): f"check((state=any(array[{states}])))",
        ("quota", "quota_id_check"): "check((id=1))",
        ("quota", "quota_capacity_check"): "check((capacity>0))",
        ("resources", "resources_capacity_check"): "check(((capacity>=1)and(capacity<=20)))",
    }
    if not legacy:
        statuses = "'hold','verifying','verified','escalated','resolved'"
        expected_checks.update({
            ("actions", "actions_attempts_check"): "check((attempts>=0))",
            ("incidents", "incidents_status_check"): f"check((status=any(array[{statuses}])))",
            ("incidents", "incidents_intervention_count_check"): "check((intervention_count>=0))",
            ("incidents", "incidents_recurrence_count_check"): "check((recurrence_count>=0))",
            ("incidents", "incidents_healthy_samples_check"): "check((healthy_samples>=0))",
            ("incident_operator_actions", "incident_operator_actions_action_check"):
                "check((action=any(array['acknowledge','resolve'])))",
            ("incident_operator_actions", "incident_operator_actions_idempotency_key_check"):
                "check(((length(idempotency_key)>=1)and(length(idempotency_key)<=200)))",
            ("incident_operator_actions", "incident_operator_actions_reason_check"):
                "check(((length(reason)>=1)and(length(reason)<=500)))",
            ("incident_transitions", "incident_transitions_transition_check"):
                "check((transition=any(array['detected','hold_applied','verification_started','verified','recurrence','escalated','acknowledged','resolved'])))",
            ("investigation_reports", "investigation_reports_provider_check"):
                "check((provider=any(array['deterministic_mock','bedrock'])))",
        })
    for key, definition in expected_checks.items():
        if definitions.get(key) != definition:
            _fail(f"missing or incompatible check constraint {key[0]}.{key[1]}")
    if not legacy:
        trace_check = definitions.get(("outbox", "outbox_trace_context_check"), "")
        required_fragments = (
            "trace_contextisnull",
            "jsonb_typeof(trace_context)='object'",
            "trace_context?'traceparent'",
            "length((trace_context->>'traceparent'))=55",
            "length((trace_context->>'tracestate'))<=512",
        )
        if any(fragment not in trace_check for fragment in required_fragments):
            _fail("missing or incompatible outbox trace-context constraint")

    indexes = {index["name"]: index for index in inspector.get_indexes("actions")}
    reservation = indexes.get("resource_reservation")
    predicate = _compact(str((reservation or {}).get("dialect_options", {}).get("postgresql_where", ""))).replace("::text", "")
    if (not reservation or not reservation["unique"] or reservation["column_names"] != ["resource"]
            or predicate != f"(state=any(array[{reserved}]))"):
        _fail("missing or incompatible resource reservation index")
    if not legacy:
        incident_indexes = {index["name"]: index for index in inspector.get_indexes("incidents")}
        incident = incident_indexes.get("one_incident")
        predicate = _compact(str((incident or {}).get("dialect_options", {}).get("postgresql_where", ""))).replace("::text", "")
        if (not incident or not incident["unique"] or incident["column_names"] != ["resource"]
                or predicate != "(status='hold')"):
            _fail("missing or incompatible incident hold index")
    trigger = connection.execute(text(
        "SELECT p.prosrc FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid "
        "WHERE n.nspname=current_schema() AND c.relname='actions' "
        "AND t.tgname='action_transition' AND NOT t.tgisinternal AND t.tgenabled IN ('O','A') "
        "AND t.tgtype=19 AND p.proname='guard_transition'"
    )).scalar_one_or_none()
    if trigger is None or _compact(trigger) != _compact(LEGACY_GUARD if legacy else HEAD_GUARD):
        _fail("missing or incompatible action transition guard")
