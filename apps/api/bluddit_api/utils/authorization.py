"""Reusable active-account and endpoint permission dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException

from bluddit_api.utils.auth import current_account
from bluddit_api.utils.permissions import Permission, RolePolicy

ActiveAccountDep = Annotated[dict, Depends(current_account)]


def require_permission(permission: Permission):
    async def check(account: ActiveAccountDep):
        if not RolePolicy.allows(account, permission):
            raise HTTPException(403, "Permission denied")
        return account

    return check
