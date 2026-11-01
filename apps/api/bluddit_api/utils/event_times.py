"""Resolve wall times without silently moving DST gaps or choosing a fold."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from fastapi import HTTPException

from bluddit_api.models.events import ScheduleInput, SchedulePreview, StartCandidate

TIMEZONES = sorted(available_timezones() - {"localtime", "Factory"})


def preview_start(body: ScheduleInput) -> SchedulePreview:
    if body.scheduling_timezone not in TIMEZONES:
        raise HTTPException(422, "Choose a supported named timezone")
    try:
        zone = ZoneInfo(body.scheduling_timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "Choose a supported named timezone") from None
    instants: dict[datetime, str] = {}
    for fold in (0, 1):
        local = body.local_start.replace(tzinfo=zone, fold=fold)
        try:
            instant = local.astimezone(UTC)
            round_trip = instant.astimezone(zone).replace(tzinfo=None)
        except (OverflowError, ValueError):
            raise HTTPException(
                422, "Choose a start time within the supported date range"
            ) from None
        if round_trip == body.local_start:
            offset = local.strftime("%z")
            instants[instant] = f"{offset[:3]}:{offset[3:]}"
    candidates = [
        StartCandidate(
            starts_at=instant,
            utc_offset=instants[instant],
            occurrence="earlier" if index == 0 else "later",
        )
        for index, instant in enumerate(sorted(instants))
    ]
    return SchedulePreview(
        status="nonexistent"
        if not candidates
        else "ambiguous"
        if len(candidates) == 2
        else "valid",
        candidates=candidates,
    )


def resolve_start(body: ScheduleInput) -> datetime:
    preview = preview_start(body)
    if preview.status == "nonexistent":
        raise HTTPException(
            422,
            "This local time does not exist because the clocks move forward. Choose another time.",
        )
    if preview.status == "ambiguous":
        if body.occurrence is None:
            raise HTTPException(
                422, "This time occurs twice. Choose the earlier or later occurrence."
            )
        return next(
            c.starts_at for c in preview.candidates if c.occurrence == body.occurrence
        )
    return preview.candidates[0].starts_at
