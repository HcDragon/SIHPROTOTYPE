"""Request transaction boundary and test isolation, on real PostgreSQL."""

import pytest
from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import SessionDep
from app.core.errors import Conflict

pytestmark = pytest.mark.usefixtures("scratch_table")


@pytest.fixture
def scratch_table(connection):
    connection.execute(text("CREATE TEMP TABLE IF NOT EXISTS scratch (value text NOT NULL)"))


@pytest.fixture
def scratch_client(app, client):
    router = APIRouter()

    @router.post("/_test/write-then-fail")
    def write_then_fail(session: SessionDep):
        session.execute(text("INSERT INTO scratch (value) VALUES ('should-roll-back')"))
        raise Conflict()

    @router.post("/_test/write")
    def write(session: SessionDep):
        session.execute(text("INSERT INTO scratch (value) VALUES ('kept')"))
        return {"ok": True}

    app.include_router(router, prefix="/api/v1")
    return client


def _values(connection) -> list[str]:
    return list(connection.execute(text("SELECT value FROM scratch")).scalars())


def test_error_in_request_rolls_back_its_writes(scratch_client, connection):
    response = scratch_client.post("/api/v1/_test/write-then-fail")
    assert response.status_code == 409
    assert _values(connection) == []


def test_successful_request_commits(scratch_client, connection):
    assert scratch_client.post("/api/v1/_test/write").status_code == 200
    assert _values(connection) == ["kept"]


@pytest.fixture(scope="module")
def marker() -> dict:
    return {}


def test_isolation_write(db_session, marker):
    db_session.execute(text("CREATE TABLE IF NOT EXISTS isolation_probe (n int)"))
    db_session.execute(text("INSERT INTO isolation_probe VALUES (1)"))
    db_session.commit()
    marker["written"] = True


def test_isolation_previous_write_is_gone(connection, marker):
    assert marker.get("written")
    exists = connection.execute(text("SELECT to_regclass('isolation_probe')")).scalar()
    assert exists is None
