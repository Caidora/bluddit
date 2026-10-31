"""Membership persistence and serialized administrative state transitions."""

from contextlib import asynccontextmanager

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from bluddit_api.database import Database
from bluddit_api.utils.permissions import Permission, Role, RolePolicy
from bluddit_api.utils.security import MembershipState


class MembershipError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class MembershipRepository:
    def __init__(self, database: Database):
        self.database = database

    async def register(self, username: str, display_name: str, password_hash: str):
        try:
            async with self.database.transaction() as connection:
                cursor = await connection.execute(
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
        except UniqueViolation:
            raise MembershipError(409, "Username unavailable") from None

    async def list_accounts(
        self, membership_state: str | None, limit: int, offset: int
    ):
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT id, username, display_name, membership_state, role_name, timezone
                FROM accounts
                WHERE (%(membership_state)s::text IS NULL OR membership_state = %(membership_state)s)
                ORDER BY id LIMIT %(limit)s OFFSET %(offset)s
                """,
                {
                    "membership_state": membership_state,
                    "limit": limit,
                    "offset": offset,
                },
            )
            cursor.row_factory = dict_row
            return await cursor.fetchall()

    async def get_account(self, account_id: int):
        async with self.database.transaction() as connection:
            return await self._get_account(connection, account_id)

    @staticmethod
    async def _get_account(connection, account_id: int):
        cursor = await connection.execute(
            """
            SELECT id, username, display_name, membership_state, role_name, timezone
            FROM accounts WHERE id = %(account_id)s
            """,
            {"account_id": account_id},
        )
        cursor.row_factory = dict_row
        account = await cursor.fetchone()
        if account is None:
            raise MembershipError(404, "Account not found")
        return account

    async def approve(self, actor_id: int, target_id: int):
        return await self._transition_membership(
            actor_id, target_id, {MembershipState.PENDING}, MembershipState.ACTIVE
        )

    async def reject(self, actor_id: int, target_id: int):
        return await self._transition_membership(
            actor_id, target_id, {MembershipState.PENDING}, MembershipState.REJECTED
        )

    async def deactivate(self, actor_id: int, target_id: int):
        return await self._transition_membership(
            actor_id, target_id, {MembershipState.ACTIVE}, MembershipState.INACTIVE
        )

    async def activate(self, actor_id: int, target_id: int):
        return await self._transition_membership(
            actor_id,
            target_id,
            {MembershipState.REJECTED, MembershipState.INACTIVE},
            MembershipState.ACTIVE,
        )

    async def promote_to_officer(self, actor_id: int, target_id: int):
        return await self._change_role(actor_id, target_id, Role.MEMBER, Role.OFFICER)

    async def demote_to_member(self, actor_id: int, target_id: int):
        return await self._change_role(actor_id, target_id, Role.OFFICER, Role.MEMBER)

    async def pass_guild_master(self, actor_id: int, target_id: int):
        async with self._administration(
            actor_id, target_id, guild_master_only=True
        ) as (connection, target):
            if target["membership_state"] != MembershipState.ACTIVE:
                raise MembershipError(409, "Guild Master recipient must be active")
            # Demote first to satisfy the unique index; both writes commit atomically.
            await self._set_role(connection, actor_id, Role.OFFICER)
            await self._set_role(connection, target_id, Role.GUILD_MASTER)
            return await self._get_account(connection, target_id)

    @asynccontextmanager
    async def _administration(
        self, actor_id: int, target_id: int, *, guild_master_only: bool = False
    ):
        async with self.database.transaction() as connection:
            # Shared with first-officer bootstrap. All membership/role writers serialize.
            await connection.execute("""SELECT pg_advisory_xact_lock(730003)""")
            await connection.execute(
                """
                SELECT id FROM accounts WHERE id = ANY(%(account_ids)s)
                ORDER BY id FOR UPDATE
                """,
                {"account_ids": [actor_id, target_id]},
            )
            actor = await self._get_account(connection, actor_id)
            if not RolePolicy.allows(actor, Permission.ACCOUNTS_MANAGE):
                raise MembershipError(403, "Permission denied")
            if guild_master_only and actor["role_name"] != Role.GUILD_MASTER:
                raise MembershipError(403, "Only the Guild Master may change roles")
            target = await self._get_account(connection, target_id)
            if target["role_name"] == Role.GUILD_MASTER:
                raise MembershipError(403, "Guild Master changes require transfer")
            if guild_master_only and actor_id == target_id:
                raise MembershipError(403, "Cannot change your own role")
            yield connection, target

    async def _transition_membership(
        self,
        actor_id: int,
        target_id: int,
        sources: set[MembershipState],
        membership_state: MembershipState,
    ):
        async with self._administration(actor_id, target_id) as (connection, target):
            if target["membership_state"] not in sources:
                raise MembershipError(409, "Invalid membership transition")
            await self._protect_last_administrator(
                connection, target, target["role_name"], membership_state
            )
            await connection.execute(
                """
                UPDATE accounts SET membership_state = %(membership_state)s, updated_at = now()
                WHERE id = %(account_id)s
                """,
                {"membership_state": membership_state.value, "account_id": target_id},
            )
            if membership_state != MembershipState.ACTIVE:
                await connection.execute(
                    """
                    UPDATE refresh_sessions SET revoked_at = now()
                    WHERE account_id = %(account_id)s AND revoked_at IS NULL
                    """,
                    {"account_id": target_id},
                )
            return await self._get_account(connection, target_id)

    async def _change_role(
        self, actor_id: int, target_id: int, source: Role, role: Role
    ):
        async with self._administration(
            actor_id, target_id, guild_master_only=True
        ) as (connection, target):
            if target["role_name"] != source:
                raise MembershipError(409, "Invalid role transition")
            await self._protect_last_administrator(
                connection, target, role, target["membership_state"]
            )
            await self._set_role(connection, target_id, role)
            return await self._get_account(connection, target_id)

    @staticmethod
    async def _set_role(connection, account_id: int, role: Role):
        await connection.execute(
            """
            UPDATE accounts SET role_name = %(role)s, updated_at = now()
            WHERE id = %(account_id)s
            """,
            {"role": role.value, "account_id": account_id},
        )

    @staticmethod
    async def _protect_last_administrator(
        connection, target, role: str, membership_state: str
    ):
        administrators = {Role.OFFICER, Role.GUILD_MASTER}
        if (
            target["membership_state"] != "active"
            or target["role_name"] not in administrators
        ):
            return
        if membership_state == MembershipState.ACTIVE and role in administrators:
            return
        cursor = await connection.execute(
            """
            SELECT count(*) FROM accounts
            WHERE membership_state = 'active' AND role_name IN ('officer', 'guild_master')
            """
        )
        if (await cursor.fetchone())[0] <= 1:
            raise MembershipError(409, "Cannot remove the last active administrator")
