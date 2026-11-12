import os
import secrets
import uuid
import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def in_process_investigator(monkeypatch):
    """Keep offline provider mocks local; process isolation is tested separately."""
    def install():
        from botkernel import investigation_service as service
        from botkernel.bedrock import BedrockProviderError
        def execute(incident_id, provider, run_id, deadline, grace):
            try:
                report = service.investigation_graph.invoke({
                    "incident_id": incident_id, "provider": provider, "run_id": run_id,
                })["report"]
                report["investigation_id"] = run_id
                return {"report": report}
            except BedrockProviderError as error:
                return {"error_category": error.category}
        monkeypatch.setattr(service, "execute", execute)
    return install


def pytest_configure(config):
    if os.getenv("BOTKERNEL_TEST_ISOLATED") != "true":
        raise pytest.UsageError("Run tests using Compose test service (isolated database required)")
    os.environ["BOTKERNEL_OPERATOR_TOKEN"] = secrets.token_urlsafe(32)
    os.environ["BOTKERNEL_AGENT_TOKEN"] = secrets.token_urlsafe(32)
    os.environ["BOTKERNEL_METRICS_TOKEN"] = secrets.token_urlsafe(32)
    os.environ.pop("BOTKERNEL_OPERATOR_TOKEN_FILE", None)
    os.environ.pop("BOTKERNEL_AGENT_TOKEN_FILE", None)
    os.environ.pop("BOTKERNEL_METRICS_TOKEN_FILE", None)
    original = os.environ["DATABASE_URL"]
    admin = create_engine(original, isolation_level="AUTOCOMMIT")
    name = "bk_test_" + uuid.uuid4().hex
    with admin.connect() as c:
        c.execute(text('CREATE DATABASE "'+name+'"'))
    os.environ["DATABASE_URL"] = original.rsplit('/',1)[0] + '/' + name
    os.environ["KAFKA_TOPIC"] = name
    from botkernel.core import initialize
    initialize()
    config._bk_cleanup = (admin, name)


def pytest_unconfigure(config):
    if hasattr(config, "_bk_cleanup"):
        from botkernel.core import engine
        engine.dispose()
        admin, name = config._bk_cleanup
        with admin.connect() as c:
            c.execute(text('DROP DATABASE "'+name+'" WITH (FORCE)'))
        admin.dispose()
        from confluent_kafka.admin import AdminClient
        client = AdminClient({'bootstrap.servers':os.environ['KAFKA_BOOTSTRAP_SERVERS']})
        topics = client.list_topics(timeout=10).topics
        if os.environ['KAFKA_TOPIC'] in topics:
            for future in client.delete_topics([os.environ['KAFKA_TOPIC']], operation_timeout=10).values():
                future.result(timeout=15)
