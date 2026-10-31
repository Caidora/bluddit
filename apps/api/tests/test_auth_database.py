import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
import pytest

from bluddit_api.admin import create_first_officer, reset_password
from bluddit_api.utils.auth import COOKIE_NAME, TOKEN_PATH, AuthSettings
from bluddit_api.main import create_app
from bluddit_api.migrate import run_migrations
from bluddit_api.utils.security import PASSWORD_HASHER, token_hash

pytestmark = pytest.mark.anyio
PASSWORD = "synthetic-password-123"
HEADERS = {"Origin": "http://test", "X-CSRF-Protection": "1"}


@pytest.fixture
async def auth(database, monkeypatch):
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True)
    await create_first_officer(database, "Officer", "Test officer", PASSWORD)
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://test")
    app = create_app()
    async with app.router.lifespan_context(app):
        yield app, database


@asynccontextmanager
async def client_for(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as client:
        yield client


async def login(client, username="officer", password=PASSWORD):
    return await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


async def me(client, access):
    return await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer " + access}
    )


async def test_login_rotation_stale_tokens_logout_and_independent_sessions(auth):
    app, database = auth
    async with client_for(app) as client, client_for(app) as other:
        response = await login(client, " OFFICER ")
        assert response.status_code == 200
        original = response.json()["access_token"]
        assert response.json()["expires_in"] == 600
        old_refresh = client.cookies.get(COOKIE_NAME)
        cookie = response.headers["set-cookie"]
        assert (
            "HttpOnly" in cookie
            and "SameSite=strict" in cookie
            and "Path=" + TOKEN_PATH in cookie
        )
        assert (
            "Max-Age=2592000" in cookie
            and "expires=" in cookie
            and "Domain=" not in cookie
        )
        assert response.headers["cache-control"] == "no-store"
        assert (await me(client, original)).json()["role_name"] == "officer"
        independent = (await login(other)).json()["access_token"]
        async with database.transaction() as connection:
            await connection.execute(
                "UPDATE refresh_sessions SET expires_at = now() + interval '1 day'"
            )
        response = await client.post(TOKEN_PATH)
        current = response.json()["access_token"]
        current_refresh = client.cookies.get(COOKIE_NAME)
        assert current_refresh != old_refresh and current != original
        async with database.transaction() as connection:
            cursor = await connection.execute(
                "SELECT token_hash, expires_at FROM refresh_sessions WHERE token_hash = %(token_hash)s",
                {"token_hash": token_hash(current_refresh)},
            )
            stored, expiry = await cursor.fetchone()
            assert bytes(stored) == token_hash(current_refresh)
            assert (expiry - datetime.now(timezone.utc)).days >= 29
            cursor = await connection.execute(
                "SELECT token_hash FROM sessions WHERE token_hash = %(token_hash)s",
                {"token_hash": token_hash(current)},
            )
            assert bytes((await cursor.fetchone())[0]) == token_hash(current)
        async with client_for(app) as stale:
            stale.cookies.set(COOKIE_NAME, old_refresh, path=TOKEN_PATH)
            rejected = await stale.post(TOKEN_PATH)
            assert rejected.status_code == 401 and "set-cookie" not in rejected.headers
        assert (await me(client, original)).status_code == 200
        assert (await me(client, current)).status_code == 200
        assert (await client.post(TOKEN_PATH)).status_code == 200
        assert (await client.delete(TOKEN_PATH)).status_code == 204
        assert client.cookies.get(COOKIE_NAME) is None
        assert (await me(client, original)).status_code == 401
        assert (await me(client, current)).status_code == 401
        assert (await me(other, independent)).status_code == 200
        assert (await client.delete(TOKEN_PATH)).status_code == 204


async def test_concurrent_refresh_has_one_winner_without_revocation(auth):
    app, _ = auth
    async with client_for(app) as client:
        access = (await login(client)).json()["access_token"]
        cookie = f"{COOKIE_NAME}={client.cookies.get(COOKIE_NAME)}"
        async with client_for(app) as a, client_for(app) as b:
            responses = await asyncio.gather(
                a.post(TOKEN_PATH, headers={"Cookie": cookie}),
                b.post(TOKEN_PATH, headers={"Cookie": cookie}),
            )
        assert sorted(response.status_code for response in responses) == [200, 401]
        winner = next(response for response in responses if response.status_code == 200)
        loser = next(response for response in responses if response.status_code == 401)
        assert "set-cookie" not in loser.headers
        assert (await me(client, access)).status_code == 200
        assert (await me(client, winner.json()["access_token"])).status_code == 200
        async with client_for(app) as fresh:
            fresh.cookies.set(
                COOKIE_NAME, winner.cookies.get(COOKIE_NAME), path=TOKEN_PATH
            )
            assert (await fresh.post(TOKEN_PATH)).status_code == 200


