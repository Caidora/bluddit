"""Officer membership administration and Guild Master succession."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict

from bluddit_api.utils.authorization import require_permission
from bluddit_api.utils.dependencies import MembershipRepositoryDep
from bluddit_api.utils.permissions import Permission, Role, RolePolicy
from bluddit_api.utils.security import MembershipState

router = APIRouter(prefix="/api")
AccountId = Annotated[int, Path(gt=0)]
AccountManager = Annotated[
    dict, Depends(require_permission(Permission.ACCOUNTS_MANAGE))
]
RoleManager = Annotated[dict, Depends(require_permission(Permission.ROLES_ASSIGN))]
GuildMaster = Annotated[
    dict, Depends(require_permission(Permission.GUILD_MASTER_TRANSFER))
]
PolicyReader = Annotated[dict, Depends(require_permission(Permission.POLICY_READ))]


class RoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_name: Literal["member", "officer"]


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


@router.post("/accounts/{account_id}/{action}")
async def membership(
    account_id: AccountId,
    action: Literal["approve", "reject", "deactivate", "reactivate"],
    actor: AccountManager,
    repository: MembershipRepositoryDep,
):
    return await repository.manage(actor["id"], account_id, action)


@router.put("/accounts/{account_id}/role")
async def assign_role(
    account_id: AccountId,
    body: RoleInput,
    actor: RoleManager,
    repository: MembershipRepositoryDep,
):
    return await repository.manage(
        actor["id"], account_id, "role", Role(body.role_name)
    )


@router.put("/accounts/{account_id}/guild-master")
async def transfer_guild_master(
    account_id: AccountId, actor: GuildMaster, repository: MembershipRepositoryDep
):
    return await repository.manage(actor["id"], account_id, "transfer")


@router.get("/permissions")
async def permissions(actor: PolicyReader):
    return {
        "permissions": sorted(Permission),
        "roles": {role: sorted(values) for role, values in RolePolicy.mappings.items()},
    }
