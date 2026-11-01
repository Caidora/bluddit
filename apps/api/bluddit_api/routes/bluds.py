"""Guild Bluds directory, member-owned progress and explicit officer corrections."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

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
from bluddit_api.utils.dependencies import BludsRepositoryDep, ReferencesDep
from bluddit_api.utils.permissions import Permission, RolePolicy

router = APIRouter(prefix="/api/bluds", tags=["bluds"])
Reader = Annotated[Account, Depends(require_permission(Permission.BLUDS_VIEW))]
Creator = Annotated[Account, Depends(require_permission(Permission.BLUDS_EDIT_OWN))]
BludId = Annotated[int, Path(gt=0)]


def present(record: BludRecord, references: BludReferenceData) -> BludResponse:
    dungeon_ids = {d.id for d in references.dungeons if d.active}
    current = [d for d in record.dungeons if d.dungeon_id in dungeon_ids]
    return BludResponse(
        **record.model_dump(),
        completed_dungeons=sum(d.status != "not_completed" for d in current),
        rerun_dungeons=sum(d.status == "completed_rerun" for d in current),
        total_dungeons=len(dungeon_ids),
    )


def validate_values(
    body: BludCreate | BludPatch,
    references: BludReferenceData,
    current: BludRecord | None = None,
):
    class_id = (
        body.class_id if "class_id" in body.model_fields_set else current.class_id
    )
    spec_id = (
        body.spec_id
        if "spec_id" in body.model_fields_set or current is None
        else current.spec_id
    )
    reference = next((c for c in references.classes if c.id == class_id), None)
    same_class = current is not None and class_id == current.class_id
    if reference is None or (not reference.active and not same_class):
        raise HTTPException(422, "Choose a valid active class")
    if spec_id is not None:
        spec = next((s for s in reference.specs if s.id == spec_id), None)
        unchanged = same_class and spec_id == current.spec_id
        if not unchanged and (spec is None or not spec.active):
            raise HTTPException(422, "Choose an active spec belonging to this class")
    if isinstance(body, BludPatch) and body.professions is not None:
        refs = {p.id: p for p in references.professions}
        ids = [p.profession_id for p in body.professions]
        previous = {p.profession_id: p for p in current.professions} if current else {}
        if len(ids) != len(set(ids)) or any(p not in refs for p in ids):
            raise HTTPException(422, "Choose valid professions without duplicates")
        if (
            sum(refs[p].category == "primary" for p in ids)
            > references.max_primary_professions
        ):
            raise HTTPException(422, "Choose at most two primary professions")
        for profession in body.professions:
            ref = refs[profession.profession_id]
            old = previous.get(profession.profession_id)
            unchanged = old is not None and old.level == profession.level
            if (not ref.active or ref.category is None) and not unchanged:
                raise HTTPException(422, "This profession is no longer available")
            if (
                not unchanged
                and profession.level is not None
                and ref.max_level is not None
                and profession.level > ref.max_level
            ):
                raise HTTPException(422, "Profession level exceeds its skill limit")
    if isinstance(body, BludPatch) and body.dungeons is not None:
        refs = {d.id: d for d in references.dungeons}
        ids = [d.dungeon_id for d in body.dungeons]
        previous = {d.dungeon_id: d.status for d in current.dungeons} if current else {}
        if len(ids) != len(set(ids)) or any(d not in refs for d in ids):
            raise HTTPException(422, "Choose valid dungeons without duplicates")
        for dungeon in body.dungeons:
            if (
                not refs[dungeon.dungeon_id].active
                and dungeon.status != previous.get(dungeon.dungeon_id)
                and not (
                    dungeon.dungeon_id in previous and dungeon.status == "not_completed"
                )
            ):
                raise HTTPException(422, "This dungeon is no longer available")


@router.get("/reference-data")
async def reference_data(actor: Reader, references: ReferencesDep) -> BludReferenceData:
    return references


@router.get("")
async def list_bluds(
    filters: Annotated[BludFilter, Query()],
    actor: Reader,
    repository: BludsRepositoryDep,
    references: ReferencesDep,
) -> BludListResponse:
    for value, allowed in [
        (filters.class_id, {c.id for c in references.classes}),
        (filters.profession_id, {p.id for p in references.professions}),
        (filters.dungeon_id, {d.id for d in references.dungeons}),
    ]:
        if value is not None and value not in allowed:
            raise HTTPException(422, "Unknown Bluds filter")
    records = await repository.list_bluds(filters, actor.id)
    return BludListResponse(
        bluds=[present(record, references) for record in records[: filters.limit]],
        limit=filters.limit,
        offset=filters.offset,
        has_more=len(records) > filters.limit,
    )


@router.post("", status_code=201)
async def create_blud(
    body: BludCreate,
    actor: Creator,
    repository: BludsRepositoryDep,
    references: ReferencesDep,
) -> BludResponse:
    validate_values(body, references)
    return present(await repository.create(body, actor.id), references)


@router.get("/{blud_id}")
async def get_blud(
    blud_id: BludId,
    actor: Reader,
    repository: BludsRepositoryDep,
    references: ReferencesDep,
) -> BludResponse:
    record = await repository.get(blud_id)
    if record is None:
        raise HTTPException(404, "Blud not found")
    return present(record, references)


@router.patch("/{blud_id}")
async def update_blud(
    blud_id: BludId,
    body: BludPatch,
    actor: Reader,
    repository: BludsRepositoryDep,
    references: ReferencesDep,
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
    validate_values(body, references, current)
    if not body.model_fields_set:
        return present(current, references)
    record = await repository.update(blud_id, body, actor.id, can_correct)
    if record is None:
        raise HTTPException(404, "Blud not found")
    return present(record, references)
