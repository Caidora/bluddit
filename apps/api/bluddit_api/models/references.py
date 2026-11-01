"""Persistence projections for public provider data."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

Kind = Literal["class", "spec", "profession", "dungeon"]


class CachedDocument(BaseModel):
    document: dict[str, Any] | None
    fetched_at: datetime | None
    expires_at: datetime | None
    retry_at: datetime | None


class CacheLease(BaseModel):
    lease_token: UUID


class ReferenceEntity(BaseModel):
    entity_kind: Kind
    reference_id: str
    blizzard_id: int | None
    payload: dict[str, Any]
    active: bool = False
