"""Membership persistence and serialized administrative state transitions."""

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from bluddit_api.database import Database
from bluddit_api.utils.permissions import Permission, Role, RolePolicy


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

    async def list_accounts(self, state: str | None, limit: int, offset: int):
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT id, username, display_name, membership_state, role_name, timezone
                FROM accounts
                WHERE (%(state)s::text IS NULL OR membership_state = %(state)s)
                ORDER BY id LIMIT %(limit)s OFFSET %(offset)s
                """,
                {"state": state, "limit": limit, "offset": offset},
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

    async def manage(
        self, actor_id: int, target_id: int, action: str, role: Role | None = None
    ):
        permission = {
            "role": Permission.ROLES_ASSIGN,
            "transfer": Permission.GUILD_MASTER_TRANSFER,
        }.get(action, Permission.ACCOUNTS_MANAGE)
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
            if not RolePolicy.allows(actor, permission):
                raise MembershipError(403, "Permission denied")
            target = await self._get_account(connection, target_id)
            if target["role_name"] == Role.GUILD_MASTER:
                raise MembershipError(403, "Guild Master changes require transfer")
            if action in {"role", "transfer"} and actor_id == target_id:
                raise MembershipError(403, "Cannot change your own role")

            if action == "transfer":
                if target["membership_state"] != "active":
                    raise MembershipError(409, "Guild Master recipient must be active")
                # Demote first to satisfy the unique index; both writes commit atomically.
                await self._set_role(connection, actor_id, Role.OFFICER)
                await self._set_role(connection, target_id, Role.GUILD_MASTER)
            elif action == "role":
                if role not in {Role.MEMBER, Role.OFFICER}:
                    raise MembershipError(422, "Role must be member or officer")
                if target["role_name"] == role:
                    raise MembershipError(409, "Account already has this role")
                await self._protect_last_administrator(
                    connection, target, role, target["membership_state"]
                )
                await self._set_role(connection, target_id, role)
            else:
                transitions = {
                    "approve": ({"pending"}, "active"),
                    "reject": ({"pending"}, "rejected"),
                    "deactivate": ({"active"}, "inactive"),
                    "reactivate": ({"rejected", "inactive"}, "active"),
                }
                if action not in transitions:
                    raise MembershipError(422, "Unknown membership action")
                sources, state = transitions[action]
                if target["membership_state"] not in sources:
                    raise MembershipError(409, "Invalid membership transition")
                await self._protect_last_administrator(
                    connection, target, target["role_name"], state
                )
                await connection.execute(
                    """
                    UPDATE accounts SET membership_state = %(state)s, updated_at = now()
                    WHERE id = %(account_id)s
                    """,
                    {"state": state, "account_id": target_id},
                )
                if state != "active":
                    await connection.execute(
                        """
                        UPDATE refresh_sessions SET revoked_at = now()
                        WHERE account_id = %(account_id)s AND revoked_at IS NULL
                        """,
                        {"account_id": target_id},
                    )
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
    async def _protect_last_administrator(connection, target, role: str, state: str):
        administrators = {Role.OFFICER, Role.GUILD_MASTER}
        if (
            target["membership_state"] != "active"
            or target["role_name"] not in administrators
        ):
            return
        if state == "active" and role in administrators:
            return
        cursor = await connection.execute(
            """
            SELECT count(*) FROM accounts
            WHERE membership_state = 'active' AND role_name IN ('officer', 'guild_master')
            """
        )
        if (await cursor.fetchone())[0] <= 1:
            raise MembershipError(409, "Cannot remove the last active administrator")
