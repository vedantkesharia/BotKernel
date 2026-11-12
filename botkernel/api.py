import csv
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path as FilePath
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Path as ApiPath, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict, AwareDatetime, ValidationError, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, NoResultFound
from botkernel.core import AdmissionError, engine, admit
import redis

app = FastAPI(title="BotKernel local gateway")
from botkernel.observability import ADMISSIONS, install_api, traced_span
install_api(app, engine)

cache = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"), socket_timeout=1, socket_connect_timeout=1)
EXPERIMENT_RESULTS = FilePath(__file__).resolve().parents[1] / "benchmarks" / "results"


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent: str = Field(min_length=1,max_length=100)
    workflow: str = Field(min_length=1,max_length=100)
    idempotency_key: str = Field(min_length=1,max_length=200)
    resource: str
    expected_version: int = Field(ge=0)
    capacity: int = Field(ge=1,le=20)
    dependencies: list[UUID] = Field(default_factory=list, max_length=20)
    risk: Literal["low", "high"] = "low"
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: int = Field(default=2, ge=1, le=60)
    deadline: AwareDatetime | None = None


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal[
        "oscillation",
        "healthy_scaling",
        "simultaneous_resources",
        "overlapping_remediation",
        "cascade",
        "recurrence",
        "temporary_spike",
        "worker_failure",
    ] = "oscillation"
    seeds: list[int] = Field(default_factory=lambda: [17, 23, 41], min_length=1, max_length=5)
    duration: int = Field(default=120, ge=120, le=180)


class IncidentOperatorAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("idempotency_key", "reason")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class AgentDecisionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)
    provider: Literal["deterministic_mock", "bedrock", "ollama_local"]
    model_id: str | None = Field(default=None, max_length=256)
    decision: Literal["PROPOSE", "NO_OP", "ERROR"]
    resource: str = Field(min_length=1, max_length=100)
    proposed_delta: int = Field(ge=-3, le=3)
    reason: str = Field(max_length=500)
    evidence_references: list[str] = Field(default_factory=list, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=10)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    invocation_count: int = Field(default=0, ge=0, le=4)
    error_category: str | None = Field(default=None, max_length=80)
    gateway_approved: bool = False
    action_id: str | None = Field(default=None, max_length=36)
    action_status: str | None = Field(default=None, max_length=24)
    effect_committed: bool | None = None

    @field_validator("reason")
    @classmethod
    def bounded_nonblank_reason(cls, value):
        if not value.strip():
            raise ValueError("reason must not be blank")
        return value


@app.post("/agents/{agent}")
def register(agent: Annotated[str, ApiPath(min_length=1,max_length=100,pattern=r"^[a-zA-Z0-9_-]+$")]):
    with engine.begin() as c:
        c.execute(text("INSERT INTO agents(id) VALUES(:id) ON CONFLICT(id) DO UPDATE SET heartbeat=now()"), {"id":agent})
    try:
        cache.setex("heartbeat:"+agent, 30, "alive")
    except (redis.RedisError,ValidationError,ValueError):
        pass
    return {"id":agent}

@app.get("/health")
def health():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "mode": "local simulation",
        "deployment_target": os.getenv("BOTKERNEL_RUNTIME_ENV", "local"),
        "cloud_mode": os.getenv("CLOUD_MODE", "mock"),
        "resource_source": "simulator",
        "real_infrastructure_remediation": False,
    }

@app.post("/actions",status_code=202)
def submit(action: Action):
    try:
        with traced_span("botkernel.http.action_submit") as span:
            action_id = admit(action)
            span.set_attribute("action.id", action_id)
            ADMISSIONS.labels("accepted").inc()
            logging.info(
                "Action accepted",
                extra={"event": "action_admitted", "action_id": action_id, "botkernel_outcome": "accepted"},
            )
            return {"id": action_id}
    except AdmissionError as e:
        ADMISSIONS.labels(e.outcome).inc()
        logging.warning(
            "Action admission rejected",
            extra={"event": "action_admission_rejected", "botkernel_outcome": e.outcome},
        )
        raise HTTPException(409,"Admission conflict: " + str(e)) from e
    except (ValueError, IntegrityError, NoResultFound) as e:
        ADMISSIONS.labels("resource_conflict").inc()
        logging.warning(
            "Action admission conflicted",
            extra={"event": "action_admission_rejected", "botkernel_outcome": "resource_conflict"},
        )
        raise HTTPException(409,"Admission conflict: " + (str(e) if isinstance(e,ValueError) else "unknown agent or resource")) from e

