"""Disposable real API/database for Playwright; never uses the member database."""

import asyncio
import os
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict
import uvicorn

from bluddit_api.migrate import run_migrations
from bluddit_api.utils.security import PASSWORD_HASHER


async def main():
    parameters = conninfo_to_dict(os.environ["TEST_DATABASE_URL"])
    if not parameters.get("dbname", "").endswith("_test"):
        raise RuntimeError(
            "Browser tests require a disposable database ending in _test"
        )
    name = "bluddit_browser_" + uuid.uuid4().hex + "_test"
    async with await psycopg.AsyncConnection.connect(
        **parameters, autocommit=True
    ) as admin:
        await admin.execute(
            psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name))
        )
        try:
            isolated = {**parameters, "dbname": name}
            async with await psycopg.AsyncConnection.connect(
                **isolated, autocommit=True
            ) as connection:
                await run_migrations(connection, apply=True)
                # Synthetic, isolated fixture. This password is never a live credential.
                await connection.execute(
                    """
                    INSERT INTO accounts (username, display_name, password_hash, membership_state, role_name)
                    VALUES (%(username)s, %(display_name)s, %(password_hash)s, 'active', 'guild_master')
                    """,
                    {
                        "username": "browser_gm",
                        "display_name": "Browser GM",
                        "password_hash": PASSWORD_HASHER.hash("browser-only-password"),
                    },
                )
            for key, value in isolated.items():
                variable = {"dbname": "PGDATABASE"}.get(key, "PG" + key.upper())
                os.environ[variable] = str(value)
            os.environ.pop("PGPASSWORD_FILE", None)
            os.environ["APP_ENV"] = "test"
            os.environ["AUTH_ALLOWED_ORIGINS"] = "http://127.0.0.1:4173"
            from bluddit_api.main import create_app

            server = uvicorn.Server(
                uvicorn.Config(
                    create_app(), host="127.0.0.1", port=18005, log_level="warning"
                )
            )
            await server.serve()
        finally:
            await admin.execute(
                psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    psycopg.sql.Identifier(name)
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