async def test_credentials_membership_throttle_and_password_reset(auth):
    app, database = auth
    async with client_for(app) as client:
        expected = (await login(client, password="incorrect-password")).json()
        assert (await login(client, "unknown")).json() == expected
        for state in ("pending", "rejected", "inactive"):
            async with database.transaction() as connection:
                await connection.execute(
                    "UPDATE accounts SET membership_state = %(membership_state)s",
                    {"membership_state": state},
                )
            assert (await login(client)).json() == expected
        async with database.transaction() as connection:
            await connection.execute("UPDATE accounts SET membership_state = 'active'")
        access = (await login(client)).json()["access_token"]
        await reset_password(database, "OFFICER", "replacement-password-123")
        assert (await me(client, access)).status_code == 401
        assert (await client.post(TOKEN_PATH)).status_code == 401
        assert (await login(client)).json() == expected
        assert (
            await login(client, password="replacement-password-123")
        ).status_code == 200
        async with database.transaction() as connection:
            cursor = await connection.execute(
                "SELECT membership_state, role_name FROM accounts"
            )
            assert await cursor.fetchone() == ("active", "officer")
        for _ in range(3):
            await login(client, password="incorrect-password")
        response = await login(client)
        assert response.status_code == 429 and int(response.headers["retry-after"]) > 0


async def test_password_reset_revokes_every_device_and_access_token(auth):
    app, database = auth
    async with client_for(app) as a, client_for(app) as b:
        first = (await login(a)).json()["access_token"]
        second = (await login(b)).json()["access_token"]
        rotated = (await a.post(TOKEN_PATH)).json()["access_token"]
        await reset_password(database, "officer", "new-synthetic-password")
        for access in (first, second, rotated):
            assert (await me(a, access)).status_code == 401
        assert (await a.post(TOKEN_PATH)).status_code == 401
        assert (await b.post(TOKEN_PATH)).status_code == 401


async def test_database_errors_do_not_expose_secrets(auth, monkeypatch):
    import psycopg
    from bluddit_api.database import Database

    app, _ = auth

    def unavailable(self):
        raise psycopg.OperationalError("private-connection-secret")

    monkeypatch.setattr(Database, "transaction", unavailable)
    async with client_for(app) as client:
        response = await login(client)
        assert response.status_code == 503
        assert "private-connection-secret" not in response.text
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "kind",
    [
        "access_expired",
        "access_revoked",
        "refresh_expired",
        "refresh_revoked",
        "inactive",
    ],
)
async def test_expiry_revocation_and_account_state(auth, kind):
    app, database = auth
    async with client_for(app) as client:
        access = (await login(client)).json()["access_token"]
        async with database.transaction() as connection:
            statements = {
                "access_expired": "UPDATE sessions SET created_at = now() - interval '1 hour', expires_at = now() - interval '1 second'",
                "access_revoked": "UPDATE sessions SET revoked_at = now()",
                "refresh_expired": "UPDATE refresh_sessions SET created_at = now() - interval '31 days', expires_at = now() - interval '1 second'",
                "refresh_revoked": "UPDATE refresh_sessions SET revoked_at = now()",
                "inactive": "UPDATE accounts SET membership_state = 'inactive'",
            }
            await connection.execute(statements[kind])
        assert (await me(client, access)).status_code == 401
        if kind.startswith("refresh") or kind == "inactive":
            response = await client.post(TOKEN_PATH)
            assert response.status_code == 401 and "set-cookie" not in response.headers


async def test_missing_malformed_tokens_and_production_cookie(auth):
    app, _ = auth
    app.state.auth_settings = AuthSettings(frozenset({"https://test"}), True)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test", headers=HEADERS
    ) as client:
        assert (await client.get("/api/auth/me")).status_code == 401
        for bad in ("bad", "a" * 44, "a" * 43):
            assert (await me(client, bad)).status_code == 401
        assert (await client.post(TOKEN_PATH)).status_code == 401
        response = await login(client)
        assert "Secure" in response.headers["set-cookie"]
        assert (await client.post(TOKEN_PATH)).status_code == 200


async def test_bootstrap_serializes_and_reset_preserves_inactive_role(database):
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True)
    results = await asyncio.gather(
        create_first_officer(database, "officer_a", "A", PASSWORD),
        create_first_officer(database, "officer_b", "B", PASSWORD),
        return_exceptions=True,
    )
    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    async with database.transaction() as connection:
        cursor = await connection.execute(
            "UPDATE accounts SET membership_state = 'inactive' RETURNING username"
        )
        username = (await cursor.fetchone())[0]
    await reset_password(database, username, "new-synthetic-password")
    async with database.transaction() as connection:
        cursor = await connection.execute(
            "SELECT membership_state, role_name, password_hash FROM accounts"
        )
        state, role, encoded = await cursor.fetchone()
        assert (state, role) == ("inactive", "officer")
        assert PASSWORD_HASHER.verify(encoded, "new-synthetic-password")
