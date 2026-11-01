"""Atomic account bootstrap and password recovery persistence."""

from bluddit_api.database import Database
from bluddit_api.utils.security import MembershipState


class AccountRepository:
    def __init__(self, database: Database):
        self.database = database

    async def create_first_officer(
        self, username: str, display_name: str, password_hash: str
    ) -> None:
        async with self.database.transaction() as connection:
            await connection.execute("""SELECT pg_advisory_xact_lock(730003)""")
            cursor = await connection.execute(
                """
                SELECT 1 FROM accounts
                WHERE membership_state = %(membership_state)s AND role_name IN ('officer', 'guild_master')
                LIMIT 1
                """,
                {"membership_state": MembershipState.ACTIVE.value},
            )
            if await cursor.fetchone():
                raise ValueError("An active Officer or Guild Master already exists")
            await connection.execute(
                """
                INSERT INTO accounts (username, display_name, password_hash, membership_state, role_name)
                VALUES (%(username)s, %(display_name)s, %(password_hash)s, %(membership_state)s, 'officer')
                """,
                {
                    "username": username,
                    "display_name": display_name,
                    "password_hash": password_hash,
                    "membership_state": MembershipState.ACTIVE.value,
                },
            )

    async def reset_password(self, username: str, password_hash: str) -> None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                UPDATE accounts SET password_hash = %(password_hash)s, updated_at = now()
                WHERE lower(username) = %(username)s AND battle_net_account_id IS NULL
                RETURNING id
                """,
                {"password_hash": password_hash, "username": username},
            )
            account = await cursor.fetchone()
            if account is None:
                raise ValueError(
                    "Unlinked account not found; linked accounts recover through Battle.net"
                )
            await connection.execute(
                """
                UPDATE refresh_sessions SET revoked_at = now()
                WHERE account_id = %(account_id)s AND revoked_at IS NULL
                """,
                {"account_id": account[0]},
            )
