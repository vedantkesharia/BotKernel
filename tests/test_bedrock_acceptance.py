from botkernel.security import operator_headers
import pytest

from botkernel.bedrock_acceptance import main
from botkernel.bedrock_acceptance import (
    AcceptanceError,
    _require_usage,
    validate_agent_observation,
    validate_live_configuration,
    validate_remaining_budget,
)


def _approved_environment(monkeypatch, checkpoint_path):
    settings = {
        "BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED": "true",
        "CLOUD_MODE": "mock",
        "AWS_DEPLOY_ALLOWED": "false",
        "AI_ACTION_EXECUTION_ENABLED": "false",
        "BEDROCK_ENABLED": "true",
        "BEDROCK_SPEND_AUTHORIZED": "true",
        "AGENT_PROVIDER": "bedrock",
        "INVESTIGATOR_PROVIDER": "bedrock",
        "BEDROCK_MODEL_ID": "us.amazon.nova-micro-v1:0",
        "BEDROCK_REGION": "us-east-2",
        "BEDROCK_MAX_OUTPUT_TOKENS": "1024",
        "BEDROCK_MAX_CALLS_PER_RUN": "1",
        "BEDROCK_MAX_CALLS_PER_DAY": "12",
        "MAX_BEDROCK_TOKENS_PER_DAY": "80000",
        "DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:15432/test",
        "REDIS_URL": "redis://127.0.0.1:16379",
        "BOTKERNEL_AGENT_CHECKPOINTS": str(checkpoint_path),
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)


def test_live_configuration_requires_exact_safety_gates(tmp_path, monkeypatch):
    _approved_environment(monkeypatch, tmp_path/"new-checkpoint.sqlite")
    validate_live_configuration()
    monkeypatch.setenv("AI_ACTION_EXECUTION_ENABLED", "true")
    with pytest.raises(AcceptanceError, match="acceptance_configuration_mismatch"):
        validate_live_configuration()


def test_live_configuration_rejects_non_loopback_endpoints_and_reused_checkpoint(
    tmp_path, monkeypatch
):
    checkpoint = tmp_path/"new-checkpoint.sqlite"
    _approved_environment(monkeypatch, checkpoint)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:pass@postgres:5432/test"
    )
    with pytest.raises(AcceptanceError, match="acceptance_endpoints_must_be_loopback"):
        validate_live_configuration("http://127.0.0.1:8000")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:pass@127.0.0.1:15432/test"
    )
    checkpoint.with_suffix(".sqlite.owner").touch()
    with pytest.raises(AcceptanceError, match="acceptance_checkpoint_must_be_new"):
        validate_live_configuration("http://127.0.0.1:8000")


def test_local_fixture_preparation_refuses_non_loopback_endpoint(tmp_path, monkeypatch):
    from botkernel.bedrock_acceptance import prepare_local_fixtures
    with pytest.raises(AcceptanceError, match="api_must_be_loopback"):
        prepare_local_fixtures(api_url="https://example.invalid", output=tmp_path/"fixture.json")


