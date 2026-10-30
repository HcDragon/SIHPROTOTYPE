"""Audit log query API and the absence of any modification endpoint."""

import pytest

from app.access.roles import Role

AUDIT = "/api/v1/audit-logs"


@pytest.fixture
def changed_user(client, auth_headers, user_factory):
    """A user whose role a Super Admin changed twice, producing two audit entries."""
    admin_headers, admin = auth_headers(Role.SUPER_ADMIN)
    target = user_factory(role=Role.SCRUTINY_OFFICER)
    for role in ("regional_officer", "evc_coordinator"):
        response = client.patch(
            f"/api/v1/users/{target.id}", json={"role": role}, headers=admin_headers
        )
        assert response.status_code == 200
    return target, admin


@pytest.mark.parametrize("role", [Role.AUDITOR, Role.AICTE_ADMIN, Role.SUPER_ADMIN])
def test_authorized_readers_filter_by_target(client, auth_headers, changed_user, role):
    target, admin = changed_user
    headers, _ = auth_headers(role)
    body = client.get(
        f"{AUDIT}?target_type=user&target_id={target.id}&action=users.update", headers=headers
    ).json()
    assert body["total"] == 2
    newest, oldest = body["items"]
    assert newest["id"] > oldest["id"]  # newest first by default
    assert newest["after"]["role"] == "evc_coordinator"
    assert newest["before"]["role"] == "regional_officer"
    assert newest["actor_id"] == str(admin.id)
    assert newest["actor_role"] == "super_admin"
    assert newest["outcome"] == "success"
    assert newest["request_id"]
    assert newest["occurred_at"].endswith(("Z", "+00:00"))


def test_filter_by_actor_and_outcome(client, auth_headers, changed_user):
    _, admin = changed_user
    headers, _ = auth_headers(Role.AUDITOR)
    body = client.get(f"{AUDIT}?actor_id={admin.id}&outcome=success", headers=headers).json()
    assert body["total"] == 2
    assert all(item["actor_id"] == str(admin.id) for item in body["items"])


def test_time_range_filter(client, auth_headers, changed_user):
    headers, _ = auth_headers(Role.AUDITOR)
    body = client.get(f"{AUDIT}?to=2000-01-01T00:00:00Z", headers=headers).json()
    assert body["total"] == 0


def test_inverted_time_range_rejected(client, auth_headers):
    headers, _ = auth_headers(Role.AUDITOR)
    response = client.get(
        f"{AUDIT}?from=2026-02-01T00:00:00Z&to=2026-01-01T00:00:00Z", headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_invalid_outcome_rejected(client, auth_headers):
    headers, _ = auth_headers(Role.AUDITOR)
    assert client.get(f"{AUDIT}?outcome=maybe", headers=headers).status_code == 422


def test_no_secrets_in_audit_entries(client, auth_headers, user_factory):
    from tests.factories import DEFAULT_PASSWORD

    user = user_factory()
    tokens = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    ).json()
    client.post("/api/v1/auth/login", json={"email": user.email, "password": "Wrong-Pass-123"})
    client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    admin_headers, _ = auth_headers(Role.SUPER_ADMIN)
    client.post(
        "/api/v1/users",
        json={
            "email": "audited@flowguard.example.org",
            "full_name": "Audited",
            "role": "auditor",
            "password": "Created-Pass-456",
        },
        headers=admin_headers,
    )
    headers, _ = auth_headers(Role.AUDITOR)
    text = client.get(f"{AUDIT}?page_size=100", headers=headers).text
    for secret in (
        DEFAULT_PASSWORD,
        "Wrong-Pass-123",
        "Created-Pass-456",
        tokens["refresh_token"],
        tokens["access_token"],
        "$argon2",
    ):
        assert secret not in text


@pytest.mark.parametrize(
    "role", [Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER, Role.INSTITUTION_REPRESENTATIVE]
)
def test_unauthorized_roles_denied(client, auth_headers, role):
    headers, _ = auth_headers(role)
    response = client.get(AUDIT, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("role", list(Role), ids=lambda r: r.value)
def test_no_modification_endpoints(client, auth_headers, changed_user, method, role):
    headers, _ = auth_headers(role)
    for path in (AUDIT, f"{AUDIT}/1"):
        response = client.request(method, path, headers=headers, json={"action": "tampered"})
        assert response.status_code in (404, 405), (method, path, response.status_code)


def test_mixed_naive_and_aware_range_is_handled(client, auth_headers):
    headers, _ = auth_headers(Role.AUDITOR)
    response = client.get(
        f"{AUDIT}?from=2026-01-01T00:00:00&to=2026-02-01T00:00:00%2B05:30", headers=headers
    )
    assert response.status_code == 200
