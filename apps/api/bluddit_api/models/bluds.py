"""Bluds contracts and typed game references. Ownership is never writable."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DungeonStatus = Literal["not_completed", "completed", "completed_rerun"]


class Choice(BaseModel):
    id: str
    name: str
    active: bool = True


class ClassReference(Choice):
    specs: list[Choice]


class ProfessionReference(Choice):
    category: Literal["primary", "secondary"] | None = None
    max_level: int | None = None


class DungeonReference(Choice):
    location: str | None = None
    suggested_level_min: int | None = None
    suggested_level_max: int | None = None
    guide_url: str | None = None
    quest_guide_url: str | None = None
    source_urls: list[str] = Field(default_factory=list)


class ReferenceSource(BaseModel):
    label: str
    url: str


class BludReferenceData(BaseModel):
    version: str
    refreshing: bool = False
    fetched_at: dict[str, datetime | None] = Field(default_factory=dict)
    sources: list[ReferenceSource]
    classes: list[ClassReference]
    professions: list[ProfessionReference]
    dungeons: list[DungeonReference]
    dungeon_statuses: list[Choice]
    max_primary_professions: int


class BludInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfessionInput(BludInput):
    profession_id: str
    level: int | None = Field(default=None, ge=0, strict=True)


class DungeonInput(BludInput):
    dungeon_id: str
    status: DungeonStatus


class BludCreate(BludInput):
    name: str = Field(min_length=1, max_length=100)
    class_id: str
    character_created_on: date
    spec_id: str | None = None


class BludPatch(BludInput):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    class_id: str | None = None
    character_created_on: date | None = None
    spec_id: str | None = None
    archived: bool | None = Field(default=None, strict=True)
    professions: list[ProfessionInput] | None = None
    dungeons: list[DungeonInput] | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        nullable = {"spec_id"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class BludFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(default="", max_length=200)
    mine: bool = False
    archived: bool = False
    class_id: str | None = None
    profession_id: str | None = None
    dungeon_id: str | None = None
    dungeon_status: DungeonStatus = "not_completed"
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class BludProfession(ProfessionInput):
    updated_at: datetime


class BludDungeon(DungeonInput):
    updated_at: datetime


class BludRecord(BaseModel):
    blud_id: int
    account_id: int
    owner_name: str
    name: str
    class_id: str
    spec_id: str | None
    character_created_on: date
    archived: bool
    created_at: datetime
    updated_at: datetime
    updated_by_account_id: int
    professions: list[BludProfession]
    dungeons: list[BludDungeon]


class BludResponse(BludRecord):
    completed_dungeons: int
    rerun_dungeons: int
    total_dungeons: int


class BludListResponse(BaseModel):
    bluds: list[BludResponse]
    limit: int
    offset: int
    has_more: bool
