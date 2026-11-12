import os
import uuid
import pytest
from sqlalchemy import create_engine, text


def pytest_configure(config):
    if os.getenv("BOTKERNEL_TEST_ISOLATED") != "true":
        raise pytest.UsageError("Run tests using Compose test service (isolated database required)")
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
