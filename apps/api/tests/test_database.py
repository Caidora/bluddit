"""Migration/readiness and rollback behavior, without application-schema assertions."""
from httpx import ASGITransport, AsyncClient
import psycopg
import pytest

from bluddit_api.main import create_app
from bluddit_api.migrate import run_migrations

pytestmark = pytest.mark.anyio




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
            await connection.execute("INSERT INTO transaction_probe VALUES (%(value)s)", {"value": "a user's input"})
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
