import json
import os
import subprocess
import sys
import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from botkernel import api
from botkernel.core import engine
from botkernel.security import agent_headers, operator_headers


def test_authenticated_gateway_incident_artifact_and_kafka_execution(tmp_path, monkeypatch):
    suffix = uuid.uuid4().hex[:12]
    resource, agent = "auth-" + suffix, "agent-" + suffix
    with engine.begin() as c:
        c.execute(text("UPDATE quota SET capacity=100 WHERE id=1"))
        c.execute(text("INSERT INTO resources(id,capacity,version) VALUES(:id,4,0)"), {"id": resource})
        c.execute(text("INSERT INTO external_resources(id,capacity) VALUES(:id,4)"), {"id": resource})
        incident = c.execute(text("INSERT INTO incidents(resource,score,status,evidence) VALUES(:r,0.8,'VERIFIED',CAST('{}' AS jsonb)) RETURNING id"), {"r": resource}).scalar_one()

    client = TestClient(api.app)
    operator, agent_token = operator_headers(), agent_headers()
    body = {"idempotency_key": "resolve-" + suffix, "reason": "reviewed"}
    assert client.get("/incidents").status_code == 401
    assert client.get("/incidents", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get("/incidents", headers=agent_token).status_code == 403
    assert client.post(f"/incidents/{incident}/resolve", json=body).status_code == 401
    assert client.post(f"/incidents/{incident}/resolve", json=body, headers=agent_token).status_code == 403
    with engine.connect() as c:
        assert c.execute(text("SELECT status FROM incidents WHERE id=:id"), {"id": incident}).scalar_one() == "VERIFIED"
    assert client.get("/incidents", headers=operator).status_code == 200
    assert client.post(f"/incidents/{incident}/acknowledge", json=body, headers=operator).status_code == 409
    assert client.post(f"/incidents/{incident}/resolve", json=body, headers=operator).json()["status"] == "RESOLVED"

    run_id = str(uuid.uuid4())
    directory = tmp_path / run_id
    directory.mkdir()
    (directory / "raw.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
    (directory / "report.md").write_text("auth artifact", encoding="utf-8")
    monkeypatch.setattr(api, "EXPERIMENT_RESULTS", tmp_path)
    artifact = f"/experiments/{run_id}/artifacts/report.md"
    assert client.get(artifact).status_code == 401
    assert client.get(artifact, headers=agent_token).status_code == 403
    assert client.get(artifact, headers=operator).text == "auth artifact"

    assert client.post("/agents/" + agent, headers=agent_token).status_code == 200
    action = client.post("/actions", headers=agent_token, json={
        "agent": agent, "workflow": "auth-integration", "idempotency_key": suffix,
        "resource": resource, "expected_version": 0, "capacity": 5,
    })
    assert action.status_code == 202, action.text
    action_id = action.json()["id"]
    processes = []
    try:
        for role in ("publisher", "worker"):
            env = {**os.environ, "ROLE": role, "METRICS_ENABLED": "false"}
            processes.append(subprocess.Popen(
                [sys.executable, "-m", "botkernel.worker"], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ))
        until = time.monotonic() + 30
        while time.monotonic() < until:
            with engine.connect() as c:
                committed = c.execute(text("SELECT EXISTS(SELECT 1 FROM effects WHERE action_id=:id)"), {"id": action_id}).scalar_one()
            if committed:
                break
            assert all(p.poll() is None for p in processes), "publisher or worker exited"
            time.sleep(.2)
        else:
            raise AssertionError("Kafka worker did not commit the action effect")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
