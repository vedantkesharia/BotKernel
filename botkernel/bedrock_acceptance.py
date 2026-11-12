"""Explicit, bounded Bedrock acceptance through BotKernel's existing workflows."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text


MODEL_ID = "us.amazon.nova-micro-v1:0"
REGION = "us-east-2"


class AcceptanceError(RuntimeError):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


def _is_loopback_host(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return bool(host) and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_live_configuration(api_url: str | None = None) -> None:
    required = {
        "BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED": "true",
        "CLOUD_MODE": "mock",
        "AWS_DEPLOY_ALLOWED": "false",
        "AI_ACTION_EXECUTION_ENABLED": "false",
        "BEDROCK_ENABLED": "true",
        "BEDROCK_SPEND_AUTHORIZED": "true",
        "AGENT_PROVIDER": "bedrock",
        "INVESTIGATOR_PROVIDER": "bedrock",
        "BEDROCK_MODEL_ID": MODEL_ID,
        "BEDROCK_REGION": REGION,
        "BEDROCK_MAX_OUTPUT_TOKENS": "512",
        "BEDROCK_MAX_CALLS_PER_RUN": "1",
        "BEDROCK_MAX_CALLS_PER_DAY": "3",
        "MAX_BEDROCK_TOKENS_PER_DAY": "20000",
    }
    if any(os.getenv(name, "").strip() != value for name, value in required.items()):
        raise AcceptanceError("acceptance_configuration_mismatch")
    database_url = os.getenv("DATABASE_URL")
    redis_url = os.getenv("REDIS_URL")
    if not database_url or not redis_url:
        raise AcceptanceError("local_database_or_redis_not_configured")
    if (
        not _is_loopback_host(urlsplit(api_url or os.getenv(
            "BOTKERNEL_API_URL", "http://127.0.0.1:8000"
        )).hostname)
        or not _is_loopback_host(urlsplit(database_url).hostname)
        or not _is_loopback_host(urlsplit(redis_url).hostname)
    ):
        raise AcceptanceError("acceptance_endpoints_must_be_loopback")
    checkpoint_path = os.getenv("BOTKERNEL_AGENT_CHECKPOINTS")
    if not checkpoint_path:
        raise AcceptanceError("dedicated_checkpoint_path_required")
    checkpoint = Path(checkpoint_path).expanduser()
    if checkpoint.exists() or Path(str(checkpoint) + ".owner").exists():
        raise AcceptanceError("acceptance_checkpoint_must_be_new")


def validate_agent_observation(role: str, telemetry: dict[str, Any]) -> None:
    if telemetry.get("simulated") is not True:
        raise AcceptanceError("non_simulator_telemetry")
    effects = telemetry.get("recent_effects")
    if not isinstance(effects, list) or not any(
        isinstance(effect, dict) and isinstance(effect.get("action_id"), str)
        for effect in effects
    ):
        raise AcceptanceError("committed_effect_evidence_required")
    if telemetry.get("controller_hold") or telemetry.get("controller_status") in {
        "HOLD", "VERIFYING", "ESCALATED",
    } or telemetry.get("pending_action"):
        raise AcceptanceError("resource_not_quiescent")
    capacity = telemetry.get("capacity")
    if type(capacity) is not int or not 1 <= capacity <= 20:
        raise AcceptanceError("invalid_resource_capacity")
    if role == "cost" and capacity <= 3:
        raise AcceptanceError("cost_case_lacks_downscale_headroom")
    if role == "performance":
        latency = telemetry.get("latency_p95")
        if type(latency) not in (int, float) or latency <= 80 or capacity > 17:
            raise AcceptanceError("performance_case_lacks_scale_up_signal")
    if role not in {"cost", "performance"}:
        raise AcceptanceError("unsupported_agent_role")


def _resource_snapshot(engine, resource: str) -> dict[str, Any]:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT capacity,version FROM resources WHERE id=:resource"),
            {"resource": resource},
        ).first()
        if row is None:
            raise AcceptanceError("resource_not_found")
        pending = connection.execute(
            text("SELECT count(*) FROM actions WHERE resource=:resource "
                 "AND state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN')"),
            {"resource": resource},
        ).scalar_one()
        counts = {}
        for name, query in {
            "actions": "SELECT count(*) FROM actions WHERE resource=:resource",
            "effects": "SELECT count(*) FROM effects WHERE resource=:resource",
            "outbox": "SELECT count(*) FROM outbox WHERE action_id IN "
                      "(SELECT id FROM actions WHERE resource=:resource)",
            "receipts": "SELECT count(*) FROM receipts WHERE action_id IN "
                        "(SELECT id FROM actions WHERE resource=:resource)",
        }.items():
            counts[name] = connection.execute(text(query), {"resource": resource}).scalar_one()
    return {
        "capacity": row.capacity,
        "version": row.version,
        "pending": pending,
        **counts,
    }


def _reasoning_record(path: str, run_id: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    try:
        with sqlite3.connect(path, timeout=3) as connection:
            row = connection.execute(
                "SELECT status,result_json,provenance_json FROM agent_reasoning WHERE run_id=?",
                (run_id,),
            ).fetchone()
    except (sqlite3.Error, OSError) as error:
        raise AcceptanceError("durable_agent_provenance_unavailable") from error
    if not row or row[0] != "COMPLETED" or not row[1] or not row[2]:
        raise AcceptanceError("durable_agent_provenance_unavailable")
    try:
        return row[0], json.loads(row[1]), json.loads(row[2])
    except (TypeError, json.JSONDecodeError) as error:
        raise AcceptanceError("durable_agent_provenance_invalid") from error


def _require_usage(provenance: dict[str, Any], *, expected_invocations: int) -> None:
    if provenance.get("provider") != "bedrock" or provenance.get("model_id") != MODEL_ID:
        raise AcceptanceError("provider_or_model_provenance_mismatch")
    if provenance.get("invocations") != expected_invocations:
        raise AcceptanceError("invocation_count_mismatch")
    for field in ("input_tokens", "output_tokens"):
        value = provenance.get(field)
        if type(value) is not int or value < 0:
            raise AcceptanceError("actual_token_usage_unavailable")


def _read_json(client: httpx.Client, path: str) -> Any:
    try:
        response = client.get(path)
        response.raise_for_status()
        return response.json()
    except Exception as error:
        raise AcceptanceError("acceptance_read_failed") from error


def _save(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def prepare_local_fixtures(*, api_url: str, output: Path) -> dict[str, Any]:
    """Create isolated simulator resources and commit one seed action per resource."""
    for name, value in {
        "CLOUD_MODE": "mock",
        "AWS_DEPLOY_ALLOWED": "false",
        "AI_ACTION_EXECUTION_ENABLED": "false",
        "BEDROCK_ENABLED": "false",
        "BEDROCK_SPEND_AUTHORIZED": "false",
        "AGENT_PROVIDER": "deterministic_mock",
        "INVESTIGATOR_PROVIDER": "deterministic_mock",
    }.items():
        if os.getenv(name, value).strip().lower() != value:
            raise AcceptanceError("local_fixture_requires_all_ai_and_cloud_gates_off")
    api_host = urlsplit(api_url).hostname
    try:
        if api_host != "localhost" and not ipaddress.ip_address(api_host or "").is_loopback:
            raise AcceptanceError("local_fixture_api_must_be_loopback")
    except ValueError as error:
        raise AcceptanceError("local_fixture_api_must_be_loopback") from error
    if output.exists():
        raise AcceptanceError("acceptance_output_already_exists")

    from botkernel.core import engine

    database_host = engine.url.host
    redis_host = urlsplit(os.getenv("REDIS_URL", "")).hostname
    try:
        db_is_local = bool(database_host) and ipaddress.ip_address(database_host).is_loopback
        redis_is_local = redis_host == "localhost" or ipaddress.ip_address(redis_host or "").is_loopback
    except ValueError:
        db_is_local = redis_is_local = False
    if not db_is_local or not redis_is_local:
        raise AcceptanceError("local_fixture_database_and_redis_must_be_loopback")

    run_id = str(uuid.uuid4())
    suffix = run_id.replace("-", "")[:12]
    resources = {
        "cost": f"bk-accept-cost-{suffix}",
        "performance": f"bk-accept-performance-{suffix}",
    }
    seed_agent = "bedrock-acceptance-seed"
    result: dict[str, Any] = {
        "run_id": run_id,
        "status": "RUNNING",
        "mode": "local_simulation_only",
        "cloud_mode": "mock",
        "bedrock_enabled": False,
        "ai_action_execution_enabled": False,
        "resources": resources,
        "seed_actions": [],
    }
    try:
        with httpx.Client(base_url=api_url.rstrip("/"), timeout=15) as client:
            health = _read_json(client, "/health")
            if (
                health.get("cloud_mode") != "mock"
                or health.get("deployment_target") != "local"
                or health.get("mode") != "local simulation"
                or health.get("real_infrastructure_remediation") is not False
            ):
                raise AcceptanceError("api_not_in_local_simulation_mode")
            with engine.begin() as connection:
                for resource in resources.values():
                    inserted = connection.execute(
                        text("INSERT INTO resources(id,capacity,version) VALUES(:id,4,0) "
                             "ON CONFLICT(id) DO NOTHING RETURNING id"),
                        {"id": resource},
                    ).first()
                    if inserted is None:
                        raise AcceptanceError("fixture_resource_already_exists")
                    connection.execute(
                        text("INSERT INTO external_resources(id,capacity) VALUES(:id,4)"),
                        {"id": resource},
                    )

            client.post(f"/agents/{seed_agent}").raise_for_status()
            for role, resource, capacity in (
                ("cost", resources["cost"], 5),
                ("performance", resources["performance"], 3),
            ):
                key = f"bedrock-acceptance-seed:{run_id}:{role}"
                payload = {
                    "agent": seed_agent,
                    "workflow": "bedrock-acceptance-fixture",
                    "idempotency_key": key,
                    "resource": resource,
                    "expected_version": 0,
                    "capacity": capacity,
                    "risk": "low",
                }
                response = client.post("/actions", json=payload)
                response.raise_for_status()
                action_id = response.json().get("id")
                if not isinstance(action_id, str):
                    raise AcceptanceError("fixture_action_id_missing")
                seed = {
                    "role": role,
                    "resource": resource,
                    "action_id": action_id,
                    "idempotency_key": key,
                }
                result["seed_actions"].append(seed)
                deadline = time.monotonic() + 60
                action = None
                while time.monotonic() < deadline:
                    actions = _read_json(client, "/actions")
                    action = next(
                        (item for item in actions if str(item.get("id")) == action_id), None
                    )
                    if action and action.get("state") in {
                        "SUCCEEDED", "FAILED", "ESCALATED", "COMPENSATED",
                    }:
                        break
                    time.sleep(0.5)
                snapshot = _resource_snapshot(engine, resource)
                if (
                    not action
                    or action.get("state") != "SUCCEEDED"
                    or snapshot["actions"] != 1
                    or snapshot["effects"] != 1
                    or snapshot["outbox"] != 1
                    or snapshot["receipts"] != 1
                    or snapshot["version"] != 1
                    or snapshot["capacity"] != capacity
                ):
                    raise AcceptanceError("fixture_action_not_committed_once")
                seed["state"] = action["state"]
                seed["capacity"] = snapshot["capacity"]
                seed["version"] = snapshot["version"]
                seed["committed_effects"] = snapshot["effects"]
                _save(output, result)

        result["status"] = "PASSED"
        _save(output, result)
        return result
    except Exception as error:
        result["status"] = "FAILED"
        result["error_category"] = getattr(error, "category", "fixture_preparation_failed")
        _save(output, result)
        raise


def run_acceptance(
    *,
    api_url: str,
    cost_resource: str,
    performance_resource: str,
    incident_id: int,
    output: Path,
) -> dict[str, Any]:
    """Run at most two role cycles and one investigation; never retry a request."""
    validate_live_configuration(api_url)
    if output.exists():
        raise AcceptanceError("acceptance_output_already_exists")
    if cost_resource == performance_resource:
        raise AcceptanceError("agent_resources_must_be_distinct")

    from botkernel.core import engine
    from botkernel.lang_agents import run_once

    run_id = str(uuid.uuid4())
    result: dict[str, Any] = {
        "run_id": run_id,
        "status": "RUNNING",
        "model_id": MODEL_ID,
        "region": REGION,
        "action_execution_enabled": False,
        "cases": {},
    }
    try:
        with httpx.Client(base_url=api_url.rstrip("/"), timeout=15) as client:
            health = _read_json(client, "/health")
            if (
                health.get("cloud_mode") != "mock"
                or health.get("deployment_target") != "local"
                or health.get("mode") != "local simulation"
                or health.get("real_infrastructure_remediation") is not False
            ):
                raise AcceptanceError("api_not_in_local_simulation_mode")
            telemetry_rows = _read_json(client, "/telemetry")
            incident_rows = _read_json(client, "/incidents")
            incident = next((item for item in incident_rows if item.get("id") == incident_id), None)
            if incident is None:
                raise AcceptanceError("incident_not_found")
            incident_resource = incident.get("resource")
            if not isinstance(incident_resource, str) or not incident_resource:
                raise AcceptanceError("incident_resource_missing")
            if incident_resource in {cost_resource, performance_resource}:
                raise AcceptanceError("incident_resource_must_be_isolated")
            incident_evidence = incident.get("evidence") or {}
            incident_snapshots = [
                incident_evidence.get(key) for key in ("origin", "last_detection", "latest")
            ]
            incident_actions = {
                action for snapshot in incident_snapshots if isinstance(snapshot, dict)
                for action in snapshot.get("actions", []) if isinstance(action, str)
            }
            if not incident_actions:
                raise AcceptanceError("incident_lacks_controller_effect_evidence")
            graph = _read_json(
                client,
                f"/graph?window=3600&resource={incident_resource}",
            )
            graph_actions = {
                effect.get("action_id") for effect in graph.get("evidence", [])
                if isinstance(effect, dict) and isinstance(effect.get("action_id"), str)
            }
            if not incident_actions.issubset(graph_actions):
                raise AcceptanceError("incident_effects_not_in_committed_graph")

            for role, resource in (
                ("cost", cost_resource),
                ("performance", performance_resource),
            ):
                telemetry = next(
                    (item for item in telemetry_rows if item.get("id") == resource), None
                )
                if telemetry is None:
                    raise AcceptanceError("resource_not_found")
                validate_agent_observation(role, telemetry)
                before = _resource_snapshot(engine, resource)
                if before["pending"]:
                    raise AcceptanceError("resource_has_pending_action")

                previous_agent_resource = os.environ.get("BOTKERNEL_AGENT_RESOURCE")
                os.environ["BOTKERNEL_AGENT_RESOURCE"] = resource
                case_run_id = f"bedrock-acceptance:{run_id}:{role}"
                try:
                    try:
                        agent_result = run_once(
                            role, api_url=api_url, run_id=case_run_id
                        )
                    except Exception as error:
                        category = getattr(error, "category", "agent_invocation_failed")
                        result["cases"][role] = {
                            "status": "FAILED_OR_OUTCOME_UNKNOWN",
                            "error_category": category,
                            "run_id": case_run_id,
                        }
                        raise AcceptanceError(category) from error
                finally:
                    if previous_agent_resource is None:
                        os.environ.pop("BOTKERNEL_AGENT_RESOURCE", None)
                    else:
                        os.environ["BOTKERNEL_AGENT_RESOURCE"] = previous_agent_resource

                if agent_result.get("run_id") != case_run_id:
                    raise AcceptanceError("agent_run_identity_mismatch")
                decision = agent_result.get("ai_decision", {})
                provenance = agent_result.get("ai_provenance", {})
                status, persisted_decision, persisted_provenance = _reasoning_record(
                    os.environ["BOTKERNEL_AGENT_CHECKPOINTS"], case_run_id
                )
                if (
                    status != "COMPLETED"
                    or persisted_decision != decision
                    or persisted_provenance != provenance
                ):
                    raise AcceptanceError("durable_agent_provenance_mismatch")
                observed = agent_result.get("telemetry", {})
                validate_agent_observation(role, observed)
                _require_usage(provenance, expected_invocations=1)
                delta = decision.get("proposed_delta")
                if decision.get("resource") != resource or type(delta) is not int:
                    raise AcceptanceError("agent_decision_invalid")
                if role == "cost" and delta > 0 or role == "performance" and delta < 0:
                    raise AcceptanceError("agent_role_direction_invalid")
                allowed_references = {
                    f"resource:{resource}",
                    *(effect["action_id"] for effect in observed["recent_effects"]),
                }
                if not decision.get("evidence_references") or not set(
                    decision["evidence_references"]
                ).issubset(allowed_references):
                    raise AcceptanceError("agent_evidence_reference_invalid")
                if agent_result.get("outcome", {}).get("decision") not in {
                    "advisory", "no_change",
                }:
                    raise AcceptanceError("agent_decision_not_advisory")
                after = _resource_snapshot(engine, resource)
                if after != before:
                    raise AcceptanceError("agent_mutated_operational_state")
                result["cases"][role] = {
                    "status": "PASSED",
                    "run_id": case_run_id,
                    "resource": resource,
                    "simulated": observed["simulated"],
                    "recent_effect_count": len(observed["recent_effects"]),
                    "decision": decision,
                    "provenance": provenance,
                    "outcome": agent_result["outcome"],
                }
                _save(output, result)

            before_incident = _resource_snapshot(engine, incident_resource)
            idempotency_key = f"bedrock-acceptance:{run_id}:investigator"
            request = {"idempotency_key": idempotency_key, "provider": "bedrock"}
            try:
                response = client.post(
                    f"/incidents/{incident_id}/investigations", json=request
                )
                response.raise_for_status()
                investigation = response.json()
            except Exception as error:
                result["cases"]["investigator"] = {
                    "status": "FAILED_OR_OUTCOME_UNKNOWN",
                    "error_category": "investigation_request_failed",
                    "idempotency_key": idempotency_key,
                }
                raise AcceptanceError("investigation_request_failed") from error

            report = investigation.get("report") or {}
            analysis = report.get("ai_analysis") or {}
            usage = report.get("usage") or {}
            result["cases"]["investigator"] = {
                "status": "RECEIVED",
                "idempotency_key": idempotency_key,
                "investigation_id": investigation.get("id"),
                "provider": investigation.get("provider"),
                "report_status": investigation.get("status"),
                "outcome": report.get("outcome"),
                "provenance": usage,
                "ai_analysis_status": analysis.get("status"),
            }
            _save(output, result)
            if (
                investigation.get("status") != "COMPLETE"
                or investigation.get("provider") != "bedrock"
                or report.get("outcome") != "COMPLETE"
                or analysis.get("status") != "COMPLETE"
            ):
                raise AcceptanceError("investigation_incomplete_or_abstained")
            _require_usage(usage, expected_invocations=1)
            refs = set(analysis.get("supporting_references", []))
            valid_refs = {
                f"incident:{incident_id}",
                *(effect["action_id"] for effect in report.get("effects", [])),
            }
            if not refs or not refs.issubset(valid_refs):
                raise AcceptanceError("investigator_evidence_reference_invalid")
            if analysis.get("hypotheses") and not any(
                ref != f"incident:{incident_id}" for ref in refs
            ):
                raise AcceptanceError("hypotheses_lack_effect_evidence")
            if not any(
                finding.get("classification") == "VERIFIED_FACT"
                for finding in report.get("findings", [])
            ):
                raise AcceptanceError("deterministic_facts_missing")

            # Only replay after a completed response, with the same idempotency key.
            replay = client.post(
                f"/incidents/{incident_id}/investigations", json=request
            )
            replay.raise_for_status()
            if replay.json() != investigation:
                raise AcceptanceError("investigation_replay_changed_report")
            persisted = _read_json(client, f"/investigations/{investigation['id']}")
            if persisted != investigation:
                raise AcceptanceError("persisted_report_mismatch")
            if _resource_snapshot(engine, incident_resource) != before_incident:
                raise AcceptanceError("investigator_mutated_operational_state")
            result["cases"]["investigator"] = {
                "status": "PASSED",
                "idempotency_key": idempotency_key,
                "investigation_id": investigation["id"],
                "provider": investigation["provider"],
                "provenance": usage,
                "hypothesis_count": len(analysis.get("hypotheses", [])),
                "effect_count": len(report.get("effects", [])),
                "replay_preserved_report": True,
                "persisted_get_matched_post": True,
                "operational_state_unchanged": True,
            }

        result["status"] = "PASSED"
        _save(output, result)
        return result
    except Exception as error:
        result["status"] = "FAILED_OR_OUTCOME_UNKNOWN"
        result["error_category"] = getattr(error, "category", "acceptance_validation_failed")
        _save(output, result)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute-live", action="store_true",
                      help="Explicitly request the bounded live workflow; all gates are still checked.")
    mode.add_argument("--prepare-local-fixtures", action="store_true",
                      help="Create fresh simulator resources/effects with every cloud and AI gate off.")
    parser.add_argument("--api-url", default=os.getenv("BOTKERNEL_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cost-resource")
    parser.add_argument("--performance-resource")
    parser.add_argument("--incident-id", type=int)
    args = parser.parse_args()
    try:
        if args.prepare_local_fixtures:
            if any((args.cost_resource, args.performance_resource, args.incident_id is not None)):
                parser.error("live case arguments are only valid with --execute-live")
            result = prepare_local_fixtures(api_url=args.api_url, output=args.output)
        else:
            missing = [
                name for name, value in (
                    ("--cost-resource", args.cost_resource),
                    ("--performance-resource", args.performance_resource),
                    ("--incident-id", args.incident_id),
                ) if value is None
            ]
            if missing:
                parser.error("required with --execute-live: " + ", ".join(missing))
            result = run_acceptance(
                api_url=args.api_url,
                cost_resource=args.cost_resource,
                performance_resource=args.performance_resource,
                incident_id=args.incident_id,
                output=args.output,
            )
    except AcceptanceError as error:
        print(f"Bedrock acceptance stopped: {error.category}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
