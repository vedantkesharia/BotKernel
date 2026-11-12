from concurrent.futures import ThreadPoolExecutor
import uuid
import pytest
from sqlalchemy import text
from botkernel.core import admit,execute,engine
from botkernel.api import Action
from botkernel.observability import normalize_trace_context

def test_concurrent_reservation_and_replay():
    # Dedicated resource avoids interference with demo agents.
    r = "test-" + uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text("INSERT INTO agents(id) VALUES(:r)"), {"r":r})
        c.execute(text("INSERT INTO resources(id,capacity) VALUES(:r,1)"), {"r":r})
        c.execute(text("INSERT INTO external_resources VALUES(:r,1)"), {"r":r})
    def attempt(i):
        try:
            return admit(Action(agent=r,workflow=r,idempotency_key=r+str(i),resource=r,expected_version=0,capacity=1))
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = [a for a in pool.map(attempt,range(16)) if a]
    assert len(ids)==1
    with engine.connect() as c:
        context = c.execute(
            text("SELECT trace_context FROM outbox WHERE action_id=:id"), {"id": ids[0]}
        ).scalar_one()
    assert normalize_trace_context(context)["traceparent"].startswith("00-")
    execute(ids[0])
    execute(ids[0])
    with engine.connect() as c:
        assert c.execute(text("SELECT version FROM resources WHERE id=:r"), {"r":r}).scalar_one()==1
        assert c.execute(text("SELECT count(*) FROM receipts WHERE action_id=:id"), {"id":ids[0]}).scalar_one()==1
    with pytest.raises(ValueError,match="stale"):
        admit(Action(agent=r,workflow=r,idempotency_key=r+"stale",resource=r,expected_version=0,capacity=1))


def test_idempotency_quota_and_independent_resources():
    tag = uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text("INSERT INTO agents(id) VALUES(:id)"), {"id":tag})
        rows = c.execute(text("SELECT * FROM resources WHERE id IN ('service-a','service-b') ORDER BY id")).mappings().all()
    def proposal(r, capacity, key):
        return Action(agent=tag,workflow=tag,idempotency_key=tag+key,resource=r['id'],expected_version=r['version'],capacity=capacity)
    a = proposal(rows[0], 4, 'a')
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids=list(pool.map(lambda _: admit(a),range(16)))
    assert len(set(ids)) == 1
    with pytest.raises(ValueError,match='reused'):
        admit(a.model_copy(update={'capacity':5}))
    b=admit(proposal(rows[1],4,'b'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(execute,[ids[0],b]))
    with engine.connect() as c:
        rows=c.execute(text("SELECT * FROM resources WHERE id IN ('service-a','service-b') ORDER BY id")).mappings().all()
    with pytest.raises(ValueError,match='quota'):
        admit(proposal(rows[0],20,'over'))


def test_quota_overage_can_be_reduced_by_admitted_downscale():
    tag = "quota-recovery-" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO agents(id) VALUES(:id)"), {"id": tag})
        connection.execute(
            text("INSERT INTO resources(id,capacity) VALUES(:id,4)"), {"id": tag}
        )
        connection.execute(
            text("INSERT INTO external_resources(id,capacity) VALUES(:id,4)"), {"id": tag}
        )
        total = connection.execute(text("SELECT sum(capacity) FROM resources")).scalar_one()
        original_quota = connection.execute(
            text("SELECT capacity FROM quota WHERE id=1 FOR UPDATE")
        ).scalar_one()
        recovery_quota = total - 1
        connection.execute(
            text("UPDATE quota SET capacity=:capacity WHERE id=1"),
            {"capacity": recovery_quota},
        )
    try:
        action_id = admit(
            Action(
                agent=tag,
                workflow=tag,
                idempotency_key=tag,
                resource=tag,
                expected_version=0,
                capacity=1,
            )
        )
        execute(action_id)
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT state FROM actions WHERE id=:id"), {"id": action_id}
            ).scalar_one() == "SUCCEEDED"
            assert connection.execute(
                text("SELECT sum(capacity) FROM resources")
            ).scalar_one() <= recovery_quota
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM effects WHERE action_id IN (SELECT id FROM actions WHERE agent=:id)"),
                {"id": tag},
            )
            connection.execute(
                text("DELETE FROM receipts WHERE action_id IN (SELECT id FROM actions WHERE agent=:id)"),
                {"id": tag},
            )
            connection.execute(
                text("DELETE FROM outbox WHERE action_id IN (SELECT id FROM actions WHERE agent=:id)"),
                {"id": tag},
            )
            connection.execute(text("DELETE FROM actions WHERE agent=:id"), {"id": tag})
            connection.execute(text("DELETE FROM external_resources WHERE id=:id"), {"id": tag})
            connection.execute(text("DELETE FROM resources WHERE id=:id"), {"id": tag})
            connection.execute(text("DELETE FROM agents WHERE id=:id"), {"id": tag})
            connection.execute(
                text("UPDATE quota SET capacity=:capacity WHERE id=1"),
                {"capacity": original_quota},
            )


