import os
import uuid
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

def database_url_from_environment() -> str:
    secret_path = os.getenv("DATABASE_URL_FILE")
    if secret_path:
        value = Path(secret_path).read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError("DATABASE_URL_FILE is empty")
        return value
    return os.getenv("DATABASE_URL", "postgresql+psycopg://botkernel:local@postgres/botkernel")


engine = create_engine(database_url_from_environment(), pool_pre_ping=True)

lock_engine = create_engine(engine.url, pool_size=4, max_overflow=0, pool_pre_ping=True)

def initialize():
    from alembic.config import Config
    from alembic import command
    command.upgrade(Config("alembic.ini"), "head")


class AdmissionError(ValueError):
    def __init__(self, message, outcome):
        super().__init__(message)
        self.outcome = outcome


def admit(body):
    from botkernel.observability import capture_trace_context, traced_span

    with traced_span("botkernel.action.admission") as admission_span:
        trace_context = capture_trace_context()
        with traced_span(
            "botkernel.postgresql.reserve_and_outbox",
            {"db.system": "postgresql", "db.operation": "reserve_and_outbox"},
        ):
            action_id = _admit(body, trace_context)
        admission_span.set_attribute("action.id", action_id)
        admission_span.set_attribute("botkernel.outcome", "accepted")
        return action_id


def _admit(body, trace_context):
    payload = body.model_dump(mode="json")
    import json
    with Session(engine) as s, s.begin():
        # Serialize idempotency keys even when the row does not yet exist.
        s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k,0))"), {"k": body.idempotency_key})
        old = s.execute(text("SELECT id,payload FROM actions WHERE idempotency_key=:k"), {"k": body.idempotency_key}).mappings().first()
        if old:
            if old["payload"] != payload:
                raise AdmissionError("idempotency key reused with different payload", "resource_conflict")
            return str(old["id"])
        from datetime import datetime, timezone
        if body.risk != "low":
            raise AdmissionError("high-risk operations require human review; unsupported locally", "policy_rejected")
        if body.deadline and body.deadline <= datetime.now(timezone.utc):
            raise AdmissionError("deadline expired", "validation_rejected")
        for dependency in body.dependencies:
            if s.execute(text("SELECT state FROM actions WHERE id=:id"), {"id":str(dependency)}).scalar() != "SUCCEEDED":
                raise AdmissionError("dependency not succeeded", "dependency_failure")
        # Global quota row is authoritative; lock order is quota then resource.
        quota = s.execute(text("SELECT * FROM quota WHERE id=1 FOR UPDATE")).mappings().one()
        resource = s.execute(text("SELECT * FROM resources WHERE id=:r FOR UPDATE"), {"r": body.resource}).mappings().one()
        if resource["version"] != body.expected_version:
            raise AdmissionError("stale resource version", "resource_conflict")
        if s.execute(text("SELECT 1 FROM actions WHERE resource=:r AND state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN','ESCALATED')"), {"r": body.resource}).first():
            raise AdmissionError("resource reserved", "resource_conflict")
        delta = body.capacity - resource["capacity"]
        if delta < 0 and s.execute(
            text(
                "SELECT 1 FROM incidents WHERE resource=:r AND "
                "(status IN ('VERIFYING','ESCALATED') OR (status='HOLD' AND hold_until>now()))"
            ),
            {"r": body.resource},
        ).first():
            raise AdmissionError("collective stability containment: scale-down restricted", "policy_rejected")
        total = s.execute(text("SELECT sum(capacity) FROM resources")).scalar_one()
        pending = s.execute(text("SELECT coalesce(sum(greatest(delta,0)),0) FROM actions WHERE state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN','ESCALATED')")).scalar_one()
        if total + pending + delta > quota["capacity"]:
            raise AdmissionError("global capacity quota exceeded", "quota_rejected")
        aid = str(uuid.uuid4())
        s.execute(text("INSERT INTO actions(id,idempotency_key,agent,resource,payload,delta,state) VALUES (:id,:key,:agent,:resource,CAST(:payload AS jsonb),:delta,'RESERVED')"), dict(id=aid,key=body.idempotency_key,agent=body.agent,resource=body.resource,payload=json.dumps(payload),delta=delta))
        s.execute(
            text("INSERT INTO outbox(action_id,trace_context) VALUES (:id,CAST(:trace_context AS jsonb))"),
            {"id": aid, "trace_context": json.dumps(trace_context) if trace_context else None},
        )
        return aid

