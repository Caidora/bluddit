"""Public HTTP response contracts, independent of repository records."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from bluddit_api.utils.permissions import Permission, Role
from bluddit_api.utils.security import MembershipState


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None
    display_name: str
    membership_state: MembershipState
    role_name: Role
    timezone: str | None
    battletag: str | None = None


class AccountListResponse(BaseModel):
    accounts: list[AccountResponse]
    limit: int
    offset: int


class CurrentAccountResponse(AccountResponse):
    permissions: list[Permission]


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int


class PermissionsResponse(BaseModel):
    permissions: list[Permission]
    roles: dict[Role, list[Permission]]


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
