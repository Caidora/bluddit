"""Fixed role policy. Resource-specific attribute checks belong to feature code."""

from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bluddit_api.models.accounts import AccountState


class Role(StrEnum):
    MEMBER = "member"
    OFFICER = "officer"
    GUILD_MASTER = "guild_master"


class Permission(StrEnum):
    GUILD_READ = "guild.read"
    PROFILE_EDIT_OWN = "profile.edit_own"
    CHARACTERS_EDIT_OWN = "characters.edit_own"
    WISHLIST_EDIT_OWN = "wishlist.edit_own"
    SIGNUPS_EDIT_OWN = "signups.edit_own"
    ACCOUNTS_MANAGE = "accounts.manage"
    HANDBOOK_EDIT = "handbook.edit"
    POLICY_READ = "policy.read"
    SHARED_RECORDS_CORRECT = "shared_records.correct"


_MEMBER = frozenset(
    {
        Permission.GUILD_READ,
        Permission.PROFILE_EDIT_OWN,
        Permission.CHARACTERS_EDIT_OWN,
        Permission.WISHLIST_EDIT_OWN,
        Permission.SIGNUPS_EDIT_OWN,
    }
)
_OFFICER = _MEMBER | frozenset(
    {
        Permission.ACCOUNTS_MANAGE,
        Permission.POLICY_READ,
        Permission.HANDBOOK_EDIT,
        Permission.SHARED_RECORDS_CORRECT,
    }
)


class RolePolicy:
    mappings = MappingProxyType(
        {
            Role.MEMBER: _MEMBER,
            Role.OFFICER: _OFFICER,
            Role.GUILD_MASTER: _OFFICER,
        }
    )

    @classmethod
    def permissions(cls, role: str) -> frozenset[Permission]:
        return cls.mappings.get(role, frozenset())

    @classmethod
    def allows(cls, account: "AccountState", permission: Permission) -> bool:
        active = account.membership_state == "active"
        return active and permission in cls.permissions(account.role_name)
