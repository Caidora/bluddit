"""OAuth account migration, daily sessions, and persisted concurrency boundaries."""

import asyncio
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlsplit

from httpx import ASGITransport, AsyncClient
import psycopg
import pytest

from oauth_helpers import (
    FakeBattleNetClient,
    TEST_KEY,
    identity,
    oauth_callback,
    oauth_login,
)
from bluddit_api.admin import create_first_officer, reset_password
from bluddit_api.utils.auth import COOKIE_NAME, TOKEN_PATH, AuthSettings
from bluddit_api.utils.battlenet import FLOW_COOKIE, REGISTRATION_COOKIE, ProviderError
from bluddit_api.main import create_app
from bluddit_api.migrate import run_migrations, MIGRATIONS
from bluddit_api.utils.security import PASSWORD_HASHER, token_hash, new_token
from cryptography.fernet import Fernet

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
    app.state.battlenet_client = FakeBattleNetClient()
    async with app.router.lifespan_context(app):
        yield app, database


@asynccontextmanager
async def client_for(app, origin="http://test"):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=origin, headers=HEADERS
    ) as client:
        yield client


async def me(client, access):
    return await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer " + access}
    )


async def migration(client):
    return await oauth_login(client, legacy=("officer", PASSWORD))


async def test_migration_preserves_account_and_removes_password_atomically(auth):
    app, database = auth
    async with client_for(app) as client:
        started = await client.post(
            "/api/auth/login", json={"username": " OFFICER ", "password": PASSWORD}
        )
        assert set(started.json()) == {"authorization_url"}
        assert client.cookies.get(COOKIE_NAME) is None
        assert (await client.post(TOKEN_PATH)).status_code == 401
        state = parse_qs(urlsplit(started.json()["authorization_url"]).query)["state"][
            0
        ]
        response = await client.get(
            "/api/oauth-redirect", params={"state": state, "code": "1000"}
        )
        assert response.headers["location"].startswith("/auth/complete")
        assert response.headers["referrer-policy"] == "no-referrer"
        access = (await client.post(TOKEN_PATH)).json()["access_token"]
        account = (await me(client, access)).json()
        assert (
            account["id"],
            account["username"],
            account["role_name"],
            account["display_name"],
        ) == (1, "officer", "officer", "Test officer")
        async with database.transaction() as connection:
            row = await connection.execute(
                "SELECT password_hash, battle_net_account_id, battle_net_access_token FROM accounts"
            )
            password, provider_id, encrypted = await row.fetchone()
        assert password is None and provider_id == 1000
        assert b"synthetic-provider-token" not in encrypted
        assert Fernet(TEST_KEY).decrypt(bytes(encrypted)) == b"synthetic-provider-token"
        assert (
            await client.post(
                "/api/auth/login", json={"username": "officer", "password": PASSWORD}
            )
        ).status_code == 401
        with pytest.raises(ValueError, match="Battle.net"):
            await reset_password(database, "officer", "new-synthetic-password")


async def test_login_rotation_stale_tokens_logout_and_independent_sessions(auth):
    app, database = auth
    async with client_for(app) as client, client_for(app) as other:
        response = await migration(client)
        original = response.json()["access_token"]
        assert response.json()["expires_in"] == 600
        old_refresh = client.cookies.get(COOKIE_NAME)
        cookie = response.headers["set-cookie"]
        assert (
            "HttpOnly" in cookie
            and "SameSite=strict" in cookie
            and "Path=" + TOKEN_PATH in cookie
        )
        assert "2592000" not in cookie and "Domain=" not in cookie
        async with database.transaction() as connection:
            row = await connection.execute("SELECT expires_at FROM refresh_sessions")
            original_expiry = (await row.fetchone())[0]
        independent = (await oauth_login(other)).json()["access_token"]
        response = await client.post(TOKEN_PATH)
        current = response.json()["access_token"]
        current_refresh = client.cookies.get(COOKIE_NAME)
        assert current_refresh != old_refresh and current != original
        async with database.transaction() as connection:
            cursor = await connection.execute(
                "SELECT expires_at FROM refresh_sessions WHERE token_hash = %(token_hash)s",
                {"token_hash": token_hash(current_refresh)},
            )
            assert (await cursor.fetchone())[0] == original_expiry
        async with client_for(app) as stale:
            stale.cookies.set(COOKIE_NAME, old_refresh, path=TOKEN_PATH)
            assert (await stale.post(TOKEN_PATH)).status_code == 401
        assert (await me(client, original)).status_code == 200
        assert (await me(client, current)).status_code == 200
        assert (await client.delete(TOKEN_PATH)).status_code == 204
        assert client.cookies.get(COOKIE_NAME) is None
        assert (await me(client, current)).status_code == 401
        assert (await me(other, independent)).status_code == 200
        assert (await client.delete(TOKEN_PATH)).status_code == 204


