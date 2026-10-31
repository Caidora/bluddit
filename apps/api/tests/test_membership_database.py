"""Membership HTTP flows, persisted invariants, and concurrent administration."""

import asyncio

from httpx import ASGITransport, AsyncClient
import psycopg
import pytest

from bluddit_api.main import create_app
from bluddit_api.migrate import MIGRATIONS, run_migrations
from bluddit_api.repositories.auth import AuthRepository
from bluddit_api.repositories.membership import MembershipRepository
from bluddit_api.utils.auth import current_account
from bluddit_api.utils.security import PASSWORD_HASHER, new_token, token_hash

pytestmark = pytest.mark.anyio
PASSWORD = "synthetic-membership-password"
ENCODED = PASSWORD_HASHER.hash(PASSWORD)
HEADERS = {"Origin": "http://test", "X-CSRF-Protection": "1"}


@pytest.fixture
async def members(database, monkeypatch):
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True)
    users, tokens = {}, {}
    for username, state, role in (
        ("officer_a", "active", "officer"),
        ("officer_b", "active", "officer"),
        ("member", "active", "member"),
        ("pending", "pending", "member"),
        ("rejected", "rejected", "member"),
        ("inactive", "inactive", "member"),
    ):
        async with database.transaction() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO accounts (username, display_name, password_hash, membership_state, role_name)
                VALUES (%(username)s, %(username)s, %(hash)s, %(state)s, %(role)s) RETURNING id
                """,
                {"username": username, "hash": ENCODED, "state": state, "role": role},
            )
            users[username] = (await cursor.fetchone())[0]
        if state == "active":
            token = new_token()
            assert await AuthRepository(database).create_session(
                users[username], ENCODED, token_hash(new_token()), token_hash(token)
            )
            tokens[username] = {"Authorization": "Bearer " + token}
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://test")
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=HEADERS,
        ) as client,
    ):
        yield client, database, app, users, tokens


async def test_registration_approval_login_and_account_reads(members):
    client, database, _, users, tokens = members
    response = await client.post(
        "/api/auth/register",
        json={
            "username": " New_User ",
            "display_name": " New User ",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    account = response.json()
    assert (account["username"], account["membership_state"], account["role_name"]) == (
        "new_user",
        "pending",
        "member",
    )
    assert "password_hash" not in account and "access_token" not in account
    assert "set-cookie" not in response.headers
    credentials = {"username": "new_user", "password": PASSWORD}
    assert (await client.post("/api/auth/login", json=credentials)).status_code == 401
    target = f"/api/accounts/{account['id']}"
    assert (
        await client.post(target + "/approve", headers=tokens["member"])
    ).status_code == 403
    assert (await client.post(target + "/approve")).status_code == 401
    assert (
        await client.post(target + "/approve", headers=tokens["officer_a"])
    ).status_code == 200
    response = await client.post("/api/auth/login", json=credentials)
    assert response.status_code == 200
    access = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert (
        "guild.read"
        in (await client.get("/api/auth/me", headers=access)).json()["permissions"]
    )
    assert (await client.get("/api/accounts", headers=access)).status_code == 403
    assert (await client.get(target, headers=tokens["officer_a"])).json()[
        "id"
    ] == account["id"]
    listing = await client.get(
        "/api/accounts?membership_state=active&limit=2&offset=1",
        headers=tokens["officer_a"],
    )
    assert listing.status_code == 200 and len(listing.json()["accounts"]) == 2
    assert all(
        a["membership_state"] == "active" and "password_hash" not in a
        for a in listing.json()["accounts"]
    )
    assert (
        await client.get("/api/accounts?limit=101", headers=tokens["officer_a"])
    ).status_code == 422
    assert (
        await client.get(
            "/api/accounts?membership_state=bogus", headers=tokens["officer_a"]
        )
    ).status_code == 422
    assert (
        await client.get("/api/accounts/999999", headers=tokens["officer_a"])
    ).status_code == 404


async def test_duplicate_registration_is_atomic(members):
    client, _, _, _, _ = members
    body = {"username": "duplicate", "display_name": "A", "password": PASSWORD}
    results = await asyncio.gather(
        client.post("/api/auth/register", json=body),
        client.post("/api/auth/register", json={**body, "display_name": "B"}),
    )
    assert sorted(response.status_code for response in results) == [201, 409]
    response = await client.post(
        "/api/auth/register", json={**body, "username": " DUPLICATE "}
    )
    assert response.status_code == 409 and PASSWORD not in response.text


@pytest.mark.parametrize(
    "source,action,destination",
    [
        ("pending", "approve", "active"),
        ("pending", "reject", "rejected"),
        ("member", "deactivate", "inactive"),
        ("rejected", "activate", "active"),
        ("inactive", "activate", "active"),
    ],
)
async def test_membership_transitions(members, source, action, destination):
    client, _, _, users, tokens = members
    url = f"/api/accounts/{users[source]}/{action}"
    response = await client.post(url, headers=tokens["officer_a"])
    assert (
        response.status_code == 200
        and response.json()["membership_state"] == destination
    )
    assert (await client.post(url, headers=tokens["officer_a"])).status_code == 409


async def test_deactivation_revokes_all_sessions_permanently(members):
    client, database, _, users, tokens = members
    for _ in range(2):
        login = await client.post(
            "/api/auth/login", json={"username": "member", "password": PASSWORD}
        )
        assert login.status_code == 200
    old_cookie = client.cookies.get("bluddit_refresh")
    target = f"/api/accounts/{users['member']}"
    assert (
        await client.post(target + "/deactivate", headers=tokens["officer_a"])
    ).status_code == 200
    assert (
        await client.get("/api/auth/me", headers=tokens["member"])
    ).status_code == 401
    assert (await client.post("/api/auth/token")).status_code == 401
    async with database.transaction() as connection:
        cursor = await connection.execute(
            """SELECT count(*) FROM refresh_sessions WHERE account_id = %(id)s AND revoked_at IS NULL""",
            {"id": users["member"]},
        )
        assert (await cursor.fetchone())[0] == 0
    assert (
        await client.post(target + "/activate", headers=tokens["officer_a"])
    ).status_code == 200
    assert (
        await client.get("/api/auth/me", headers=tokens["member"])
    ).status_code == 401
    assert client.cookies.get("bluddit_refresh") == old_cookie
    assert (await client.post("/api/auth/token")).status_code == 401
    assert (
        await client.post(
            "/api/auth/login", json={"username": "member", "password": PASSWORD}
        )
    ).status_code == 200


async def test_role_permissions_protected_gm_and_live_authority(members):
    client, database, _, users, tokens = members
    member = f"/api/accounts/{users['member']}"
    assert (
        await client.get("/api/permissions", headers=tokens["member"])
    ).status_code == 403
    policy = await client.get("/api/permissions", headers=tokens["officer_a"])
    assert policy.status_code == 200
    assert "accounts.manage" in policy.json()["roles"]["guild_master"]
    assert policy.json()["roles"]["officer"] == policy.json()["roles"]["guild_master"]
    assert (
        await client.put("/api/permissions", headers=tokens["officer_a"], json={})
    ).status_code == 405
    # The generic mutation routes are gone.
    assert (
        await client.put(
            member + "/role", headers=tokens["officer_a"], json={"role_name": "officer"}
        )
    ).status_code == 404
    assert (
        await client.put(member + "/guild-master", headers=tokens["officer_a"])
    ).status_code == 404
    assert (
        await client.post(member + "/activate-unknown", headers=tokens["officer_a"])
    ).status_code == 404
    async with database.transaction() as connection:
        await connection.execute(
            """UPDATE accounts SET role_name = 'guild_master' WHERE id = %(id)s""",
            {"id": users["officer_b"]},
        )
    gm = f"/api/accounts/{users['officer_b']}"
    for action in ("promote-to-officer", "demote-to-member", "pass-guild-master"):
        for caller in ("member", "officer_a"):
            assert (
                await client.post(member + "/" + action, headers=tokens[caller])
            ).status_code == 403
        assert (
            await client.post(gm + "/" + action, headers=tokens["officer_b"])
        ).status_code == 403
    assert (
        await client.post(member + "/promote-to-officer", headers=tokens["officer_b"])
    ).status_code == 200
    assert (
        await client.post(member + "/promote-to-officer", headers=tokens["officer_b"])
    ).status_code == 409
    assert (
        await client.get("/api/accounts", headers=tokens["member"])
    ).status_code == 200
    assert (
        await client.post(member + "/demote-to-member", headers=tokens["officer_b"])
    ).status_code == 200
    assert (
        await client.post(member + "/demote-to-member", headers=tokens["officer_b"])
    ).status_code == 409
    assert (
        await client.get("/api/accounts", headers=tokens["member"])
    ).status_code == 403
    for action in (
        "approve",
        "reject",
        "deactivate",
        "activate",
        "promote-to-officer",
        "demote-to-member",
        "pass-guild-master",
    ):
        assert (
            await client.post(gm + "/" + action, headers=tokens["officer_a"])
        ).status_code == 403
    assert (
        await client.post(gm + "/deactivate", headers=tokens["officer_b"])
    ).status_code == 403
    assert (
        await client.post(
            f"/api/accounts/{users['inactive']}/pass-guild-master",
            headers=tokens["officer_b"],
        )
    ).status_code == 409
    assert (
        await client.post(member + "/pass-guild-master", headers=tokens["officer_b"])
    ).status_code == 200
    assert (await client.get("/api/auth/me", headers=tokens["officer_b"])).json()[
        "role_name"
    ] == "officer"
    assert (await client.get("/api/auth/me", headers=tokens["member"])).json()[
        "role_name"
    ] == "guild_master"
    assert (
        await client.post(
            f"/api/accounts/{users['officer_a']}/demote-to-member",
            headers=tokens["officer_b"],
        )
    ).status_code == 403


async def test_concurrent_deactivations_and_last_officer(members):
    client, database, _, users, tokens = members
    results = await asyncio.gather(
        client.post(
            f"/api/accounts/{users['officer_b']}/deactivate",
            headers=tokens["officer_a"],
        ),
        client.post(
            f"/api/accounts/{users['officer_a']}/deactivate",
            headers=tokens["officer_b"],
        ),
    )
    assert sum(response.status_code == 200 for response in results) == 1
    assert sum(response.status_code in {401, 403} for response in results) == 1
    async with database.transaction() as connection:
        repository = MembershipRepository(connection)
        assert await repository.count_active_administrators() == 1
        accounts = await repository.list_accounts("active", 100, 0)
    survivor = next(
        account for account in accounts if account["role_name"] == "officer"
    )
    assert (
        await client.post(
            f"/api/accounts/{survivor['id']}/deactivate",
            headers=tokens[survivor["username"]],
        )
    ).status_code == 409


@pytest.mark.parametrize(
    "action", ["promote-to-officer", "demote-to-member", "pass-guild-master"]
)
async def test_role_changes_recheck_stale_gm_authority(members, action):
    client, _, app, users, tokens = members
    # Simulate the route's auth lookup completing before a concurrent GM transfer.
    # The locked SQL read must override this stale snapshot's apparent authority.
    app.dependency_overrides[current_account] = lambda: {
        "id": users["officer_a"],
        "role_name": "guild_master",
        "membership_state": "active",
    }
    response = await client.post(
        f"/api/accounts/{users['member']}/{action}", headers=tokens["officer_a"]
    )
    assert response.status_code == 403


async def test_gm_transfer_serialization_and_atomic_rollback(members, monkeypatch):
    client, database, _, users, tokens = members
    actor = users["officer_a"]
    async with database.transaction() as connection:
        await connection.execute(
            """UPDATE accounts SET role_name = 'guild_master' WHERE id = %(id)s""",
            {"id": actor},
        )
    original = MembershipRepository.pass_guild_master

    async def fail_promotion(self, account_id):
        raise psycopg.OperationalError("injected failure")

    monkeypatch.setattr(MembershipRepository, "pass_guild_master", fail_promotion)
    response = await client.post(
        f"/api/accounts/{users['member']}/pass-guild-master",
        headers=tokens["officer_a"],
    )
    assert response.status_code == 503 and "injected failure" not in response.text
    async with database.transaction() as connection:
        repository = MembershipRepository(connection)
        assert (await repository.get_account(actor))["role_name"] == "guild_master"
        assert (await repository.get_account(users["member"]))["role_name"] == "member"
    monkeypatch.setattr(MembershipRepository, "pass_guild_master", original)
    results = await asyncio.gather(
        client.post(
            f"/api/accounts/{users['member']}/pass-guild-master",
            headers=tokens["officer_a"],
        ),
        client.post(
            f"/api/accounts/{users['officer_b']}/pass-guild-master",
            headers=tokens["officer_a"],
        ),
    )
    assert sorted(response.status_code for response in results) == [200, 403]
    async with database.transaction() as connection:
        accounts = await MembershipRepository(connection).list_accounts(None, 100, 0)
    assert sum(account["role_name"] == "guild_master" for account in accounts) == 1


async def test_deactivation_rolls_back_if_session_revocation_fails(
    members, monkeypatch
):
    client, database, _, users, tokens = members

    async def fail_revocation(self, account_id):
        raise psycopg.OperationalError("injected failure")

    monkeypatch.setattr(MembershipRepository, "revoke_sessions", fail_revocation)
    response = await client.post(
        f"/api/accounts/{users['member']}/deactivate", headers=tokens["officer_a"]
    )
    assert response.status_code == 503 and "injected failure" not in response.text
    assert (
        await client.get("/api/auth/me", headers=tokens["member"])
    ).status_code == 200
    async with database.transaction() as connection:
        account = await MembershipRepository(connection).get_account(users["member"])
    assert account["membership_state"] == "active"


async def test_upgrade_preserves_accounts_and_removes_permission_tables(
    database, tmp_path
):
    for migration in sorted(MIGRATIONS.glob("*.sql"))[:2]:
        (tmp_path / migration.name).write_bytes(migration.read_bytes())
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True, directory=tmp_path)
        await connection.execute(
            """INSERT INTO accounts (username, display_name, password_hash, role_name, membership_state) VALUES ('existing', 'Preserved', 'hash', 'guild_master', 'active')"""
        )
        await run_migrations(connection, apply=True)
        cursor = await connection.execute(
            """SELECT username, display_name, password_hash, role_name, membership_state FROM accounts"""
        )
        assert await cursor.fetchone() == (
            "existing",
            "Preserved",
            "hash",
            "guild_master",
            "active",
        )
        cursor = await connection.execute(
            """SELECT to_regclass('permissions'), to_regclass('role_permissions'), to_regclass('roles')"""
        )
        assert await cursor.fetchone() == (None, None, "roles")
        with pytest.raises(psycopg.errors.UniqueViolation):
            await connection.execute(
                """INSERT INTO accounts (username, display_name, password_hash, role_name) VALUES ('second', 'Second', 'hash', 'guild_master')"""
            )


async def test_duplicate_gm_upgrade_fails_without_partial_changes(database, tmp_path):
    for migration in sorted(MIGRATIONS.glob("*.sql"))[:2]:
        (tmp_path / migration.name).write_bytes(migration.read_bytes())
    async with database.pool.connection() as connection:
        await run_migrations(connection, apply=True, directory=tmp_path)
        await connection.execute(
            """INSERT INTO accounts (username, display_name, password_hash, role_name) VALUES ('gm_a', 'A', 'hash', 'guild_master'), ('gm_b', 'B', 'hash', 'guild_master')"""
        )
        with pytest.raises(
            psycopg.errors.RaiseException, match="Multiple Guild Masters"
        ):
            await run_migrations(connection, apply=True)
        cursor = await connection.execute(
            """SELECT to_regclass('permissions'), to_regclass('role_permissions'), (SELECT count(*) FROM schema_migrations), (SELECT count(*) FROM accounts)"""
        )
        assert await cursor.fetchone() == ("permissions", "role_permissions", 2, 2)
