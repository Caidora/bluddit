from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import psycopg
from psycopg_pool import PoolTimeout

from bluddit_api.database import Database, DatabaseSettings
from bluddit_api.migrate import MigrationError, load_migrations, pending_migrations


def create_app() -> FastAPI:
    environment = os.environ.get("APP_ENV", "development")
    if environment not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV must be development, test, or production")
    settings = DatabaseSettings.from_env(required=environment == "production")
    migrations = load_migrations()

    @asynccontextmanager
    async def lifespan(app):
        database = Database(settings) if settings else None
        app.state.database = database
        if database:
            # Don't wait for connectivity: liveness remains available during DB outages.
            database.pool.open(wait=False)
        try:
            yield
        finally:
            if database:
                database.pool.close()

    app = FastAPI(title="Bluddit API", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/ready")
    def ready():
        database = app.state.database
        if database:
            try:
                with database.transaction() as connection:
                    connection.execute("SELECT 1")
                    if not pending_migrations(connection, migrations):
                        return {"status": "ok"}
            except (psycopg.Error, PoolTimeout, MigrationError):
                pass
        return JSONResponse(status_code=503, content={"status": "unavailable"})

    return app
