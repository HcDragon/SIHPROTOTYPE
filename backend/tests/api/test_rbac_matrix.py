"""Every role against every protected route, driven by the app's own route table (design D7).

Each /api/v1 operation must either be listed as public or declare its permission via
`requires(...)` / `requires_authentication()`. A new protected route without a declaration
fails `test_every_route_is_in_the_matrix` until it is added.
"""

import re
import uuid

import pytest
from fastapi import APIRouter, FastAPI

from app.access.dependencies import AUTHENTICATED, PERMISSION_EXTENSION
from app.access.permissions import Permission, has_permission
from app.access.roles import Role
from app.main import create_app

PUBLIC_OPERATIONS = {
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/health/db"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
}
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def operations(app: FastAPI) -> list[tuple[str, str, str | None]]:
    """(METHOD, path, declared permission or None) for every /api/v1 operation."""
    found = []
    for path, item in app.openapi()["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        for method, operation in item.items():
            if method in HTTP_METHODS:
                found.append((method.upper(), path, operation.get(PERMISSION_EXTENSION)))
    return sorted(found)


def unlisted_operations(app: FastAPI) -> list[tuple[str, str]]:
    return [
        (method, path)
        for method, path, permission in operations(app)
        if permission is None and (method, path) not in PUBLIC_OPERATIONS
    ]


def protected_operations(settings) -> list[tuple[str, str, str]]:
    return [(m, p, perm) for m, p, perm in operations(create_app(settings)) if perm is not None]


def _expected_allowed(role: Role, permission: str) -> bool:
    return permission == AUTHENTICATED or has_permission(role, Permission(permission))


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


def test_every_route_is_in_the_matrix(app):
    assert unlisted_operations(app) == []


def test_unlisted_protected_route_is_detected(settings):
    app = create_app(settings)
    router = APIRouter()

    @router.post("/_test/forgot-to-declare")
    def forgot():
        return {}

    app.include_router(router, prefix="/api/v1")
    assert ("POST", "/api/v1/_test/forgot-to-declare") in unlisted_operations(app)


@pytest.mark.parametrize("role", list(Role), ids=lambda r: r.value)
def test_role_against_every_protected_route(client, auth_headers, settings, role):
    headers, _ = auth_headers(role)
    mismatches = []
    for method, path, permission in protected_operations(settings):
        response = client.request(method, _concrete(path), headers=headers, json={})
        allowed = _expected_allowed(role, permission)
        denied = response.status_code == 403
        if allowed == denied or response.status_code == 401:
            mismatches.append((method, path, permission, response.status_code))
    assert mismatches == [], f"{role.value}: responses disagree with the matrix: {mismatches}"


def test_protected_routes_require_authentication(client, settings):
    for method, path, _ in protected_operations(settings):
        response = client.request(method, _concrete(path), json={})
        assert response.status_code == 401, (method, path)
