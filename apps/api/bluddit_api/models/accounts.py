"""Account query projections; credentials stay separate from public records."""

from pydantic import BaseModel, Field

from bluddit_api.utils.permissions import Role
from bluddit_api.utils.security import MembershipState


class AccountState(BaseModel):
    id: int
    role_name: Role
    membership_state: MembershipState


class Account(AccountState):
    username: str
    display_name: str
    timezone: str | None


class AccountCredentials(BaseModel):
    id: int
    password_hash: str = Field(repr=False)
    membership_state: MembershipState