def test_crash_after_external_effect():
    import subprocess,sys,os
    tag=uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text("INSERT INTO agents(id) VALUES(:id)"), {'id':tag})
        r=c.execute(text("SELECT * FROM resources WHERE id='service-a'")).mappings().one()
    aid=admit(Action(agent=tag,workflow=tag,idempotency_key=tag,resource=r['id'],expected_version=r['version'],capacity=4))
    result=subprocess.run([sys.executable,'-c','from botkernel.core import execute; execute("'+aid+'")'],env={**os.environ,'CRASH_AFTER_EFFECT':'true'},timeout=30)
    assert result.returncode==17
    with engine.connect() as c:
        assert c.execute(text("SELECT state FROM actions WHERE id=:id"),{'id':aid}).scalar_one()=='DISPATCHED'
        assert c.execute(text("SELECT count(*) FROM receipts WHERE action_id=:id"),{'id':aid}).scalar_one()==1
    execute(aid)
    execute(aid)
    with engine.connect() as c:
        assert c.execute(text("SELECT version FROM resources WHERE id=:id"),{'id':r['id']}).scalar_one()==r['version']+1
        assert c.execute(text("SELECT count(*) FROM resources WHERE capacity<1")).scalar_one()==0


def test_kafka_duplicate_and_restart():
    import subprocess,sys,time,os
    from confluent_kafka import Producer
    tag=uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text("INSERT INTO agents(id) VALUES(:id)"),{'id':tag})
        r=c.execute(text("SELECT * FROM resources WHERE id='service-b'")).mappings().one()
    aid=admit(Action(agent=tag,workflow=tag,idempotency_key=tag,resource=r['id'],expected_version=r['version'],capacity=4))
    producer=Producer({'bootstrap.servers':os.environ['KAFKA_BOOTSTRAP_SERVERS']})
    errors=[]
    for index in range(2):
        headers = [("traceparent", b"malformed")] if index == 0 else None
        producer.produce(
            os.environ['KAFKA_TOPIC'],
            key=aid,
            value=aid,
            headers=headers,
            on_delivery=lambda e,m: errors.append(e) if e else None,
        )
    assert producer.flush(30)==0 and not errors
    env={**os.environ,'CRASH_AFTER_EFFECT':'true','ROLE':'worker'}
    crashed=subprocess.Popen([sys.executable,'-m','botkernel.worker'],env=env)
    try:
        assert crashed.wait(timeout=45)==17
    finally:
        if crashed.poll() is None:
            crashed.kill(); crashed.wait()
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM receipts WHERE action_id=:id"), {'id':aid}).scalar_one()==1
        assert c.execute(text("SELECT count(*) FROM effects WHERE action_id=:id"), {'id':aid}).scalar_one()==0
        assert c.execute(text("SELECT version FROM resources WHERE id=:id"), {'id':r['id']}).scalar_one()==r['version']
    restarted=subprocess.Popen([sys.executable,'-m','botkernel.worker'],env={**os.environ,'ROLE':'worker'})
    try:
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            with engine.connect() as c:
                state=c.execute(text("SELECT state FROM actions WHERE id=:id"),{'id':aid}).scalar_one()
            if state=='SUCCEEDED':
                break
            time.sleep(.2)
        assert state=='SUCCEEDED'
        time.sleep(2)
    finally:
        restarted.terminate(); restarted.wait(timeout=15)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM receipts WHERE action_id=:id"),{'id':aid}).scalar_one()==1
        assert c.execute(text("SELECT count(*) FROM effects WHERE action_id=:id"),{'id':aid}).scalar_one()==1
        assert c.execute(text("SELECT version FROM resources WHERE id=:id"),{'id':r['id']}).scalar_one()==r['version']+1


