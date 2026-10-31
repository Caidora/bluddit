"""Interactive account bootstrap and password recovery; never accept password flags."""
import argparse
import asyncio
import getpass
import sys
import warnings

import psycopg
from psycopg_pool import PoolTimeout
from starlette.concurrency import run_in_threadpool

from bluddit_api.database import Database, DatabaseSettings
from bluddit_api.repositories.accounts import AccountRepository
from bluddit_api.utils.security import PASSWORD_HASHER, normalize_username, validate_password


async def create_first_officer(database, username: str, display_name: str, password: str):
    username = normalize_username(username)
    validate_password(password)
    display_name = display_name.strip()
    if not 1 <= len(display_name) <= 100:
        raise ValueError("Display name must contain 1–100 characters")
    encoded = await run_in_threadpool(PASSWORD_HASHER.hash, password)
    await AccountRepository(database).create_first_officer(username, display_name, encoded)


async def reset_password(database, username: str, password: str):
    username = normalize_username(username)
    validate_password(password)
    encoded = await run_in_threadpool(PASSWORD_HASHER.hash, password)
    await AccountRepository(database).reset_password(username, encoded)


async def run(args, password):
    database = Database(DatabaseSettings.from_env(required=True))
    try:
        await database.pool.open(wait=True)
        if args.command == "create-first-officer":
            await create_first_officer(database, args.username, args.display_name, password)
        else:
            await reset_password(database, args.username, password)
    finally:
        await database.pool.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-first-officer")
    create.add_argument("--username", required=True)
    create.add_argument("--display-name", required=True)
    reset = commands.add_parser("reset-password")
    reset.add_argument("--username", required=True)
    args = parser.parse_args()
    try:
        # Refuse getpass's fallback to an echoed prompt when no terminal exists.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New password: ")
            confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise ValueError("Passwords do not match")
        validate_password(password)
        asyncio.run(run(args, password))
    except (ValueError, RuntimeError, psycopg.Error, PoolTimeout, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("Account operation failed; check input, account state, and database availability.", file=sys.stderr)
        return 1
    print("Account operation completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