@app.get("/agents/{agent}/action-by-key")
def agent_action_by_key(agent: str, key: Annotated[str, Query(min_length=1,max_length=200)]):
    with engine.connect() as c:
        row=c.execute(text("SELECT id,agent,state,idempotency_key,payload FROM actions WHERE agent=:agent AND idempotency_key=:key"), {'agent':agent,'key':key}).mappings().first()
    if row is None:
        raise HTTPException(404,"action not found")
    return dict(row)

@app.get("/resources")
def resources():
    with engine.connect() as c:
        return [dict(r) for r in c.execute(text("SELECT * FROM resources ORDER BY id")).mappings()]

@app.get("/actions")
def actions():
    with engine.connect() as c:
        return [dict(r) for r in c.execute(text("SELECT * FROM actions ORDER BY created_at DESC LIMIT 200")).mappings()]

@app.get("/agents")
def agents():
    with engine.connect() as c:
        rows=[dict(r) for r in c.execute(text("SELECT id,heartbeat,heartbeat > now()-interval '30 seconds' AS healthy FROM agents ORDER BY id")).mappings()]
        for row in rows:
            try:
                cached=cache.get("agent-decision:"+row["id"])
                if cached:
                    decision=AgentDecisionSnapshot.model_validate_json(cached)
                    if decision.action_id:
                        action=c.execute(text("SELECT state,EXISTS(SELECT 1 FROM effects WHERE action_id=actions.id) AS effect_committed FROM actions WHERE id=:id AND agent=:agent"),{"id":decision.action_id,"agent":row["id"]}).mappings().first()
                        if action:
                            decision=decision.model_copy(update={"gateway_approved":True,"action_status":action["state"],"effect_committed":action["effect_committed"]})
                    row["latest_decision"]=decision.model_dump(mode="json")
            except redis.RedisError:
                pass
        return rows

@app.post("/agents/{agent}/decision", status_code=204)
def publish_agent_decision(agent: Annotated[str, ApiPath(min_length=1,max_length=100,pattern=r"^[a-zA-Z0-9_-]+$")], snapshot: AgentDecisionSnapshot):
    with engine.connect() as c:
        exists=c.execute(text("SELECT 1 FROM agents WHERE id=:id"),{"id":agent}).first()
        if not exists:
            raise HTTPException(404,"agent not registered")
        if snapshot.action_id:
            action=c.execute(text("SELECT 1 FROM actions WHERE id=:id AND agent=:agent AND idempotency_key=:key"),{"id":snapshot.action_id,"agent":agent,"key":snapshot.idempotency_key}).first()
            if not action:
                raise HTTPException(409,"decision action is not in the gateway ledger")
        snapshot=snapshot.model_copy(update={"gateway_approved":False,"action_status":None,"effect_committed":None})
    try:
        cache.setex("agent-decision:"+agent, 86400, snapshot.model_dump_json())
    except redis.RedisError:
        raise HTTPException(503,"agent status cache unavailable")

@app.get("/ready")
def ready():
    from confluent_kafka.admin import AdminClient
    try:
        with engine.connect() as c:
            revision = c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            if revision != "0008":
                raise RuntimeError("migration required")
        AdminClient({"bootstrap.servers":os.getenv("KAFKA_BOOTSTRAP_SERVERS","kafka:9092")}).list_topics(timeout=3)
    except Exception as error:
        raise HTTPException(503,"database or Kafka not ready") from error
    return {"status":"ready","redis":"advisory"}

@app.get("/graph")
def effect_graph(window: int = 60, resource: str | None = None):
    if not 1 <= window <= 3600:
        raise HTTPException(422,"window must be 1..3600 seconds")
    from botkernel.stability import graph
    return graph(window,resource)

@app.get("/incidents")
def incidents():
    with engine.connect() as c:
        return [
            dict(r)
            for r in c.execute(
                text(
                    "SELECT i.*,COALESCE(a.actions,'[]'::jsonb) AS operator_actions "
                    "FROM incidents i LEFT JOIN LATERAL ("
                    "SELECT jsonb_agg(jsonb_build_object("
                    "'id',id,'action',action,'reason',reason,'actor',actor,'created_at',created_at"
                    ") ORDER BY created_at,id) AS actions "
                    "FROM incident_operator_actions WHERE incident_id=i.id"
                    ") a ON true ORDER BY i.opened_at DESC LIMIT 100"
                )
            ).mappings()
        ]


