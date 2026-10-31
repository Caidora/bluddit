"""Officer membership administration and Guild Master succession."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from bluddit_api.utils.authorization import require_permission, require_guild_master
from bluddit_api.utils.dependencies import MembershipRepositoryDep
from bluddit_api.utils.permissions import Permission, RolePolicy
from bluddit_api.utils.security import MembershipState

router = APIRouter(prefix="/api")
AccountId = Annotated[int, Path(gt=0)]
AccountManager = Annotated[
    dict, Depends(require_permission(Permission.ACCOUNTS_MANAGE))
]
GuildMaster = Annotated[dict, Depends(require_guild_master)]
PolicyReader = Annotated[dict, Depends(require_permission(Permission.POLICY_READ))]


@router.get("/accounts")
async def accounts(
    actor: AccountManager,
    repository: MembershipRepositoryDep,
    membership_state: MembershipState | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items = await repository.list_accounts(membership_state, limit, offset)
    return {"accounts": items, "limit": limit, "offset": offset}


@router.get("/accounts/{account_id}")
async def account(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    return await repository.get_account(account_id)


@router.post("/accounts/{account_id}/approve")
async def approve(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    return await repository.approve(actor["id"], account_id)


@router.post("/accounts/{account_id}/reject")
async def reject(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    return await repository.reject(actor["id"], account_id)


@router.post("/accounts/{account_id}/deactivate")
async def deactivate(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    return await repository.deactivate(actor["id"], account_id)


@router.post("/accounts/{account_id}/activate")
async def activate(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    return await repository.activate(actor["id"], account_id)


@router.post("/accounts/{account_id}/promote-to-officer")
async def promote_to_officer(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    return await repository.promote_to_officer(actor["id"], account_id)


@router.post("/accounts/{account_id}/demote-to-member")
async def demote_to_member(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    return await repository.demote_to_member(actor["id"], account_id)


@router.post("/accounts/{account_id}/pass-guild-master")
async def pass_guild_master(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    return await repository.pass_guild_master(actor["id"], account_id)


@router.get("/permissions")
async def permissions(actor: PolicyReader):
    return {
        "permissions": sorted(Permission),
        "roles": {role: sorted(values) for role, values in RolePolicy.mappings.items()},
    }
