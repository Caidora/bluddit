"""Opaque bearer access tokens and cookie-bound rotating refresh sessions."""
import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import os
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from psycopg.rows import dict_row
from starlette.concurrency import run_in_threadpool

from bluddit_api.database import Database, get_database
from bluddit_api.security import (
    ACTIVE, DUMMY_HASH, new_token, normalize_username,
    token_hash, verify_password,
)

ACCESS_SECONDS = 600
REFRESH_SECONDS = 30 * 24 * 60 * 60
COOKIE_NAME = "bluddit_refresh"
TOKEN_PATH = "/api/auth/token"
router = APIRouter(prefix="/api/auth")


@dataclass(frozen=True)
class AuthSettings:
    origins: frozenset[str]
    secure: bool

    @classmethod
    def from_env(cls, environment: str):
        origins = frozenset(filter(None, (
            value.strip() for value in os.environ.get("AUTH_ALLOWED_ORIGINS", "").split(",")
        )))
        if environment == "production" and not origins:
            raise RuntimeError("Set AUTH_ALLOWED_ORIGINS in production")
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                    or parsed.username is not None or parsed.password is not None
                    or parsed.path or parsed.query or parsed.fragment
                    or (environment == "production" and parsed.scheme != "https")):
                raise RuntimeError("AUTH_ALLOWED_ORIGINS must contain exact origins (HTTPS in production)")
        return cls(origins, environment == "production")


class LoginThrottle:
    """Process-local fixed windows; never evict an unexpired bucket to admit a key."""
    def __init__(self, *, capacity=10000, clock=time.monotonic):
        self.buckets = OrderedDict()
        self.capacity = capacity
        self.clock = clock
        self.lock = asyncio.Lock()

    async def reserve(self, username: str):
        async with self.lock:
            now = self.clock()
            while self.buckets and next(iter(self.buckets.values()))[0] <= now:
                self.buckets.popitem(last=False)
            bucket = self.buckets.get(username)
            if bucket is None:
                if len(self.buckets) >= self.capacity:
                    retry = next(iter(self.buckets.values()))[0] - now
                    raise HTTPException(429, "Try again later", headers={"Retry-After": str(max(1, math.ceil(retry)))})
                bucket = [now + 900, 0]
                self.buckets[username] = bucket
            if bucket[1] >= 10:
                raise HTTPException(429, "Try again later", headers={"Retry-After": str(max(1, math.ceil(bucket[0] - now)))})
            bucket[1] += 1


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(max_length=256)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def username_format(cls, value):
        return normalize_username(value)


def unauthorized():
    return HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})


def set_refresh_cookie(response: Response, token: str, settings: AuthSettings):
    response.set_cookie(
        COOKIE_NAME, token, max_age=REFRESH_SECONDS,
        expires=datetime.now(timezone.utc) + timedelta(seconds=REFRESH_SECONDS),
        path=TOKEN_PATH, secure=settings.secure, httponly=True, samesite="strict",
    )


async def issue_access(connection, account_id: int, refresh_id: int):
    token = new_token()
    await connection.execute(
        "INSERT INTO sessions (token_hash, account_id, refresh_session_id, expires_at) "
        "VALUES (%s, %s, %s, now() + interval '10 minutes')",
        (token_hash(token), account_id, refresh_id),
    )
    return {"access_token": token, "token_type": "Bearer", "expires_in": ACCESS_SECONDS}


async def current_account(request: Request, database: Database = Depends(get_database)):
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    hashed = token_hash(token) if scheme.lower() == "bearer" else None
    if hashed is None:
        raise unauthorized()
    async with database.transaction() as connection:
        cursor = await connection.execute(
            "SELECT a.id, a.username, a.display_name, a.membership_state, a.role_name, a.timezone "
            "FROM sessions s JOIN refresh_sessions r ON r.id = s.refresh_session_id "
            "JOIN accounts a ON a.id = s.account_id AND a.id = r.account_id "
            "WHERE s.token_hash = %s AND s.expires_at > now() AND s.revoked_at IS NULL "
            "AND r.expires_at > now() AND r.revoked_at IS NULL AND a.membership_state = %s",
            (hashed, ACTIVE),
        )
        cursor.row_factory = dict_row
        account = await cursor.fetchone()
    if account is None:
        raise unauthorized()
    return account


@router.post("/login")
async def login(body: LoginInput, request: Request, response: Response,
                database: Database = Depends(get_database)):
    await request.app.state.login_throttle.reserve(body.username)
    async with database.transaction() as connection:
        cursor = await connection.execute(
            "SELECT id, password_hash, membership_state FROM accounts WHERE lower(username) = %s",
            (body.username,),
        )
        cursor.row_factory = dict_row
        account = await cursor.fetchone()
    # Bound memory-intensive password work even across many different usernames.
    async with request.app.state.password_slots:
        valid = await run_in_threadpool(
            verify_password, account["password_hash"] if account else DUMMY_HASH,
            body.password.get_secret_value(),
        )
    if not valid or account is None or account["membership_state"] != ACTIVE:
        raise HTTPException(401, "Invalid username or password")
    refresh = new_token()
    async with database.transaction() as connection:
        # Coordinate login/reset and recheck credentials after the costly verification.
        cursor = await connection.execute(
            "SELECT id FROM accounts WHERE id = %s AND membership_state = %s "
            "AND password_hash = %s FOR UPDATE",
            (account["id"], ACTIVE, account["password_hash"]),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(401, "Invalid username or password")
        cursor = await connection.execute(
            "INSERT INTO refresh_sessions (account_id, token_hash, expires_at) "
            "VALUES (%s, %s, now() + interval '30 days') RETURNING id",
            (account["id"], token_hash(refresh)),
        )
        refresh_id = (await cursor.fetchone())[0]
        result = await issue_access(connection, account["id"], refresh_id)
    set_refresh_cookie(response, refresh, request.app.state.auth_settings)
    return result


@router.post("/token")
async def refresh(request: Request, response: Response, database: Database = Depends(get_database)):
    hashed = token_hash(request.cookies.get(COOKIE_NAME))
    if hashed is None:
        raise unauthorized()
    replacement = new_token()
    async with database.transaction() as connection:
        # UPDATE rechecks its predicate after a concurrent updater commits.
        cursor = await connection.execute(
            "UPDATE refresh_sessions r SET token_hash = %s, expires_at = now() + interval '30 days' "
            "WHERE r.token_hash = %s AND r.expires_at > now() AND r.revoked_at IS NULL "
            "AND EXISTS (SELECT 1 FROM accounts a WHERE a.id = r.account_id AND a.membership_state = %s) "
            "RETURNING r.id, r.account_id",
            (token_hash(replacement), hashed, ACTIVE),
        )
        session = await cursor.fetchone()
        if session is None:
            raise unauthorized()
        result = await issue_access(connection, session[1], session[0])
    set_refresh_cookie(response, replacement, request.app.state.auth_settings)
    return result


@router.delete("/token", status_code=204)
async def logout(request: Request, database: Database = Depends(get_database)):
    hashed = token_hash(request.cookies.get(COOKIE_NAME))
    if hashed is not None:
        async with database.transaction() as connection:
            await connection.execute(
                "UPDATE refresh_sessions SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
                (hashed,),
            )
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path=TOKEN_PATH, secure=request.app.state.auth_settings.secure,
                           httponly=True, samesite="strict")
    return response


@router.get("/me")
async def me(account=Depends(current_account)):
    return account
