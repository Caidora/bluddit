"""Operation-level membership SQL and atomic persistence boundaries."""

from psycopg.rows import class_row

from bluddit_api.database import Database
from bluddit_api.models.accounts import Account, AccountState


class GuildMasterChangedError(Exception):
    """The caller is no longer the active Guild Master at transfer time."""


class MembershipRepository:
    def __init__(self, database: Database):
        self.database = database

    async def register(
        self, username: str, display_name: str, password_hash: str
    ) -> Account:
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
            cursor.row_factory = class_row(Account)
            account = await cursor.fetchone()
            assert account is not None  # INSERT ... RETURNING always produces a row.
            return account

    async def list_accounts(
        self, membership_state: str | None, limit: int, offset: int
    ) -> list[Account]:
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
            cursor.row_factory = class_row(Account)
            return await cursor.fetchall()

    async def get_account(self, account_id: int) -> Account | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT id, username, display_name, membership_state, role_name, timezone
                FROM accounts WHERE id = %(account_id)s
                """,
                {"account_id": account_id},
            )
            cursor.row_factory = class_row(Account)
            return await cursor.fetchone()

    async def approve(self, account_id: int) -> Account | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                UPDATE accounts SET membership_state = 'active', updated_at = now()
                WHERE id = %(account_id)s AND membership_state = 'pending'
                RETURNING id, username, display_name, membership_state, role_name, timezone
                """,
                {"account_id": account_id},
            )
            cursor.row_factory = class_row(Account)
            account = await cursor.fetchone()
        return account

    async def reject(self, account_id: int) -> Account | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                UPDATE accounts SET membership_state = 'rejected', updated_at = now()
                WHERE id = %(account_id)s AND membership_state = 'pending'
                RETURNING id, username, display_name, membership_state, role_name, timezone
                """,
                {"account_id": account_id},
            )
            cursor.row_factory = class_row(Account)
            account = await cursor.fetchone()
        return account

    async def deactivate(self, account_id: int) -> Account | None:
        async with self.database.transaction() as connection:
            await connection.execute("""SELECT pg_advisory_xact_lock(730003)""")
            cursor = await connection.execute(
                """
                UPDATE accounts SET membership_state = 'inactive', updated_at = now()
                WHERE id = %(account_id)s AND membership_state = 'active' AND role_name <> 'guild_master'
                    AND (role_name <> 'officer' OR (
                        SELECT count(*) FROM accounts
                        WHERE membership_state = 'active' AND role_name IN ('officer', 'guild_master')
                    ) > 1)
                RETURNING id, username, display_name, membership_state, role_name, timezone
                """,
                {"account_id": account_id},
            )
            cursor.row_factory = class_row(Account)
            account = await cursor.fetchone()
        return account

    async def activate(self, account_id: int) -> Account | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                UPDATE accounts SET membership_state = 'active', updated_at = now()
                WHERE id = %(account_id)s AND membership_state IN ('rejected', 'inactive')
                RETURNING id, username, display_name, membership_state, role_name, timezone
                """,
                {"account_id": account_id},
            )
            cursor.row_factory = class_row(Account)
            account = await cursor.fetchone()
        return account

    async def promote_to_officer(self, account_id: int) -> Account | None:
        async with self.database.transaction() as connection:
            cursor = await connection.execute(
                """
                UPDATE accounts SET role_name = 'officer', updated_at = now()
                WHERE id = %(account_id)s AND role_name = 'member'
                RETURNING id, username, display_name, membership_state, role_name, timezone
                """,
                {"account_id": account_id},
            )
            cursor.row_factory = class_row(Account)
            account = await cursor.fetchone()
        return account

    async def demote_to_member(self, account_id: int) -> Account | None:
        async with self.database.transaction() as connection:
            await connection.execute("""SELECT pg_advisory_xact_lock(730003)""")
            cursor = await connection.execute(
                """
                UPDATE accounts SET role_name = 'member', updated_at = now()
                WHERE id = %(account_id)s AND role_name = 'officer'
                    AND (membership_state <> 'active' OR (
                        SELECT count(*) FROM accounts
                        WHERE membership_state = 'active' AND role_name IN ('officer', 'guild_master')
                    ) > 1)
                RETURNING id, username, display_name, membership_state, role_name, timezone
                """,
                {"account_id": account_id},
            )
            cursor.row_factory = class_row(Account)
            account = await cursor.fetchone()
        return account

    async def pass_guild_master(self, actor_id: int, account_id: int) -> Account | None:
        if actor_id == account_id:
            return None
        async with self.database.transaction() as connection:
            await connection.execute("""SELECT pg_advisory_xact_lock(730003)""")
            cursor = await connection.execute(
                """
                SELECT id, role_name, membership_state FROM accounts
                WHERE id = ANY(%(account_ids)s) ORDER BY id FOR UPDATE
                """,
                {"account_ids": [actor_id, account_id]},
            )
            cursor.row_factory = class_row(AccountState)
            locked = {account.id: account for account in await cursor.fetchall()}
            actor = locked.get(actor_id)
            if (
                actor is None
                or actor.role_name != "guild_master"
                or actor.membership_state != "active"
            ):
                raise GuildMasterChangedError
            target = locked.get(account_id)
            if target is None or target.membership_state != "active":
                return None
            # Both writes and the current-GM check share this transaction.
            # Demote first to satisfy the unique index; a failure rolls both back.
            await connection.execute(
                """
                UPDATE accounts SET role_name = 'officer', updated_at = now()
                WHERE id = %(actor_id)s
                """,
                {"actor_id": actor_id},
            )
            cursor = await connection.execute(
                """
                UPDATE accounts SET role_name = 'guild_master', updated_at = now()
                WHERE id = %(account_id)s
                RETURNING id, username, display_name, membership_state, role_name, timezone
                """,
                {"account_id": account_id},
            )
            cursor.row_factory = class_row(Account)
            account = await cursor.fetchone()
        return account
