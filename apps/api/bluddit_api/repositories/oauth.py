"""Atomic OAuth intent consumption, identity linking, and verified registration."""

from psycopg.rows import class_row

from bluddit_api.database import Database
from bluddit_api.models.accounts import Account, AccountCredentials
from bluddit_api.models.oauth import OAuthAttempt, OAuthRegistration, ProviderIdentity
from bluddit_api.utils.battlenet import credential_version


class LinkingConflict(Exception):
    """The verified legacy credential is no longer eligible for linking."""


class OAuthRepository:
    def __init__(self, database: Database):
        self.database = database

    async def create_attempt(
        self,
        state_hash: bytes,
        browser_hash: bytes,
        return_to: str,
        account: AccountCredentials | None = None,
    ) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                """DELETE FROM oauth_attempts WHERE expires_at <= now()"""
            )
            await connection.execute(
                """DELETE FROM oauth_registrations WHERE expires_at <= now()"""
            )
            await connection.execute(
                """
                INSERT INTO oauth_attempts (state_hash, browser_hash, return_to, account_id, credential_version)
                VALUES (%(state_hash)s, %(browser_hash)s, %(return_to)s, %(account_id)s, %(credential_version)s)
                """,
                {
                    "state_hash": state_hash,
                    "browser_hash": browser_hash,
                    "return_to": return_to,
                    "account_id": account.id if account else None,
                    "credential_version": credential_version(account.password_hash)
                    if account and account.password_hash
                    else None,
                },
            )

    async def consume_attempt(
        self, state_hash: bytes, browser_hash: bytes
    ) -> OAuthAttempt | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                UPDATE oauth_attempts SET consumed_at = now()
                WHERE state_hash = %(state_hash)s AND browser_hash = %(browser_hash)s
                    AND expires_at > now() AND consumed_at IS NULL
                RETURNING oauth_attempt_id, account_id, credential_version, return_to
                """,
                {"state_hash": state_hash, "browser_hash": browser_hash},
            )
            cursor.row_factory = class_row(OAuthAttempt)
            return await cursor.fetchone()

    async def authenticate(
        self, attempt: OAuthAttempt, identity: ProviderIdentity
    ) -> Account | None:
        async with self.database.transaction() as connection:
            if attempt.account_id is not None:
                cursor = await connection.execute(
                    """
                    SELECT id, password_hash, membership_state, battle_net_account_id
                    FROM accounts WHERE id = %(account_id)s FOR UPDATE
                    """,
                    {"account_id": attempt.account_id},
                )
                cursor.row_factory = class_row(AccountCredentials)
                account = await cursor.fetchone()
                if (
                    account is None
                    or account.battle_net_account_id is not None
                    or not account.password_hash
                    or credential_version(account.password_hash)
                    != attempt.credential_version
                ):
                    raise LinkingConflict
                cursor = await connection.execute(
                    """
                    UPDATE accounts
                    SET battle_net_account_id = %(battle_net_account_id)s, battletag = %(battletag)s,
                        battle_net_access_token = %(access_token)s, battle_net_token_obtained_at = %(obtained_at)s,
                        battle_net_token_expires_at = %(expires_at)s, password_hash = NULL, updated_at = now()
                    WHERE id = %(account_id)s
                    RETURNING id, username, display_name, membership_state, role_name, timezone, battletag
                    """,
                    {
                        "battle_net_account_id": identity.battle_net_account_id,
                        "battletag": identity.battletag,
                        "access_token": identity.access_token,
                        "obtained_at": identity.obtained_at,
                        "expires_at": identity.token_expires_at,
                        "account_id": attempt.account_id,
                    },
                )
                cursor.row_factory = class_row(Account)
                linked = await cursor.fetchone()
                await connection.execute(
                    """
                    UPDATE refresh_sessions SET revoked_at = now()
                    WHERE account_id = %(account_id)s AND revoked_at IS NULL
                    """,
                    {"account_id": attempt.account_id},
                )
                return linked
            cursor = await connection.execute(
                """
                UPDATE accounts
                SET battletag = %(battletag)s, battle_net_access_token = %(access_token)s,
                    battle_net_token_obtained_at = %(obtained_at)s, battle_net_token_expires_at = %(expires_at)s,
                    updated_at = now()
                WHERE battle_net_account_id = %(battle_net_account_id)s
                RETURNING id, username, display_name, membership_state, role_name, timezone, battletag
                """,
                {
                    "battletag": identity.battletag,
                    "access_token": identity.access_token,
                    "obtained_at": identity.obtained_at,
                    "expires_at": identity.token_expires_at,
                    "battle_net_account_id": identity.battle_net_account_id,
                },
            )
            cursor.row_factory = class_row(Account)
            return await cursor.fetchone()

    async def create_registration(
        self, hashed: bytes, identity: ProviderIdentity
    ) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                """
                INSERT INTO oauth_registrations
                    (token_hash, battle_net_account_id, battletag, access_token, obtained_at, token_expires_at)
                VALUES (%(token_hash)s, %(battle_net_account_id)s, %(battletag)s, %(access_token)s,
                    %(obtained_at)s, %(expires_at)s)
                """,
                {
                    "token_hash": hashed,
                    "battle_net_account_id": identity.battle_net_account_id,
                    "battletag": identity.battletag,
                    "access_token": identity.access_token,
                    "obtained_at": identity.obtained_at,
                    "expires_at": identity.token_expires_at,
                },
            )

    async def get_registration(self, hashed: bytes) -> OAuthRegistration | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT oauth_registration_id, battle_net_account_id, battletag, access_token, obtained_at, token_expires_at
                FROM oauth_registrations WHERE token_hash = %(token_hash)s
                    AND expires_at > now() AND token_expires_at > now() AND consumed_at IS NULL
                """,
                {"token_hash": hashed},
            )
            cursor.row_factory = class_row(OAuthRegistration)
            return await cursor.fetchone()

    async def register(self, hashed: bytes, display_name: str) -> Account | None:
        async with self.database.transaction() as connection:
            # DELETE ... RETURNING serializes submissions. An INSERT conflict rolls back consumption.
            cursor = await connection.execute(
                """
                DELETE FROM oauth_registrations WHERE token_hash = %(token_hash)s
                    AND expires_at > now() AND token_expires_at > now() AND consumed_at IS NULL
                RETURNING oauth_registration_id, battle_net_account_id, battletag, access_token, obtained_at, token_expires_at
                """,
                {"token_hash": hashed},
            )
            cursor.row_factory = class_row(OAuthRegistration)
            identity = await cursor.fetchone()
            if identity is None:
                return None
            cursor = await connection.execute(
                """
                INSERT INTO accounts (display_name, battle_net_account_id, battletag, battle_net_access_token,
                    battle_net_token_obtained_at, battle_net_token_expires_at, membership_state, role_name)
                VALUES (%(display_name)s, %(battle_net_account_id)s, %(battletag)s, %(access_token)s,
                    %(obtained_at)s, %(expires_at)s, 'pending', 'member')
                RETURNING id, username, display_name, membership_state, role_name, timezone, battletag
                """,
                {
                    "display_name": display_name,
                    "battle_net_account_id": identity.battle_net_account_id,
                    "battletag": identity.battletag,
                    "access_token": identity.access_token,
                    "obtained_at": identity.obtained_at,
                    "expires_at": identity.token_expires_at,
                },
            )
            cursor.row_factory = class_row(Account)
            return await cursor.fetchone()
