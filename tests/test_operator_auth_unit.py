"""Service-free authentication and incident-guard tests.

Run directly with ``python tests/test_operator_auth_unit.py``; the regular
pytest suite deliberately requires isolated PostgreSQL and Kafka.
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import redis  # noqa: F401
except ModuleNotFoundError as error:
    if error.name != "redis":
        raise
    redis = types.ModuleType("redis")
    redis.RedisError = type("RedisError", (Exception,), {})
    redis.Redis = type("Redis", (), {"from_url": classmethod(lambda cls, *a, **k: object())})
    sys.modules["redis"] = redis

from fastapi.testclient import TestClient
from botkernel.api import app


OPERATOR = "operator-" + "x" * 50
AGENT = "agent-" + "y" * 50
METRICS = "metrics-" + "z" * 50
HEADERS = {"Authorization": f"Bearer {OPERATOR}"}
AGENT_HEADERS = {"Authorization": f"Bearer {AGENT}"}


class Result:
    def __init__(self, value=None):
        self.value = value

    def mappings(self):
        return self

    def first(self):
        return self.value

    def scalar_one(self):
        return self.value


class IncidentEngine:
    def __init__(self, status):
        self.incident = {"resource": "resource-a", "status": status, "evidence": {},
                         "last_score": None, "score": 0.8}
        self.previous = None
        self.calls = []

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=None):
        sql = str(query)
        self.calls.append(sql)
        if "SELECT * FROM incidents" in sql:
            return Result(self.incident)
        if "SELECT id FROM resources" in sql:
            return Result({"id": "resource-a"})
        if "SELECT action,reason,created_at" in sql:
            return Result(self.previous)
        if "UPDATE incidents" in sql:
            self.incident["status"] = "RESOLVED"
        if "INSERT INTO incident_operator_actions" in sql:
            self.previous = {"action": params["action"], "reason": params["reason"], "created_at": "2025-01-01"}
            return Result("2025-01-01")
        return Result()


class OperatorAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "BOTKERNEL_OPERATOR_TOKEN": OPERATOR, "BOTKERNEL_AGENT_TOKEN": AGENT,
            "BOTKERNEL_METRICS_TOKEN": METRICS,
            "BOTKERNEL_OPERATOR_TOKEN_FILE": "", "BOTKERNEL_AGENT_TOKEN_FILE": "",
            "BOTKERNEL_METRICS_TOKEN_FILE": "",
        })
        self.env.start()
        self.client = TestClient(app)
        self.addCleanup(self.env.stop)
        self.addCleanup(self.client.close)

    def test_operator_and_invalid_credentials(self):
        self.assertEqual(self.client.get("/auth/session", headers=HEADERS).json(), {"role": "operator"})
        response = self.client.get("/auth/session", headers={"Authorization": "Bearer invalid"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_reads_mutations_metrics_and_agent_scope(self):
        for path in ("/agents", "/resources", "/incidents", "/graph", "/metrics", "/experiments"):
            self.assertEqual(self.client.get(path).status_code, 401, path)
            self.assertEqual(self.client.get(path, headers=AGENT_HEADERS).status_code, 403, path)
        for path in ("/incidents/1/acknowledge", "/incidents/1/resolve", "/incidents/1/investigations", "/experiments"):
            self.assertEqual(self.client.post(path, json={}).status_code, 401, path)
            self.assertEqual(self.client.post(path, json={}, headers=AGENT_HEADERS).status_code, 403, path)
        self.assertEqual(self.client.get("/auth/session", headers=AGENT_HEADERS).status_code, 403)
        self.assertEqual(self.client.post("/actions", json={}, headers=AGENT_HEADERS).status_code, 422)
        self.assertEqual(self.client.get("/telemetry", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        db = IncidentEngine("HOLD")
        with patch("botkernel.api.engine", db), patch("botkernel.api.cache") as cache:
            response = self.client.post("/agents/langgraph-cost", headers=AGENT_HEADERS)
            self.assertEqual(response.status_code, 200)
            cache.setex.assert_called_once_with("heartbeat:langgraph-cost", 30, "alive")

    def test_missing_weak_or_shared_configuration_fails_closed(self):
        for name, value in (("BOTKERNEL_OPERATOR_TOKEN", ""), ("BOTKERNEL_OPERATOR_TOKEN", "weak"),
                            ("BOTKERNEL_AGENT_TOKEN", OPERATOR), ("BOTKERNEL_METRICS_TOKEN", AGENT)):
            with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}):
                self.assertEqual(self.client.get("/auth/session", headers=HEADERS).status_code, 503)
                self.assertEqual(self.client.post("/actions", json={}, headers=AGENT_HEADERS).status_code, 503)
                self.assertEqual(self.client.get("/ready").status_code, 503)

    def test_metrics_token_is_read_only_and_scoped(self):
        headers = {"Authorization": f"Bearer {METRICS}"}
        with patch("botkernel.observability.generate_latest", return_value=b"metric 1\n"):
            self.assertEqual(self.client.get("/metrics", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/incidents", headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/actions", json={}, headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/metrics", headers={"Authorization": "Bearer invalid"}).status_code, 401)

    def test_secret_file_and_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operator.token"
            path.write_text(OPERATOR, encoding="utf-8")
            with patch.dict(os.environ, {"BOTKERNEL_OPERATOR_TOKEN": "", "BOTKERNEL_OPERATOR_TOKEN_FILE": str(path)}):
                self.assertEqual(self.client.get("/auth/session", headers=HEADERS).status_code, 200)
                path.write_text("rotated-" + "z" * 50, encoding="utf-8")
                self.assertEqual(self.client.get("/auth/session", headers=HEADERS).status_code, 401)
                self.assertEqual(self.client.get("/auth/session", headers={"Authorization": "Bearer rotated-" + "z" * 50}).status_code, 200)

    def test_authenticated_resolution_preserves_guards_and_idempotency(self):
        db = IncidentEngine("HOLD")
        body = {"idempotency_key": "test-key", "reason": "reviewed"}
        with patch("botkernel.api.engine", db):
            self.assertEqual(self.client.post("/incidents/1/resolve", json=body).status_code, 401)
            self.assertEqual(db.calls, [])
            self.assertEqual(self.client.post("/incidents/1/resolve", json=body, headers=AGENT_HEADERS).status_code, 403)
            self.assertEqual(db.calls, [])
            self.assertEqual(self.client.post("/incidents/1/resolve", json=body, headers=HEADERS).status_code, 409)
            self.assertEqual(db.incident["status"], "HOLD")
            db.incident["status"] = "VERIFIED"
            first = self.client.post("/incidents/1/resolve", json=body, headers=HEADERS)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json()["status"], "RESOLVED")
            replay = self.client.post("/incidents/1/resolve", json=body, headers=HEADERS)
            self.assertTrue(replay.json()["duplicate"])
            conflict = self.client.post("/incidents/1/resolve", json={**body, "reason": "changed"}, headers=HEADERS)
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(sum("INSERT INTO incident_operator_actions" in sql for sql in db.calls), 1)


if __name__ == "__main__":
    unittest.main()
