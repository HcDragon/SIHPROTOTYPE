"""Concurrent refreshes of one token, with real separate connections and commits.

Runs in its own temporary database because it needs committed data across connections,
which the per-test rollback harness cannot provide (and audit rows cannot be deleted).
"""

import threading

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.core.config import load_settings
from app.main import create_app
from tests.conftest import alembic_config
from tests.db_utils import temporary_database
from tests.factories import DEFAULT_PASSWORD, make_user

TRIALS = 5


@pytest.fixture(scope="module")
def isolated_app(settings):
    with temporary_database(settings.database_url) as url:
        command.upgrade(alembic_config(url), "head")
        app = create_app(
            load_settings(
                database_url=url,
                jwt_secret=settings.jwt_secret,
                app_env="test",
                argon2_time_cost=settings.argon2_time_cost,
                argon2_memory_cost=settings.argon2_memory_cost,
                argon2_parallelism=settings.argon2_parallelism,
            )
        )
        yield app
        app.state.engine.dispose()


def _refresh_twice_at_once(app, raw_token: str) -> list[int]:
    barrier = threading.Barrier(2)
    statuses: list[int] = []

    def worker():
        with TestClient(app) as client:
            barrier.wait()
            response = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_token})
            statuses.append(response.status_code)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return statuses


def test_one_token_cannot_be_rotated_twice_concurrently(isolated_app):
    with Session(isolated_app.state.engine) as session:
        user = make_user(session, isolated_app.state.settings)
        email = user.email

    with TestClient(isolated_app) as client:
        for _ in range(TRIALS):
            raw = client.post(
                "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
            ).json()["refresh_token"]
            assert sorted(_refresh_twice_at_once(isolated_app, raw)) == [200, 401]

    with Session(isolated_app.state.engine) as session:
        reuse_events = session.scalar(
            select(func.count()).where(AuditLog.action == "auth.refresh_reuse_detected")
        )
    # The losing request is indistinguishable from a replayed token: the family is revoked.
    assert reuse_events == TRIALS
