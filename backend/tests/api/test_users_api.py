"""User administration endpoints over HTTP."""

import uuid

import pytest
from sqlalchemy import select

from app.access.roles import Role
from app.audit.models import AuditLog
from tests.factories import DEFAULT_PASSWORD

USERS = "/api/v1/users"
NEW_USER = {
    "email": "Fresh.Officer@FlowGuard.example.org",
    "full_name": "Fresh Officer",
    "role": "scrutiny_officer",
    "password": "a-long-enough-password",
}


@pytest.fixture
def admin_headers(auth_headers):
    headers, _ = auth_headers(Role.SUPER_ADMIN)
    return headers


def _denied_entries(db_session, action):
    return db_session.scalars(
        select(AuditLog).where(AuditLog.action == action, AuditLog.outcome == "denied")
    ).all()


# 9.2 list and get


def test_list_filters_by_role(client, admin_headers, user_factory):
    user_factory(role=Role.AUDITOR)
    user_factory(role=Role.EVC_COORDINATOR)
    body = client.get(f"{USERS}?role=auditor", headers=admin_headers).json()
    assert body["total"] >= 1
    assert {u["role"] for u in body["items"]} == {"auditor"}
    assert "password_hash" not in str(body)


def test_list_pagination_and_sort(client, admin_headers, user_factory):
    for _ in range(3):
        user_factory(role=Role.EVC_COORDINATOR)
    body = client.get(
        f"{USERS}?role=evc_coordinator&page_size=2&sort=-email", headers=admin_headers
    ).json()
    assert body["page_size"] == 2 and len(body["items"]) == 2 and body["total"] == 3
    emails = [u["email"] for u in body["items"]]
    assert emails == sorted(emails, reverse=True)


def test_list_filter_inactive(client, admin_headers, user_factory):
    inactive = user_factory(is_active=False)
    body = client.get(f"{USERS}?is_active=false", headers=admin_headers).json()
    assert str(inactive.id) in {u["id"] for u in body["items"]}
    assert all(u["is_active"] is False for u in body["items"])


def test_list_invalid_sort(client, admin_headers):
    response = client.get(f"{USERS}?sort=password_hash", headers=admin_headers)
    assert response.status_code == 422


