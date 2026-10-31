"""Shared authentication configuration, throttling, cookies, and dependencies."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import os
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response

from bluddit_api.models.accounts import Account
from bluddit_api.utils.dependencies import AuthRepositoryDep
from bluddit_api.utils.security import token_hash

ACCESS_SECONDS = 600
REFRESH_SECONDS = 30 * 24 * 60 * 60
COOKIE_NAME = "bluddit_refresh"
TOKEN_PATH = "/api/auth/token"


@dataclass(frozen=True)
class AuthSettings:
    origins: frozenset[str]
    secure: bool

    @classmethod
    def from_env(cls, environment: str):
        origins = frozenset(
            filter(
                None,
                (
                    value.strip()
                    for value in os.environ.get("AUTH_ALLOWED_ORIGINS", "").split(",")
                ),
            )
        )
        if environment == "production" and not origins:
            raise RuntimeError("Set AUTH_ALLOWED_ORIGINS in production")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or (environment == "production" and parsed.scheme != "https")
            ):
                raise RuntimeError(
                    "AUTH_ALLOWED_ORIGINS must contain exact origins (HTTPS in production)"
                )
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
                    raise HTTPException(
                        429,
                        "Try again later",
                        headers={"Retry-After": str(max(1, math.ceil(retry)))},
                    )
                bucket = [now + 900, 0]
                self.buckets[username] = bucket
            if bucket[1] >= 10:
                raise HTTPException(
                    429,
                    "Try again later",
                    headers={"Retry-After": str(max(1, math.ceil(bucket[0] - now)))},
                )
            bucket[1] += 1


def unauthorized():
    return HTTPException(
        401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
    )


def set_refresh_cookie(response: Response, token: str, settings: AuthSettings):
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=REFRESH_SECONDS,
        expires=datetime.now(timezone.utc) + timedelta(seconds=REFRESH_SECONDS),
        path=TOKEN_PATH,
        secure=settings.secure,
        httponly=True,
        samesite="strict",
    )


async def current_account(request: Request, repository: AuthRepositoryDep) -> Account:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    hashed = token_hash(token) if scheme.lower() == "bearer" else None
    if hashed is None:
        raise unauthorized()
    account = await repository.get_account_for_hashed_access_token(hashed)
    if account is None:
        raise unauthorized()
    return account


def access_response(token: str):
    return {"access_token": token, "token_type": "Bearer", "expires_in": ACCESS_SECONDS}
