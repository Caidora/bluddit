import os
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest

from bluddit_api.database import Database, DatabaseSettings


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
