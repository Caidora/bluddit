"""Authentication queries and their transaction boundaries."""

from psycopg.rows import dict_row

from bluddit_api.database import Database
from bluddit_api.utils.security import MembershipState


class AuthRepository:
    def __init__(self, database: Database):
        self.database = database

    async def account_credentials(self, username: str):
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT id, password_hash, membership_state
                FROM accounts
                WHERE lower(username) = %(username)s
                """,
                {"username": username},
            )
            cursor.row_factory = dict_row
            return await cursor.fetchone()

    async def account_for_access(self, hashed: bytes):
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT a.id, a.username, a.display_name, a.membership_state, a.role_name, a.timezone
                FROM sessions s
                JOIN refresh_sessions r ON r.id = s.refresh_session_id
                JOIN accounts a ON a.id = s.account_id AND a.id = r.account_id
                WHERE s.token_hash = %(token_hash)s AND s.expires_at > now() AND s.revoked_at IS NULL
                    AND r.expires_at > now() AND r.revoked_at IS NULL
                    AND a.membership_state = %(membership_state)s
                """,
                {
                    "token_hash": hashed,
                    "membership_state": MembershipState.ACTIVE.value,
                },
            )
            cursor.row_factory = dict_row
            return await cursor.fetchone()

    async def create_session(
        self,
        account_id: int,
        password_hash: str,
        refresh_hash: bytes,
        access_hash: bytes,
    ) -> bool:
        async with self.database.transaction() as connection:
            # Coordinate login/reset and recheck credentials after password verification.
            cursor = await connection.execute(
                """
                SELECT id FROM accounts
                WHERE id = %(account_id)s AND membership_state = %(membership_state)s
                    AND password_hash = %(password_hash)s
                FOR UPDATE
                """,
                {
                    "account_id": account_id,
                    "membership_state": MembershipState.ACTIVE.value,
                    "password_hash": password_hash,
                },
            )
            if await cursor.fetchone() is None:
                return False
            cursor = await connection.execute(
                """
                INSERT INTO refresh_sessions (account_id, token_hash, expires_at)
                VALUES (%(account_id)s, %(refresh_hash)s, now() + interval '30 days')
                RETURNING id
                """,
                {"account_id": account_id, "refresh_hash": refresh_hash},
            )
            refresh_id = (await cursor.fetchone())[0]
            await self._insert_access(connection, account_id, refresh_id, access_hash)
        return True

    async def rotate_session(
        self, current_hash: bytes, replacement_hash: bytes, access_hash: bytes
    ) -> bool:
        async with self.database.transaction() as connection:
            # UPDATE rechecks its predicate after a concurrent updater commits.
            cursor = await connection.execute(
                """
                UPDATE refresh_sessions r
                SET token_hash = %(replacement_hash)s, expires_at = now() + interval '30 days'
                WHERE r.token_hash = %(current_hash)s AND r.expires_at > now() AND r.revoked_at IS NULL
                    AND EXISTS (
                        SELECT 1 FROM accounts a
                        WHERE a.id = r.account_id AND a.membership_state = %(membership_state)s
                    )
                RETURNING r.id, r.account_id
                """,
                {
                    "replacement_hash": replacement_hash,
                    "current_hash": current_hash,
                    "membership_state": MembershipState.ACTIVE.value,
                },
            )
            session = await cursor.fetchone()
            if session is None:
                return False
            await self._insert_access(connection, session[1], session[0], access_hash)
        return True

    async def revoke_session(self, hashed: bytes):
        async with self.database.transaction() as connection:
            await connection.execute(
                """
                UPDATE refresh_sessions SET revoked_at = now()
                WHERE token_hash = %(token_hash)s AND revoked_at IS NULL
                """,
                {"token_hash": hashed},
            )

    @staticmethod
    async def _insert_access(
        connection, account_id: int, refresh_id: int, hashed: bytes
    ):
        await connection.execute(
            """
            INSERT INTO sessions (token_hash, account_id, refresh_session_id, expires_at)
            VALUES (%(token_hash)s, %(account_id)s, %(refresh_session_id)s, now() + interval '10 minutes')
            """,
            {
                "token_hash": hashed,
                "account_id": account_id,
                "refresh_session_id": refresh_id,
            },
        )
