"""Server-only Blizzard OAuth and validated, leased one-hour document caching."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import wraps
import hashlib
import json
import os
import re
from pathlib import Path
import time

import httpx

from bluddit_api.repositories.references import ReferencesRepository


class ProviderUnavailable(Exception):
    def __init__(self, retry_seconds: int = 60):
        self.retry_seconds = max(1, retry_seconds)


@dataclass(frozen=True)
class BlizzardSettings:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    region: str = "us"
    locale: str = "en_US"
    namespace: str = "static-1.60.1_70399-forever-us"

    @classmethod
    def from_env(cls):
        secret = os.environ.get("BLIZZARD_CLIENT_SECRET", "")
        secret_file = os.environ.get("BLIZZARD_CLIENT_SECRET_FILE")
        if secret_file:
            if secret:
                raise RuntimeError("Set only one Blizzard secret source")
            secret = Path(secret_file).read_text().strip()
        region = os.environ.get("BLIZZARD_REGION", "us")
        namespace = os.environ.get(
            "BLIZZARD_STATIC_NAMESPACE", f"static-1.60.1_70399-forever-{region}"
        )
        locale = os.environ.get("BLIZZARD_LOCALE", "en_US")
        if region not in {"us", "eu", "kr", "tw"}:
            raise RuntimeError("Unsupported BLIZZARD_REGION")
        if not re.fullmatch(
            r"static-[0-9][A-Za-z0-9_.-]*-forever-" + region, namespace
        ):
            raise RuntimeError(
                "BLIZZARD_STATIC_NAMESPACE must be a versioned Forever namespace"
            )
        return cls(
            os.environ.get("BLIZZARD_CLIENT_ID", ""), secret, region, locale, namespace
        )

    @property
    def enabled(self):
        return bool(self.client_id and self.client_secret)


def utcnow():
    return datetime.now(timezone.utc)


def cache_document(method):
    """Cache validated public GET results; never cache OAuth or failures."""

    @wraps(method)
    async def wrapped(self, path: str, collection: str | None = None, page: int = 1):
        key = self.key("document", path, page=page)
        cached = await self.repository.cached(key)
        if cached and cached.document is not None and cached.expires_at > utcnow():
            return cached.document
        token = await self.repository.claim(key)
        if token is None:
            # Another worker owns the refresh, or a previous attempt is backing off.
            # Abort this category rather than publish an inconsistent mix of snapshots.
            raise ProviderUnavailable()
        try:
            document = await method(self, path, collection, page)
            await self.repository.finish(key, token, document)
            return document
        except asyncio.CancelledError:
            await self.repository.fail(key, token, 5)
            raise
        except Exception as error:
            await self.repository.fail(key, token, getattr(error, "retry_seconds", 60))
            raise

    return wrapped


class BlizzardClient:
    def __init__(
        self,
        settings: BlizzardSettings,
        repository: ReferencesRepository,
        http: httpx.AsyncClient,
    ):
        self.settings = settings
        self.repository = repository
        self.http = http
        self._token = None
        self._expires = 0.0
        self._token_lock = asyncio.Lock()

    def key(self, kind: str, path: str, **parameters) -> str:
        content = json.dumps(
            [
                self.settings.region,
                self.settings.namespace,
                self.settings.locale,
                path,
                parameters,
            ],
            sort_keys=True,
        )
        return kind + ":" + hashlib.sha256(content.encode()).hexdigest()

    async def access_token(self) -> str:
        async with self._token_lock:
            if self._token and time.monotonic() < self._expires:
                return self._token
            response = await self.http.post(
                "https://oauth.battle.net/token",
                auth=(self.settings.client_id, self.settings.client_secret),
                data={"grant_type": "client_credentials"},
            )
            self.check_status(response)
            body = response.json()
            token, lifetime = body.get("access_token"), body.get("expires_in")
            if (
                not isinstance(token, str)
                or not token
                or type(lifetime) is not int
                or lifetime <= 0
            ):
                raise ValueError("Invalid OAuth response")
            self._token = token
            self._expires = time.monotonic() + max(0, lifetime - 30)
            return token

    def check_status(self, response: httpx.Response):
        if response.status_code == 429 or response.status_code >= 500:
            value = response.headers.get("retry-after", "60")
            try:
                seconds = int(value)
            except ValueError:
                try:
                    seconds = int(
                        (parsedate_to_datetime(value) - utcnow()).total_seconds()
                    )
                except (ValueError, TypeError, OverflowError):
                    seconds = 60
            raise ProviderUnavailable(seconds)
        if response.status_code != 200:
            raise ProviderUnavailable()

    @cache_document
    async def document(
        self, path: str, collection: str | None = None, page: int = 1
    ) -> dict:
        if not self.settings.enabled or not path.startswith("/data/wow/"):
            raise ProviderUnavailable()
        for attempt in range(2):
            token = await self.access_token()
            response = await self.http.get(
                f"https://{self.settings.region}.api.blizzard.com{path}",
                params={
                    "namespace": self.settings.namespace,
                    "locale": self.settings.locale,
                    "_page": page,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 401 and attempt == 0:
                async with self._token_lock:
                    if self._token == token:
                        self._expires = 0
                continue
            self.check_status(response)
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Expected provider object")
            if collection is not None:
                if not isinstance(body.get(collection), list):
                    raise ValueError("Missing provider collection")
                for entry in body[collection]:
                    self.validate_identity(entry)
            else:
                self.validate_identity(body)
                self.validate_detail(path, body)
            return body
        raise ProviderUnavailable()

    @staticmethod
    def validate_identity(body):
        if (
            not isinstance(body, dict)
            or type(body.get("id")) is not int
            or body["id"] <= 0
            or not isinstance(body.get("name"), str)
            or not body["name"].strip()
        ):
            raise ValueError("Invalid provider identity")

    @staticmethod
    def validate_detail(path: str, body: dict):
        if "/playable-specialization/" in path:
            parent = body.get("playable_class")
            if (
                not isinstance(parent, dict)
                or type(parent.get("id")) is not int
                or parent["id"] <= 0
            ):
                raise ValueError("Invalid specialization parent")
        if "/profession/" in path:
            category = body.get("type")
            if category is not None and (
                not isinstance(category, dict)
                or not isinstance(category.get("type"), str)
            ):
                raise ValueError("Invalid profession type")
        if "/journal-instance/" in path:
            category = body.get("category")
            if not isinstance(category, dict) or category.get("type") not in {
                "DUNGEON",
                "RAID",
            }:
                raise ValueError("Invalid journal category")
        for level_field in ("maximum_skill_level", "minimum_level", "maximum_level"):
            value = body.get(level_field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Invalid provider level")
        low, high = body.get("minimum_level"), body.get("maximum_level")
        if low is not None and high is not None and low > high:
            raise ValueError("Invalid provider range")

    async def index(self, path: str, collection: str) -> list[dict]:
        entries = []
        seen = set()
        page = 1
        while True:
            body = await self.document(path, collection, page)
            for entry in body[collection]:
                if entry["id"] in seen:
                    raise ValueError("Duplicate provider identity")
                seen.add(entry["id"])
                entries.append(entry)
            page_count = body.get("pageCount", 1)
            if type(page_count) is not int or not 1 <= page_count <= 1000:
                raise ValueError("Invalid provider pagination")
            if page >= page_count:
                return entries
            page += 1

    async def details(self, path: str, collection: str) -> list[dict]:
        result = []
        for entry in await self.index(path + "/index", collection):
            detail = await self.document(f"{path}/{entry['id']}")
            if detail["id"] != entry["id"]:
                raise ValueError("Mismatched provider identity")
            result.append(detail)
        return result
