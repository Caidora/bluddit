"""DST resolution and scheduling input validation independent of the database."""

from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import ValidationError
import pytest

from bluddit_api.models.events import (
    EventCreate,
    EventPatch,
    OrganizerInput,
    ScheduleInput,
)
from bluddit_api.utils.event_times import preview_start, resolve_start


def schedule(zone, local, occurrence=None):
    return ScheduleInput(
        local_start=local, scheduling_timezone=zone, occurrence=occurrence
    )


@pytest.mark.parametrize(
    "zone,local",
    [
        ("Pacific/Auckland", "2026-09-27T02:30:00"),
        ("Australia/Sydney", "2026-10-04T02:30:00"),
    ],
)
def test_dst_gaps_are_not_shifted(zone, local):
    body = schedule(zone, local)
    assert preview_start(body).status == "nonexistent"
    with pytest.raises(HTTPException, match="does not exist"):
        resolve_start(body)


@pytest.mark.parametrize(
    "zone,earlier,later",
    [
        ("Pacific/Auckland", "2026-04-04T13:30:00+00:00", "2026-04-04T14:30:00+00:00"),
        ("Australia/Sydney", "2026-04-04T15:30:00+00:00", "2026-04-04T16:30:00+00:00"),
    ],
)
def test_repeated_times_require_explicit_choice(zone, earlier, later):
    body = schedule(zone, "2026-04-05T02:30:00")
    preview = preview_start(body)
    assert preview.status == "ambiguous"
    assert len(preview.candidates) == 2
    with pytest.raises(HTTPException, match="occurs twice"):
        resolve_start(body)
    assert resolve_start(
        schedule(zone, "2026-04-05T02:30:00", "earlier")
    ) == datetime.fromisoformat(earlier)
    assert resolve_start(
        schedule(zone, "2026-04-05T02:30:00", "later")
    ) == datetime.fromisoformat(later)


@pytest.mark.parametrize("local", ["2026-04-05T02:30:00", "2026-10-04T02:30:00"])
def test_perth_does_not_change_clocks(local):
    preview = preview_start(schedule("Australia/Perth", local))
    assert preview.status == "valid"
    assert preview.candidates[0].utc_offset == "+08:00"


def test_date_rollover_and_utc():
    assert resolve_start(
        schedule("Pacific/Auckland", "2026-11-01T00:30:00")
    ) == datetime(2026, 10, 31, 11, 30, tzinfo=UTC)
    assert resolve_start(schedule("UTC", "2026-11-01T00:30:00")) == datetime(
        2026, 11, 1, 0, 30, tzinfo=UTC
    )


def test_invalid_zone_and_offset_input():
    with pytest.raises(HTTPException):
        preview_start(schedule("Unknown/Somewhere", "2026-11-01T00:30:00"))
    with pytest.raises(ValidationError):
        schedule("Australia/Perth", "2026-11-01T00:30:00+08:00")


@pytest.mark.parametrize(
    "body",
    [
        {"local_start": "2026-11-01T12:00"},
        {"scheduling_timezone": "UTC"},
        {"occurrence": "later"},
        {"title": None},
        {"requirements": None},
        {"capacity": 0},
        {"capacity": True},
        {"duration_minutes": -1},
        {"activity_type": "raid"},
        {"created_by_account_id": 99},
    ],
)
def test_patch_rejects_invalid_values(body):
    with pytest.raises(ValidationError):
        EventPatch.model_validate(body)


@pytest.mark.parametrize("ids", [[], [1, 1], [0], [True], ["1"]])
def test_assignment_ids_are_distinct_positive_integers(ids):
    with pytest.raises(ValidationError):
        OrganizerInput(account_ids=ids)


def test_creation_minimum_and_nullable_patch():
    body = EventCreate(
        title=" Run ",
        activity_type="other",
        local_start="2026-01-01T12:00",
        scheduling_timezone="UTC",
    )
    assert body.title == "Run"
    assert body.capacity is None and body.duration_minutes is None
    assert EventPatch(capacity=None).model_fields_set == {"capacity"}


def test_unrepresentable_utc_instant_is_validation_failure():
    with pytest.raises(HTTPException) as error:
        resolve_start(schedule("Pacific/Auckland", "0001-01-01T00:00:00"))
    assert error.value.status_code == 422
