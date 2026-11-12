"""Bounded deterministic gateway-to-recovery demonstration."""
import json
import os
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
from botkernel.security import operator_headers


API_URL = os.getenv("BOTKERNEL_API_URL", "http://api:8000")
TIMEOUT_SECONDS = int(os.getenv("DEMO_TIMEOUT_SECONDS", "180"))
if not 60 <= TIMEOUT_SECONDS <= 240:
    raise ValueError("DEMO_TIMEOUT_SECONDS must be between 60 and 240")


def _resource(client: httpx.Client, resource_id: str) -> dict[str, Any] | None:
    resources = client.get("/resources").raise_for_status().json()
    return next((resource for resource in resources if resource["id"] == resource_id), None)


def _wait_for_action(client: httpx.Client, action_id: str, deadline: float) -> None:
    while time.monotonic() < deadline:
        actions = client.get("/actions").raise_for_status().json()
        action = next((item for item in actions if item["id"] == action_id), None)
        if action and action["state"] == "SUCCEEDED":
            return
        if action and action["state"] in ("FAILED", "ESCALATED"):
            raise RuntimeError(f"Demo action {action_id} ended in {action['state']}.")
        time.sleep(0.25)
    raise TimeoutError(f"Demo action {action_id} did not complete before the deadline.")


def _oscillate(
    client: httpx.Client,
    resource_id: str,
    run_id: str,
    cycle: int,
    deadline: float,
) -> list[str]:
    action_ids = []
    cost_step = 1 if cycle == 1 else 2
    for step, agent in enumerate(("cost-demo", "performance-demo", "cost-demo", "performance-demo")):
        resource = _resource(client, resource_id)
        if resource is None:
            raise RuntimeError(f"Demo resource {resource_id} is unavailable.")
        capacity = resource["capacity"]
        target = max(1, capacity - cost_step) if agent == "cost-demo" else min(20, capacity + 2)
        response = client.post(
            "/actions",
            json={
                "agent": agent,
                "workflow": "bounded-live-demo",
                "idempotency_key": f"{run_id}:{cycle}:{step}:{agent}",
                "resource": resource_id,
                "expected_version": resource["version"],
                "capacity": target,
            },
        )
        response.raise_for_status()
        action_id = response.json()["id"]
        _wait_for_action(client, action_id, deadline)
        action_ids.append(action_id)
    return action_ids


def _incident(client: httpx.Client, resource_id: str) -> dict | None:
    incidents = client.get("/incidents").raise_for_status().json()
    return next((incident for incident in incidents if incident["resource"] == resource_id), None)


def _wait_for_incident(
    client: httpx.Client,
    resource_id: str,
    deadline: float,
    predicate: Callable[[dict[str, Any]], bool],
    expected: str,
) -> dict:
    while time.monotonic() < deadline:
        incident = _incident(client, resource_id)
        if incident and predicate(incident):
            return incident
        if incident and incident["status"] == "ESCALATED":
            raise RuntimeError(f"Live demo escalated before reaching {expected}.")
        time.sleep(1)
    raise TimeoutError(f"Live demo did not reach {expected} before its deadline.")