async def test_concurrent_refresh_has_one_winner(auth):
    app, _ = auth
    async with client_for(app) as client:
        access = (await migration(client)).json()["access_token"]
        cookie = f"{COOKIE_NAME}={client.cookies.get(COOKIE_NAME)}"
        async with client_for(app) as a, client_for(app) as b:
            results = await asyncio.gather(
                a.post(TOKEN_PATH, headers={"Cookie": cookie}),
                b.post(TOKEN_PATH, headers={"Cookie": cookie}),
            )
        assert sorted(result.status_code for result in results) == [200, 401]
        assert (await me(client, access)).status_code == 200


@pytest.mark.parametrize("state", ["pending", "rejected", "inactive"])
async def test_migration_preserves_membership_without_granting_access(auth, state):
    app, database = auth
    async with database.transaction() as connection:
        await connection.execute(
            "UPDATE accounts SET membership_state = %(state)s", {"state": state}
        )
    async with client_for(app) as client:
        result = await oauth_callback(client, legacy=("officer", PASSWORD))
        expected = (
            "/pending-approval" if state == "pending" else "/login?authError=membership"
        )
        assert result.headers["location"] == expected
        assert client.cookies.get(COOKIE_NAME) is None
        assert (await client.post(TOKEN_PATH)).status_code == 401
    async with database.transaction() as connection:
        row = await connection.execute(
            "SELECT password_hash, membership_state FROM accounts"
        )
        assert await row.fetchone() == (None, state)


async def test_password_reset_invalidates_inflight_migration(auth):
    app, database = auth
    async with client_for(app) as client:
        response = await client.post(
            "/api/auth/login", json={"username": "officer", "password": PASSWORD}
        )
        state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][
            0
        ]
        await reset_password(database, "officer", "replacement-password-123")
        callback = await client.get(
            "/api/oauth-redirect", params={"state": state, "code": "1000"}
        )
        assert callback.headers["location"] == "/login?authError=link_conflict"
    async with database.transaction() as connection:
        row = await connection.execute(
            "SELECT password_hash, battle_net_account_id FROM accounts"
        )
        encoded, provider_id = await row.fetchone()
        assert (
            PASSWORD_HASHER.verify(encoded, "replacement-password-123")
            and provider_id is None
        )


async def test_unknown_identity_verified_registration_approval_and_login(auth):
    app, database = auth
    async with client_for(app) as client:
        assert (
            await client.post("/api/auth/register", json={"display_name": "Member"})
        ).status_code == 401
        assert (
            await client.post(
                "/api/auth/register",
                json={
                    "username": "old",
                    "password": PASSWORD,
                    "display_name": "Member",
                },
            )
        ).status_code == 422
        response = await oauth_callback(client, 2000)
        assert response.headers["location"] == "/register/complete"
        assert (await client.get("/api/auth/battlenet/registration")).json() == {
            "battletag": "Synthetic#1234"
        }
        ticket = client.cookies.get(REGISTRATION_COOKIE)
        response = await client.post(
            "/api/auth/register", json={"display_name": " New Member "}
        )
        assert response.status_code == 201
        account = response.json()
        assert (
            account["username"],
            account["display_name"],
            account["membership_state"],
            account["role_name"],
        ) == (None, "New Member", "pending", "member")
        assert client.cookies.get(COOKIE_NAME) is None
        assert (
            "access_token" not in account and "battle_net_access_token" not in account
        )
        client.cookies.set(REGISTRATION_COOKIE, ticket, path="/api")
        assert (
            await client.post("/api/auth/register", json={"display_name": "Duplicate"})
        ).status_code == 401
        async with database.transaction() as connection:
            await connection.execute(
                "UPDATE accounts SET membership_state = 'active' WHERE id = %(account_id)s",
                {"account_id": account["id"]},
            )
        access = (await oauth_login(client, 2000)).json()["access_token"]
        assert (await me(client, access)).json()["id"] == account["id"]


async def test_concurrent_registration_has_one_winner(auth):
    app, database = auth
    async with client_for(app) as client:
        await oauth_callback(client, 2000)
        cookie = f"{REGISTRATION_COOKIE}={client.cookies.get(REGISTRATION_COOKIE)}"
        async with client_for(app) as a, client_for(app) as b:
            results = await asyncio.gather(
                *(
                    c.post(
                        "/api/auth/register",
                        json={"display_name": "Member"},
                        headers={"Cookie": cookie},
                    )
                    for c in (a, b)
                )
            )
        assert sorted(r.status_code for r in results) == [201, 401]
    async with database.transaction() as connection:
        row = await connection.execute(
            "SELECT count(*) FROM accounts WHERE battle_net_account_id = 2000"
        )
        assert (await row.fetchone())[0] == 1