def test_bounded_recovery_and_sweeper_concurrency(monkeypatch):
    from botkernel.core import sweep
    tag=uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text("INSERT INTO agents(id) VALUES(:id)"),{'id':tag})
        r=c.execute(text("SELECT * FROM resources WHERE id='service-a'")).mappings().one()
    aid=admit(Action(agent=tag,workflow=tag,idempotency_key=tag,resource=r['id'],expected_version=r['version'],capacity=4,max_attempts=2))
    monkeypatch.setenv('SIMULATOR_FAILURE','permanent')
    for _ in range(3):
        with engine.begin() as c:
            c.execute(text("UPDATE actions SET next_attempt=now(),created_at=now()-interval '31 seconds' WHERE id=:id"),{'id':aid})
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _:sweep(),range(4)))
    with engine.connect() as c:
        a=c.execute(text("SELECT * FROM actions WHERE id=:id"),{'id':aid}).mappings().one()
        assert a['state']=='FAILED' and a['attempts']==2
        assert c.execute(text("SELECT count(*) FROM receipts WHERE action_id=:id"),{'id':aid}).scalar_one()==0


def test_quota_race_and_illegal_transition():
    from sqlalchemy.exc import DBAPIError
    tag=uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text("INSERT INTO agents(id) VALUES(:id)"),{'id':tag})
        rows=c.execute(text("SELECT * FROM resources WHERE id IN ('service-a','service-b') ORDER BY id")).mappings().all()
    def attempt(r):
        try:
            return admit(Action(agent=tag,workflow=tag,idempotency_key=tag+r['id'],resource=r['id'],expected_version=r['version'],capacity=12))
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids=[a for a in pool.map(attempt,rows) if a]
    assert len(ids)==1
    with pytest.raises(DBAPIError):
        with engine.begin() as c:
            c.execute(text("UPDATE actions SET state='SUCCEEDED' WHERE id=:id"),{'id':ids[0]})
    execute(ids[0])
    with engine.connect() as c:
        assert c.execute(text("SELECT sum(capacity) FROM resources")).scalar_one()<=20


def test_publisher_crash_after_ack():
    import subprocess,sys,os
    # Existing outbox rows from previous tests are intentionally replayed.
    result=subprocess.run([sys.executable,'-m','botkernel.worker'],env={**os.environ,'ROLE':'publisher','CRASH_AFTER_PUBLISH':'true'},timeout=30)
    assert result.returncode==18
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM outbox WHERE NOT published")).scalar_one()>0
    publisher=subprocess.Popen([sys.executable,'-m','botkernel.worker'],env={**os.environ,'ROLE':'publisher'})
    try:
        import time
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            with engine.connect() as c:
                remaining=c.execute(text("SELECT count(*) FROM outbox WHERE NOT published")).scalar_one()
            if remaining==0:
                break
            time.sleep(.2)
        assert remaining==0
    finally:
        publisher.terminate(); publisher.wait(timeout=15)


