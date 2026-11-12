import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text

from botkernel.core import engine


@pytest.fixture
def migration_schema():
    name = "migration_test_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{name}"')
    try:
        yield name
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{name}" CASCADE')


def _initialize(schema):
    env = {**os.environ, "PGOPTIONS": f"-csearch_path={schema}"}
    return subprocess.run(
        [sys.executable, "-c", "from botkernel.core import initialize; initialize()"],
        env=env, text=True, capture_output=True, timeout=30,
    )


def _legacy(schema):
    sql = Path("migrations/versions/0001_schema.sql").read_text()
    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        connection.exec_driver_sql(sql)
        connection.execute(text("INSERT INTO agents(id) VALUES ('legacy-agent')"))
        connection.execute(text("UPDATE resources SET capacity=5 WHERE id='service-a'"))
        connection.execute(text("UPDATE external_resources SET capacity=5 WHERE id='service-a'"))
        connection.execute(text(
            "INSERT INTO actions(id,idempotency_key,agent,resource,payload,delta,state) "
            "VALUES ('00000000-0000-0000-0000-000000000001','legacy-key',"
            "'legacy-agent','service-a',CAST(:payload AS jsonb),0,'RESERVED')"
        ), {"payload": json.dumps({
            "agent": "legacy-agent", "workflow": "legacy", "idempotency_key": "legacy-key",
            "resource": "service-a", "expected_version": 0, "capacity": 5,
        })})
        connection.execute(text(
            "INSERT INTO outbox(action_id) VALUES ('00000000-0000-0000-0000-000000000001')"
        ))


def test_fresh_migration_and_repeated_startup(migration_schema):
    for _ in range(2):
        result = _initialize(migration_schema)
        assert result.returncode == 0, result.stderr
    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0009"
        assert connection.execute(text("SELECT count(*) FROM resources")).scalar_one() == 2
        assert connection.execute(text("SELECT count(*) FROM incident_transitions")).scalar_one() == 0


def test_valid_legacy_upgrade_preserves_data(migration_schema):
    _legacy(migration_schema)
    result = _initialize(migration_schema)
    assert result.returncode == 0, result.stderr
    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0009"
        assert connection.execute(text("SELECT count(*) FROM agents WHERE id='legacy-agent'")).scalar_one() == 1
        assert connection.execute(text("SELECT capacity FROM resources WHERE id='service-a'")).scalar_one() == 5
        assert connection.execute(text("SELECT capacity FROM external_resources WHERE id='service-a'")).scalar_one() == 5
        assert connection.execute(text("SELECT count(*) FROM actions WHERE idempotency_key='legacy-key' AND state='RESERVED'")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM outbox WHERE NOT published")).scalar_one() == 1
        assert connection.execute(text("SELECT trace_context FROM outbox WHERE action_id='00000000-0000-0000-0000-000000000001'")).scalar_one() is None


@pytest.mark.parametrize("drift", [
    "DROP INDEX resource_reservation",
    "ALTER TABLE actions DROP CONSTRAINT actions_idempotency_key_key",
    "ALTER TABLE resources ALTER COLUMN capacity DROP NOT NULL",
    "DROP TRIGGER action_transition ON actions",
    "ALTER TABLE quota DROP CONSTRAINT quota_capacity_check",
    "ALTER TABLE actions ALTER COLUMN created_at DROP DEFAULT",
])
def test_incompatible_legacy_is_rejected_without_repair(migration_schema, drift):
    _legacy(migration_schema)
    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        connection.exec_driver_sql(drift)
    result = _initialize(migration_schema)
    assert result.returncode != 0
    assert "Incompatible BotKernel schema:" in result.stderr
    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        assert connection.execute(text("SELECT capacity FROM resources WHERE id='service-a'")).scalar_one() == 5
        assert not connection.execute(text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_schema=current_schema() AND table_name='alembic_version')"
        )).scalar_one()


@pytest.mark.parametrize("drift,reason", [
    ("DROP INDEX resource_reservation", "resource reservation index"),
    ("DROP INDEX one_incident", "incident hold index"),
    ("ALTER TABLE actions DISABLE TRIGGER action_transition", "transition guard"),
    ("ALTER TABLE actions DROP CONSTRAINT actions_state_check", "actions_state_check"),
    ("ALTER TABLE incidents ALTER COLUMN hold_until DROP DEFAULT", "incidents.hold_until"),
    ("ALTER TABLE outbox DROP CONSTRAINT outbox_trace_context_check", "outbox trace-context constraint"),
    ("ALTER TABLE incident_transitions DROP CONSTRAINT incident_transitions_transition_check",
     "incident_transitions_transition_check"),
])
def test_head_schema_drift_fails_repeated_startup(migration_schema, drift, reason):
    result = _initialize(migration_schema)
    assert result.returncode == 0, result.stderr
    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        connection.execute(text(drift))
    result = _initialize(migration_schema)
    assert result.returncode != 0
    assert reason in result.stderr
    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0009"


