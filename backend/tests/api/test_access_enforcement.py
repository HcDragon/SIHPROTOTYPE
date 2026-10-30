"""require-permission behavior using a throwaway write endpoint."""

import pytest
from fastapi import APIRouter
from sqlalchemy import select, text

from app.access.dependencies import authorize, requires
from app.access.permissions import Permission
from app.access.roles import Role
from app.audit.models import AuditLog
from app.auth.dependencies import CurrentUser
from app.core.db import SessionDep
from app.core.errors import PermissionDenied


@pytest.fixture
def guarded_client(app, client, connection):
    connection.execute(text("CREATE TEMP TABLE IF NOT EXISTS guarded (value text)"))
    router = APIRouter()

    @router.post(
        "/_test/guarded/{item_id}",
        **requires(
            Permission.USERS_MANAGE,
            audit_action="test.write",
            target_type="item",
            target_param="item_id",
        ),
    )
    def guarded_write(item_id: str, actor: CurrentUser, session: SessionDep):
        session.execute(text("INSERT INTO guarded VALUES ('written')"))
        return {"ok": True}

    @router.get("/_test/guarded-read", **requires(Permission.USERS_READ))
    def guarded_read():
        return {"ok": True}

    app.include_router(router, prefix="/api/v1")
    return client


def _rows(connection):
    return connection.execute(text("SELECT count(*) FROM guarded")).scalar()


def test_denied_write_is_403_audited_and_changes_nothing(
    guarded_client, auth_headers, connection, db_session
):
    headers, user = auth_headers(Role.INSTITUTION_REPRESENTATIVE)
    response = guarded_client.post("/api/v1/_test/guarded/item-7", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
    assert _rows(connection) == 0
    entry = db_session.scalar(select(AuditLog).where(AuditLog.action == "test.write"))
    assert entry.outcome == "denied"
    assert entry.actor_id == user.id
    assert entry.actor_role == "institution_representative"
    assert entry.target_type == "item" and entry.target_id == "item-7"


def test_allowed_write_runs(guarded_client, auth_headers, connection):
    headers, _ = auth_headers(Role.SUPER_ADMIN)
    assert guarded_client.post("/api/v1/_test/guarded/1", headers=headers).status_code == 200
    assert _rows(connection) == 1


def test_denied_read_is_not_audited(guarded_client, auth_headers, db_session):
    headers, _ = auth_headers(Role.AUDITOR)
    assert guarded_client.get("/api/v1/_test/guarded-read", headers=headers).status_code == 403
    assert db_session.scalar(select(AuditLog).where(AuditLog.outcome == "denied")) is None


def test_unauthenticated_gets_401_not_403(guarded_client):
    assert guarded_client.post("/api/v1/_test/guarded/1").status_code == 401


def test_service_level_authorize():
    class Actor:
        id = None
        role = "auditor"

    authorize(Actor, Permission.AUDIT_READ)
    with pytest.raises(PermissionDenied):
        authorize(Actor, Permission.USERS_MANAGE)
