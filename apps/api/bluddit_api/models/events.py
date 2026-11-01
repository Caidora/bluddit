"""Event scheduling input and public response contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from bluddit_api.models.bluds import Choice

Activity = Literal["dungeon", "leveling", "questing", "pvp", "guild_meeting", "other"]
Occurrence = Literal["earlier", "later"]


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ScheduleInput(EventInput):
    local_start: datetime
    scheduling_timezone: str = Field(min_length=1, max_length=100)
    occurrence: Occurrence | None = None

    @model_validator(mode="after")
    def naive_time(self):
        if self.local_start.tzinfo is not None:
            raise ValueError("Enter a local time without an offset")
        return self


class EventCreate(ScheduleInput):
    title: str = Field(min_length=1, max_length=200)
    activity_type: Activity
    dungeon_id: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=2147483647, strict=True)
    capacity: int | None = Field(default=None, gt=0, le=2147483647, strict=True)
    requirements: str = Field(default="", max_length=10000)


class EventPatch(EventInput):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    activity_type: Activity | None = None
    dungeon_id: str | None = None
    local_start: datetime | None = None
    scheduling_timezone: str | None = Field(default=None, min_length=1, max_length=100)
    occurrence: Occurrence | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=2147483647, strict=True)
    capacity: int | None = Field(default=None, gt=0, le=2147483647, strict=True)
    requirements: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def valid_patch(self):
        nullable = {"dungeon_id", "duration_minutes", "capacity", "occurrence"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        scheduling = {"local_start", "scheduling_timezone"}
        if self.model_fields_set & (scheduling | {"occurrence"}):
            if not scheduling <= self.model_fields_set:
                raise ValueError("Supply local_start and scheduling_timezone together")
            if self.local_start.tzinfo is not None:
                raise ValueError("Enter a local time without an offset")
        return self


class OrganizerInput(EventInput):
    account_ids: list[StrictInt] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_ids(self):
        if any(i <= 0 for i in self.account_ids) or len(set(self.account_ids)) != len(
            self.account_ids
        ):
            raise ValueError("Choose distinct account IDs")
        return self


class EventFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: Literal["upcoming", "past", "all"] = "upcoming"
    state: Literal["scheduled", "cancelled", "all"] = "scheduled"
    mine: bool = False
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class Organizer(BaseModel):
    account_id: int
    display_name: str
    active: bool


class EventRecord(BaseModel):
    event_id: int
    title: str
    activity_type: Activity
    dungeon_id: str | None
    starts_at: datetime
    scheduling_timezone: str
    duration_minutes: int | None
    capacity: int | None
    requirements: str
    state: Literal["scheduled", "cancelled"]
    created_by_account_id: int
    updated_by_account_id: int
    created_at: datetime
    updated_at: datetime
    organizers: list[Organizer]


class EventList(BaseModel):
    events: list[EventRecord]
    limit: int
    offset: int
    has_more: bool


class StartCandidate(BaseModel):
    starts_at: datetime
    utc_offset: str
    occurrence: Occurrence


class SchedulePreview(BaseModel):
    status: Literal["valid", "ambiguous", "nonexistent"]
    candidates: list[StartCandidate]


class EventReferences(BaseModel):
    activities: list[Choice]
    dungeons: list[Choice]
    timezones: list[str]
