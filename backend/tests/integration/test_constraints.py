"""Database-level guarantees: append-only audit log and case-insensitive unique emails."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.audit.models import AuditLog
from app.users.models import User


def _insert_audit_row(db_session) -> int:
    entry = AuditLog(action="test.event", outcome="success", target_type="test", target_id="1")
    db_session.add(entry)
    db_session.flush()
    return entry.id


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_logs SET action = 'tampered' WHERE id = :id",
        "DELETE FROM audit_logs WHERE id = :id",
    ],
)
def test_audit_row_changes_rejected(db_session, statement):
    entry_id = _insert_audit_row(db_session)
    nested = db_session.begin_nested()
    with pytest.raises(DBAPIError, match="append-only"):
        db_session.execute(text(statement), {"id": entry_id})
    nested.rollback()
    action = db_session.execute(
        text("SELECT action FROM audit_logs WHERE id = :id"), {"id": entry_id}
    ).scalar_one()
    assert action == "test.event"


def test_audit_truncate_rejected(db_session):
    entry_id = _insert_audit_row(db_session)
    nested = db_session.begin_nested()
    with pytest.raises(DBAPIError, match="append-only"):
        db_session.execute(text("TRUNCATE audit_logs"))
    nested.rollback()
    assert db_session.get(AuditLog, entry_id) is not None


def _user(email: str) -> User:
    return User(
        id=uuid.uuid4(), email=email, full_name="Test Person", password_hash="x", role="auditor"
    )


def test_duplicate_email_rejected(db_session):
    db_session.add(_user("same@flowguard.example.org"))
    db_session.flush()
    db_session.add(_user("same@flowguard.example.org"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_mixed_case_email_cannot_bypass_uniqueness(db_session):
    """Emails are stored lowercased; a mixed-case row is rejected outright by the CHECK."""
    db_session.add(_user("Same@FlowGuard.example.org"))
    with pytest.raises(IntegrityError, match="email_lowercase"):
        db_session.flush()


def test_unknown_role_rejected_by_database(db_session):
    user = _user("role@flowguard.example.org")
    user.role = "wizard"
    db_session.add(user)
    with pytest.raises(IntegrityError, match="role_valid"):
        db_session.flush()
