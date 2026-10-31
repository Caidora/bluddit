"""Migration/readiness and rollback behavior, without application-schema assertions."""
import os
import uuid

from httpx import ASGITransport, AsyncClient
import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest

from bluddit_api.database import Database, DatabaseSettings
from bluddit_api.main import create_app
from bluddit_api.migrate import run_migrations

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    parameters = conninfo_to_dict(url)
    if not parameters.get("dbname", "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a disposable database ending in _test")
    name = "bluddit_" + uuid.uuid4().hex + "_test"
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as admin:
        await admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        settings = DatabaseSettings({**parameters, "dbname": name})
        db = Database(settings)
        try:
            await db.pool.open(wait=True)
            for key, value in settings.parameters.items():
                variable = {"dbname": "PGDATABASE"}.get(key, "PG" + key.upper())
                monkeypatch.setenv(variable, value)
            monkeypatch.delenv("PGPASSWORD_FILE", raising=False)
            monkeypatch.setenv("APP_ENV", "test")
            yield db
        finally:
            await db.pool.close()
            await admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


async def test_migrations_rerun_safely_and_make_api_ready(database):
    app = create_app()
    async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/health")).status_code == 200
        assert (await client.get("/api/ready")).status_code == 503
        async with database.pool.connection() as connection:
            assert (await run_migrations(connection, apply=True))["applied"]
            assert (await run_migrations(connection, apply=True))["applied"] == []
        assert (await client.get("/api/ready")).json() == {"status": "ok"}


async def test_failed_transaction_leaves_no_partial_writes(database):
    async with database.transaction() as connection:
        await connection.execute("CREATE TABLE transaction_probe (value text)")
    with pytest.raises(RuntimeError, match="abort"):
        async with database.transaction() as connection:
            await connection.execute("INSERT INTO transaction_probe VALUES (%s)", ("a user's input",))
            raise RuntimeError("abort operation")
    async with database.transaction() as connection:
        cursor = await connection.execute("SELECT count(*) FROM transaction_probe")
        assert (await cursor.fetchone())[0] == 0


async def test_failed_migration_rolls_back_changes_and_ledger(database, tmp_path):
    migration = tmp_path / "0001_failure_probe.sql"
    migration.write_text("CREATE TABLE migration_probe (value text); SELECT 1/0;")
    async with database.pool.connection() as connection:
        with pytest.raises(psycopg.errors.DivisionByZero):
            await run_migrations(connection, apply=True, directory=tmp_path)
        cursor = await connection.execute("SELECT to_regclass('migration_probe')")
        assert (await cursor.fetchone())[0] is None
        # A successful retry proves the failed migration was not recorded as applied.
        migration.write_text("CREATE TABLE migration_probe (value text);")
        assert (await run_migrations(connection, apply=True, directory=tmp_path))["applied"] == [migration.name]
