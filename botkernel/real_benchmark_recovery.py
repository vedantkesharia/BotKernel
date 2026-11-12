"""Fault injection against a stopped, benchmark-owned worker only."""
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from confluent_kafka import Producer
from sqlalchemy import text

from botkernel.core import engine


def snapshot(action_id, resource):
    with engine.connect() as connection:
        return dict(connection.execute(text(
            "SELECT a.state, o.published, r.version, "
            "(SELECT count(*) FROM receipts WHERE action_id=a.id) AS receipts, "
            "(SELECT count(*) FROM effects WHERE action_id=a.id) AS effects "
            "FROM actions a JOIN outbox o ON o.action_id=a.id "
            "JOIN resources r ON r.id=a.resource WHERE a.id=:id AND r.id=:resource"
        ), {"id": action_id, "resource": resource}).mappings().one())


def run():
    if os.getenv("BOTKERNEL_BENCHMARK_OWNED") != "true" or engine.url.database != "bk_benchmark":
        raise RuntimeError("A dedicated benchmark-owned database is required")
    run_id = str(uuid.uuid4())
    name = "recovery-" + run_id
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO agents(id) VALUES (:id)"), {"id": name})
        connection.execute(text("INSERT INTO resources(id,capacity) VALUES (:id,1)"), {"id": name})
        connection.execute(text("INSERT INTO external_resources(id,capacity) VALUES (:id,1)"), {"id": name})
    folder = Path("/results") / run_id
    folder.mkdir(parents=True, exist_ok=False)
    environment = {**os.environ, "ROLE": "worker", "METRICS_ENABLED": "false"}
    crash = None
    recovery = None
    try:
        with (folder / "crash-worker.log").open("w", encoding="utf-8") as crash_log:
            crash = subprocess.Popen(
                [sys.executable, "-m", "botkernel.worker"],
                env={**environment, "CRASH_AFTER_EFFECT": "true"}, stdout=crash_log, stderr=crash_log,
            )
            with httpx.Client(base_url="http://api:8000", timeout=10) as client:
                response = client.post("/actions", json={
                    "agent": name, "workflow": "benchmark-recovery",
                    "idempotency_key": run_id, "resource": name,
                    "expected_version": 0, "capacity": 2,
                })
                response.raise_for_status()
                action_id = response.json()["id"]
            exit_code = crash.wait(timeout=90)
        crashed_at = time.monotonic()
        if exit_code != 17:
            raise RuntimeError(f"Crash worker exited with unexpected code {exit_code}")
        before = snapshot(action_id, name)
        if before["state"] != "DISPATCHED" or before["receipts"] != 1 or before["effects"] != 0 or before["version"] != 0:
            raise RuntimeError(f"Unexpected crash boundary: {before}")
        producer = Producer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]})
        errors = []
        producer.produce(os.environ["KAFKA_TOPIC"], key=action_id, value=action_id,
                         on_delivery=lambda error, message: errors.append(str(error)) if error else None)
        if producer.flush(15) or errors:
            raise RuntimeError(f"Duplicate injection was not acknowledged: {errors}")
        with (folder / "recovery-worker.log").open("w", encoding="utf-8") as recovery_log:
            recovery = subprocess.Popen(
                [sys.executable, "-m", "botkernel.worker"], env=environment,
                stdout=recovery_log, stderr=recovery_log,
            )
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                after = snapshot(action_id, name)
                if after["state"] == "SUCCEEDED":
                    break
                if recovery.poll() is not None:
                    raise RuntimeError(f"Recovery worker exited: {recovery.returncode}")
                time.sleep(0.1)
            else:
                raise TimeoutError("Recovery did not complete")
            completion_seconds = time.monotonic() - crashed_at
            deadline = time.monotonic() + 15
            deliveries = 0
            while time.monotonic() < deadline:
                recovery_log.flush()
                lines = (folder / "recovery-worker.log").read_text(encoding="utf-8").splitlines()
                deliveries = sum(action_id in line and "kafka_event_handled" in line for line in lines)
                if deliveries >= 2:
                    break
                time.sleep(0.2)
        result = {
            "run_id": run_id, "action_id": action_id, "crash_exit_code": exit_code,
            "before_recovery": before, "after_recovery": after,
            "completion_seconds_after_observed_crash": round(completion_seconds, 3),
            "explicit_duplicate_messages_acknowledged": 1,
            "recovery_worker_handled_log_entries": deliveries,
            "notes": ["The original consumer exits after committing the simulator receipt and before ledger finalization.",
                      "A second Kafka message is deliberately published after the crash.",
                      "Timing uses the benchmark process monotonic clock and includes duplicate injection and consumer startup."],
        }
        (folder / "recovery.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        if after["receipts"] != 1 or after["effects"] != 1 or after["version"] != 1 or deliveries < 2:
            raise RuntimeError(f"Recovery evidence incomplete; inspect {folder}")
    finally:
        for process in (crash, recovery):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    run()
