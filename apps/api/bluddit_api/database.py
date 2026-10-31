"""Shared connections. Callers own a short, explicit transaction per operation."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import os
from pathlib import Path

from fastapi import HTTPException, Request
from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class DatabaseSettings:
    parameters: dict = field(repr=False)

    @classmethod
    def from_env(cls, *, required: bool = False):
        if not os.environ.get("PGHOST"):
            if required:
                raise RuntimeError("Set PGHOST, PGDATABASE, PGUSER and PGPASSWORD or PGPASSWORD_FILE")
            return None
        if not all(os.environ.get(key) for key in ("PGDATABASE", "PGUSER")):
            raise RuntimeError("Set PGDATABASE and PGUSER")
        password = os.environ.get("PGPASSWORD")
        password_file = os.environ.get("PGPASSWORD_FILE")
        if password and password_file:
            raise RuntimeError("Set only one of PGPASSWORD and PGPASSWORD_FILE")
        if password_file:
            try:
                password = Path(password_file).read_text()
            except OSError:
                raise RuntimeError("Cannot read PGPASSWORD_FILE") from None
        if not password:
            raise RuntimeError("Set PGPASSWORD or PGPASSWORD_FILE")
        try:
            port = int(os.environ.get("PGPORT", "5432"))
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            raise RuntimeError("PGPORT must be a port number") from None
        return cls(dict(host=os.environ["PGHOST"], port=port,
                        dbname=os.environ["PGDATABASE"], user=os.environ["PGUSER"],
                        password=password, connect_timeout=3, options="-c statement_timeout=3000"))


class Database:
    def __init__(self, settings: DatabaseSettings):
        self.pool = ConnectionPool(conninfo="", kwargs={**settings.parameters, "autocommit": True},
                                   min_size=1, max_size=5, timeout=3, open=False,
                                   check=ConnectionPool.check_connection)

    @contextmanager
    def transaction(self):
        with self.pool.connection() as connection:
            with connection.transaction():
                yield connection


def get_database(request: Request) -> Database:
    database = request.app.state.database
    if database is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return database
