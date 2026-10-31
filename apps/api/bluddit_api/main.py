from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import psycopg
from psycopg_pool import PoolTimeout

from bluddit_api.database import Database, DatabaseSettings
from bluddit_api.migrate import load_migrations
from bluddit_api.routes.auth import router as auth_router
from bluddit_api.routes.health import router as health_router
from bluddit_api.utils.auth import AuthSettings, LoginThrottle


def create_app() -> FastAPI:
    environment = os.environ.get("APP_ENV", "development")
    if environment not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV must be development, test, or production")
    settings = DatabaseSettings.from_env(required=environment == "production")
    auth_settings = AuthSettings.from_env(environment)
    migrations = load_migrations()

    @asynccontextmanager
    async def lifespan(app):
        database = Database(settings) if settings else None
        app.state.database = database
        if database:
            # Don't wait for connectivity: liveness remains available during DB outages.
            await database.pool.open(wait=False)
        try:
            yield
        finally:
            if database:
                await database.pool.close()

    app = FastAPI(title="Bluddit API", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.migrations = migrations
    app.state.auth_settings = auth_settings
    app.state.login_throttle = LoginThrottle()
    app.state.password_slots = asyncio.Semaphore(2)
    app.include_router(auth_router)
    app.include_router(health_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # FastAPI's default validation response includes rejected credential values.
        return JSONResponse(status_code=422, content={"detail": "Invalid request input"})

    @app.middleware("http")
    async def protect_requests(request: Request, call_next):
        response = None
        if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            if (request.headers.get("origin") not in auth_settings.origins
                    or request.headers.get("x-csrf-protection") != "1"):
                response = JSONResponse(status_code=403, content={"detail": "Request origin or CSRF header rejected"})
        if response is None and request.url.path == "/api/auth/login" and request.method == "POST":
            if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                response = JSONResponse(status_code=415, content={"detail": "JSON required"})
            elif request.method == "POST":
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 8192:
                        response = JSONResponse(status_code=413, content={"detail": "Request too large"})
                        break
                if response is None:
                    request._body = bytes(body)
        if response is None:
            try:
                response = await call_next(request)
            except (psycopg.Error, PoolTimeout):
                response = JSONResponse(status_code=503, content={"detail": "Database unavailable"})
        if request.url.path.startswith("/api/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