def test_acknowledged_outbox_replay_and_worker_crash_after_completion():
    import os
    import subprocess
    import sys
    import time
    from confluent_kafka import Consumer, ConsumerGroupTopicPartitions
    from confluent_kafka.admin import AdminClient

    def wait_for(predicate, timeout=45):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.2)
        pytest.fail("timed out waiting for expected durable state")

    def pending():
        with engine.connect() as connection:
            return connection.execute(text("SELECT count(*) FROM outbox WHERE NOT published")).scalar_one()

    # Drain earlier tests' rows on their original topic before isolating this action.
    publisher = subprocess.Popen([sys.executable, "-m", "botkernel.worker"],
                                 env={**os.environ, "ROLE": "publisher"})
    try:
        wait_for(lambda: pending() == 0)
    finally:
        publisher.terminate()
        publisher.wait(timeout=15)

    tag = uuid.uuid4().hex
    topic = "replay_" + tag
    env = {**os.environ, "KAFKA_TOPIC": topic}
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO agents(id) VALUES(:id)"), {"id": tag})
        resource = connection.execute(text("SELECT * FROM resources WHERE id='service-b'")).mappings().one()
    aid = admit(Action(agent=tag, workflow=tag, idempotency_key=tag, resource=resource["id"],
                       expected_version=resource["version"], capacity=resource["capacity"]))
    observer = Consumer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
                         "group.id": "replay_observer_" + tag,
                         "auto.offset.reset": "earliest", "enable.auto.commit": False})
    observer.subscribe([topic])
    try:
        crashed = subprocess.run([sys.executable, "-m", "botkernel.worker"],
                                 env={**env, "ROLE": "publisher", "CRASH_AFTER_PUBLISH": "true"},
                                 timeout=45)
        assert crashed.returncode == 18
        with engine.connect() as connection:
            assert connection.execute(text("SELECT published FROM outbox WHERE action_id=:id"),
                                      {"id": aid}).scalar_one() is False

        messages = []
        def receive(count):
            message = observer.poll(.5)
            if message and not message.error() and message.value() == aid.encode():
                messages.append((message.partition(), message.offset(), dict(message.headers() or [])))
            return len(messages) >= count
        wait_for(lambda: receive(1))

        publisher = subprocess.Popen([sys.executable, "-m", "botkernel.worker"],
                                     env={**env, "ROLE": "publisher"})
        try:
            wait_for(lambda: pending() == 0)
            wait_for(lambda: receive(2))
        finally:
            publisher.terminate()
            publisher.wait(timeout=15)
        assert messages[0][0] == messages[1][0]
        assert messages[0][1] != messages[1][1]
        first_context = messages[0][2]
        second_context = messages[1][2]
        assert "traceparent" in first_context
        assert "traceparent" in second_context
        first_parent = first_context["traceparent"].decode()
        second_parent = second_context["traceparent"].decode()
        assert first_parent.startswith("00-") and second_parent.startswith("00-")
        assert first_parent[3:35] == second_parent[3:35]
        assert first_parent[36:52] != second_parent[36:52]

        crashed_worker = subprocess.run(
            [sys.executable, "-m", "botkernel.worker"],
            env={**env, "ROLE": "worker", "CRASH_AFTER_COMPLETION": "true"}, timeout=60,
        )
        assert crashed_worker.returncode == 19
        with engine.connect() as connection:
            assert connection.execute(text("SELECT state FROM actions WHERE id=:id"), {"id": aid}).scalar_one() == "SUCCEEDED"
            assert connection.execute(text("SELECT version FROM resources WHERE id=:id"), {"id": resource["id"]}).scalar_one() == resource["version"] + 1
        admin = AdminClient({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]})
        offsets = admin.list_consumer_group_offsets(
            [ConsumerGroupTopicPartitions("executors")]
        )["executors"].result(timeout=5)
        assert not any(p.topic == topic and p.partition == messages[0][0]
                       and p.offset > messages[0][1] for p in offsets.topic_partitions)

        worker = subprocess.Popen([sys.executable, "-m", "botkernel.worker"],
                                  env={**env, "ROLE": "worker"})
        try:
            # Synchronously observe the committed offset after both duplicate deliveries.
            def worker_caught_up():
                groups = admin.list_consumer_group_offsets(
                    [ConsumerGroupTopicPartitions("executors")]
                )["executors"].result(timeout=5)
                return any(p.topic == topic and p.partition == messages[1][0]
                           and p.offset > messages[1][1] for p in groups.topic_partitions)
            wait_for(worker_caught_up)
        finally:
            worker.terminate()
            worker.wait(timeout=15)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM receipts WHERE action_id=:id"), {"id": aid}).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM effects WHERE action_id=:id"), {"id": aid}).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM outbox WHERE action_id=:id AND published"), {"id": aid}).scalar_one() == 1
            assert connection.execute(text("SELECT version FROM resources WHERE id=:id"), {"id": resource["id"]}).scalar_one() == resource["version"] + 1
            assert connection.execute(text("SELECT capacity FROM external_resources WHERE id=:id"), {"id": resource["id"]}).scalar_one() == resource["capacity"]
    finally:
        observer.close()
        admin = AdminClient({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]})
        if topic in admin.list_topics(timeout=10).topics:
            admin.delete_topics([topic], operation_timeout=10)[topic].result(timeout=15)


