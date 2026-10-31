"""Database connectivity and migration readiness queries."""

from bluddit_api.database import Database
from bluddit_api.migrate import pending_migrations


class HealthRepository:
    def __init__(self, database: Database):
        self.database = database

    async def is_ready(self, migrations) -> bool:
        async with self.database.transaction() as connection:
            await connection.execute("""SELECT 1""")
            return not await pending_migrations(connection, migrations)
