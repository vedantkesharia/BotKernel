import pytest


def test_database_url_uses_secret_file_when_configured(tmp_path, monkeypatch):
    from botkernel.core import database_url_from_environment

    secret = tmp_path / "database-url"
    secret.write_text("postgresql+psycopg://botkernel:offline@postgres/botkernel\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL_FILE", str(secret))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://ignored:ignored@ignored/ignored")

    assert database_url_from_environment() == "postgresql+psycopg://botkernel:offline@postgres/botkernel"


def test_database_url_rejects_empty_secret_file(tmp_path, monkeypatch):
    from botkernel.core import database_url_from_environment

    secret = tmp_path / "empty-database-url"
    secret.write_text("\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL_FILE", str(secret))

    with pytest.raises(ValueError, match="DATABASE_URL_FILE is empty"):
        database_url_from_environment()
