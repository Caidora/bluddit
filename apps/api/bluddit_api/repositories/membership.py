"""Membership SQL operations on the API request's shared transaction."""

from psycopg import AsyncConnection
from psycopg.rows import dict_row


class MembershipRepository:
    def __init__(self, connection: AsyncConnection):
        self.connection = connection

    async def register(self, username: str, display_name: str, password_hash: str):
        cursor = await self.connection.execute(
            """
            INSERT INTO accounts (username, display_name, password_hash, membership_state, role_name)
            VALUES (%(username)s, %(display_name)s, %(password_hash)s, 'pending', 'member')
            RETURNING id, username, display_name, membership_state, role_name, timezone
            """,
            {
                "username": username,
                "display_name": display_name,
                "password_hash": password_hash,
            },
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()

    async def list_accounts(
        self, membership_state: str | None, limit: int, offset: int
    ):
        cursor = await self.connection.execute(
            """
            SELECT id, username, display_name, membership_state, role_name, timezone
            FROM accounts
            WHERE (%(membership_state)s::text IS NULL OR membership_state = %(membership_state)s)
            ORDER BY id LIMIT %(limit)s OFFSET %(offset)s
            """,
            {"membership_state": membership_state, "limit": limit, "offset": offset},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchall()

    async def get_account(self, account_id: int):
        cursor = await self.connection.execute(
            """
            SELECT id, username, display_name, membership_state, role_name, timezone
            FROM accounts WHERE id = %(account_id)s
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()

    async def lock_administration(self):
        await self.connection.execute("""SELECT pg_advisory_xact_lock(730003)""")

    async def lock_accounts(self, account_ids: list[int]):
        cursor = await self.connection.execute(
            """
            SELECT id, username, display_name, membership_state, role_name, timezone
            FROM accounts WHERE id = ANY(%(account_ids)s)
            ORDER BY id FOR UPDATE
            """,
            {"account_ids": account_ids},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchall()

    async def count_active_administrators(self):
        cursor = await self.connection.execute(
            """
            SELECT count(*) FROM accounts
            WHERE membership_state = 'active' AND role_name IN ('officer', 'guild_master')
            """
        )
        return (await cursor.fetchone())[0]

    async def approve(self, account_id: int):
        cursor = await self.connection.execute(
            """
            UPDATE accounts SET membership_state = 'active', updated_at = now()
            WHERE id = %(account_id)s
            RETURNING id, username, display_name, membership_state, role_name, timezone
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()

    async def reject(self, account_id: int):
        cursor = await self.connection.execute(
            """
            UPDATE accounts SET membership_state = 'rejected', updated_at = now()
            WHERE id = %(account_id)s
            RETURNING id, username, display_name, membership_state, role_name, timezone
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()

    async def deactivate(self, account_id: int):
        cursor = await self.connection.execute(
            """
            UPDATE accounts SET membership_state = 'inactive', updated_at = now()
            WHERE id = %(account_id)s
            RETURNING id, username, display_name, membership_state, role_name, timezone
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()

    async def activate(self, account_id: int):
        cursor = await self.connection.execute(
            """
            UPDATE accounts SET membership_state = 'active', updated_at = now()
            WHERE id = %(account_id)s
            RETURNING id, username, display_name, membership_state, role_name, timezone
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()

    async def revoke_sessions(self, account_id: int):
        await self.connection.execute(
            """
            UPDATE refresh_sessions SET revoked_at = now()
            WHERE account_id = %(account_id)s AND revoked_at IS NULL
            """,
            {"account_id": account_id},
        )

    async def promote_to_officer(self, account_id: int):
        cursor = await self.connection.execute(
            """
            UPDATE accounts SET role_name = 'officer', updated_at = now()
            WHERE id = %(account_id)s
            RETURNING id, username, display_name, membership_state, role_name, timezone
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()

    async def demote_to_member(self, account_id: int):
        cursor = await self.connection.execute(
            """
            UPDATE accounts SET role_name = 'member', updated_at = now()
            WHERE id = %(account_id)s
            RETURNING id, username, display_name, membership_state, role_name, timezone
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()

    async def demote_guild_master(self, account_id: int):
        await self.connection.execute(
            """
            UPDATE accounts SET role_name = 'officer', updated_at = now()
            WHERE id = %(account_id)s
            """,
            {"account_id": account_id},
        )

    async def pass_guild_master(self, account_id: int):
        cursor = await self.connection.execute(
            """
            UPDATE accounts SET role_name = 'guild_master', updated_at = now()
            WHERE id = %(account_id)s
            RETURNING id, username, display_name, membership_state, role_name, timezone
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        return await cursor.fetchone()
