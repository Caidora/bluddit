"""Policy and registration boundary checks that do not require PostgreSQL."""

from unittest.mock import AsyncMock
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
import psycopg

from bluddit_api.main import create_app
from bluddit_api.models.accounts import Account, AccountState
from bluddit_api.database import get_database
from bluddit_api.utils.dependencies import get_membership_repository
from bluddit_api.utils.permissions import Permission, Role, RolePolicy


def test_policy_is_immutable_and_requires_active_membership():
    assert RolePolicy.permissions(Role.MEMBER) < RolePolicy.permissions(Role.OFFICER)
    assert RolePolicy.permissions(Role.OFFICER) == RolePolicy.permissions(
        Role.GUILD_MASTER
    )
    assert not RolePolicy.permissions("unknown")
    for state in ("pending", "rejected", "inactive"):
        assert not RolePolicy.allows(
            AccountState(id=1, role_name="guild_master", membership_state=state),
            Permission.ACCOUNTS_MANAGE,
        )
    with pytest.raises(TypeError):
        RolePolicy.mappings[Role.MEMBER] = frozenset(Permission)
    with pytest.raises(AttributeError):
        RolePolicy.permissions(Role.MEMBER).add(Permission.ACCOUNTS_MANAGE)


def test_registration_guards_validation_normalization_and_throttle(monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    repository = AsyncMock()
    repository.register.return_value = Account(
        id=1,
        username="new_member",
        display_name="New Member",
        membership_state="pending",
        role_name="member",
        timezone=None,
    )
    app = create_app()
    app.dependency_overrides[get_membership_repository] = lambda: repository
    body = {
        "username": " New_Member ",
        "display_name": " New Member ",
        "password": "private-password",
    }
    headers = {"Origin": "http://testserver", "X-CSRF-Protection": "1"}
    with TestClient(app) as client:
        assert client.post("/api/auth/register", json=body).status_code == 403
        assert (
            client.post(
                "/api/auth/register", headers=headers, content="bad"
            ).status_code
            == 415
        )
        assert (
            client.post(
                "/api/auth/register",
                headers=headers,
                json={**body, "password": "x" * 9000},
            ).status_code
            == 413
        )
        for change in (
            {"password": "short"},
            {"display_name": "  "},
            {"username": "!"},
            {"role_name": "officer"},
            {"membership_state": "active"},
        ):
            response = client.post(
                "/api/auth/register", headers=headers, json={**body, **change}
            )
            assert response.status_code == 422
            assert "private-password" not in response.text
        response = client.post("/api/auth/register", headers=headers, json=body)
        assert response.status_code == 201
        assert "set-cookie" not in response.headers
        assert response.headers["cache-control"] == "no-store"
        username, display_name, encoded = repository.register.await_args.args
        assert (username, display_name) == ("new_member", "New Member")
        assert encoded.startswith("$argon2id$") and "private-password" not in encoded
        # Exhaust the bucket without spending time hashing more passwords.
        for _ in range(9):
            import asyncio

            asyncio.run(app.state.registration_throttle.reserve("registration"))
        response = client.post(
            "/api/auth/register",
            headers=headers,
            json={**body, "username": "different"},
        )
        assert response.status_code == 429 and "retry-after" in response.headers
        assert repository.register.await_count == 1


def test_registration_commit_failure_cannot_return_success(monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    connection = AsyncMock()
    connection.execute.return_value.fetchone.return_value = {
        "membership_state": "pending"
    }

    @asynccontextmanager
    async def transaction():
        yield connection
        raise psycopg.OperationalError("private-commit-failure")

    app = create_app()
    app.dependency_overrides[get_database] = lambda: SimpleNamespace(
        transaction=transaction
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            headers={"Origin": "http://testserver", "X-CSRF-Protection": "1"},
            json={
                "username": "member",
                "display_name": "Member",
                "password": "private-password",
            },
        )
    assert response.status_code == 503
    assert "private-commit-failure" not in response.text
    assert response.headers["cache-control"] == "no-store"