def test_upgrade_0006_to_head_preserves_incident_effects(migration_schema):
    env={**os.environ, "PGOPTIONS": f"-csearch_path={migration_schema}"}
    result=subprocess.run([sys.executable,"-c","from alembic.config import Config; from alembic import command; command.upgrade(Config('alembic.ini'),'0006')"],env=env,text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr
    action='00000000-0000-0000-0000-000000000077'
    with engine.begin() as c:
        c.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        c.execute(text("INSERT INTO agents(id) VALUES('upgrade-agent')"))
        c.execute(text("UPDATE resources SET capacity=3,version=1 WHERE id='service-a'"))
        c.execute(text("UPDATE external_resources SET capacity=3 WHERE id='service-a'"))
        c.execute(text("INSERT INTO actions(id,idempotency_key,agent,resource,payload,delta,state) VALUES(:id,'upgrade-key','upgrade-agent','service-a',CAST('{}' AS jsonb),-1,'SUCCEEDED')"),{'id':action})
        c.execute(text("INSERT INTO effects(action_id,resource,agent,version,before_capacity,after_capacity,latency) VALUES(:id,'service-a','upgrade-agent',1,4,3,200)"),{'id':action})
        incident=c.execute(text("INSERT INTO incidents(resource,score,evidence) VALUES('service-a',0.9,CAST('{}' AS jsonb)) RETURNING id")).scalar_one()
        snapshot={table:c.execute(text('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY 1')).scalars().all() for table in ('resources','actions','effects','incidents')}
    result=_initialize(migration_schema)
    assert result.returncode==0,result.stderr
    with engine.begin() as c:
        c.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0009'
        for table,expected in snapshot.items(): assert c.execute(text('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY 1')).scalars().all()==expected
        assert c.execute(text("SELECT count(*) FROM pg_constraint WHERE conrelid='investigation_reports'::regclass AND contype IN ('p','f','u','c')")).scalar_one()>=6
        assert c.execute(text("SELECT count(*) FROM pg_indexes WHERE schemaname=current_schema() AND tablename='investigation_reports'")).scalar_one()>=3
        c.execute(text("INSERT INTO investigation_reports(id,incident_id,idempotency_key,request_fingerprint,status,provider,lease_token,lease_until) VALUES(:id,:incident,'upgrade',:fingerprint,'RUNNING','deterministic_mock',:token,now()+interval '60 seconds')"),dict(id=str(uuid.uuid4()),incident=incident,fingerprint='0'*64,token=str(uuid.uuid4())))
        c.execute(text("INSERT INTO investigation_reports(id,incident_id,idempotency_key,request_fingerprint,status,provider,lease_token,lease_until) VALUES(:id,:incident,'bedrock-upgrade',:fingerprint,'RUNNING','bedrock',:token,now()+interval '60 seconds')"),dict(id=str(uuid.uuid4()),incident=incident,fingerprint='1'*64,token=str(uuid.uuid4())))


def test_upgrade_0008_to_0009_preserves_existing_reports(migration_schema):
    env = {**os.environ, "PGOPTIONS": f"-csearch_path={migration_schema}"}
    result = subprocess.run(
        [sys.executable, "-c", "from alembic.config import Config; from alembic import command; command.upgrade(Config('alembic.ini'),'0008')"],
        env=env, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    with engine.begin() as c:
        c.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        incident = c.execute(text("INSERT INTO incidents(resource,score,evidence) VALUES('service-a',0.8,CAST('{}' AS jsonb)) RETURNING id")).scalar_one()
        report_id = str(uuid.uuid4())
        c.execute(text("INSERT INTO investigation_reports(id,incident_id,idempotency_key,request_fingerprint,status,provider,error_category,completed_at) VALUES(:id,:incident,'old',:fingerprint,'FAILED','deterministic_mock','lease_expired',now())"),
                  {"id": report_id, "incident": incident, "fingerprint": "0"*64})
        before = c.execute(text("SELECT row_to_json(r)::text FROM investigation_reports r WHERE id=:id"), {"id": report_id}).scalar_one()
    result = _initialize(migration_schema)
    assert result.returncode == 0, result.stderr
    with engine.begin() as c:
        c.exec_driver_sql(f'SET LOCAL search_path TO "{migration_schema}"')
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0009"
        assert c.execute(text("SELECT row_to_json(r)::text FROM investigation_reports r WHERE id=:id"), {"id": report_id}).scalar_one() == before
        c.execute(text("INSERT INTO investigation_reports(id,incident_id,idempotency_key,request_fingerprint,status,provider,error_category,completed_at) VALUES(:id,:incident,'new',:fingerprint,'FAILED','deterministic_mock','execution_timeout',now())"),
                  {"id": str(uuid.uuid4()), "incident": incident, "fingerprint": "1"*64})
