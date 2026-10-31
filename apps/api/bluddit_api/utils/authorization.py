"""Reusable active-account and endpoint permission dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException

from bluddit_api.models.accounts import Account
from bluddit_api.utils.auth import current_account
from bluddit_api.utils.permissions import Permission, Role, RolePolicy

ActiveAccountDep = Annotated[Account, Depends(current_account)]


def require_permission(permission: Permission):
    async def check(account: ActiveAccountDep) -> Account:
        if not RolePolicy.allows(account, permission):
            raise HTTPException(403, "Permission denied")
        return account

    return check


AccountManagerDep = Annotated[
    Account, Depends(require_permission(Permission.ACCOUNTS_MANAGE))
]


async def require_guild_master(account: AccountManagerDep) -> Account:
    if account.role_name != Role.GUILD_MASTER:
        raise HTTPException(403, "Only the Guild Master may change roles")
    return account
