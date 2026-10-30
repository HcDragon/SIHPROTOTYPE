from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.main import create_app
from tests.db_utils import temporary_database


def test_liveness(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok(client):
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "migrations": "current"}


def test_readiness_database_unavailable(settings):
    bad = load_settings(
        database_url="postgresql+psycopg://nobody:wrong-secret@127.0.0.1:1/missing",
        jwt_secret=settings.jwt_secret,
        app_env="test",
    )
    response = TestClient(create_app(bad)).get("/api/v1/health/db")
    assert response.status_code == 503
    body = response.json()
    assert body["database"] == "unavailable"
    for leaked in ("127.0.0.1", "nobody", "wrong-secret", "missing"):
        assert leaked not in response.text


def test_readiness_pending_migrations(settings):
    with temporary_database(settings.database_url) as empty_url:
        unmigrated = load_settings(
            database_url=empty_url, jwt_secret=settings.jwt_secret, app_env="test"
        )
        app = create_app(unmigrated)
        response = TestClient(app).get("/api/v1/health/db")
        app.state.engine.dispose()
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "ok", "migrations": "pending"}
