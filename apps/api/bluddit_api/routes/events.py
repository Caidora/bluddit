"""Member-created activities and explicitly assigned event management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from bluddit_api.models.accounts import Account
from bluddit_api.models.bluds import Choice
from bluddit_api.models.events import (
    EventCreate,
    EventFilter,
    EventList,
    EventPatch,
    EventRecord,
    EventReferences,
    OrganizerInput,
    ScheduleInput,
    SchedulePreview,
)
from bluddit_api.repositories.events import (
    EventCancelled,
    EventForbidden,
    InvalidOrganizers,
)
from bluddit_api.utils.authorization import require_permission
from bluddit_api.utils.dependencies import EventsRepositoryDep, ReferencesDep
from bluddit_api.utils.event_times import TIMEZONES, preview_start, resolve_start
from bluddit_api.utils.permissions import Permission, RolePolicy

router = APIRouter(prefix="/api/events", tags=["events"])
Reader = Annotated[Account, Depends(require_permission(Permission.GUILD_READ))]
Creator = Annotated[Account, Depends(require_permission(Permission.EVENTS_CREATE))]
Manager = Annotated[Account, Depends(require_permission(Permission.EVENTS_MANAGE))]
Officer = Annotated[
    Account, Depends(require_permission(Permission.SHARED_RECORDS_CORRECT))
]
EventId = Annotated[int, Path(gt=0)]
ACTIVITIES = [
    Choice(id=key, name=name)
    for key, name in [
        ("dungeon", "Dungeon"),
        ("leveling", "Leveling"),
        ("questing", "Questing"),
        ("pvp", "PvP"),
        ("guild_meeting", "Guild meeting"),
        ("other", "Other"),
    ]
]


def validate_destination(body: EventCreate | EventPatch, references, current=None):
    active_ids = {d.id for d in references.dungeons if d.active}
    unchanged = current is not None and body.dungeon_id == current.dungeon_id
    if (
        body.dungeon_id is not None
        and body.dungeon_id not in active_ids
        and not unchanged
    ):
        raise HTTPException(422, "Choose a valid dungeon destination")


@router.get("/reference-data")
async def references(actor: Reader, catalog: ReferencesDep) -> EventReferences:
    return EventReferences(
        refreshing=catalog.refreshing,
        activities=ACTIVITIES,
        dungeons=[
            Choice(id=d.id, name=d.name, active=d.active) for d in catalog.dungeons
        ],
        timezones=TIMEZONES,
    )


@router.post("/preview-start")
async def preview(body: ScheduleInput, actor: Creator) -> SchedulePreview:
    return preview_start(body)


@router.get("")
async def list_events(
    filters: Annotated[EventFilter, Query()],
    actor: Reader,
    repository: EventsRepositoryDep,
) -> EventList:
    records = await repository.list_events(filters, actor.id)
    return EventList(
        events=records[: filters.limit],
        limit=filters.limit,
        offset=filters.offset,
        has_more=len(records) > filters.limit,
    )


@router.post("", status_code=201)
async def create(
    body: EventCreate,
    actor: Creator,
    repository: EventsRepositoryDep,
    references: ReferencesDep,
) -> EventRecord:
    validate_destination(body, references)
    return await repository.create(body, resolve_start(body), actor.id)


@router.get("/{event_id}")
async def detail(
    event_id: EventId, actor: Reader, repository: EventsRepositoryDep
) -> EventRecord:
    record = await repository.get(event_id)
    if record is None:
        raise HTTPException(404, "Event not found")
    return record


async def manage(repository, event_id, actor, **operation) -> EventRecord:
    try:
        record = await repository.manage(
            event_id,
            actor.id,
            RolePolicy.allows(actor, Permission.SHARED_RECORDS_CORRECT),
            **operation,
        )
    except EventForbidden:
        raise HTTPException(
            403, "Only assigned organizers or officers may manage this event"
        ) from None
    except EventCancelled:
        raise HTTPException(409, "Cancelled events cannot be changed") from None
    except InvalidOrganizers:
        raise HTTPException(
            422, "Choose at least one organizer; all must be active members"
        ) from None
    if record is None:
        raise HTTPException(404, "Event not found")
    return record


@router.patch("/{event_id}")
async def update(
    event_id: EventId,
    body: EventPatch,
    actor: Manager,
    repository: EventsRepositoryDep,
    references: ReferencesDep,
) -> EventRecord:
    current = await repository.get(event_id)
    if current is None:
        raise HTTPException(404, "Event not found")
    validate_destination(body, references, current)
    starts_at = None
    if "local_start" in body.model_fields_set:
        starts_at = resolve_start(
            ScheduleInput(
                local_start=body.local_start,
                scheduling_timezone=body.scheduling_timezone,
                occurrence=body.occurrence,
            )
        )
    return await manage(repository, event_id, actor, patch=body, starts_at=starts_at)


@router.post("/{event_id}/cancel")
async def cancel(
    event_id: EventId, actor: Manager, repository: EventsRepositoryDep
) -> EventRecord:
    return await manage(repository, event_id, actor, cancel=True)


@router.put("/{event_id}/organizers")
async def organizers(
    event_id: EventId,
    body: OrganizerInput,
    actor: Officer,
    repository: EventsRepositoryDep,
) -> EventRecord:
    return await manage(repository, event_id, actor, organizer_ids=body.account_ids)
