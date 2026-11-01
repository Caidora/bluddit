"""Authentication queries and their transaction boundaries."""

from datetime import datetime

from psycopg.rows import class_row

from bluddit_api.models.oauth import SessionExpiry

from bluddit_api.database import Database
from bluddit_api.models.accounts import Account, AccountCredentials
from bluddit_api.utils.security import MembershipState


class AuthRepository:
    def __init__(self, database: Database):
        self.database = database

    async def get_account_credentials(self, username: str) -> AccountCredentials | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT id, password_hash, membership_state, battle_net_account_id
                FROM accounts
                WHERE lower(username) = %(username)s
                """,
                {"username": username},
            )
            cursor.row_factory = class_row(AccountCredentials)
            return await cursor.fetchone()

    async def get_account_for_hashed_access_token(
        self, hashed: bytes
    ) -> Account | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT a.id, a.username, a.display_name, a.membership_state, a.role_name, a.timezone, a.battletag
                FROM sessions s
                JOIN refresh_sessions r ON r.id = s.refresh_session_id
                JOIN accounts a ON a.id = s.account_id AND a.id = r.account_id
                WHERE s.token_hash = %(token_hash)s AND s.expires_at > now() AND s.revoked_at IS NULL
                    AND r.expires_at > now() AND r.revoked_at IS NULL
                    AND a.membership_state = %(membership_state)s AND a.battle_net_account_id IS NOT NULL
                """,
                {
                    "token_hash": hashed,
                    "membership_state": MembershipState.ACTIVE.value,
                },
            )
            cursor.row_factory = class_row(Account)
            return await cursor.fetchone()

    async def create_session(
        self,
        account_id: int,
        authenticated_until: datetime,
        refresh_hash: bytes,
        access_hash: bytes | None = None,
    ) -> datetime | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT id FROM accounts
                WHERE id = %(account_id)s AND membership_state = 'active'
                    AND battle_net_account_id IS NOT NULL AND battle_net_token_expires_at > now()
                    AND %(authenticated_until)s > now()
                FOR UPDATE
                """,
                {"account_id": account_id, "authenticated_until": authenticated_until},
            )
            if await cursor.fetchone() is None:
                return None
            cursor = await connection.execute(
                """
                INSERT INTO refresh_sessions (account_id, token_hash, expires_at)
                SELECT id, %(refresh_hash)s, LEAST(battle_net_token_expires_at, %(authenticated_until)s, now() + interval '1 day')
                FROM accounts WHERE id = %(account_id)s
                RETURNING id, account_id, expires_at
                """,
                {
                    "account_id": account_id,
                    "refresh_hash": refresh_hash,
                    "authenticated_until": authenticated_until,
                },
            )
            cursor.row_factory = class_row(SessionExpiry)
            session = await cursor.fetchone()
            if access_hash is not None:
                await self._insert_access(
                    connection, account_id, session.id, access_hash, session.expires_at
                )
            return session.expires_at

    async def rotate_session(
        self, current_hash: bytes, replacement_hash: bytes, access_hash: bytes
    ) -> datetime | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                UPDATE refresh_sessions r SET token_hash = %(replacement_hash)s
                WHERE r.token_hash = %(current_hash)s AND r.expires_at > now() AND r.revoked_at IS NULL
                    AND EXISTS (
                        SELECT 1 FROM accounts a
                        WHERE a.id = r.account_id AND a.membership_state = 'active'
                            AND a.battle_net_account_id IS NOT NULL
                    )
                RETURNING r.id, r.account_id, r.expires_at
                """,
                {"replacement_hash": replacement_hash, "current_hash": current_hash},
            )
            cursor.row_factory = class_row(SessionExpiry)
            session = await cursor.fetchone()
            if session is None:
                return None
            await self._insert_access(
                connection,
                session.account_id,
                session.id,
                access_hash,
                session.expires_at,
            )
            return session.expires_at

    async def revoke_session(self, hashed: bytes) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                """
                UPDATE refresh_sessions SET revoked_at = now()
                WHERE token_hash = %(token_hash)s AND revoked_at IS NULL
                """,
                {"token_hash": hashed},
            )

    async def revoke_account_sessions(self, account_id: int) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                """
                UPDATE refresh_sessions SET revoked_at = now()
                WHERE account_id = %(account_id)s AND revoked_at IS NULL
                """,
                {"account_id": account_id},
            )

    @staticmethod
    async def _insert_access(
        connection,
        account_id: int,
        refresh_id: int,
        hashed: bytes,
        expires_at: datetime,
    ):
        await connection.execute(
            """
            INSERT INTO sessions (token_hash, account_id, refresh_session_id, expires_at)
            VALUES (%(token_hash)s, %(account_id)s, %(refresh_session_id)s, LEAST(now() + interval '10 minutes', %(expires_at)s))
            """,
            {
                "token_hash": hashed,
                "account_id": account_id,
                "refresh_session_id": refresh_id,
                "expires_at": expires_at,
            },
        )
