"""Fixed role policy. Resource-specific attribute checks belong to feature code."""

from enum import StrEnum
from types import MappingProxyType


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
    ROLES_ASSIGN = "roles.assign"
    POLICY_READ = "policy.read"
    SHARED_RECORDS_CORRECT = "shared_records.correct"
    GUILD_MASTER_TRANSFER = "guild_master.transfer"


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
        Permission.ROLES_ASSIGN,
        Permission.POLICY_READ,
        Permission.SHARED_RECORDS_CORRECT,
    }
)


class RolePolicy:
    mappings = MappingProxyType(
        {
            Role.MEMBER: _MEMBER,
            Role.OFFICER: _OFFICER,
            Role.GUILD_MASTER: _OFFICER | {Permission.GUILD_MASTER_TRANSFER},
        }
    )

    @classmethod
    def permissions(cls, role: str) -> frozenset[Permission]:
        return cls.mappings.get(role, frozenset())

    @classmethod
    def allows(cls, account: dict, permission: Permission) -> bool:
        active = account["membership_state"] == "active"
        return active and permission in cls.permissions(account["role_name"])
