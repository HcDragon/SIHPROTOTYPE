"""The role-permission map matches design D7, and Super Admin holds no business permissions."""

import uuid

import pytest

from app.access.permissions import (
    PERMISSION_CATEGORIES,
    ROLE_PERMISSIONS,
    Permission,
    PermissionCategory,
    permissions_for,
)
from app.access.roles import Role
from app.access.scope import Scope, found_in_scope
from app.core.errors import NotFound

# Written out independently of the code on purpose (design.md D7).
EXPECTED = {
    Role.SUPER_ADMIN: {"users.read", "users.manage", "audit.read"},
    Role.AICTE_ADMIN: {"audit.read"},
    Role.REGIONAL_OFFICER: set(),
    Role.SCRUTINY_OFFICER: set(),
    Role.EVC_COORDINATOR: set(),
    Role.INSTITUTION_REPRESENTATIVE: set(),
    Role.AUDITOR: {"audit.read"},
}


def test_exactly_seven_roles():
    assert {r.value for r in Role} == {
        "super_admin",
        "aicte_admin",
        "regional_officer",
        "scrutiny_officer",
        "evc_coordinator",
        "institution_representative",
        "auditor",
    }


@pytest.mark.parametrize("role", list(Role))
def test_role_permissions_match_matrix(role):
    assert {p.value for p in permissions_for(role)} == EXPECTED[role]


def test_every_role_is_mapped():
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_every_permission_has_a_category():
    assert set(PERMISSION_CATEGORIES) == set(Permission)


def test_super_admin_has_no_business_permissions():
    business = {
        p for p in permissions_for(Role.SUPER_ADMIN) if p.category is PermissionCategory.BUSINESS
    }
    assert business == set()


def test_unknown_role_rejected():
    with pytest.raises(ValueError):
        permissions_for("wizard")


def test_out_of_scope_lookup_matches_missing_record():
    with pytest.raises(NotFound) as out_of_scope:
        found_in_scope(None)
    missing = NotFound()
    assert (
        out_of_scope.value.status_code,
        out_of_scope.value.code,
        out_of_scope.value.message,
    ) == (
        missing.status_code,
        missing.code,
        missing.message,
    )


def test_found_in_scope_returns_record():
    record = object()
    assert found_in_scope(record) is record


def test_scope_for_user():
    class U:
        id = uuid.uuid4()
        role = "auditor"

    scope = Scope.for_user(U)
    assert scope.role is Role.AUDITOR and scope.institution_id is None