def test_get_user_and_unknown(client, admin_headers, user_factory):
    user = user_factory()
    assert client.get(f"{USERS}/{user.id}", headers=admin_headers).json()["email"] == user.email
    response = client.get(f"{USERS}/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_user_invalid_id(client, admin_headers):
    assert client.get(f"{USERS}/not-a-uuid", headers=admin_headers).status_code == 422


def test_aicte_admin_cannot_list(client, auth_headers):
    headers, _ = auth_headers(Role.AICTE_ADMIN)
    response = client.get(USERS, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


# 9.3 create and update


def test_create_user_then_login(client, admin_headers):
    response = client.post(USERS, json=NEW_USER, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["email"] == "fresh.officer@flowguard.example.org"
    login = client.post(
        "/api/v1/auth/login", json={"email": NEW_USER["email"], "password": NEW_USER["password"]}
    )
    assert login.status_code == 200


def test_create_duplicate_email(client, admin_headers):
    client.post(USERS, json=NEW_USER, headers=admin_headers)
    dup = NEW_USER | {"email": "FRESH.officer@flowguard.example.org"}
    response = client.post(USERS, json=dup, headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize(
    "change",
    [{"password": "Xq7#tiny"}, {"role": "wizard"}, {"is_admin": True}, {"email": "nope"}],
    ids=["weak-password", "unknown-role", "unknown-field", "bad-email"],
)
def test_create_validation(client, admin_headers, change):
    response = client.post(USERS, json=NEW_USER | change, headers=admin_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "Xq7#tiny" not in response.text  # submitted values are not echoed


@pytest.mark.parametrize("role", [Role.AUDITOR, Role.REGIONAL_OFFICER])
def test_unauthorized_create_denied_and_audited(client, auth_headers, db_session, role):
    headers, user = auth_headers(role)
    response = client.post(USERS, json=NEW_USER, headers=headers)
    assert response.status_code == 403
    [entry] = _denied_entries(db_session, "users.create")
    assert entry.actor_id == user.id
    login = client.post(
        "/api/v1/auth/login", json={"email": NEW_USER["email"], "password": NEW_USER["password"]}
    )
    assert login.status_code == 401  # nobody was created


def test_role_change_applies_to_next_request(client, admin_headers, user_factory, settings):
    from tests.factories import bearer

    target = user_factory(role=Role.SCRUTINY_OFFICER)
    target_headers = bearer(target, settings)
    response = client.patch(
        f"{USERS}/{target.id}", json={"role": "regional_officer"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "regional_officer"
    assert client.get("/api/v1/auth/me", headers=target_headers).json()["role"] == (
        "regional_officer"
    )


def test_update_rejects_email_and_password_changes(client, admin_headers, user_factory):
    target = user_factory()
    for body in ({"email": "other@flowguard.example.org"}, {"password": "new-long-password"}):
        response = client.patch(f"{USERS}/{target.id}", json=body, headers=admin_headers)
        assert response.status_code == 422


def test_update_requires_a_field(client, admin_headers, user_factory):
    target = user_factory()
    assert client.patch(f"{USERS}/{target.id}", json={}, headers=admin_headers).status_code == 422


@pytest.mark.parametrize("role", [Role.REGIONAL_OFFICER, Role.INSTITUTION_REPRESENTATIVE])
def test_unauthorized_update_denied_and_audited(
    client, auth_headers, user_factory, db_session, role
):
    target = user_factory(role=Role.SCRUTINY_OFFICER)
    headers, user = auth_headers(role)
    response = client.patch(f"{USERS}/{target.id}", json={"role": "aicte_admin"}, headers=headers)
    assert response.status_code == 403
    db_session.refresh(target)
    assert target.role == "scrutiny_officer"
    [entry] = _denied_entries(db_session, "users.update")
    assert entry.actor_id == user.id and entry.target_id == str(target.id)


# 9.4 deactivate and activate


def test_deactivation_blocks_login_and_tokens(client, admin_headers, user_factory, settings):
    from tests.factories import bearer

    target = user_factory()
    target_headers = bearer(target, settings)
    tokens = client.post(
        "/api/v1/auth/login", json={"email": target.email, "password": DEFAULT_PASSWORD}
    ).json()

    response = client.post(f"{USERS}/{target.id}/deactivate", headers=admin_headers)
    assert response.status_code == 200 and response.json()["is_active"] is False

    assert client.get("/api/v1/auth/me", headers=target_headers).status_code == 401
    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401
    login = client.post(
        "/api/v1/auth/login", json={"email": target.email, "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 401


def test_reactivation(client, admin_headers, user_factory):
    target = user_factory(is_active=False)
    response = client.post(f"{USERS}/{target.id}/activate", headers=admin_headers)
    assert response.json()["is_active"] is True
    login = client.post(
        "/api/v1/auth/login", json={"email": target.email, "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 200


def test_self_deactivation_rejected(client, auth_headers):
    headers, admin = auth_headers(Role.SUPER_ADMIN)
    response = client.post(f"{USERS}/{admin.id}/deactivate", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_self_demotion_rejected(client, auth_headers):
    headers, admin = auth_headers(Role.SUPER_ADMIN)
    response = client.patch(f"{USERS}/{admin.id}", json={"role": "auditor"}, headers=headers)
    assert response.status_code == 409


def test_aicte_admin_cannot_deactivate(client, auth_headers, user_factory, db_session):
    target = user_factory()
    headers, _ = auth_headers(Role.AICTE_ADMIN)
    response = client.post(f"{USERS}/{target.id}/deactivate", headers=headers)
    assert response.status_code == 403
    db_session.refresh(target)
    assert target.is_active is True
    assert len(_denied_entries(db_session, "users.deactivate")) == 1


def test_failed_audit_write_discards_the_change(
    client, admin_headers, user_factory, db_session, monkeypatch
):
    """audit-logging spec: if the audit entry cannot be recorded, the change is not saved."""
    from app.audit.service import AuditService

    original = AuditService.record

    def failing_record(self, action, **kwargs):
        if action == "users.update":
            raise RuntimeError("simulated audit storage failure")
        return original(self, action, **kwargs)

    monkeypatch.setattr(AuditService, "record", failing_record)
    target = user_factory(role=Role.SCRUTINY_OFFICER)
    response = client.patch(
        f"{USERS}/{target.id}", json={"role": "regional_officer"}, headers=admin_headers
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    db_session.expire_all()
    assert db_session.get(type(target), target.id).role == "scrutiny_officer"
