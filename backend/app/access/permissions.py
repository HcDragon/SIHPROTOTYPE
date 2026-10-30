"""Named permissions and the fixed role-to-permission map (design D7)."""

from enum import StrEnum

from app.access.roles import Role
from app.core.errors import PermissionDenied


class PermissionCategory(StrEnum):
    SYSTEM = "system"
    AUDIT = "audit"
    BUSINESS = "business"


class Permission(StrEnum):
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"
    AUDIT_READ = "audit.read"

    @property
    def category(self) -> PermissionCategory:
        return PERMISSION_CATEGORIES[self]


PERMISSION_CATEGORIES: dict[Permission, PermissionCategory] = {
    Permission.USERS_READ: PermissionCategory.SYSTEM,
    Permission.USERS_MANAGE: PermissionCategory.SYSTEM,
    Permission.AUDIT_READ: PermissionCategory.AUDIT,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SUPER_ADMIN: frozenset(
        {Permission.USERS_READ, Permission.USERS_MANAGE, Permission.AUDIT_READ}
    ),
    Role.AICTE_ADMIN: frozenset({Permission.AUDIT_READ}),
    Role.REGIONAL_OFFICER: frozenset(),
    Role.SCRUTINY_OFFICER: frozenset(),
    Role.EVC_COORDINATOR: frozenset(),
    Role.INSTITUTION_REPRESENTATIVE: frozenset(),
    Role.AUDITOR: frozenset({Permission.AUDIT_READ}),
}


def permissions_for(role: Role | str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[Role(role)]


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in permissions_for(role)


def authorize(actor, permission: Permission) -> None:
    """Service-level re-check, so no code path can act without the permission."""
    if not has_permission(actor.role, permission):
        raise PermissionDenied()
