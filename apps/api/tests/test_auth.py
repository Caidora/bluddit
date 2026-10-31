import asyncio
import base64
from unittest.mock import AsyncMock

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from bluddit_api import admin
from bluddit_api.models.accounts import Account, AccountCredentials
from bluddit_api.utils.auth import AuthSettings, LoginThrottle
from bluddit_api.main import create_app
from bluddit_api.utils.dependencies import get_auth_repository
from bluddit_api.utils.security import (
    new_token,
    normalize_username,
    token_hash,
    validate_password,
)


def test_credentials_and_token_validation():
    assert normalize_username("  Officer_1 ") == "officer_1"
    for value in ("ab", "a" * 33, "a b", "officér", "a'b"):
        with pytest.raises(ValueError):
            normalize_username(value)
    assert validate_password(" a password  ") == " a password  "
    for password in ("short", "a" * 129):
        with pytest.raises(ValueError):
            validate_password(password)
    token = new_token()
    assert len(token) == 43 and len(token_hash(token)) == 32
    for value in (None, "", "a" * 42, "a" * 44, "!" * 43, "a" * 42 + "B"):
        assert token_hash(value) is None
    assert base64.urlsafe_b64encode(bytes(32)).decode().rstrip("=") != token


@pytest.mark.anyio
async def test_throttle_concurrency_expiry_and_bounded_capacity():
    now = [0]
    limiter = LoginThrottle(capacity=1, clock=lambda: now[0])
    results = await asyncio.gather(
        *(limiter.reserve("member") for _ in range(12)), return_exceptions=True
    )
    assert sum(result is None for result in results) == 10
    assert all(
        result.status_code == 429 and result.headers["Retry-After"] == "900"
        for result in results
        if isinstance(result, HTTPException)
    )
    with pytest.raises(HTTPException) as rejected:
        await limiter.reserve("another")
    assert rejected.value.status_code == 429
    now[0] = 900
    await limiter.reserve("another")
    assert list(limiter.buckets) == ["another"]


def test_origin_csrf_json_and_secret_safe_validation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    app = create_app()
    app.dependency_overrides[get_auth_repository] = lambda: object()
    with TestClient(app) as client:
        headers = {"Origin": "http://testserver", "X-CSRF-Protection": "1"}
        for bad in (
            {},
            {"Origin": "https://evil.invalid", "X-CSRF-Protection": "1"},
            {"Origin": "http://testserver"},
        ):
            response = client.post(
                "/api/auth/login",
                headers=bad,
                json={"username": "member", "password": "private-password"},
            )
            assert response.status_code == 403
            assert response.headers["cache-control"] == "no-store"
        assert (
            client.post(
                "/api/auth/login", headers=headers, content="username=member"
            ).status_code
            == 415
        )
        assert (
            client.post(
                "/api/auth/login", headers=headers, json={"password": "x" * 9000}
            ).status_code
            == 413
        )
        response = client.post(
            "/api/auth/login",
            headers=headers,
            json={"username": "!", "password": "private-password"},
        )
        assert response.status_code == 422
        assert "private-password" not in response.text
        assert "set-cookie" not in response.headers


def test_production_settings_require_explicit_https_origins(monkeypatch):
    monkeypatch.delenv("AUTH_ALLOWED_ORIGINS", raising=False)
    with pytest.raises(RuntimeError, match="AUTH_ALLOWED_ORIGINS"):
        AuthSettings.from_env("production")
    for origin in (
        "*",
        "http://example.org",
        "https://example.org/",
        "https://user@example.org",
        "https://example.org/path",
    ):
        monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", origin)
        with pytest.raises(RuntimeError):
            AuthSettings.from_env("production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "https://example.org")
    assert AuthSettings.from_env("production").secure


def test_cli_hidden_confirmation_and_safe_failures(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["admin", "reset-password", "--username", "member"])
    prompts = []
    answers = iter(["private-password", "different-password"])
    monkeypatch.setattr(
        admin.getpass,
        "getpass",
        lambda prompt: (prompts.append(prompt), next(answers))[1],
    )
    assert admin.main() == 1
    assert len(prompts) == 2
    output = capsys.readouterr()
    assert "private-password" not in output.err + output.out


def test_auth_routes_accept_repository_override_without_database(monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    monkeypatch.setattr("bluddit_api.routes.auth.verify_password", lambda *_: True)
    repository = AsyncMock()
    repository.get_account_credentials.return_value = AccountCredentials(
        id=1, password_hash="test-hash", membership_state="active"
    )
    repository.create_session.return_value = True
    repository.rotate_session.return_value = True
    repository.get_account_for_hashed_access_token.return_value = Account(
        id=1,
        username="member",
        display_name="Member",
        role_name="member",
        membership_state="active",
        timezone=None,
    )
    app = create_app()
    app.dependency_overrides[get_auth_repository] = lambda: repository
    headers = {"Origin": "http://testserver", "X-CSRF-Protection": "1"}
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            headers=headers,
            json={"username": "member", "password": "test-password"},
        )
        assert response.status_code == 200
        assert set(response.json()) == {"access_token", "token_type", "expires_in"}
        assert response.json()["token_type"] == "Bearer"
        assert response.json()["expires_in"] == 600
        access = response.json()["access_token"]
        refresh = client.cookies.get("bluddit_refresh")
        response = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer " + access}
        )
        assert response.json()["username"] == "member"
        assert "guild.read" in response.json()["permissions"]
        repository.get_account_for_hashed_access_token.assert_awaited_once_with(
            token_hash(access)
        )
        response = client.post("/api/auth/token", headers=headers)
        assert response.status_code == 200
        assert set(response.json()) == {"access_token", "token_type", "expires_in"}
        assert response.json()["token_type"] == "Bearer"
        assert response.json()["expires_in"] == 600
        assert repository.rotate_session.await_args.args[0] == token_hash(refresh)
        rotated_refresh = client.cookies.get("bluddit_refresh")
        response = client.delete("/api/auth/token", headers=headers)
        assert response.status_code == 204
        assert response.content == b""
        repository.revoke_session.assert_awaited_once_with(token_hash(rotated_refresh))
        repository.get_account_credentials.assert_awaited_once_with("member")
        repository.create_session.assert_awaited_once()
