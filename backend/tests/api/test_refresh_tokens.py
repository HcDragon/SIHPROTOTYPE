"""Refresh-token storage, rotation, reuse detection, logout and revocation."""

from datetime import timedelta

from sqlalchemy import select

from app.audit.models import AuditLog
from app.auth.models import RefreshToken
from app.core.clock import frozen_time, utcnow
from app.core.security import hash_refresh_token
from tests.factories import DEFAULT_PASSWORD

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"


def _login(client, user) -> dict:
    response = client.post(LOGIN, json={"email": user.email, "password": DEFAULT_PASSWORD})
    assert response.status_code == 200
    return response.json()


def _refresh(client, raw):
    return client.post(REFRESH, json={"refresh_token": raw})


def _audit_actions(db_session) -> list[str]:
    return list(db_session.scalars(select(AuditLog.action).order_by(AuditLog.id)))


# 7.1 storage


def test_only_hash_is_stored(client, user_factory, db_session):
    user = user_factory()
    raw = _login(client, user)["refresh_token"]
    stored = db_session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
    assert len(stored) == 1
    assert stored[0].token_hash == hash_refresh_token(raw)
    assert raw not in {stored[0].token_hash, str(stored[0].id), str(stored[0].family_id)}


def test_refresh_ttl_from_settings(client, user_factory, db_session, settings):
    user = user_factory()
    before = utcnow()
    _login(client, user)
    token = db_session.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
    expected = before + timedelta(days=settings.refresh_token_ttl_days)
    assert abs((token.expires_at - expected).total_seconds()) < 60


# 7.2 rotation


def test_successful_rotation(client, user_factory):
    user = user_factory()
    first = _login(client, user)
    response = _refresh(client, first["refresh_token"])
    assert response.status_code == 200
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"}
    )
    assert me.status_code == 200


def test_rotated_token_cannot_be_used_again(client, user_factory):
    user = user_factory()
    raw = _login(client, user)["refresh_token"]
    assert _refresh(client, raw).status_code == 200
    response = _refresh(client, raw)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_unknown_refresh_token(client):
    assert _refresh(client, "not-a-real-token").status_code == 401


def test_expired_refresh_token(client, user_factory, settings):
    user = user_factory()
    raw = _login(client, user)["refresh_token"]
    later = utcnow() + timedelta(days=settings.refresh_token_ttl_days, seconds=1)
    with frozen_time(later):
        response = _refresh(client, raw)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_refresh_for_deactivated_user(client, user_factory, db_session):
    user = user_factory()
    raw = _login(client, user)["refresh_token"]
    user.is_active = False
    db_session.commit()
    assert _refresh(client, raw).status_code == 401


# 7.3 reuse detection


def test_reuse_revokes_whole_family_and_is_audited(client, user_factory, db_session):
    user = user_factory()
    first = _login(client, user)["refresh_token"]
    second = _refresh(client, first).json()["refresh_token"]

    reuse = _refresh(client, first)
    assert reuse.status_code == 401

    assert _refresh(client, second).status_code == 401  # newest token in the family is dead too
    entry = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "auth.refresh_reuse_detected")
    )
    assert entry is not None
    assert entry.target_id == str(user.id)
    assert first not in str(entry.details) and second not in str(entry.details)


def test_reuse_does_not_affect_other_sessions(client, user_factory):
    user = user_factory()
    session_a = _login(client, user)["refresh_token"]
    session_b = _login(client, user)["refresh_token"]
    _refresh(client, session_a)
    _refresh(client, session_a)  # reuse in family A
    assert _refresh(client, session_b).status_code == 200


# 7.4 logout


def test_logout_revokes_and_is_audited(client, user_factory, db_session):
    user = user_factory()
    tokens = _login(client, user)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]}, headers=headers)
    assert response.status_code == 204
    assert _refresh(client, tokens["refresh_token"]).status_code == 401
    assert "auth.logout" in _audit_actions(db_session)


def test_logout_requires_authentication(client, user_factory):
    tokens = _login(client, user_factory())
    response = client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


def test_logout_with_someone_elses_token_rejected(client, user_factory):
    mine = _login(client, user_factory())
    theirs = _login(client, user_factory())
    headers = {"Authorization": f"Bearer {mine['access_token']}"}
    response = client.post(LOGOUT, json={"refresh_token": theirs["refresh_token"]}, headers=headers)
    assert response.status_code == 401
    assert _refresh(client, theirs["refresh_token"]).status_code == 200
