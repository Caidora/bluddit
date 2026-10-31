"""Forward-only SQL migrations: python -m bluddit_api.migrate status|apply."""

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys

import psycopg

from bluddit_api.database import DatabaseSettings

MIGRATIONS = Path(__file__).with_name("migrations")
LOCK_ID = 727518902


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    filename: str
    checksum: str
    sql: str


def load_migrations(directory: Path = MIGRATIONS) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = re.fullmatch(r"(\d{4})_[a-z0-9_]+\.sql", path.name)
        if not match:
            raise MigrationError("Migration names must be NNNN_description.sql")
        content = path.read_bytes()
        migrations.append(
            Migration(
                int(match[1]),
                path.name,
                hashlib.sha256(content).hexdigest(),
                content.decode(),
            )
        )
    if not migrations or [m.version for m in migrations] != list(
        range(1, len(migrations) + 1)
    ):
        raise MigrationError("Migrations must be consecutively numbered from 0001")
    return migrations


async def pending_migrations(
    connection, migrations: list[Migration]
) -> list[Migration]:
    cursor = await connection.execute("SELECT to_regclass('public.schema_migrations')")
    if (await cursor.fetchone())[0] is None:
        return migrations
    cursor = await connection.execute(
        "SELECT version, filename, checksum FROM public.schema_migrations ORDER BY version"
    )
    applied = await cursor.fetchall()
    expected = [(m.version, m.filename, m.checksum) for m in migrations]
    if applied != expected[: len(applied)]:
        raise MigrationError(
            "Migration history differs from this image; restore applied files or use a compatible release"
        )
    return migrations[len(applied) :]


async def run_migrations(
    connection, *, apply: bool = False, directory: Path = MIGRATIONS
) -> dict:
    migrations = load_migrations(directory)
    # A session lock spans all per-migration transactions, including ledger creation.
    await connection.execute(
        """SELECT pg_advisory_lock(%(lock_id)s)""", {"lock_id": LOCK_ID}
    )
    try:
        pending = await pending_migrations(connection, migrations)
        result = {"pending": [m.filename for m in pending], "applied": []}
        if apply:
            for migration in pending:
                async with connection.transaction():
                    await connection.execute("""
                        CREATE TABLE IF NOT EXISTS public.schema_migrations (
                            version integer PRIMARY KEY,
                            filename text NOT NULL,
                            checksum text NOT NULL,
                            applied_at timestamptz NOT NULL DEFAULT now()
                        )
                    """)
                    await connection.execute(migration.sql)
                    await connection.execute(
                        """
                        INSERT INTO public.schema_migrations (version, filename, checksum)
                        VALUES (%(version)s, %(filename)s, %(checksum)s)
                        """,
                        {
                            "version": migration.version,
                            "filename": migration.filename,
                            "checksum": migration.checksum,
                        },
                    )
                result["applied"].append(migration.filename)
            result["pending"] = []
        return result
    finally:
        await connection.execute(
            """SELECT pg_advisory_unlock(%(lock_id)s)""", {"lock_id": LOCK_ID}
        )


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "apply"))
    args = parser.parse_args()
    try:
        settings = DatabaseSettings.from_env(required=True)
        # Migrations may take longer than ordinary API queries; keep lock waits bounded.
        parameters = {
            **settings.parameters,
            "options": "-c lock_timeout=30000 -c statement_timeout=300000",
        }
        async with await psycopg.AsyncConnection.connect(
            **parameters, autocommit=True
        ) as connection:
            print(
                json.dumps(
                    await run_migrations(connection, apply=args.command == "apply")
                )
            )
    except (RuntimeError, psycopg.Error, OSError, UnicodeError) as error:
        message = (
            str(error)
            if isinstance(error, RuntimeError)
            else "Database migration failed; inspect private database logs"
        )
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
