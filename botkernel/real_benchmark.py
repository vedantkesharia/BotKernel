"""Bounded client-observed benchmark for a dedicated local Compose project."""
import argparse
import csv
import json
import os
import platform
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

from botkernel.core import engine
from botkernel.security import operator_headers
from botkernel.benchmark_runtime import require_owned_database, benchmark_api_url


class BacklogSampler:
    """Best effort bounded telemetry, independent of workload success."""

    def __init__(self, interval=0.2, max_samples=5000):
        if not 0.1 <= interval <= 10:
            raise ValueError("Sample interval must be 0.1..10 seconds")
        self.interval, self.max_samples = interval, max_samples
        self.samples, self.errors = [], []
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.started = time.monotonic()

    def _error(self, stage, error):
        with self.lock:
            if len(self.errors) < 100:
                self.errors.append({"stage": stage, "type": type(error).__name__})

    def _run(self):
        db = consumer = None
        partitions = None
        try:
            try:
                db = create_engine(engine.url, pool_size=1, max_overflow=0,
                                   pool_timeout=0.2, connect_args={"connect_timeout": 1})
            except Exception as error:
                self._error("database_setup", error)
            try:
                from confluent_kafka import Consumer, TopicPartition
                group = os.getenv("KAFKA_CONSUMER_GROUP")
                topic = os.getenv("KAFKA_TOPIC")
                if not group or not topic:
                    raise ValueError("Unique topic/group required")
                consumer = Consumer({
                    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                    "group.id": group, "enable.auto.commit": False,
                    "allow.auto.create.topics": False,
                })
            except Exception as error:
                self._error("kafka_setup", error)
            for _ in range(self.max_samples):
                if self.stop_event.is_set():
                    break
                tick = time.monotonic()
                sample = {"elapsed_seconds": round(tick - self.started, 3),
                          "timestamp_ns": time.time_ns(), "unpublished_outbox": None,
                          "active_actions": None, "consumer_lag": None, "partitions": None}
                if db is not None:
                    try:
                        with db.begin() as connection:
                            connection.execute(text("SET LOCAL statement_timeout = '500ms'"))
                            row = connection.execute(text(
                                "SELECT (SELECT count(*) FROM outbox WHERE NOT published) AS unpublished_outbox, "
                                "(SELECT count(*) FROM actions WHERE state IN "
                                "('RESERVED','DISPATCHED','OUTCOME_UNKNOWN','ESCALATED')) AS active_actions"
                            )).mappings().one()
                            sample.update(dict(row))
                    except Exception as error:
                        self._error("database_sample", error)
                if consumer is not None:
                    try:
                        if partitions is None:
                            metadata = consumer.list_topics(topic=topic, timeout=0.5).topics[topic]
                            if metadata.error or not metadata.partitions or len(metadata.partitions) > 64:
                                raise ValueError("Unavailable or excessive partitions")
                            partitions = [TopicPartition(topic, p) for p in sorted(metadata.partitions)]
                        committed = consumer.committed(partitions, timeout=0.5)
                        offsets = []
                        for partition in committed:
                            if partition.error:
                                raise ValueError("Committed offset unavailable")
                            low, high = consumer.get_watermark_offsets(partition, timeout=0.5)
                            offset = partition.offset if partition.offset >= 0 else None
                            lag = high - offset if offset is not None and low <= offset <= high else (
                                0 if offset is None and low == high else None)
                            offsets.append({"partition": partition.partition, "low": low,
                                            "high": high, "committed": offset, "lag": lag})
                        sample["partitions"] = offsets
                        if all(p["lag"] is not None for p in offsets):
                            sample["consumer_lag"] = sum(p["lag"] for p in offsets)
                    except Exception as error:
                        self._error("kafka_sample", error)
                with self.lock:
                    self.samples.append(sample)
                self.stop_event.wait(max(0, self.interval - (time.monotonic() - tick)))
        except Exception as error:
            self._error("sampler", error)
        finally:
            if consumer is not None:
                try:
                    consumer.close()
                except Exception as error:
                    self._error("kafka_close", error)
            if db is not None:
                db.dispose()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=2)
        with self.lock:
            samples, errors = list(self.samples), list(self.errors)
        return {"interval_seconds": self.interval, "max_samples": self.max_samples,
                "sample_limit_reached": len(samples) == self.max_samples,
                "thread_still_stopping": self.thread.is_alive(),
                "samples": samples, "errors": errors,
                "coverage": {key: sum(s[key] is not None for s in samples)
                             for key in ("unpublished_outbox", "active_actions", "consumer_lag")},
                "highwaters": {key: max((s[key] for s in samples if s[key] is not None), default=None)
                               for key in ("unpublished_outbox", "active_actions", "consumer_lag")}}


