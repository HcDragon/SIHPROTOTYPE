import uuid
from types import SimpleNamespace

from sqlalchemy import func, select

from app.audit.models import AuditLog, AuditOutcome
from app.audit.service import AuditService
from app.users.models import User


def _count(session, action: str) -> int:
    return session.scalar(select(func.count()).where(AuditLog.action == action))


def _user() -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@flowguard.example.org",
        full_name="Audit Subject",
        password_hash="x",
        role="auditor",
    )


def test_entry_contains_all_fields(db_session):
    actor = _user()
    db_session.add(actor)
    db_session.flush()
    entry = AuditService(db_session).record(
        "users.update",
        actor=actor,
        target_type="user",
        target_id=actor.id,
        before={"role": "auditor"},
        after={"role": "aicte_admin"},
    )
    stored = db_session.get(AuditLog, entry.id)
    assert stored.actor_id == actor.id
    assert stored.actor_role == "auditor"
    assert stored.target_type == "user"
    assert stored.target_id == str(actor.id)
    assert stored.outcome == "success"
    assert stored.before == {"role": "auditor"}
    assert stored.after == {"role": "aicte_admin"}
    assert stored.occurred_at.utcoffset().total_seconds() == 0


def test_entry_rolls_back_with_the_change(db_session):
    savepoint = db_session.begin_nested()
    user = _user()
    db_session.add(user)
    AuditService(db_session).record("users.create", target_type="user", target_id=user.id)
    savepoint.rollback()
    assert db_session.get(User, user.id) is None
    assert _count(db_session, "users.create") == 0


def test_entry_saved_with_the_change(db_session):
    user = _user()
    db_session.add(user)
    AuditService(db_session).record("users.create", target_type="user", target_id=user.id)
    db_session.commit()
    assert db_session.get(User, user.id) is not None
    assert _count(db_session, "users.create") == 1


def test_security_event_survives_request_rollback(db_session):
    AuditService(db_session).record_security_event(
        "auth.login", outcome=AuditOutcome.FAILURE, details={"email": "x@example.org"}
    )
    db_session.rollback()
    assert _count(db_session, "auth.login") == 1


def test_anonymous_actor(db_session):
    entry = AuditService(db_session).record("auth.login", outcome=AuditOutcome.FAILURE)
    assert entry.actor_id is None and entry.actor_role is None


def test_actor_protocol_accepts_any_object_with_id_and_role(db_session):
    user = _user()
    db_session.add(user)
    db_session.flush()
    entry = AuditService(db_session).record(
        "test.event", actor=SimpleNamespace(id=user.id, role="super_admin")
    )
    assert entry.actor_role == "super_admin"
