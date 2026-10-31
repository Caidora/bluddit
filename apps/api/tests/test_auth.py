import asyncio
import base64

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from bluddit_api import admin
from bluddit_api.utils.auth import AuthSettings, LoginThrottle
from bluddit_api.main import create_app
from bluddit_api.database import get_database
from bluddit_api.utils.security import new_token, normalize_username, token_hash, validate_password


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
    results = await asyncio.gather(*(limiter.reserve("member") for _ in range(12)), return_exceptions=True)
    assert sum(result is None for result in results) == 10
    assert all(result.status_code == 429 and result.headers["Retry-After"] == "900"
               for result in results if isinstance(result, HTTPException))
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
    app.dependency_overrides[get_database] = lambda: object()
    with TestClient(app) as client:
        headers = {"Origin": "http://testserver", "X-CSRF-Protection": "1"}
        for bad in ({}, {"Origin": "https://evil.invalid", "X-CSRF-Protection": "1"}, {"Origin": "http://testserver"}):
            response = client.post("/api/auth/login", headers=bad, json={"username": "member", "password": "private-password"})
            assert response.status_code == 403
            assert response.headers["cache-control"] == "no-store"
        assert client.post("/api/auth/login", headers=headers, content="username=member").status_code == 415
        assert client.post("/api/auth/login", headers=headers, json={"password": "x" * 9000}).status_code == 413
        response = client.post("/api/auth/login", headers=headers, json={"username": "!", "password": "private-password"})
        assert response.status_code == 422
        assert "private-password" not in response.text
        assert "set-cookie" not in response.headers


def test_production_settings_require_explicit_https_origins(monkeypatch):
    monkeypatch.delenv("AUTH_ALLOWED_ORIGINS", raising=False)
    with pytest.raises(RuntimeError, match="AUTH_ALLOWED_ORIGINS"):
        AuthSettings.from_env("production")
    for origin in ("*", "http://example.org", "https://example.org/", "https://user@example.org", "https://example.org/path"):
        monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", origin)
        with pytest.raises(RuntimeError):
            AuthSettings.from_env("production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "https://example.org")
    assert AuthSettings.from_env("production").secure


def test_cli_hidden_confirmation_and_safe_failures(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["admin", "reset-password", "--username", "member"])
    prompts = []
    answers = iter(["private-password", "different-password"])
    monkeypatch.setattr(admin.getpass, "getpass", lambda prompt: (prompts.append(prompt), next(answers))[1])
    assert admin.main() == 1
    assert len(prompts) == 2
    output = capsys.readouterr()
    assert "private-password" not in output.err + output.out