def test_aws_acceptance_requires_explicit_private_runtime(tmp_path, monkeypatch):
    _approved_environment(monkeypatch, tmp_path / "aws.sqlite")
    monkeypatch.setenv("BOTKERNEL_BEDROCK_ACCEPTANCE_RUNTIME", "aws-demo")
    monkeypatch.setenv("BOTKERNEL_RUNTIME_ENV", "aws-demo")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("BEDROCK_PROFILE", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@postgres:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/15")
    validate_live_configuration("http://api:8000")
    monkeypatch.setenv("AWS_PROFILE", "botkernel-dev")
    with pytest.raises(AcceptanceError, match="aws_acceptance_runtime_mismatch"):
        validate_live_configuration("http://api:8000")


def test_aws_acceptance_matches_database_secret_precedence(tmp_path, monkeypatch):
    _approved_environment(monkeypatch, tmp_path / "aws.sqlite")
    monkeypatch.setenv("BOTKERNEL_BEDROCK_ACCEPTANCE_RUNTIME", "aws-demo")
    monkeypatch.setenv("BOTKERNEL_RUNTIME_ENV", "aws-demo")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("BEDROCK_PROFILE", raising=False)
    secret = tmp_path / "database_url"
    secret.write_text("postgresql+psycopg://user:pass@postgres:5432/test", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL_FILE", str(secret))
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/15")
    validate_live_configuration("http://api:8000")
    secret.write_text("postgresql+psycopg://user:pass@unexpected:5432/test", encoding="utf-8")
    with pytest.raises(AcceptanceError, match="aws_acceptance_runtime_mismatch"):
        validate_live_configuration("http://api:8000")


@pytest.mark.parametrize("endpoint", ["http://example.com:8000", "http://api:8080", "http://api:8000/other"])
def test_aws_acceptance_rejects_unexpected_api(tmp_path, monkeypatch, endpoint):
    _approved_environment(monkeypatch, tmp_path / "aws.sqlite")
    monkeypatch.setenv("BOTKERNEL_BEDROCK_ACCEPTANCE_RUNTIME", "aws-demo")
    monkeypatch.setenv("BOTKERNEL_RUNTIME_ENV", "aws-demo")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@postgres:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/15")
    with pytest.raises(AcceptanceError, match="aws_acceptance_runtime_mismatch"):
        validate_live_configuration(endpoint)


@pytest.mark.parametrize(
    ("values", "error"),
    [
        ((None, None), None),
        ((b"0", b"1812"), None),
        ((b"1", b"1812"), None),
        ((b"9", b"76928"), None),
        ((b"10", b"1812"), "acceptance_daily_budget_insufficient"),
        ((b"0", b"76929"), "acceptance_daily_budget_insufficient"),
        ((b"1", None), "budget_counter_unavailable"),
        ((b"invalid", b"0"), "budget_counter_unavailable"),
        ((b"-1", b"0"), "budget_counter_unavailable"),
    ],
)
def test_acceptance_preflight_preserves_and_checks_shared_budget(monkeypatch, values, error):
    import redis

    class Counter:
        def hmget(self, key, *fields):
            assert key.startswith("botkernel:bedrock-budget:")
            assert fields == ("calls", "reserved_tokens")
            return values

        def exists(self, key):
            return False

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/15")
    monkeypatch.setattr(redis.Redis, "from_url", lambda *args, **kwargs: Counter())
    if error:
        with pytest.raises(AcceptanceError, match=error):
            validate_remaining_budget()
    else:
        validate_remaining_budget()


def test_insufficient_shared_budget_stops_before_any_workflow(tmp_path, monkeypatch):
    import botkernel.bedrock_acceptance as acceptance
    import redis

    class Counter:
        def hmget(self, key, *fields):
            return (b"10", b"1812")

    _approved_environment(monkeypatch, tmp_path / "new-checkpoint.sqlite")
    monkeypatch.setattr(redis.Redis, "from_url", lambda *args, **kwargs: Counter())
    output = tmp_path / "acceptance.json"
    with pytest.raises(AcceptanceError, match="acceptance_daily_budget_insufficient"):
        acceptance.run_acceptance(
            api_url="http://127.0.0.1:8000", cost_resource="cost",
            performance_resource="performance", incident_id=1, output=output,
        )
    assert not output.exists()
    assert not (tmp_path / "new-checkpoint.sqlite").exists()


def test_acceptance_rejects_existing_budget_without_required_fields(monkeypatch):
    import redis

    class Counter:
        def hmget(self, key, *fields):
            return (None, None)

        def exists(self, key):
            return True

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/15")
    monkeypatch.setattr(redis.Redis, "from_url", lambda *args, **kwargs: Counter())
    with pytest.raises(AcceptanceError, match="budget_counter_unavailable"):
        validate_remaining_budget()


def test_acceptance_rejects_unavailable_budget_store(monkeypatch):
    import redis

    class Counter:
        def hmget(self, key, *fields):
            raise redis.ConnectionError("unavailable")

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/15")
    monkeypatch.setattr(redis.Redis, "from_url", lambda *args, **kwargs: Counter())
    with pytest.raises(AcceptanceError, match="budget_counter_unavailable"):
        validate_remaining_budget()


def test_live_cli_accepts_all_case_arguments_before_configuration_gate(
    tmp_path, monkeypatch, capsys
):
    _approved_environment(monkeypatch, tmp_path/"new-checkpoint.sqlite")
    monkeypatch.setenv("BEDROCK_ENABLED", "false")
    monkeypatch.setattr(
        "sys.argv",
        [
            "botkernel.bedrock_acceptance",
            "--execute-live",
            "--api-url",
            "http://127.0.0.1:8000",
            "--cost-resource",
            "cost",
            "--performance-resource",
            "performance",
            "--incident-id",
            "1",
            "--output",
            str(tmp_path/"result.json"),
        ],
    )
    assert main() == 2
    assert "acceptance_configuration_mismatch" in capsys.readouterr().err


def test_acceptance_exercises_both_graphs_and_persisted_investigation_without_actions(
    tmp_path, monkeypatch, request, in_process_investigator
):
    import httpx
    import os
    import uuid
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    import botkernel.bedrock_acceptance as acceptance
    import botkernel.lang_agents as lang_agents
    from botkernel.api import Action, app
    from botkernel.bedrock import AgentDecision, InvestigationAnalysis
    from botkernel.core import admit, engine, execute
    from botkernel.stability import tick

    suffix = uuid.uuid4().hex[:12]
    resources = {
        "cost": f"accept-cost-{suffix}",
        "performance": f"accept-performance-{suffix}",
        "incident": f"accept-incident-{suffix}",
    }
    resource_ids = list(resources.values())
    agent_ids = [
        f"{role}-{suffix}" for role in (
            "cost-seed", "performance-seed", "cost-loop", "performance-loop"
        )
    ]
    with engine.connect() as connection:
        original_quota = connection.execute(
            text("SELECT capacity FROM quota WHERE id=1")
        ).scalar_one()

    def cleanup():
        with engine.begin() as connection:
            incident_ids = connection.execute(
                text("SELECT id FROM incidents WHERE resource=ANY(:resources)"),
                {"resources": resource_ids},
            ).scalars().all()
            connection.execute(
                text("DELETE FROM investigation_reports WHERE incident_id=ANY(:ids)"),
                {"ids": incident_ids},
            )
            connection.execute(
                text("DELETE FROM incident_transitions WHERE incident_id=ANY(:ids)"),
                {"ids": incident_ids},
            )
            connection.execute(
                text("DELETE FROM incident_operator_actions WHERE incident_id=ANY(:ids)"),
                {"ids": incident_ids},
            )
            connection.execute(
                text("DELETE FROM incidents WHERE id=ANY(:ids)"),
                {"ids": incident_ids},
            )
            action_ids = connection.execute(
                text("SELECT id FROM actions WHERE resource=ANY(:resources)"),
                {"resources": resource_ids},
            ).scalars().all()
            for table in ("receipts", "effects", "outbox"):
                connection.execute(
                    text(f"DELETE FROM {table} WHERE action_id=ANY(:ids)"),
                    {"ids": action_ids},
                )
            connection.execute(
                text("DELETE FROM actions WHERE id=ANY(:ids)"), {"ids": action_ids}
            )
            connection.execute(
                text("DELETE FROM external_resources WHERE id=ANY(:ids)"),
                {"ids": resource_ids},
            )
            connection.execute(
                text("DELETE FROM resources WHERE id=ANY(:ids)"),
                {"ids": resource_ids},
            )
            connection.execute(
                text("DELETE FROM agents WHERE id=ANY(:ids)"), {"ids": agent_ids}
            )
            connection.execute(
                text("UPDATE quota SET capacity=:capacity WHERE id=1"),
                {"capacity": original_quota},
            )

    request.addfinalizer(cleanup)
    with engine.begin() as connection:
        connection.execute(text("UPDATE quota SET capacity=500 WHERE id=1"))
        for agent in agent_ids:
            connection.execute(
                text("INSERT INTO agents(id) VALUES(:id) ON CONFLICT(id) DO NOTHING"),
                {"id": agent},
            )
        for resource, capacity in (
            (resources["cost"], 6),
            (resources["performance"], 4),
            (resources["incident"], 4),
        ):
            connection.execute(
                text("INSERT INTO resources(id,capacity,version) VALUES(:id,:capacity,0)"),
                {"id": resource, "capacity": capacity},
            )
            connection.execute(
                text("INSERT INTO external_resources(id,capacity) VALUES(:id,:capacity)"),
                {"id": resource, "capacity": capacity},
            )

    def commit(resource, agent, key, version, capacity):
        action_id = admit(Action(
            agent=agent,
            workflow="bedrock-acceptance-offline-test",
            idempotency_key=key,
            resource=resource,
            expected_version=version,
            capacity=capacity,
            risk="low",
        ))
        execute(action_id)
        return action_id

    commit(resources["cost"], f"cost-seed-{suffix}", f"{suffix}-cost", 0, 5)
    commit(
        resources["performance"],
        f"performance-seed-{suffix}",
        f"{suffix}-performance",
        0,
        3,
    )
    for index, capacity in enumerate((3, 4, 3, 4)):
        commit(
            resources["incident"],
            ("cost-loop-" if capacity == 3 else "performance-loop-") + suffix,
            f"{suffix}-loop-{index}",
            index,
            capacity,
        )
    tick()
    with engine.connect() as connection:
        incident_id = connection.execute(
            text("SELECT id FROM incidents WHERE resource=:resource ORDER BY opened_at DESC LIMIT 1"),
            {"resource": resources["incident"]},
        ).scalar_one()

    for name, value in {
        "BOTKERNEL_BEDROCK_ACCEPTANCE_APPROVED": "true",
        "CLOUD_MODE": "mock",
        "AWS_DEPLOY_ALLOWED": "false",
        "AI_ACTION_EXECUTION_ENABLED": "false",
        "BEDROCK_ENABLED": "true",
        "BEDROCK_SPEND_AUTHORIZED": "true",
        "AGENT_PROVIDER": "bedrock",
        "INVESTIGATOR_PROVIDER": "bedrock",
        "BEDROCK_MODEL_ID": acceptance.MODEL_ID,
        "BEDROCK_REGION": acceptance.REGION,
        "BEDROCK_MAX_OUTPUT_TOKENS": "1024",
        "BEDROCK_MAX_CALLS_PER_RUN": "1",
        "BEDROCK_MAX_CALLS_PER_DAY": "12",
        "MAX_BEDROCK_TOKENS_PER_DAY": "80000",
        "BOTKERNEL_AGENT_CHECKPOINTS": str(tmp_path/"agent-checkpoints.sqlite"),
        "BOTKERNEL_RUNTIME_ENV": "local",
    }.items():
        monkeypatch.setenv(name, value)

    class OfflineReasoner:
        name = "bedrock"
        model_id = acceptance.MODEL_ID

        def decide(self, role, telemetry, run_id):
            references = [f"resource:{telemetry['id']}"]
            references.extend(
                effect["action_id"] for effect in telemetry["recent_effects"]
            )
            return AgentDecision(
                decision="NO_OP",
                resource=telemetry["id"],
                proposed_delta=0,
                reason=f"Offline {role} acceptance response.",
                evidence_references=references,
                uncertainties=[],
            ), {
                "provider": "bedrock",
                "model_id": self.model_id,
                "input_tokens": 117,
                "output_tokens": 23,
                "invocations": 1,
            }

    monkeypatch.setattr(lang_agents, "configured_reasoner", OfflineReasoner)

    class OfflineConverse:
        def invoke_json(self, *, payload, **kwargs):
            action_ids = [effect["action_id"] for effect in payload["effects"]]
            assert action_ids
            return InvestigationAnalysis(
                explanation="The cited committed effects document the incident.",
                hypotheses=["Independent objectives may have contributed; causation is unproven."],
                cross_agent_analysis="Both agent identities occur in committed evidence.",
                instability_mechanism="Opposing capacity changes form a reversal pattern.",
                supporting_references=[action_ids[0], f"incident:{incident_id}"],
                contradictory_or_missing_evidence=[],
                preventive_actions=["Review existing controller evidence before operator action."],
                confidence_caveats=["This mocked analysis does not establish causation."],
            ), {
                "provider": "bedrock",
                "model_id": acceptance.MODEL_ID,
                "input_tokens": 321,
                "output_tokens": 88,
                "invocations": 1,
            }

    monkeypatch.setattr("botkernel.bedrock.BedrockConverse", OfflineConverse)
    in_process_investigator()
    client = TestClient(app, headers=operator_headers())

    class LocalApiSession:
        investigation_timeouts = []

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, path):
            if path.startswith('/graph'):
                pytest.fail('Acceptance must verify durable evidence, not a rolling UI graph')
            return client.get(path)

        def post(self, path, **kwargs):
            if "/investigations" in path:
                self.investigation_timeouts.append(kwargs.pop("timeout", None))
            return client.post(path, **kwargs)

    monkeypatch.setattr(httpx, "Client", LocalApiSession)
    monkeypatch.setattr(
        httpx, "post", lambda *args, **kwargs: pytest.fail("acceptance must not submit actions")
    )
    monkeypatch.setattr(acceptance, "validate_live_configuration", lambda _api_url: None)
    monkeypatch.setenv("BOTKERNEL_AGENT_RESOURCE", "acceptance-outer-resource")

    result = acceptance.run_acceptance(
        api_url="http://127.0.0.1:8000",
        cost_resource=resources["cost"],
        performance_resource=resources["performance"],
        incident_id=incident_id,
        output=tmp_path/"acceptance.json",
    )
    assert result["status"] == "PASSED"
    assert result["cases"]["cost"]["provenance"]["output_tokens"] == 23
    assert result["cases"]["performance"]["provenance"]["output_tokens"] == 23
    assert result["cases"]["investigator"]["provenance"]["output_tokens"] == 88
    assert result["cases"]["investigator"]["replay_preserved_report"] is True
    assert result["cases"]["investigator"]["operational_state_unchanged"] is True
    assert LocalApiSession.investigation_timeouts == [75, None]
    assert os.environ["BOTKERNEL_AGENT_RESOURCE"] == "acceptance-outer-resource"

    from botkernel.bedrock import BedrockProviderError
    diagnostics = {
        "category": "client_configuration", "stage": "client_initialization",
        "missing_module": "dateutil", "response_received": False,
        "remote_outcome_unknown": False,
    }

    def failed_run(*args, **kwargs):
        raise BedrockProviderError("client_configuration", diagnostics=diagnostics)

    monkeypatch.setattr(lang_agents, "run_once", failed_run)
    failure_file = tmp_path/"failed-acceptance.json"
    with pytest.raises(AcceptanceError, match="client_configuration"):
        acceptance.run_acceptance(
            api_url="http://127.0.0.1:8000", cost_resource=resources["cost"],
            performance_resource=resources["performance"], incident_id=incident_id,
            output=failure_file,
        )
    import json
    failure = json.loads(failure_file.read_text())
    assert failure["status"] == "FAILED_OR_OUTCOME_UNKNOWN"
    assert failure["cases"]["cost"]["diagnostics"] == diagnostics
    assert "performance" not in failure["cases"]


@pytest.mark.parametrize(
    ("role", "telemetry", "category"),
    [
        ("cost", {"id": "c", "capacity": 4, "recent_effects": []},
         "non_simulator_telemetry"),
        ("cost", {"id": "c", "capacity": 4, "simulated": True,
                  "recent_effects": []}, "committed_effect_evidence_required"),
        ("cost", {"id": "c", "capacity": 3, "simulated": True,
                  "recent_effects": [{"action_id": "a"}]},
         "cost_case_lacks_downscale_headroom"),
        ("performance", {"id": "p", "capacity": 5, "latency_p95": 80,
                         "simulated": True, "recent_effects": [{"action_id": "a"}]},
         "performance_case_lacks_scale_up_signal"),
    ],
)
def test_agent_case_requires_evidence_and_role_relevant_telemetry(role, telemetry, category):
    with pytest.raises(AcceptanceError, match=category):
        validate_agent_observation(role, telemetry)


def test_usage_must_be_actual_and_single_invocation():
    _require_usage(
        {"provider": "bedrock", "model_id": "us.amazon.nova-micro-v1:0",
         "input_tokens": 20, "output_tokens": 10, "invocations": 1},
        expected_invocations=1,
    )
    with pytest.raises(AcceptanceError, match="actual_token_usage_unavailable"):
        _require_usage(
            {"provider": "bedrock", "model_id": "us.amazon.nova-micro-v1:0",
             "input_tokens": None, "output_tokens": 10, "invocations": 1},
            expected_invocations=1,
        )