def percentile(values, percentile_value):
    ordered = sorted(values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * percentile_value / 100
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 3)


def _request(client, agent, resource, version, capacity, run_id, key):
    started = time.monotonic()
    response = client.post("/actions", json={
        "agent": agent, "workflow": "real-benchmark", "resource": resource,
        "idempotency_key": f"{run_id}:{key}", "expected_version": version,
        "capacity": capacity,
    })
    admitted = time.monotonic()
    row = {
        "key": key, "resource": resource, "http_status": response.status_code,
        "admission_ms": round((admitted - started) * 1000, 3),
        "completion_ms": None, "action_id": None, "state": "REJECTED",
    }
    if response.status_code != 202:
        row["error"] = response.text[:500]
        return row
    row["action_id"] = response.json()["id"]
    deadline = started + 90
    while time.monotonic() < deadline:
        status = client.get(
            f"/agents/{agent}/action-by-key", params={"key": f"{run_id}:{key}"}
        )
        status.raise_for_status()
        state = status.json()["state"]
        if state in ("SUCCEEDED", "FAILED", "ESCALATED"):
            row["state"] = state
            row["completion_ms"] = round((time.monotonic() - started) * 1000, 3)
            return row
        time.sleep(0.05)
    row["state"] = "TIMEOUT"
    return row