def _investigate_incident(
    client: httpx.Client,
    incident: dict[str, Any],
    run_id: str,
    resource_id: str,
) -> dict[str, Any]:
    """Create and verify a deterministic report from persisted incident evidence."""
    incident_id = incident["id"]
    idempotency_key = f"live-demo:{run_id}:{incident_id}"
    path = f"/incidents/{incident_id}/investigations"
    request = {"idempotency_key": idempotency_key, "provider": "deterministic_mock"}

    created = client.post(path, json=request)
    created.raise_for_status()
    initial = created.json()
    investigation_id = initial["id"]
    if initial["status"] not in ("COMPLETE", "INSUFFICIENT_EVIDENCE"):
        raise RuntimeError(f"Investigation ended in unexpected status {initial['status']}.")

    retrieved_response = client.get(f"/investigations/{investigation_id}")
    retrieved_response.raise_for_status()
    retrieved = retrieved_response.json()
    if retrieved["id"] != investigation_id or retrieved["report"] != initial["report"]:
        raise RuntimeError("Persisted investigation differs from the created report.")

    replay = client.post(path, json=request)
    replay.raise_for_status()
    replayed = replay.json()
    if replayed["id"] != investigation_id:
        raise RuntimeError("Identical investigation request did not reuse its durable report.")

    report = retrieved["report"]
    actions = client.get("/actions").raise_for_status().json()
    action_ids = {str(action["id"]) for action in actions}
    action_states = {str(action["id"]): action["state"] for action in actions}
    referenced_ids = {str(effect["action_id"]) for effect in report["effects"]}
    if not referenced_ids.issubset(action_ids):
        raise RuntimeError("Investigation references an action missing from the gateway ledger.")
    if any(action_states[action_id] != "SUCCEEDED" for action_id in referenced_ids):
        raise RuntimeError("Investigation cites an action that has not succeeded in the gateway ledger.")
    if any(effect["resource"] != resource_id for effect in report["effects"]):
        raise RuntimeError("Investigation contains an effect for an unrelated resource.")

    graph = client.get("/graph", params={"window": 3600, "resource": resource_id})
    graph.raise_for_status()
    graph_data = graph.json()
    graph_action_ids = {
        node["id"].removeprefix("action:")
        for node in graph_data["nodes"]
        if node.get("kind") == "action"
    }
    graph_matches = referenced_ids.issubset(graph_action_ids)
    if not graph_matches:
        raise RuntimeError("The Effect Graph does not contain every action cited by the report.")

    findings = report["findings"]
    return {
        "investigation_id": investigation_id,
        "incident_id": incident_id,
        "status": retrieved["status"],
        "outcome": report["outcome"],
        "provider": report["provider"],
        "reasoning_label": "Deterministic analysis — no LLM used",
        "effect_action_ids": sorted(referenced_ids),
        "effect_timeline": [
            {
                "action_id": effect["action_id"],
                "agent": effect["agent"],
                "version": effect["version"],
                "capacity": [effect["before_capacity"], effect["after_capacity"]],
                "state": effect["state"],
            }
            for effect in report["effects"]
        ],
        "transitions": report["transitions"],
        "reversal_pairs": report["reversals"],
        "finding_counts": {
            classification: sum(item["classification"] == classification for item in findings)
            for classification in (
                "VERIFIED_FACT",
                "DETERMINISTIC_INFERENCE",
                "HYPOTHESIS",
            )
        },
        "graph_action_references_verified": graph_matches,
        "duplicate_request_reused_id": replayed["id"] == investigation_id,
        "persisted_get_matched_post": retrieved["report"] == initial["report"],
    }


def run() -> dict:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    run_id = os.getenv("DEMO_RUN_ID", str(uuid.uuid4()))
    with httpx.Client(base_url=API_URL, timeout=5, headers=operator_headers()) as client:
        while time.monotonic() < deadline:
            try:
                if client.get("/ready").status_code == 200:
                    break
                time.sleep(1)
            except httpx.HTTPError:
                time.sleep(1)
        else:
            raise TimeoutError("Local API was not ready before the demo deadline.")

        for agent in ("cost-demo", "performance-demo"):
            client.post(f"/agents/{agent}").raise_for_status()
        resources = client.get("/resources").raise_for_status().json()
        requested_resource = os.getenv("DEMO_RESOURCE")
        resource_id = (
            next((resource["id"] for resource in resources if resource["id"] == requested_resource), None)
            if requested_resource
            else next(
                (resource["id"] for resource in resources if resource["id"] == "service-a"),
                resources[0]["id"] if resources else None,
            )
        )
        if resource_id is None:
            raise RuntimeError("The requested demo resource is not registered.")

        first_actions = _oscillate(client, resource_id, run_id, 1, deadline)
        detected = _wait_for_incident(
            client,
            resource_id,
            deadline,
            lambda incident: incident["status"] in ("HOLD", "VERIFYING", "VERIFIED"),
            "a detected incident",
        )
        verified = _wait_for_incident(
            client,
            resource_id,
            deadline,
            lambda incident: incident["status"] == "VERIFIED",
            "sustained recovery verification",
        )
        recurrence_actions = _oscillate(client, resource_id, run_id, 2, deadline)
        recurred = _wait_for_incident(
            client,
            resource_id,
            deadline,
            lambda incident: incident["status"] == "HOLD" and incident["recurrence_count"] > 0,
            "incident recurrence and selective containment",
        )
        investigation = _investigate_incident(client, recurred, run_id, resource_id)
        return {
            "run_id": run_id,
            "resource": resource_id,
            "first_cycle_actions": first_actions,
            "recurrence_cycle_actions": recurrence_actions,
            "detection_status": detected["status"],
            "verified_status": verified["status"],
            "final_status": recurred["status"],
            "recurrences": recurred["recurrence_count"],
            "interventions": recurred["intervention_count"],
            "lifecycle": recurred["evidence"].get("lifecycle", []),
            "investigation": investigation,
        }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
