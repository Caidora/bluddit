"""Member handbook reads and officer editorial history."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from bluddit_api.models.accounts import Account
from bluddit_api.models.handbook import (
    HandbookCreate,
    HandbookDelete,
    HandbookEdit,
    HandbookSection,
    HandbookSectionsResponse,
    HandbookRevisionsResponse,
)
from bluddit_api.repositories.handbook import HandbookSlugExists, StaleHandbookEdit
from bluddit_api.utils.authorization import require_permission
from bluddit_api.utils.dependencies import HandbookRepositoryDep
from bluddit_api.utils.permissions import Permission

router = APIRouter(prefix="/api/handbook", tags=["handbook"])
Reader = Annotated[Account, Depends(require_permission(Permission.GUILD_READ))]
Editor = Annotated[Account, Depends(require_permission(Permission.HANDBOOK_EDIT))]
Slug = Annotated[str, Path(pattern=r"^[a-z][a-z0-9-]{0,79}$")]


@router.post("", status_code=201)
async def create_section(
    section: HandbookCreate, actor: Editor, repository: HandbookRepositoryDep
) -> HandbookSection:
    try:
        return await repository.create(section, actor.id)
    except HandbookSlugExists:
        raise HTTPException(409, "Handbook slug already exists") from None


@router.get("")
async def sections(
    actor: Reader,
    repository: HandbookRepositoryDep,
    q: Annotated[str, Query(max_length=200)] = "",
) -> HandbookSectionsResponse:
    return HandbookSectionsResponse(sections=await repository.list_sections(q.strip()))


@router.get("/{slug}")
async def section(
    slug: Slug, actor: Reader, repository: HandbookRepositoryDep
) -> HandbookSection:
    result = await repository.get_section(slug)
    if result is None:
        raise HTTPException(404, "Handbook section not found")
    return result


@router.put("/{slug}")
async def edit_section(
    slug: Slug, edit: HandbookEdit, actor: Editor, repository: HandbookRepositoryDep
) -> HandbookSection:
    try:
        result = await repository.edit(slug, edit, actor.id)
    except StaleHandbookEdit:
        raise HTTPException(
            409,
            "A newer revision was saved. Keep a copy of your draft, then reload the latest section before editing again.",
        ) from None
    if result is None:
        raise HTTPException(404, "Handbook section not found")
    return result


@router.get("/{slug}/revisions")
async def revisions(
    slug: Slug,
    actor: Editor,
    repository: HandbookRepositoryDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HandbookRevisionsResponse:
    if await repository.get_section(slug) is None:
        raise HTTPException(404, "Handbook section not found")
    return HandbookRevisionsResponse(
        revisions=await repository.revisions(slug, limit, offset),
        limit=limit,
        offset=offset,
    )


@router.delete("/{slug}", status_code=204)
async def delete_section(
    slug: Slug,
    query: Annotated[HandbookDelete, Query()],
    actor: Editor,
    repository: HandbookRepositoryDep,
) -> Response:
    try:
        deleted = await repository.delete(slug, query.expected_revision)
    except StaleHandbookEdit:
        raise HTTPException(
            409,
            "A newer revision was saved. Reload and review the latest section before deleting again.",
        ) from None
    if not deleted:
        raise HTTPException(404, "Handbook section not found")
    return Response(status_code=204)
