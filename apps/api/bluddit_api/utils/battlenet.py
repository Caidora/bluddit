"""Battle.net confidential OAuth client, secret settings, and redirect validation."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlencode, urlsplit

from cryptography.fernet import Fernet
from fastapi import HTTPException, Request
import httpx

from bluddit_api.models.oauth import ProviderIdentity

FLOW_COOKIE = "bluddit_oauth"
REGISTRATION_COOKIE = "bluddit_registration"
FLOW_SECONDS = 600
AUTHORIZE_URL = "https://oauth.battle.net/authorize"
TOKEN_URL = "https://oauth.battle.net/token"
USERINFO_URL = "https://oauth.battle.net/userinfo"


def credential_version(encoded: str) -> bytes:
    return hashlib.sha256(encoded.encode()).digest()


def safe_return(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/home"
    try:
        decoded = unquote(value, errors="strict")
        if re.search(r"[\\\x00-\x20\x7f]", decoded) or decoded.startswith("//"):
            return "/home"
        parsed = urlsplit(decoded)
        # Match browser normalization, including dot segments and encoded slashes.
        segments = []
        for part in parsed.path.split("/"):
            if part == "..":
                if segments:
                    segments.pop()
            elif part not in {"", "."}:
                segments.append(part)
        path = "/" + "/".join(segments).lower()
        if path in {
            "/",
            "/login",
            "/register",
            "/logout",
            "/pending-approval",
        } or path.startswith(("/auth", "/api")):
            return "/home"
        return value
    except (ValueError, UnicodeError):
        return "/home"


def read_setting(name: str) -> str:
    value, filename = os.environ.get(name, ""), os.environ.get(name + "_FILE", "")
    if value and filename:
        raise RuntimeError(f"Set only one of {name} and {name}_FILE")
    if filename:
        try:
            value = Path(filename).read_text().strip()
        except OSError:
            raise RuntimeError(f"Cannot read {name}_FILE") from None
    return value


@dataclass(frozen=True)
class BattleNetSettings:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    encryption_key: str = field(repr=False)

    @classmethod
    def from_env(cls, environment: str, origins: frozenset[str]):
        names = (
            "BATTLE_NET_CLIENT_ID",
            "BATTLE_NET_CLIENT_SECRET",
            "BATTLE_NET_REDIRECT_URI",
            "BATTLE_NET_TOKEN_ENCRYPTION_KEY",
        )
        values = [read_setting(name) for name in names]
        if not any(values) and environment != "production":
            return None
        if not all(values):
            raise RuntimeError(
                "Set BATTLE_NET_CLIENT_ID, BATTLE_NET_CLIENT_SECRET, BATTLE_NET_REDIRECT_URI and BATTLE_NET_TOKEN_ENCRYPTION_KEY"
            )
        parsed = urlsplit(values[2])
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if (
            origin not in origins
            or parsed.path != "/api/oauth-redirect"
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
            or parsed.scheme not in {"http", "https"}
            or (environment == "production" and parsed.scheme != "https")
        ):
            raise RuntimeError(
                "BATTLE_NET_REDIRECT_URI must use an allowed origin and /api/oauth-redirect"
            )
        try:
            Fernet(values[3].encode())
        except (ValueError, UnicodeError):
            raise RuntimeError(
                "BATTLE_NET_TOKEN_ENCRYPTION_KEY must be a Fernet key"
            ) from None
        return cls(*values)


class ProviderError(Exception):
    """Safe boundary for provider responses, credentials, and connection failures."""


class BattleNetClient:
    def __init__(self, settings: BattleNetSettings):
        self.settings = settings
        self.cipher = Fernet(settings.encryption_key.encode())

    def authorization_url(self, state: str) -> str:
        return (
            AUTHORIZE_URL
            + "?"
            + urlencode(
                {
                    "client_id": self.settings.client_id,
                    "redirect_uri": self.settings.redirect_uri,
                    "response_type": "code",
                    "scope": "openid",
                    "state": state,
                }
            )
        )

    async def exchange(self, code: str) -> ProviderIdentity:
        try:
            # Explicit endpoints, no redirects, and bounded network/connection resources.
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=False,
                limits=httpx.Limits(max_connections=2),
            ) as client:
                obtained = datetime.now(timezone.utc)
                token_response = await client.post(
                    TOKEN_URL,
                    auth=(self.settings.client_id, self.settings.client_secret),
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.settings.redirect_uri,
                    },
                )
                token_response.raise_for_status()
                token = token_response.json()
                access = token.get("access_token")
                lifetime = token.get("expires_in")
                if (
                    not isinstance(access, str)
                    or not access
                    or len(access) > 16384
                    or type(lifetime) is not int
                    or lifetime <= 1
                    or str(token.get("token_type", "")).lower() != "bearer"
                ):
                    raise ValueError
                expiry = obtained + timedelta(seconds=min(lifetime, 86400))
                user_response = await client.get(
                    USERINFO_URL, headers={"Authorization": "Bearer " + access}
                )
                user_response.raise_for_status()
                user = user_response.json()
                account_id, battletag = user.get("id"), user.get("battletag")
                if (
                    type(account_id) is not int
                    or not 0 < account_id < 2**63
                    or not isinstance(battletag, str)
                    or not battletag.strip()
                    or len(battletag) > 256
                ):
                    raise ValueError
                return ProviderIdentity(
                    battle_net_account_id=account_id,
                    battletag=battletag,
                    access_token=self.cipher.encrypt(access.encode()),
                    obtained_at=obtained,
                    token_expires_at=expiry,
                )
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, OverflowError):
            raise ProviderError(
                "Battle.net authentication failed. Please try again."
            ) from None


def provider(request: Request) -> BattleNetClient:
    result = request.app.state.battlenet_client
    if result is None:
        raise HTTPException(503, "Battle.net sign-in is not configured")
    return result


class CallbackLogFilter(logging.Filter):
    """Uvicorn logs scope paths including query strings; redact before formatting."""

    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            if str(path).split("?", 1)[0] == "/api/oauth-redirect":
                record.args = (client, method, "/api/oauth-redirect", version, status)
        return True