def _execute(aid):
    # Local external system has its own durable operation receipt. This is an
    # explicitly idempotent simulator, not an exactly-once claim for cloud APIs.
    from botkernel.observability import traced_span
    with traced_span(
        "botkernel.postgresql.mark_dispatched",
        {"db.system": "postgresql", "db.operation": "mark_dispatched", "action.id": str(aid)},
    ):
        with engine.begin() as c:
            a = c.execute(text("SELECT * FROM actions WHERE id=:id FOR UPDATE"), {"id": aid}).mappings().one()
            if a["state"] == "SUCCEEDED":
                return
            c.execute(text("UPDATE actions SET state='DISPATCHED' WHERE id=:id"), {"id": aid})
    with traced_span(
        "botkernel.simulator.commit_receipt",
        {"db.system": "postgresql", "db.operation": "commit_simulator_receipt", "action.id": str(aid)},
    ):
        with engine.begin() as c:
            a = c.execute(text("SELECT * FROM actions WHERE id=:id"), {"id": aid}).mappings().one()
            receipt = c.execute(text("INSERT INTO receipts(action_id) VALUES (:id) ON CONFLICT DO NOTHING RETURNING action_id"), {"id": aid}).first()
            if receipt:
                if os.getenv("SIMULATOR_FAILURE") == "permanent":
                    raise RuntimeError("simulated permanent failure")
                result = c.execute(text("UPDATE external_resources SET capacity=:v WHERE id=:r"), {"v": a["payload"]["capacity"], "r": a["resource"]})
                if result.rowcount != 1:
                    raise RuntimeError("simulated resource missing; effect rolled back")
    if os.getenv("CRASH_AFTER_EFFECT") == "true":
        os._exit(17)
    with traced_span(
        "botkernel.postgresql.finalize_action",
        {"db.system": "postgresql", "db.operation": "finalize_action", "action.id": str(aid)},
    ):
        with engine.begin() as c:
            c.execute(text("SELECT id FROM quota WHERE id=1 FOR UPDATE"))
            a = c.execute(text("SELECT * FROM actions WHERE id=:id FOR UPDATE"), {"id": aid}).mappings().one()
            if a["state"] == "SUCCEEDED":
                return
            before = c.execute(text("SELECT * FROM resources WHERE id=:r"), {'r':a['resource']}).mappings().one()
            from botkernel.stability import latency
            c.execute(text("INSERT INTO effects(action_id,resource,agent,version,before_capacity,after_capacity,latency) VALUES(:id,:r,:agent,:version,:before,:after,:latency) ON CONFLICT DO NOTHING"), {'id':aid,'r':a['resource'],'agent':a['agent'],'version':before['version']+1,'before':before['capacity'],'after':a['payload']['capacity'],'latency':latency(a['payload']['capacity'])})
            c.execute(text("UPDATE resources SET capacity=:v,version=version+1 WHERE id=:r"), {"v": a["payload"]["capacity"], "r": a["resource"]})
            c.execute(text("UPDATE actions SET state='SUCCEEDED' WHERE id=:id"), {"id": aid})