def test_sweeper_reconciles_effect_after_kafka_worker_death():
    import os
    import subprocess
    import sys
    from confluent_kafka import Producer
    from confluent_kafka.admin import AdminClient
    from botkernel.core import sweep

    tag = uuid.uuid4().hex
    topic = "sweep_" + tag
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO agents(id) VALUES(:id)"), {"id": tag})
        resource = connection.execute(text("SELECT * FROM resources WHERE id='service-b'")).mappings().one()
    aid = admit(Action(agent=tag, workflow=tag, idempotency_key=tag, resource=resource["id"],
                       expected_version=resource["version"], capacity=resource["capacity"]))
    producer = Producer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]})
    errors = []
    try:
        producer.produce(topic, key=aid, value=aid,
                         on_delivery=lambda error, message: errors.append(error) if error else None)
        assert producer.flush(30) == 0 and not errors
        crashed = subprocess.run(
            [sys.executable, "-m", "botkernel.worker"],
            env={**os.environ, "KAFKA_TOPIC": topic, "ROLE": "worker", "CRASH_AFTER_EFFECT": "true"},
            timeout=60,
        )
        assert crashed.returncode == 17
        with engine.begin() as connection:
            assert connection.execute(text("SELECT state FROM actions WHERE id=:id"), {"id": aid}).scalar_one() == "DISPATCHED"
            assert connection.execute(text("SELECT count(*) FROM receipts WHERE action_id=:id"), {"id": aid}).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM effects WHERE action_id=:id"), {"id": aid}).scalar_one() == 0
            connection.execute(text("UPDATE actions SET next_attempt=now() WHERE id=:id"), {"id": aid})
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: sweep(), range(4)))
        with engine.connect() as connection:
            assert connection.execute(text("SELECT state FROM actions WHERE id=:id"), {"id": aid}).scalar_one() == "SUCCEEDED"
            assert connection.execute(text("SELECT count(*) FROM receipts WHERE action_id=:id"), {"id": aid}).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM effects WHERE action_id=:id"), {"id": aid}).scalar_one() == 1
            assert connection.execute(text("SELECT version FROM resources WHERE id=:id"), {"id": resource["id"]}).scalar_one() == resource["version"] + 1
            assert connection.execute(text("SELECT capacity FROM external_resources WHERE id=:id"), {"id": resource["id"]}).scalar_one() == resource["capacity"]
    finally:
        admin = AdminClient({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]})
        if topic in admin.list_topics(timeout=10).topics:
            admin.delete_topics([topic], operation_timeout=10)[topic].result(timeout=15)


def test_divergence_retains_reservation():
    tag=uuid.uuid4().hex
    with engine.begin() as c:
        c.execute(text("INSERT INTO agents(id) VALUES(:id)"),{'id':tag})
        c.execute(text("INSERT INTO resources VALUES(:id,1,0)"),{'id':tag})
        c.execute(text("INSERT INTO external_resources VALUES(:id,1)"),{'id':tag})
    aid=admit(Action(agent=tag,workflow=tag,idempotency_key=tag,resource=tag,expected_version=0,capacity=1))
    with engine.begin() as c:
        c.execute(text("UPDATE external_resources SET capacity=2 WHERE id=:id"),{'id':tag})
    execute(aid)
    with engine.connect() as c:
        assert c.execute(text("SELECT state FROM actions WHERE id=:id"),{'id':aid}).scalar_one()=='ESCALATED'
    with pytest.raises(ValueError,match='reserved'):
        admit(Action(agent=tag,workflow=tag,idempotency_key=tag+'again',resource=tag,expected_version=0,capacity=1))


def test_contracts_and_poison_events():
    import os, subprocess, sys, time
    from datetime import datetime, timezone, timedelta
    from fastapi.testclient import TestClient
    from botkernel.api import app
    from confluent_kafka import Producer
    client=TestClient(app)
    assert client.post('/agents/bad!').status_code==422
    assert client.post('/agents/contracts').status_code==200
    base=dict(agent='contracts',workflow='contracts',idempotency_key='contract',resource='service-b',expected_version=0,capacity=1)
    for changes,status in [({'risk':'high'},409),({'deadline':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()},409),({'dependencies':[str(uuid.uuid4())]},409),({'max_attempts':0},422)]:
        assert client.post('/actions',json={**base,**changes}).status_code==status
    producer=Producer({'bootstrap.servers':os.environ['KAFKA_BOOTSTRAP_SERVERS']})
    for value in [b'not-uuid',b'\xff',None]:
        producer.produce(os.environ['KAFKA_TOPIC'],value=value)
    assert producer.flush(20)==0
    worker=subprocess.Popen([sys.executable,'-m','botkernel.worker'],env={**os.environ,'ROLE':'worker'})
    try:
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            with engine.connect() as c:
                count=c.execute(text('SELECT count(*) FROM dead_letters')).scalar_one()
            if count==3: break
            time.sleep(.2)
        assert count==3 and worker.poll() is None
        with engine.connect() as c:
            # Publisher replay from the previous test must not duplicate receipts.
            assert c.execute(text('SELECT count(*) FROM receipts')).scalar_one()==c.execute(text("SELECT count(*) FROM actions WHERE state='SUCCEEDED'")).scalar_one()
    finally:
        worker.terminate(); worker.wait(timeout=15)