def _record_incident_operator_action_transaction(
    incident_id: int,
    action: Literal["ACKNOWLEDGE", "RESOLVE"],
    request: IncidentOperatorAction,
):
    with engine.begin() as connection:
        connection.execute(text("SELECT id FROM quota WHERE id=1 FOR UPDATE"))
        incident = connection.execute(
            text("SELECT * FROM incidents WHERE id=:id FOR UPDATE"),
            {"id": incident_id},
        ).mappings().first()
        if not incident:
            raise HTTPException(404, "incident not found")
        resource = connection.execute(
            text("SELECT id FROM resources WHERE id=:resource FOR UPDATE"),
            {"resource": incident["resource"]},
        ).first()
        if not resource:
            raise HTTPException(409, "incident resource is unavailable")

        previous = connection.execute(
            text(
                "SELECT action,reason,created_at FROM incident_operator_actions "
                "WHERE incident_id=:incident AND idempotency_key=:key"
            ),
            {"incident": incident_id, "key": request.idempotency_key},
        ).mappings().first()
        if previous:
            if previous["action"] != action or previous["reason"] != request.reason:
                raise HTTPException(409, "idempotency key was already used for a different action")
            return {
                "incident_id": incident_id,
                "action": action,
                "status": incident["status"],
                "created_at": previous["created_at"],
                "duplicate": True,
            }

        allowed_status = "ESCALATED" if action == "ACKNOWLEDGE" else "VERIFIED"
        if incident["status"] != allowed_status:
            raise HTTPException(409, f"{action.lower()} requires incident status {allowed_status}")

        if action == "RESOLVE":
            evidence = incident["evidence"] or {}
            lifecycle = evidence.get("lifecycle", [])
            lifecycle.append({
                "transition": "resolved by local operator",
                "score": incident["last_score"] if incident["last_score"] is not None else incident["score"],
            })
            evidence["lifecycle"] = lifecycle[-20:]
            connection.execute(
                text(
                    "UPDATE incidents SET status='RESOLVED',resolved_at=now(),"
                    "evidence=CAST(:evidence AS jsonb) WHERE id=:id"
                ),
                {"id": incident_id, "evidence": json.dumps(evidence)},
            )

        recorded = connection.execute(
            text(
                "INSERT INTO incident_operator_actions(incident_id,action,idempotency_key,reason) "
                "VALUES(:incident,:action,:key,:reason) RETURNING created_at"
            ),
            {
                "incident": incident_id,
                "action": action,
                "key": request.idempotency_key,
                "reason": request.reason,
            },
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO incident_transitions(incident_id,transition,score) "
                "VALUES(:incident,:transition,:score)"
            ),
            {
                "incident": incident_id,
                "transition": "acknowledged" if action == "ACKNOWLEDGE" else "resolved",
                "score": incident["last_score"] if incident["last_score"] is not None else incident["score"],
            },
        )
        return {
            "incident_id": incident_id,
            "action": action,
            "status": "RESOLVED" if action == "RESOLVE" else incident["status"],
            "created_at": recorded,
            "duplicate": False,
        }


def _record_incident_operator_action(
    incident_id: int,
    action: Literal["ACKNOWLEDGE", "RESOLVE"],
    request: IncidentOperatorAction,
):
    with traced_span(
        "botkernel.incident.operator_transition",
        {"incident.id": incident_id, "botkernel.outcome": action.lower()},
    ):
        result = _record_incident_operator_action_transaction(incident_id, action, request)
        logging.info(
            "Incident operator action recorded",
            extra={
                "event": "incident_operator_action",
                "incident_id": incident_id,
                "botkernel_outcome": result["action"].lower(),
            },
        )
        return result


@app.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident(
    incident_id: Annotated[int, ApiPath(ge=1)],
    request: IncidentOperatorAction,
):
    return _record_incident_operator_action(incident_id, "ACKNOWLEDGE", request)


@app.post("/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: Annotated[int, ApiPath(ge=1)],
    request: IncidentOperatorAction,
):
    return _record_incident_operator_action(incident_id, "RESOLVE", request)