def _execute_with_lock(aid):
    """Serialize all execution/recovery attempts across transaction boundaries.

    Session advisory lock is held on a dedicated connection. Worker death releases
    it. This relies on the simulator's atomic effect receipt, not generic API safety.
    """
    from datetime import datetime, timezone
    with lock_engine.connect() as lock:
        acquired = lock.execute(text("SELECT pg_try_advisory_lock(hashtextextended(:id,1))"), {"id":str(aid)}).scalar_one()
        lock.commit()
        if not acquired:
            return
        try:
            with engine.begin() as c:
                a = c.execute(text("SELECT * FROM actions WHERE id=:id FOR UPDATE"), {"id":aid}).mappings().one()
                if a['state'] in ('SUCCEEDED','FAILED','ESCALATED'):
                    return
                receipt = c.execute(text("SELECT 1 FROM receipts WHERE action_id=:id"), {'id':aid}).first()
                external = c.execute(text("SELECT capacity FROM external_resources WHERE id=:r"), {'r':a['resource']}).scalar()
                expected = a['payload']['capacity'] if receipt else c.execute(text("SELECT capacity FROM resources WHERE id=:r"), {'r':a['resource']}).scalar_one()
                if external != expected:
                    c.execute(text("UPDATE actions SET state='ESCALATED',last_error='external state divergence; reservation retained' WHERE id=:id"),{'id':aid})
                    return
                now = datetime.now(timezone.utc)
                if not receipt:
                    deadline = a['payload'].get('deadline')
                    expired = deadline and datetime.fromisoformat(deadline.replace('Z','+00:00')) <= now
                    if expired or a['attempts'] >= a['payload'].get('max_attempts',3):
                        c.execute(text("UPDATE actions SET state='FAILED',last_error='deadline or attempt limit; no effect receipt' WHERE id=:id"), {'id':aid})
                        return
                    if a['next_attempt'] > now:
                        return
                    c.execute(text("UPDATE actions SET attempts=attempts+1,next_attempt=now()+interval '30 seconds' WHERE id=:id"),{'id':aid})
            try:
                _execute(aid)
            except RuntimeError:
                with engine.begin() as c:
                    # Only simulator-known rollback failures enter this path.
                    c.execute(text("UPDATE actions SET state='OUTCOME_UNKNOWN',last_error='simulator execution failed',next_attempt=now()+(:delay * interval '1 second') WHERE id=:id"), {'id':aid,'delay':min(300,a['payload'].get('backoff_seconds',2)*2**a['attempts'])})
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(hashtextextended(:id,1))"), {'id':str(aid)})
            lock.commit()


def execute(aid, origin_trace_context=None):
    from botkernel.observability import extract_trace_context, span_links_from_carriers, traced_span
    from opentelemetry import trace

    current = trace.get_current_span().get_span_context()
    parent_context = None
    links = []
    if origin_trace_context:
        if current.is_valid:
            links = span_links_from_carriers([origin_trace_context])
        else:
            parent_context = extract_trace_context(origin_trace_context)
    elif not current.is_valid:
        with engine.connect() as connection:
            stored = connection.execute(
                text("SELECT o.trace_context FROM outbox o JOIN actions a ON a.id=o.action_id WHERE a.id=:id"),
                {"id": aid},
            ).scalar_one_or_none()
        if stored:
            parent_context = extract_trace_context(stored)
    with traced_span(
        "botkernel.action.execute",
        {"action.id": str(aid)},
        parent_context=parent_context,
        links=links,
    ):
        return _execute_with_lock(aid)


def sweep():
    from botkernel.observability import traced_span

    with traced_span("botkernel.recovery.sweep"):
        with engine.connect() as c:
            due = c.execute(text(
                "SELECT a.id,o.trace_context FROM actions a "
                "LEFT JOIN outbox o ON o.action_id=a.id "
                "WHERE a.state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN') AND a.next_attempt<=now() "
                "AND (a.state<>'RESERVED' OR a.created_at<now()-interval '30 seconds') "
                "ORDER BY a.next_attempt LIMIT 100"
            )).mappings().all()
        for action in due:
            execute(str(action["id"]), origin_trace_context=action["trace_context"])
        return len(due)
