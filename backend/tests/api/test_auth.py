"""Login, current user, and token validation over HTTP against PostgreSQL."""

import pytest
from sqlalchemy import select

from app.access.roles import Role
from app.audit.models import AuditLog
from tests.factories import DEFAULT_PASSWORD
from tests.unit.test_permissions import EXPECTED as EXPECTED_PERMISSIONS

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def _audit(db_session, action):
    return db_session.scalars(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)
    ).all()


def test_successful_login(client, user_factory):
    user = user_factory(role=Role.SCRUTINY_OFFICER)
    response = client.post(LOGIN, json={"email": user.email, "password": DEFAULT_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["access_token"] and body["refresh_token"]


def test_login_email_is_case_insensitive(client, user_factory):
    user = user_factory()
    response = client.post(LOGIN, json={"email": user.email.upper(), "password": DEFAULT_PASSWORD})
    assert response.status_code == 200


def test_successful_login_is_audited(client, user_factory, db_session):
    user = user_factory()
    client.post(LOGIN, json={"email": user.email, "password": DEFAULT_PASSWORD})
    [entry] = _audit(db_session, "auth.login")
    assert entry.outcome == "success"
    assert entry.actor_id == user.id
    assert entry.target_id == str(user.id)


def _failure(client, email, password):
    response = client.post(LOGIN, json={"email": email, "password": password})
    assert response.status_code == 401
    error = response.json()["error"]
    return error["code"], error["message"]


def test_login_failures_are_indistinguishable(client, user_factory):
    active = user_factory()
    inactive = user_factory(is_active=False)
    wrong_password = _failure(client, active.email, "not-the-password")
    unknown_email = _failure(client, "nobody@flowguard.example.org", DEFAULT_PASSWORD)
    deactivated = _failure(client, inactive.email, DEFAULT_PASSWORD)
    assert wrong_password == unknown_email == deactivated
    assert wrong_password[0] == "invalid_credentials"


def test_deactivated_login_issues_no_tokens(client, user_factory):
    user = user_factory(is_active=False)
    response = client.post(LOGIN, json={"email": user.email, "password": DEFAULT_PASSWORD})
    assert "access_token" not in response.text


def test_failed_login_is_audited_without_password(client, db_session):
    client.post(LOGIN, json={"email": "ghost@flowguard.example.org", "password": "hunter2-secret"})
    [entry] = _audit(db_session, "auth.login")
    assert entry.outcome == "failure"
    assert entry.actor_id is None
    assert entry.details == {"email": "ghost@flowguard.example.org"}
    stored = str([entry.before, entry.after, entry.details])
    assert "hunter2-secret" not in stored


def test_login_validation_error(client):
    response = client.post(LOGIN, json={"email": "not-an-email"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("role", list(Role))
def test_me_for_every_role(client, auth_headers, role):
    headers, user = auth_headers(role)
    response = client.get(ME, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["role"] == role.value
    assert set(body["permissions"]) == EXPECTED_PERMISSIONS[role]  # exactly the matrix
    assert "password_hash" not in body


def test_me_requires_authentication(client):
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_me_with_login_token(client, user_factory):
    user = user_factory(role=Role.AUDITOR)
    token = client.post(LOGIN, json={"email": user.email, "password": DEFAULT_PASSWORD}).json()
    response = client.get(ME, headers={"Authorization": f"Bearer {token['access_token']}"})
    assert response.json()["email"] == user.email


@pytest.mark.parametrize("value", ["Bearer garbage", "Bearer a.b.c", "Basic dXNlcjpwYXNz"])
def test_invalid_or_wrong_scheme_tokens(client, value):
    response = client.get(ME, headers={"Authorization": value})
    assert response.status_code == 401
    assert response.json()["error"]["code"] in {"invalid_token", "not_authenticated"}


def test_garbage_bearer_token_is_invalid_token(client):
    response = client.get(ME, headers={"Authorization": "Bearer garbage"})
    assert response.json()["error"]["code"] == "invalid_token"


def test_user_deactivated_after_token_issued(client, auth_headers, db_session):
    headers, user = auth_headers(Role.AUDITOR)
    user.is_active = False
    db_session.commit()
    response = client.get(ME, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_role_changed_after_token_issued(client, auth_headers, db_session):
    headers, user = auth_headers(Role.SCRUTINY_OFFICER)
    user.role = Role.AUDITOR.value
    db_session.commit()
    body = client.get(ME, headers=headers).json()
    assert body["role"] == "auditor"
    assert body["permissions"] == ["audit.read"]