@app.get("/telemetry")
def telemetry():
    from botkernel.stability import latency
    with engine.connect() as c:
        rows=[dict(r) for r in c.execute(text(
            "SELECT r.*, (SELECT capacity FROM quota WHERE id=1) AS quota_capacity, "
            "(SELECT COALESCE(sum(capacity),0) FROM resources) AS total_allocation, "
            "EXISTS(SELECT 1 FROM actions a WHERE a.resource=r.id AND a.state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN')) AS pending_action, "
            "(SELECT i.status FROM incidents i WHERE i.resource=r.id AND i.status IN ('HOLD','VERIFYING','ESCALATED') ORDER BY i.opened_at DESC LIMIT 1) AS controller_status, "
            "COALESCE((SELECT json_agg(e) FROM (SELECT action_id,agent,version,before_capacity,after_capacity,latency,observed_at "
            "FROM effects WHERE resource=r.id ORDER BY version DESC LIMIT 8) e),'[]'::json) AS recent_effects "
            "FROM resources r ORDER BY r.id"
        )).mappings()]
    return [{**r,'latency_p95':latency(r['capacity']),'workload':6,'workload_source':'fixed_simulator_input','simulated':True,
             'utilization':None,'controller_hold':r['controller_status']=='HOLD',
             'controller_status':r['controller_status']} for r in rows]


def _experiment_payload(run_id: str) -> dict:
    try:
        canonical_id = str(UUID(run_id))
    except ValueError as error:
        raise HTTPException(422, "invalid experiment run ID") from error
    result_file = EXPERIMENT_RESULTS / canonical_id / "raw.json"
    if not result_file.is_file():
        raise HTTPException(404, "experiment run not found")
    return json.loads(result_file.read_text(encoding="utf-8"))


def _experiment_detail(payload: dict, include_series: bool = True) -> dict:
    series = []
    if include_series:
        by_mode_tick: dict[tuple[str, int], list[dict]] = {}
        for run in payload["runs"]:
            for sample in run["ticks"]:
                by_mode_tick.setdefault((run["mode"], sample["tick"]), []).append(sample)
        for (mode, tick), samples in sorted(
            by_mode_tick.items(), key=lambda item: (item[0][0], item[0][1])
        ):
            count = len(samples)
            series.append({
                "mode": mode,
                "tick": tick,
                "application_latency_ms": round(sum(sample["application_latency_ms"] for sample in samples) / count, 3),
                "capacity_a": round(sum(sample["capacity_a"] for sample in samples) / count, 3),
                "capacity_b": round(sum(sample["capacity_b"] for sample in samples) / count, 3),
                "alarm_rate": round(sum(sample["alarm_active"] for sample in samples) / count, 3),
                "ground_truth_harmful": samples[0]["ground_truth_harmful"],
            })
    result = {
        "run_id": payload["run_id"],
        "created_at": payload["created_at"],
        "scenario": payload["scenarios"][0] if len(payload["scenarios"]) == 1 else "multiple",
        "scenarios": payload["scenarios"],
        "seeds": payload["seeds"],
        "duration_ticks": payload["duration_ticks"],
        "summaries": payload["summaries"],
        "artifacts": {
            artifact: f"/experiments/{payload['run_id']}/artifacts/{artifact}"
            for artifact in ("raw.json", "summary.csv", "ticks.csv", "effects.csv", "report.md")
        },
    }
    if include_series:
        result["time_series"] = series
    return result


def _experiment_history_payload(directory: FilePath) -> dict:
    history_file = directory / "history.json"
    if history_file.is_file():
        return json.loads(history_file.read_text(encoding="utf-8"))

    report_file = directory / "report.md"
    summary_file = directory / "summary.csv"
    if report_file.is_file() and summary_file.is_file():
        report = report_file.read_text(encoding="utf-8")
        metadata = re.search(
            r"^Seeds: `(\[[^`]*\])`\. Scenarios: `(.*?)`\. Duration: `(\d+)` virtual seconds per case\.$",
            report,
            re.MULTILINE,
        )
        if metadata:
            summaries = []
            with summary_file.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    summary = {}
                    for key, value in row.items():
                        if value == "True":
                            summary[key] = True
                        elif value == "False":
                            summary[key] = False
                        else:
                            try:
                                summary[key] = json.loads(value)
                            except json.JSONDecodeError:
                                summary[key] = value
                    summaries.append(summary)

            raw_file = directory / "raw.json"
            timestamp = raw_file.stat().st_mtime if raw_file.is_file() else report_file.stat().st_mtime
            scenarios = metadata.group(2).split(", ")
            return {
                "run_id": directory.name,
                "created_at": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                "scenarios": scenarios,
                "seeds": json.loads(metadata.group(1)),
                "duration_ticks": int(metadata.group(3)),
                "summaries": summaries,
            }

    raw_file = directory / "raw.json"
    return json.loads(raw_file.read_text(encoding="utf-8"))