@pytest.mark.parametrize(
    "failure", ["wrong_browser", "missing_state", "expired", "cancelled", "provider"]
)
async def test_oauth_attempt_failures_preserve_credentials(auth, failure):
    app, database = auth
    async with client_for(app) as client:
        response = await client.post(
            "/api/auth/login", json={"username": "officer", "password": PASSWORD}
        )
        state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][
            0
        ]
        params = {"state": state, "code": "1000"}
        if failure == "wrong_browser":
            client.cookies.clear()
        elif failure == "missing_state":
            params.pop("state")
        elif failure == "expired":
            async with database.transaction() as connection:
                await connection.execute(
                    "UPDATE oauth_attempts SET expires_at = now() - interval '1 second'"
                )
        elif failure == "cancelled":
            params = {"state": state, "error": "access_denied"}
        elif failure == "provider":

            async def unavailable(code):
                raise ProviderError("private-provider-error")

            app.state.battlenet_client.exchange = unavailable
        result = await client.get("/api/oauth-redirect", params=params)
        assert result.status_code == 303 and result.headers["location"].startswith(
            "/login?authError="
        )
        assert "private" not in result.text
    async with database.transaction() as connection:
        row = await connection.execute(
            "SELECT password_hash, battle_net_account_id FROM accounts"
        )
        encoded, provider_id = await row.fetchone()
        assert PASSWORD_HASHER.verify(encoded, PASSWORD) and provider_id is None


async def test_callback_single_use_and_cross_account_identity_conflict(auth):
    app, database = auth
    async with client_for(app) as first, client_for(app) as second:
        await migration(first)
        async with database.transaction() as connection:
            await connection.execute(
                "INSERT INTO accounts (username, display_name, password_hash) VALUES ('other', 'Other', %(encoded)s)",
                {"encoded": PASSWORD_HASHER.hash(PASSWORD)},
            )
        response = await second.post(
            "/api/auth/login", json={"username": "other", "password": PASSWORD}
        )
        state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][
            0
        ]
        cookie = second.cookies.get(FLOW_COOKIE)
        callback = await second.get(
            "/api/oauth-redirect", params={"state": state, "code": "1000"}
        )
        assert callback.headers["location"] == "/login?authError=link_conflict"
        second.cookies.set(FLOW_COOKIE, cookie, path="/api")
        replay = await second.get(
            "/api/oauth-redirect", params={"state": state, "code": "1000"}
        )
        assert replay.headers["location"] == "/login?authError=expired"
    async with database.transaction() as connection:
        row = await connection.execute(
            "SELECT password_hash, battle_net_account_id FROM accounts WHERE username = 'other'"
        )
        encoded, provider_id = await row.fetchone()
        assert PASSWORD_HASHER.verify(encoded, PASSWORD) and provider_id is None


async def test_expired_registration_cannot_create_account(auth):
    app, database = auth
    async with client_for(app) as client:
        await oauth_callback(client, 2000)
        async with database.transaction() as connection:
            await connection.execute(
                "UPDATE oauth_registrations SET expires_at = now() - interval '1 second'"
            )
        assert (await client.get("/api/auth/battlenet/registration")).status_code == 401
        assert (
            await client.post("/api/auth/register", json={"display_name": "Late"})
        ).status_code == 401


async def test_short_provider_lifetime_caps_session_and_other_device_does_not_extend_it(
    auth,
):
    app, database = auth

    async def short(code):
        return identity(int(code), lifetime=90)

    app.state.battlenet_client.exchange = short
    async with client_for(app) as first, client_for(app) as other:
        response = await migration(first)
        assert 1 <= response.json()["expires_in"] <= 90
        original = response.json()["access_token"]
        hashed = token_hash(first.cookies.get(COOKIE_NAME))
        async with database.transaction() as connection:
            row = await connection.execute(
                "SELECT expires_at FROM refresh_sessions WHERE token_hash = %(hashed)s",
                {"hashed": hashed},
            )
            expiry = (await row.fetchone())[0]
        app.state.battlenet_client = FakeBattleNetClient()
        await oauth_login(other)
        await first.post(TOKEN_PATH)
        async with database.transaction() as connection:
            row = await connection.execute(
                "SELECT min(expires_at) FROM refresh_sessions"
            )
            assert (await row.fetchone())[0] == expiry
            await connection.execute(
                "UPDATE refresh_sessions SET created_at = now() - interval '1 hour', expires_at = now() - interval '1 second' WHERE expires_at = %(expiry)s",
                {"expiry": expiry},
            )
        assert (await me(first, original)).status_code == 401
        assert (await first.post(TOKEN_PATH)).status_code == 401
        assert (await other.post(TOKEN_PATH)).status_code == 200


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
        access = (await migration(client)).json()["access_token"]
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
            assert (await client.post(TOKEN_PATH)).status_code == 401


