"""Officer membership administration and Guild Master succession."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from bluddit_api.utils.authorization import require_permission, require_guild_master
from bluddit_api.utils.dependencies import MembershipRepositoryDep
from bluddit_api.utils.permissions import Permission, Role, RolePolicy
from bluddit_api.repositories.membership import MembershipRepository
from bluddit_api.utils.security import MembershipState

router = APIRouter(prefix="/api")
AccountId = Annotated[int, Path(gt=0)]
AccountManager = Annotated[
    dict, Depends(require_permission(Permission.ACCOUNTS_MANAGE))
]
GuildMaster = Annotated[dict, Depends(require_guild_master)]
PolicyReader = Annotated[dict, Depends(require_permission(Permission.POLICY_READ))]


async def _administration(
    actor: dict,
    account_id: int,
    repository: MembershipRepository,
    *,
    guild_master_only: bool = False,
):
    await repository.lock_administration()
    locked = {
        account["id"]: account
        for account in await repository.lock_accounts([actor["id"], account_id])
    }
    current_actor = locked.get(actor["id"])
    if current_actor is None or not RolePolicy.allows(
        current_actor, Permission.ACCOUNTS_MANAGE
    ):
        raise HTTPException(403, "Permission denied")
    if guild_master_only and current_actor["role_name"] != Role.GUILD_MASTER:
        raise HTTPException(403, "Only the Guild Master may change roles")
    target = locked.get(account_id)
    if target is None:
        raise HTTPException(404, "Account not found")
    if target["role_name"] == Role.GUILD_MASTER:
        raise HTTPException(403, "Guild Master changes require transfer")
    if guild_master_only and current_actor["id"] == account_id:
        raise HTTPException(403, "Cannot change your own role")
    return target


def _require_membership_state(account: dict, *allowed: MembershipState):
    if account["membership_state"] not in allowed:
        raise HTTPException(409, "Invalid membership transition")


async def _protect_last_administrator(account: dict, repository: MembershipRepository):
    if account["membership_state"] == MembershipState.ACTIVE and account[
        "role_name"
    ] in {Role.OFFICER, Role.GUILD_MASTER}:
        if await repository.count_active_administrators() <= 1:
            raise HTTPException(409, "Cannot remove the last active administrator")


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
    target = await _administration(actor, account_id, repository)
    _require_membership_state(target, MembershipState.PENDING)
    return await repository.approve(account_id)


@router.post("/accounts/{account_id}/reject")
async def reject(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    target = await _administration(actor, account_id, repository)
    _require_membership_state(target, MembershipState.PENDING)
    result = await repository.reject(account_id)
    await repository.revoke_sessions(account_id)
    return result


@router.post("/accounts/{account_id}/deactivate")
async def deactivate(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    target = await _administration(actor, account_id, repository)
    _require_membership_state(target, MembershipState.ACTIVE)
    await _protect_last_administrator(target, repository)
    result = await repository.deactivate(account_id)
    await repository.revoke_sessions(account_id)
    return result


@router.post("/accounts/{account_id}/activate")
async def activate(
    account_id: AccountId, actor: AccountManager, repository: MembershipRepositoryDep
):
    target = await _administration(actor, account_id, repository)
    _require_membership_state(
        target, MembershipState.REJECTED, MembershipState.INACTIVE
    )
    return await repository.activate(account_id)


@router.post("/accounts/{account_id}/promote-to-officer")
async def promote_to_officer(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    target = await _administration(
        actor, account_id, repository, guild_master_only=True
    )
    if target["role_name"] != Role.MEMBER:
        raise HTTPException(409, "Invalid role transition")
    return await repository.promote_to_officer(account_id)


@router.post("/accounts/{account_id}/demote-to-member")
async def demote_to_member(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    target = await _administration(
        actor, account_id, repository, guild_master_only=True
    )
    if target["role_name"] != Role.OFFICER:
        raise HTTPException(409, "Invalid role transition")
    await _protect_last_administrator(target, repository)
    return await repository.demote_to_member(account_id)


@router.post("/accounts/{account_id}/pass-guild-master")
async def pass_guild_master(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    target = await _administration(
        actor, account_id, repository, guild_master_only=True
    )
    if target["membership_state"] != MembershipState.ACTIVE:
        raise HTTPException(409, "Guild Master recipient must be active")
    # Both updates share the request transaction; demote first for the unique index.
    await repository.demote_guild_master(actor["id"])
    return await repository.pass_guild_master(account_id)


@router.get("/permissions")
async def permissions(actor: PolicyReader):
    return {
        "permissions": sorted(Permission),
        "roles": {role: sorted(values) for role, values in RolePolicy.mappings.items()},
    }
