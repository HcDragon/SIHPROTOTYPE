"""UserService against PostgreSQL: each operation and the audit entry it writes."""

import pytest
from sqlalchemy import select

from app.access.roles import Role
from app.audit.models import AuditLog
from app.auth.models import RefreshToken
from app.core.errors import Conflict, NotFound, PermissionDenied
from app.core.pagination import PageParams, SortSpec
from app.users.repository import UserFilters
from app.users.schemas import UserCreate, UserUpdate
from app.users.service import UserService


@pytest.fixture
def admin(user_factory):
    return user_factory(role=Role.SUPER_ADMIN)


@pytest.fixture
def service(db_session, settings, admin):
    return UserService(db_session, settings, admin)


def _last_audit(db_session, action) -> AuditLog:
    return db_session.scalar(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id.desc())
    )


def _create(service, **overrides):
    data = {
        "email": "New.Person@FlowGuard.example.org",
        "full_name": "New Person",
        "role": "scrutiny_officer",
        "password": "a-long-enough-password",
    } | overrides
    return service.create(UserCreate(**data))


def test_create_lowercases_email_and_audits(service, db_session, admin):
    user = _create(service)
    assert user.email == "new.person@flowguard.example.org"
    entry = _last_audit(db_session, "users.create")
    assert entry.actor_id == admin.id
    assert entry.target_id == str(user.id)
    assert entry.before is None
    assert entry.after == {
        "email": "new.person@flowguard.example.org",
        "full_name": "New Person",
        "role": "scrutiny_officer",
        "is_active": True,
    }


def test_create_duplicate_email_any_case(service):
    _create(service)
    with pytest.raises(Conflict):
        _create(service, email="NEW.PERSON@flowguard.example.org")


def test_update_role_audits_before_and_after(service, db_session, user_factory):
    target = user_factory(role=Role.SCRUTINY_OFFICER)
    service.update(target.id, UserUpdate(role=Role.REGIONAL_OFFICER))
    entry = _last_audit(db_session, "users.update")
    assert entry.before["role"] == "scrutiny_officer"
    assert entry.after["role"] == "regional_officer"


def test_deactivate_revokes_tokens_and_audits(service, db_session, user_factory, client):
    from tests.factories import DEFAULT_PASSWORD

    target = user_factory()
    client.post("/api/v1/auth/login", json={"email": target.email, "password": DEFAULT_PASSWORD})
    service.deactivate(target.id)
    db_session.flush()
    tokens = db_session.scalars(select(RefreshToken).where(RefreshToken.user_id == target.id))
    assert all(t.revoked_at is not None for t in tokens)
    entry = _last_audit(db_session, "users.deactivate")
    assert (entry.before["is_active"], entry.after["is_active"]) == (True, False)


def test_activate_audits(service, db_session, user_factory):
    target = user_factory(is_active=False)
    service.activate(target.id)
    entry = _last_audit(db_session, "users.activate")
    assert (entry.before["is_active"], entry.after["is_active"]) == (False, True)


def test_self_protection(service, admin):
    with pytest.raises(Conflict):
        service.deactivate(admin.id)
    with pytest.raises(Conflict):
        service.update(admin.id, UserUpdate(role=Role.AUDITOR))


def test_last_super_admin_protected(db_session, settings, user_factory):
    """Guard holds even if the caller is not the last Super Admin themselves (defense in depth)."""
    only_admin = user_factory(role=Role.SUPER_ADMIN)
    for other in db_session.scalars(
        select(type(only_admin)).where(type(only_admin).role == "super_admin")
    ):
        if other.id != only_admin.id:
            other.is_active = False
    db_session.flush()
    stranger = user_factory(role=Role.AUDITOR)
    stranger.role = "super_admin"  # in-memory actor with permission, not persisted as admin
    db_session.expunge(stranger)
    with pytest.raises(Conflict, match="Super Admin must remain"):
        UserService(db_session, settings, stranger).update(
            only_admin.id, UserUpdate(role=Role.AUDITOR)
        )


def test_list_filters_and_paginates(service, user_factory):
    for _ in range(3):
        user_factory(role=Role.EVC_COORDINATOR)
    items, total = service.list(
        UserFilters(role=Role.EVC_COORDINATOR), PageParams(1, 2), SortSpec("email", False)
    )
    assert total == 3 and len(items) == 2
    assert all(u.role == "evc_coordinator" for u in items)


def test_get_unknown(service):
    import uuid

    with pytest.raises(NotFound):
        service.get(uuid.uuid4())


def test_service_rechecks_permission(db_session, settings, user_factory):
    auditor = user_factory(role=Role.AUDITOR)
    with pytest.raises(PermissionDenied):
        UserService(db_session, settings, auditor).create(
            UserCreate(
                email="x@flowguard.example.org",
                full_name="X",
                role=Role.AUDITOR,
                password="a-long-enough-password",
            )
        )
