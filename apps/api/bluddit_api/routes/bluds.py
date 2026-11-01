"""Guild Bluds directory, member-owned progress and explicit officer corrections."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from bluddit_api.data.bluds import (
    CLASS_BY_ID,
    DUNGEON_IDS,
    PROFESSION_BY_ID,
    REFERENCES,
    ZONE_IDS,
)
from bluddit_api.models.accounts import Account
from bluddit_api.models.bluds import (
    BludCreate,
    BludFilter,
    BludListResponse,
    BludPatch,
    BludRecord,
    BludReferenceData,
    BludResponse,
)
from bluddit_api.utils.authorization import require_permission
from bluddit_api.utils.dependencies import BludsRepositoryDep
from bluddit_api.utils.permissions import Permission, RolePolicy

router = APIRouter(prefix="/api/bluds", tags=["bluds"])
Reader = Annotated[Account, Depends(require_permission(Permission.BLUDS_VIEW))]
Creator = Annotated[Account, Depends(require_permission(Permission.BLUDS_EDIT_OWN))]
BludId = Annotated[int, Path(gt=0)]


def present(record: BludRecord) -> BludResponse:
    current = [d for d in record.dungeons if d.dungeon_id in DUNGEON_IDS]
    return BludResponse(
        **record.model_dump(),
        completed_dungeons=sum(d.status != "not_completed" for d in current),
        rerun_dungeons=sum(d.status == "completed_rerun" for d in current),
        total_dungeons=len(DUNGEON_IDS),
    )


def validate_values(body: BludCreate | BludPatch, current: BludRecord | None = None):
    class_id = (
        body.class_id if "class_id" in body.model_fields_set else current.class_id
    )
    spec_id = (
        body.spec_id
        if "spec_id" in body.model_fields_set or current is None
        else current.spec_id
    )
    reference = CLASS_BY_ID.get(class_id)
    if reference is None:
        raise HTTPException(422, "Choose a valid class")
    if spec_id is not None and spec_id not in {s.id for s in reference.specs}:
        raise HTTPException(422, "Choose a spec belonging to this class")
    if body.farming_zone_id is not None and body.farming_zone_id not in ZONE_IDS:
        raise HTTPException(422, "Choose a valid farming zone")
    if isinstance(body, BludPatch) and body.professions is not None:
        ids = [p.profession_id for p in body.professions]
        if len(ids) != len(set(ids)) or any(p not in PROFESSION_BY_ID for p in ids):
            raise HTTPException(422, "Choose valid professions without duplicates")
        if (
            sum(PROFESSION_BY_ID[p].category == "primary" for p in ids)
            > REFERENCES.max_primary_professions
        ):
            raise HTTPException(422, "Choose at most two primary professions")
        for profession in body.professions:
            if (
                profession.level is not None
                and profession.level
                > PROFESSION_BY_ID[profession.profession_id].max_level
            ):
                raise HTTPException(422, "Profession level exceeds its skill limit")
    if isinstance(body, BludPatch) and body.dungeons is not None:
        ids = [d.dungeon_id for d in body.dungeons]
        if len(ids) != len(set(ids)) or any(d not in DUNGEON_IDS for d in ids):
            raise HTTPException(422, "Choose valid dungeons without duplicates")


@router.get("/reference-data")
async def reference_data(actor: Reader) -> BludReferenceData:
    return REFERENCES


@router.get("")
async def list_bluds(
    filters: Annotated[BludFilter, Query()],
    actor: Reader,
    repository: BludsRepositoryDep,
) -> BludListResponse:
    for value, allowed in [
        (filters.class_id, CLASS_BY_ID),
        (filters.profession_id, PROFESSION_BY_ID),
        (filters.farming_zone_id, ZONE_IDS),
        (filters.dungeon_id, DUNGEON_IDS),
    ]:
        if value is not None and value not in allowed:
            raise HTTPException(422, "Unknown Bluds filter")
    records = await repository.list_bluds(filters, actor.id)
    return BludListResponse(
        bluds=[present(record) for record in records[: filters.limit]],
        limit=filters.limit,
        offset=filters.offset,
        has_more=len(records) > filters.limit,
    )


@router.post("", status_code=201)
async def create_blud(
    body: BludCreate, actor: Creator, repository: BludsRepositoryDep
) -> BludResponse:
    validate_values(body)
    return present(await repository.create(body, actor.id))


@router.get("/{blud_id}")
async def get_blud(
    blud_id: BludId, actor: Reader, repository: BludsRepositoryDep
) -> BludResponse:
    record = await repository.get(blud_id)
    if record is None:
        raise HTTPException(404, "Blud not found")
    return present(record)


@router.patch("/{blud_id}")
async def update_blud(
    blud_id: BludId, body: BludPatch, actor: Reader, repository: BludsRepositoryDep
) -> BludResponse:
    current = await repository.get(blud_id)
    if current is None:
        raise HTTPException(404, "Blud not found")
    can_correct = RolePolicy.allows(actor, Permission.SHARED_RECORDS_CORRECT)
    own = actor.id == current.account_id and RolePolicy.allows(
        actor, Permission.BLUDS_EDIT_OWN
    )
    if not own and not can_correct:
        raise HTTPException(403, "Only the owner or an officer may update this Blud")
    validate_values(body, current)
    if not body.model_fields_set:
        return present(current)
    record = await repository.update(blud_id, body, actor.id, can_correct)
    if record is None:
        raise HTTPException(404, "Blud not found")
    return present(record)
