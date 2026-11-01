"""Disposable real API/database for Playwright; never uses the member database."""

import asyncio
import os
import uuid
from html import escape

from fastapi import Request
from fastapi.responses import HTMLResponse
from oauth_helpers import FakeBattleNetClient, identity

import psycopg
from psycopg.conninfo import conninfo_to_dict
import uvicorn

from bluddit_api.migrate import run_migrations
from bluddit_api.utils.security import PASSWORD_HASHER
from bluddit_api.utils.dependencies import get_reference_data
from reference_data import REFERENCES


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
                value = identity(9001, battletag="BrowserGM#1234")
                await connection.execute(
                    """
                    INSERT INTO accounts (username, display_name, battle_net_account_id, battletag, battle_net_access_token,
                        battle_net_token_obtained_at, battle_net_token_expires_at, membership_state, role_name)
                    VALUES (%(username)s, %(display_name)s, 9001, %(battletag)s, %(token)s,
                        %(obtained_at)s, %(expires_at)s, 'active', 'guild_master')
                    """,
                    {
                        "username": "browser_gm",
                        "display_name": "Browser GM",
                        "battletag": value.battletag,
                        "token": value.access_token,
                        "obtained_at": value.obtained_at,
                        "expires_at": value.token_expires_at,
                    },
                )
                await connection.execute(
                    """INSERT INTO accounts (username, display_name, password_hash, membership_state, role_name)
                    VALUES ('browser_legacy', 'Browser Legacy', %(hash)s, 'active', 'member')""",
                    {"hash": PASSWORD_HASHER.hash("browser-only-password")},
                )
            for key, value in isolated.items():
                variable = {"dbname": "PGDATABASE"}.get(key, "PG" + key.upper())
                os.environ[variable] = str(value)
            os.environ.pop("PGPASSWORD_FILE", None)
            os.environ["APP_ENV"] = "test"
            os.environ["AUTH_ALLOWED_ORIGINS"] = "http://127.0.0.1:4173"
            from bluddit_api.main import create_app

            app = create_app()
            app.dependency_overrides[get_reference_data] = lambda: REFERENCES

            class BrowserProvider(FakeBattleNetClient):
                async def exchange(self, code):
                    tags = {
                        9001: "BrowserGM#1234",
                        9002: "BrowserMember#1234",
                        9003: "BrowserLegacy#1234",
                    }
                    return identity(int(code), battletag=tags[int(code)])

            app.state.battlenet_client = BrowserProvider()

            @app.get("/api/test-battlenet/authorize", response_class=HTMLResponse)
            async def authorize(request: Request):
                state = escape(request.query_params.get("state", ""), quote=True)
                return HTMLResponse(f'''<!doctype html><html><body><h1>Synthetic Battle.net</h1>
                  <form action="/api/oauth-redirect" method="get">
                    <input type="hidden" name="state" value="{state}">
                    <button name="code" value="9001">Authorize Browser GM</button>
                    <button name="code" value="9002">Authorize Browser Member</button>
                    <button name="code" value="9003">Authorize Browser Legacy</button>
                  </form></body></html>''')

            server = uvicorn.Server(
                uvicorn.Config(app, host="127.0.0.1", port=18005, log_level="warning")
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