def run(count, concurrency, warmup, output):
    require_owned_database(engine.url.database, allow_legacy=True)
    if not 1 <= concurrency <= min(count, 10) or not 1 <= count <= 1000 or not 0 <= warmup <= 10:
        raise ValueError("Bounds: actions 1..1000, concurrency 1..min(actions,10), warmup 0..10")
    run_id = str(uuid.uuid4())
    agent = "benchmark-" + run_id
    resources = [f"benchmark-{run_id}-{i}" for i in range(concurrency)]
    with engine.begin() as connection:
        if connection.execute(text("SELECT count(*) FROM actions")).scalar_one():
            raise RuntimeError("Benchmark database is not fresh; use a new Compose project")
        connection.execute(text("UPDATE quota SET capacity=40 WHERE id=1"))
        connection.execute(text("INSERT INTO agents(id) VALUES (:id)"), {"id": agent})
        for resource in resources:
            connection.execute(text("INSERT INTO resources(id,capacity) VALUES (:id,1)"), {"id": resource})
            connection.execute(text("INSERT INTO external_resources(id,capacity) VALUES (:id,1)"), {"id": resource})
        pg_version = connection.execute(text("SHOW server_version")).scalar_one()

    barrier = threading.Barrier(concurrency)
    measurement_starts = [None] * concurrency
    measurement_ends = [None] * concurrency

    def worker(index):
        samples = []
        version, capacity = 0, 1
        with httpx.Client(base_url=benchmark_api_url(engine.url.database),
                          timeout=10, headers=operator_headers()) as client:
            for phase, amount in (("warmup", warmup), ("measured", count // concurrency + (index < count % concurrency))):
                if phase == "measured":
                    try:
                        barrier.wait(timeout=120)
                    except threading.BrokenBarrierError:
                        return samples
                    measurement_starts[index] = time.monotonic()
                for step in range(amount):
                    target = 2 if capacity == 1 else 1
                    result = _request(client, agent, resources[index], version, target, run_id, f"{phase}:{index}:{step}")
                    result["phase"] = phase
                    samples.append(result)
                    if result["state"] != "SUCCEEDED":
                        barrier.abort()
                        if phase == "measured":
                            measurement_ends[index] = time.monotonic()
                        return samples
                    version, capacity = version + 1, target
                if phase == "measured":
                    measurement_ends[index] = time.monotonic()
        return samples

    sampler = BacklogSampler(float(os.getenv("BOTKERNEL_BENCHMARK_SAMPLE_INTERVAL", "0.2")))
    sampler.thread.start()
    started = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            samples = [sample for group in executor.map(worker, range(concurrency)) for sample in group]
    finally:
        telemetry = sampler.stop()
    elapsed = time.monotonic() - started
    measured = [sample for sample in samples if sample["phase"] == "measured"]
    starts = [value for value in measurement_starts if value is not None]
    ends = [value for value in measurement_ends if value is not None]
    measured_seconds = max(ends) - min(starts) if starts and ends else None
    ids = [sample["action_id"] for sample in samples if sample["action_id"]]
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(text(
            "SELECT a.id::text AS id, a.state, o.published, o.trace_context, "
            "(SELECT count(*) FROM receipts r WHERE r.action_id=a.id) AS receipts, "
            "(SELECT count(*) FROM effects e WHERE e.action_id=a.id) AS effects "
            "FROM actions a JOIN outbox o ON o.action_id=a.id WHERE a.agent=:agent"
        ), {"agent": agent}).mappings()]
        versions = [dict(row) for row in connection.execute(text(
            "SELECT r.id, r.version, count(e.action_id) AS effect_count, "
            "COALESCE(max(e.version),0) AS max_effect_version "
            "FROM resources r LEFT JOIN effects e ON e.resource=r.id "
            "WHERE r.id = ANY(:resources) GROUP BY r.id,r.version ORDER BY r.id"
        ), {"resources": resources}).mappings()]
    by_id = {row["id"]: row for row in rows}
    confirmed = [sample for sample in measured if sample["state"] == "SUCCEEDED"
                 and sample["action_id"] in by_id and by_id[sample["action_id"]]["state"] == "SUCCEEDED"
                 and by_id[sample["action_id"]]["effects"] == 1
                 and by_id[sample["action_id"]]["receipts"] == 1
                 and by_id[sample["action_id"]]["published"]]
    admission = [sample["admission_ms"] for sample in measured]
    completion = [sample["completion_ms"] for sample in confirmed]
    result = {
        "run_id": run_id, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "requested": count, "concurrency": concurrency, "warmup_per_worker": warmup,
        "total_run_seconds_including_warmup": round(elapsed, 3),
        "measurement_seconds": round(measured_seconds, 3) if measured_seconds is not None else None,
        "confirmed_effects": len(confirmed),
        "confirmed_effects_per_second": round(len(confirmed) / measured_seconds, 3) if measured_seconds else None,
        "admission_ms": {f"p{p}": percentile(admission, p) for p in (50, 95, 99)},
        "completion_ms": {f"p{p}": percentile(completion, p) for p in (50, 95, 99)},
        "outcomes": {state: sum(sample["state"] == state for sample in measured)
                     for state in ("SUCCEEDED", "REJECTED", "FAILED", "ESCALATED", "TIMEOUT")},
        "observed_action_count": len(ids), "authoritative_rows": rows,
        "resource_versions": versions,
        "backlog_telemetry": telemetry,
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "postgresql": pg_version, "kafka_image": "apache/kafka:3.9.0"},
        "unavailable": ["publication latency", "Kafka delivery latency", "worker execution latency",
                        "duplicate deliveries", "CPU and memory", "recovery fault injection"],
        "notes": ["Client monotonic timing; completion includes 50ms polling.",
                  "Throughput spans first measured submission to last observed terminal outcome after warmup.",
                  "Dedicated local PostgreSQL and Kafka; simulator resource changes only."],
    }
    folder = Path(output) / run_id
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "raw.json").write_text(json.dumps({"summary": result, "samples": samples}, indent=2), encoding="utf-8")
    with (folder / "samples.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["phase", "key", "resource", "http_status", "admission_ms",
                                                  "completion_ms", "action_id", "state", "error"])
        writer.writeheader()
        writer.writerows(samples)
    (folder / "report.md").write_text(
        "# Local PostgreSQL/Kafka benchmark\n\n```json\n" + json.dumps(result, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    if (len(confirmed) != count or len(rows) != len(ids) or len(versions) != concurrency
            or any(row["version"] != row["effect_count"] or row["version"] != row["max_effect_version"]
                   for row in versions)):
        raise RuntimeError(f"Benchmark incomplete or authoritative evidence mismatch; artifacts: {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--actions", type=int, default=25)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--output", default="/results")
    parser.add_argument("--sample-interval", type=float, default=0.2)
    args = parser.parse_args()
    os.environ["BOTKERNEL_BENCHMARK_SAMPLE_INTERVAL"] = str(args.sample_interval)
    run(args.actions, args.concurrency, args.warmup, args.output)
