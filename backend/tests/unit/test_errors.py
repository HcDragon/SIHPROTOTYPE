"""Standard error format, request ids, and the 500 path, using a throwaway router."""

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.errors import Conflict, NotAuthenticated
from app.core.schemas import RequestModel
from app.main import create_app


class Body(RequestModel):
    name: str
    count: int


def _client(settings) -> TestClient:
    app = create_app(settings)
    router = APIRouter()

    @router.get("/_test/boom")
    def boom():
        raise RuntimeError("database password=hunter2 exploded")

    @router.get("/_test/conflict")
    def conflict():
        raise Conflict()

    @router.get("/_test/auth")
    def auth():
        raise NotAuthenticated()

    @router.post("/_test/body")
    def body(payload: Body):
        return payload

    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _assert_standard(response, code):
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["code"] == code
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_unknown_path_returns_standard_404(settings):
    response = _client(settings).get("/api/v1/does-not-exist")
    assert response.status_code == 404
    _assert_standard(response, "not_found")


def test_wrong_method_returns_405(settings):
    response = _client(settings).delete("/api/v1/_test/conflict")
    assert response.status_code == 405
    _assert_standard(response, "method_not_allowed")


def test_app_error_rendered(settings):
    response = _client(settings).get("/api/v1/_test/conflict")
    assert response.status_code == 409
    _assert_standard(response, "conflict")


def test_not_authenticated_has_bearer_challenge(settings):
    response = _client(settings).get("/api/v1/_test/auth")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_unhandled_error_is_generic_500(settings):
    response = _client(settings).get("/api/v1/_test/boom")
    assert response.status_code == 500
    _assert_standard(response, "internal_error")
    text = response.text
    assert "hunter2" not in text
    assert "Traceback" not in text
    assert "RuntimeError" not in text


def test_incoming_request_id_is_echoed(settings):
    response = _client(settings).get("/api/v1/_test/conflict", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"
    assert response.json()["error"]["request_id"] == "abc-123"


def test_invalid_incoming_request_id_is_replaced(settings):
    response = _client(settings).get(
        "/api/v1/_test/conflict", headers={"X-Request-ID": "bad id with spaces"}
    )
    assert response.headers["X-Request-ID"] != "bad id with spaces"


def test_validation_error_lists_each_field(settings):
    response = _client(settings).post("/api/v1/_test/body", json={"count": "not-a-number"})
    assert response.status_code == 422
    _assert_standard(response, "validation_error")
    locations = [tuple(d["loc"]) for d in response.json()["error"]["details"]]
    assert ("body", "name") in locations
    assert ("body", "count") in locations
    assert "not-a-number" not in response.text


def test_unknown_field_rejected(settings):
    response = _client(settings).post(
        "/api/v1/_test/body", json={"name": "a", "count": 1, "extra": True}
    )
    assert response.status_code == 422
    _assert_standard(response, "validation_error")