async def test_database_errors_do_not_expose_secrets(auth, monkeypatch):
    from bluddit_api.database import Database

    app, _ = auth

    def unavailable(self):
        raise psycopg.OperationalError("private-connection-secret")

    monkeypatch.setattr(Database, "transaction", unavailable)
    async with client_for(app) as client:
        response = await client.post(
            "/api/auth/login", json={"username": "officer", "password": PASSWORD}
        )
        assert response.status_code == 503
        assert "private-connection-secret" not in response.text


async def test_production_cookie(auth):
    app, _ = auth
    app.state.auth_settings = AuthSettings(frozenset({"https://test"}), True)
    async with client_for(app, "https://test") as client:
        assert (await client.get("/api/auth/me")).status_code == 401
        result = await migration(client)
        assert "Secure" in result.headers["set-cookie"]


async def test_rollout_revokes_legacy_sessions_and_preserves_content(
    database, tmp_path
):
    previous = tmp_path / "previous"
    previous.mkdir()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name < "0008":
            (previous / path.name).write_bytes(path.read_bytes())
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True, directory=previous)
        await connection.execute(
            "INSERT INTO accounts (username, display_name, password_hash, role_name, membership_state) VALUES ('legacy', 'Legacy', 'hash', 'guild_master', 'active')"
        )
        await connection.execute(
            "INSERT INTO refresh_sessions (account_id, token_hash, expires_at) VALUES (1, %(hashed)s, now() + interval '1 day')",
            {"hashed": token_hash(new_token())},
        )
        await connection.execute(
            "INSERT INTO sessions (account_id, refresh_session_id, token_hash, expires_at) VALUES (1, 1, %(hashed)s, now() + interval '10 minutes')",
            {"hashed": token_hash(new_token())},
        )
        await run_migrations(connection, apply=True)
        row = await connection.execute(
            "SELECT username, password_hash, role_name FROM accounts"
        )
        assert await row.fetchone() == ("legacy", "hash", "guild_master")
        for table in ("sessions", "refresh_sessions"):
            # Static known identifiers, not application SQL.
            row = await connection.execute(
                psycopg.sql.SQL("SELECT revoked_at FROM {}").format(
                    psycopg.sql.Identifier(table)
                )
            )
            assert (await row.fetchone())[0] is not None


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


async def test_concurrent_legacy_linking_has_one_winner(auth):
    app, database = auth
    async with client_for(app) as first, client_for(app) as second:
        starts = await asyncio.gather(
            *(
                client.post(
                    "/api/auth/login",
                    json={"username": "officer", "password": PASSWORD},
                )
                for client in (first, second)
            )
        )
        states = [
            parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
            for start in starts
        ]
        callbacks = await asyncio.gather(
            *(
                client.get(
                    "/api/oauth-redirect",
                    params={"state": state, "code": str(account_id)},
                )
                for client, state, account_id in zip(
                    (first, second), states, (2000, 3000)
                )
            )
        )
        locations = [result.headers["location"] for result in callbacks]
        assert sum(location.startswith("/auth/complete") for location in locations) == 1
        assert locations.count("/login?authError=link_conflict") == 1
    async with database.transaction() as connection:
        row = await connection.execute(
            "SELECT password_hash, battle_net_account_id FROM accounts"
        )
        password, provider_id = await row.fetchone()
        assert password is None and provider_id in (2000, 3000)


async def test_identity_matching_uses_id_and_updates_battletag(auth):
    app, _ = auth
    async with client_for(app) as client:
        await migration(client)

        async def renamed(code):
            return identity(int(code), battletag="Renamed#5678")

        app.state.battlenet_client.exchange = renamed
        result = await oauth_login(client, 1000)
        account = (await me(client, result.json()["access_token"])).json()
        assert account["id"] == 1 and account["battletag"] == "Renamed#5678"
        # An identical mutable BattleTag is not evidence of account ownership.
        other = await oauth_callback(client, 2000)
        assert other.headers["location"] == "/register/complete"


async def test_legacy_invalid_credentials_remain_generic_and_throttled(auth):
    app, _ = auth
    async with client_for(app) as client:
        wrong = {"username": "officer", "password": "wrong-password"}
        expected = (await client.post("/api/auth/login", json=wrong)).json()
        assert (
            await client.post("/api/auth/login", json={**wrong, "username": "unknown"})
        ).json() == expected
        for _ in range(9):
            assert (await client.post("/api/auth/login", json=wrong)).status_code == 401
        limited = await client.post("/api/auth/login", json=wrong)
        assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
        assert client.cookies.get(COOKIE_NAME) is None