@app.get("/experiments")
def list_experiments():
    if not EXPERIMENT_RESULTS.exists():
        return []
    results = []
    for directory in sorted(
        (path for path in EXPERIMENT_RESULTS.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ):
        try:
            UUID(directory.name)
        except ValueError:
            continue
        result_file = directory / "raw.json"
        if result_file.is_file():
            payload = _experiment_history_payload(directory)
            results.append(_experiment_detail(payload, include_series=False))
        if len(results) >= 20:
            break
    return results


@app.post("/experiments", status_code=201)
def create_experiment(request: ExperimentRequest):
    if len(set(request.seeds)) != len(request.seeds):
        raise HTTPException(422, "experiment seeds must be unique")
    if any(seed < 0 or seed > 1_000_000 for seed in request.seeds):
        raise HTTPException(422, "seeds must be between 0 and 1000000")
    from botkernel.evaluation import run_evaluation

    try:
        result = run_evaluation(request.seeds, [request.scenario], request.duration, EXPERIMENT_RESULTS)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return _experiment_detail(_experiment_payload(result["run_id"]))


@app.get("/experiments/{run_id}")
def get_experiment(run_id: str):
    return _experiment_detail(_experiment_payload(run_id))


@app.get("/experiments/{run_id}/artifacts/{artifact}")
def get_experiment_artifact(
    run_id: str,
    artifact: Literal["raw.json", "summary.csv", "ticks.csv", "effects.csv", "report.md"],
):
    payload = _experiment_payload(run_id)
    path = EXPERIMENT_RESULTS / payload["run_id"] / artifact
    if not path.is_file():
        raise HTTPException(404, "experiment artifact not found")
    return FileResponse(path, filename=artifact)


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)
    provider: Literal["deterministic_mock", "bedrock"] | None = None

    @field_validator("idempotency_key")
    @classmethod
    def nonblank_key(cls, value):
        if not value.strip(): raise ValueError("must not be blank")
        return value


class InvestigationResponse(BaseModel):
    id: UUID
    incident_id: int
    status: Literal["RUNNING", "COMPLETE", "INSUFFICIENT_EVIDENCE", "FAILED"]
    provider: str
    report: dict | None = None
    error_category: str | None = None
    created_at: AwareDatetime
    completed_at: AwareDatetime | None = None


@app.post("/incidents/{incident_id}/investigations", response_model=InvestigationResponse)
def create_investigation(incident_id: Annotated[int, ApiPath(ge=1)], request: InvestigationRequest):
    from botkernel.investigation_service import start, MissingIncident, Conflict, Busy
    provider=request.provider or os.getenv("INVESTIGATOR_PROVIDER","deterministic_mock")
    if provider not in ("deterministic_mock","bedrock"):
        raise HTTPException(503,"configured investigator provider is unavailable")
    try:
        return start(incident_id, request.idempotency_key, provider)
    except Busy as error:
        raise HTTPException(503, "investigation capacity busy", headers={"Retry-After":"2"}) from error
    except MissingIncident as error:
        raise HTTPException(404, "incident not found") from error
    except Conflict as error:
        raise HTTPException(409, "idempotency key conflicts with previous request") from error


@app.get("/incidents/{incident_id}/investigations", response_model=list[InvestigationResponse])
def investigations_for_incident(incident_id: Annotated[int, ApiPath(ge=1)]):
    from botkernel.investigation_service import list_reports
    with engine.connect() as c:
        if not c.execute(text("SELECT 1 FROM incidents WHERE id=:id"), {'id':incident_id}).first():
            raise HTTPException(404, "incident not found")
    return list_reports(incident_id)


@app.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(investigation_id: UUID):
    from botkernel.investigation_service import get
    result=get(str(investigation_id))
    if result is None: raise HTTPException(404, "investigation not found")
    return result
