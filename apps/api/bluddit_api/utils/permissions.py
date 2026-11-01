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
    BLUDS_VIEW = "bluds.view"
    BLUDS_EDIT_OWN = "bluds.edit_own"
    PROFILE_EDIT_OWN = "profile.edit_own"
    CHARACTERS_EDIT_OWN = "characters.edit_own"
    WISHLIST_EDIT_OWN = "wishlist.edit_own"
    EVENTS_CREATE = "events.create"
    EVENTS_MANAGE = "events.manage"
    SIGNUPS_EDIT_OWN = "signups.edit_own"
    ACCOUNTS_MANAGE = "accounts.manage"
    HANDBOOK_EDIT = "handbook.edit"
    HANDBOOK_DELETE = "handbook.delete"
    POLICY_READ = "policy.read"
    SHARED_RECORDS_CORRECT = "shared_records.correct"


_MEMBER = frozenset(
    {
        Permission.GUILD_READ,
        Permission.BLUDS_VIEW,
        Permission.BLUDS_EDIT_OWN,
        Permission.PROFILE_EDIT_OWN,
        Permission.CHARACTERS_EDIT_OWN,
        Permission.WISHLIST_EDIT_OWN,
        Permission.SIGNUPS_EDIT_OWN,
        Permission.EVENTS_CREATE,
        Permission.EVENTS_MANAGE,
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
            Role.GUILD_MASTER: _OFFICER | frozenset({Permission.HANDBOOK_DELETE}),
        }
    )

    @classmethod
    def permissions(cls, role: str) -> frozenset[Permission]:
        return cls.mappings.get(role, frozenset())

    @classmethod
    def allows(cls, account: "AccountState", permission: Permission) -> bool:
        active = account.membership_state == "active"
        return active and permission in cls.permissions(account.role_name)
