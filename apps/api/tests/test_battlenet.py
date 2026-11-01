"""Provider protocol, configuration, redirection and credential redaction boundaries."""

from datetime import datetime, timezone
import logging

from cryptography.fernet import Fernet
import httpx
import pytest

from oauth_helpers import TEST_KEY, configure_battlenet
from bluddit_api.utils.battlenet import (
    BattleNetClient,
    BattleNetSettings,
    CallbackLogFilter,
    ProviderError,
    safe_return,
)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "//evil.invalid",
        "https://evil.invalid",
        "/\\evil.invalid",
        "/%2f%2fevil.invalid",
        "/%0a/evil.invalid",
        "/logout",
        "/LoGoUt/",
        "/%6cogout",
        "/events/../logout",
        "/%E0%A4%A",
        "/auth/complete",
        "/api/oauth-redirect",
    ],
)
def test_unsafe_return_destinations(value):
    assert safe_return(value) == "/home"


def test_safe_return_destination():
    assert safe_return("/events?view=upcoming") == "/events?view=upcoming"


def test_production_settings_and_file_secrets(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError, match="BATTLE_NET"):
        BattleNetSettings.from_env("production", frozenset({"https://test"}))
    configure_battlenet(monkeypatch, "https://test")
    settings = BattleNetSettings.from_env("production", frozenset({"https://test"}))
    assert settings.redirect_uri == "https://test/api/oauth-redirect"
    assert "synthetic-secret" not in repr(settings) and TEST_KEY.decode() not in repr(
        settings
    )
    secret = tmp_path / "secret"
    secret.write_text("file-secret")
    monkeypatch.delenv("BATTLE_NET_CLIENT_SECRET")
    monkeypatch.setenv("BATTLE_NET_CLIENT_SECRET_FILE", str(secret))
    assert (
        BattleNetSettings.from_env(
            "production", frozenset({"https://test"})
        ).client_secret
        == "file-secret"
    )
    monkeypatch.setenv("BATTLE_NET_REDIRECT_URI", "https://test/oauth-redirect")
    with pytest.raises(RuntimeError, match="/api/oauth-redirect"):
        BattleNetSettings.from_env("production", frozenset({"https://test"}))
    monkeypatch.setenv("BATTLE_NET_REDIRECT_URI", "https://test/api/oauth-redirect")
    monkeypatch.setenv("BATTLE_NET_TOKEN_ENCRYPTION_KEY", "invalid")
    with pytest.raises(RuntimeError, match="Fernet"):
        BattleNetSettings.from_env("production", frozenset({"https://test"}))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [None, "token_http", "timeout", "no_token", "bad_expiry", "bad_user", "bad_tag"],
)
async def test_server_side_provider_exchange_and_safe_failures(monkeypatch, failure):
    settings = BattleNetSettings(
        "client",
        "private-client-secret",
        "https://test/api/oauth-redirect",
        TEST_KEY.decode(),
    )
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.path == "/token":
            assert request.method == "POST"
            assert request.headers["authorization"].startswith("Basic ")
            assert (
                b"redirect_uri=https%3A%2F%2Ftest%2Fapi%2Foauth-redirect"
                in request.content
            )
            if failure == "timeout":
                raise httpx.ReadTimeout("private-token", request=request)
            if failure == "token_http":
                return httpx.Response(401, json={"error": "private-provider-error"})
            return httpx.Response(
                200,
                json={
                    "access_token": None
                    if failure == "no_token"
                    else "private-provider-token",
                    "expires_in": "bad" if failure == "bad_expiry" else 172800,
                    "token_type": "bearer",
                },
            )
        assert request.url.path == "/userinfo"
        assert request.headers["authorization"] == "Bearer private-provider-token"
        assert "access_token" not in str(request.url)
        return httpx.Response(
            200,
            json={
                "id": "bad" if failure == "bad_user" else 1234,
                "battletag": "" if failure == "bad_tag" else "Blud#1234",
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        "bluddit_api.utils.battlenet.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    client = BattleNetClient(settings)
    if failure:
        with pytest.raises(ProviderError) as result:
            await client.exchange("private-code")
        assert "private" not in str(result.value)
    else:
        identity = await client.exchange("private-code")
        assert (
            identity.battle_net_account_id == 1234 and identity.battletag == "Blud#1234"
        )
        assert (
            86390
            < (identity.token_expires_at - datetime.now(timezone.utc)).total_seconds()
            <= 86400
        )
        assert (
            Fernet(TEST_KEY).decrypt(identity.access_token) == b"private-provider-token"
        )
        assert "private-provider-token" not in repr(identity)
    assert requests[0].url.host == "oauth.battle.net"


def test_callback_access_log_redaction():
    record = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        (
            "client",
            "GET",
            "/api/oauth-redirect?code=private-code&state=private-state",
            "1.1",
            303,
        ),
        None,
    )
    assert CallbackLogFilter().filter(record)
    assert "private" not in record.getMessage()
