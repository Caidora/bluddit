"""Synthetic provider injection and linked test accounts; never use live credentials."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet

from bluddit_api.models.oauth import OAuthAttempt, ProviderIdentity
from bluddit_api.repositories.auth import AuthRepository
from bluddit_api.repositories.oauth import OAuthRepository
from bluddit_api.utils.battlenet import credential_version
from bluddit_api.utils.security import new_token, token_hash

TEST_KEY = Fernet.generate_key()


def configure_battlenet(monkeypatch, origin="http://test"):
    monkeypatch.setenv("BATTLE_NET_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("BATTLE_NET_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setenv("BATTLE_NET_REDIRECT_URI", origin + "/api/oauth-redirect")
    monkeypatch.setenv("BATTLE_NET_TOKEN_ENCRYPTION_KEY", TEST_KEY.decode())


def identity(account_id=1000, *, lifetime=86400, battletag="Synthetic#1234"):
    now = datetime.now(timezone.utc)
    return ProviderIdentity(
        battle_net_account_id=account_id,
        battletag=battletag,
        access_token=Fernet(TEST_KEY).encrypt(b"synthetic-provider-token"),
        obtained_at=now,
        token_expires_at=now + timedelta(seconds=lifetime),
    )


class FakeBattleNetClient:
    def authorization_url(self, state):
        return "/api/test-battlenet/authorize?state=" + state

    async def exchange(self, code):
        return identity(int(code))


async def linked_session(database, account_id, access):
    auth = AuthRepository(database)
    async with database.transaction() as connection:
        cursor = await connection.execute(
            """SELECT username FROM accounts WHERE id = %(account_id)s""",
            {"account_id": account_id},
        )
        username = (await cursor.fetchone())[0]
    credentials = await auth.get_account_credentials(username)
    value = identity(1000 + account_id)
    await OAuthRepository(database).authenticate(
        OAuthAttempt(
            oauth_attempt_id=0,
            account_id=account_id,
            credential_version=credential_version(credentials.password_hash),
            return_to="/home",
        ),
        value,
    )
    return await auth.create_session(
        account_id, value.token_expires_at, token_hash(new_token()), token_hash(access)
    )


async def oauth_callback(client, account_id=1000, *, legacy=None, return_to="/home"):
    if legacy:
        started = await client.post(
            "/api/auth/login",
            json={"username": legacy[0], "password": legacy[1], "return_to": return_to},
        )
    else:
        started = await client.post(
            "/api/auth/battlenet/start", json={"return_to": return_to}
        )
    assert started.status_code == 200, started.text
    state = parse_qs(urlsplit(started.json()["authorization_url"]).query)["state"][0]
    return await client.get(
        "/api/oauth-redirect", params={"state": state, "code": str(account_id)}
    )


async def oauth_login(client, account_id=1000, *, legacy=None):
    callback = await oauth_callback(client, account_id, legacy=legacy)
    assert callback.status_code == 303 and callback.headers["location"].startswith(
        "/auth/complete"
    ), callback.headers
    return await client.post("/api/auth/token")
