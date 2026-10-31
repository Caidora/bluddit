"""Officer membership administration and Guild Master succession."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from bluddit_api.utils.authorization import require_permission, require_guild_master
from bluddit_api.utils.dependencies import MembershipRepositoryDep
from bluddit_api.utils.permissions import Permission, Role, RolePolicy
from bluddit_api.repositories.membership import (
    MembershipRepository,
    GuildMasterChangedError,
)
from bluddit_api.utils.security import MembershipState

router = APIRouter(prefix="/api")
AccountId = Annotated[int, Path(gt=0)]
AccountManager = Annotated[
    dict, Depends(require_permission(Permission.ACCOUNTS_MANAGE))
]
GuildMaster = Annotated[dict, Depends(require_guild_master)]
PolicyReader = Annotated[dict, Depends(require_permission(Permission.POLICY_READ))]


async def _target(account_id: int, repository: MembershipRepository):
    account = await repository.get_account(account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    if account["role_name"] == Role.GUILD_MASTER:
        raise HTTPException(403, "Guild Master changes require transfer")
    return account


def _updated(account):
    if account is None:
        raise HTTPException(409, "Account update conflicts with current state")
    return account


def _require_membership_state(account: dict, *allowed: MembershipState):
    if account["membership_state"] not in allowed:
        raise HTTPException(409, "Invalid membership transition")


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
    result = await repository.get_account(account_id)
    if result is None:
        raise HTTPException(404, "Account not found")
    return result


@router.post("/accounts/{account_id}/approve")
async def approve(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    target = await _target(account_id, repository)
    _require_membership_state(target, MembershipState.PENDING)
    return _updated(await repository.approve(account_id))


@router.post("/accounts/{account_id}/reject")
async def reject(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    target = await _target(account_id, repository)
    _require_membership_state(target, MembershipState.PENDING)
    return _updated(await repository.reject(account_id))


@router.post("/accounts/{account_id}/deactivate")
async def deactivate(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    target = await _target(account_id, repository)
    _require_membership_state(target, MembershipState.ACTIVE)
    return _updated(await repository.deactivate(account_id))


@router.post("/accounts/{account_id}/activate")
async def activate(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    target = await _target(account_id, repository)
    _require_membership_state(
        target, MembershipState.REJECTED, MembershipState.INACTIVE
    )
    return _updated(await repository.activate(account_id))


@router.post("/accounts/{account_id}/promote-to-officer")
async def promote_to_officer(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    target = await _target(account_id, repository)
    if target["role_name"] != Role.MEMBER:
        raise HTTPException(409, "Invalid role transition")
    return _updated(await repository.promote_to_officer(account_id))


@router.post("/accounts/{account_id}/demote-to-member")
async def demote_to_member(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    target = await _target(account_id, repository)
    if target["role_name"] != Role.OFFICER:
        raise HTTPException(409, "Invalid role transition")
    return _updated(await repository.demote_to_member(account_id))


@router.post("/accounts/{account_id}/pass-guild-master")
async def pass_guild_master(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    target = await _target(account_id, repository)
    if target["membership_state"] != MembershipState.ACTIVE:
        raise HTTPException(409, "Guild Master recipient must be active")
    try:
        return _updated(await repository.pass_guild_master(actor["id"], account_id))
    except GuildMasterChangedError:
        raise HTTPException(
            403, "Only the current Guild Master may pass the role"
        ) from None


@router.get("/permissions")
async def permissions(actor: PolicyReader):
    return {
        "permissions": sorted(Permission),
        "roles": {role: sorted(values) for role, values in RolePolicy.mappings.items()},
    }
