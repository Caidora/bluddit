"""Migration/readiness and rollback behavior, without application-schema assertions."""
import os
import uuid

from fastapi.testclient import TestClient
import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest

from bluddit_api.database import Database, DatabaseSettings
from bluddit_api.main import create_app
from bluddit_api.migrate import run_migrations


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    parameters = conninfo_to_dict(url)
    if not parameters.get("dbname", "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a disposable database ending in _test")
    name = "bluddit_" + uuid.uuid4().hex + "_test"
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        settings = DatabaseSettings({**parameters, "dbname": name})
        db = Database(settings)
        try:
            db.pool.open(wait=True)
            for key, value in settings.parameters.items():
                variable = {"dbname": "PGDATABASE"}.get(key, "PG" + key.upper())
                monkeypatch.setenv(variable, value)
            monkeypatch.delenv("PGPASSWORD_FILE", raising=False)
            monkeypatch.setenv("APP_ENV", "test")
            yield db
        finally:
            db.pool.close()
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


def test_migrations_rerun_safely_and_make_api_ready(database):
    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/ready").status_code == 503
        with database.pool.connection() as connection:
            assert run_migrations(connection, apply=True)["applied"]
            assert run_migrations(connection, apply=True)["applied"] == []
        assert client.get("/api/ready").json() == {"status": "ok"}


def test_failed_transaction_leaves_no_partial_writes(database):
    with database.transaction() as connection:
        connection.execute("CREATE TABLE transaction_probe (value text)")
    with pytest.raises(RuntimeError, match="abort"):
        with database.transaction() as connection:
            connection.execute("INSERT INTO transaction_probe VALUES (%s)", ("a user's input",))
            raise RuntimeError("abort operation")
    with database.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM transaction_probe").fetchone()[0] == 0


def test_failed_migration_rolls_back_changes_and_ledger(database, tmp_path):
    migration = tmp_path / "0001_failure_probe.sql"
    migration.write_text("CREATE TABLE migration_probe (value text); SELECT 1/0;")
    with database.pool.connection() as connection:
        with pytest.raises(psycopg.errors.DivisionByZero):
            run_migrations(connection, apply=True, directory=tmp_path)
        assert connection.execute("SELECT to_regclass('migration_probe')").fetchone()[0] is None
        # A successful retry proves the failed migration was not recorded as applied.
        migration.write_text("CREATE TABLE migration_probe (value text);")
        assert run_migrations(connection, apply=True, directory=tmp_path)["applied"] == [migration.name]
