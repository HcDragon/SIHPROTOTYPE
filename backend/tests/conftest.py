"""Shared fixtures. Tests only ever use the disposable test database (docker compose db_test)."""

import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import dotenv_values

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOTENV = dotenv_values(_REPO_ROOT / ".env")

TEST_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or _DOTENV.get("TEST_DATABASE_URL")
    or "postgresql+psycopg://flowguard_test:change-me-test-password@localhost:5433/flowguard_test"
)

# Must run before any app module reads settings. DATABASE_URL is forced to the test database
# so nothing in the suite can reach the development database.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-signing"
os.environ["ARGON2_TIME_COST"] = "1"
os.environ["ARGON2_MEMORY_COST"] = "1024"
os.environ["ARGON2_PARALLELISM"] = "1"
os.environ["DEMO_PASSWORD"] = "demo-password-for-tests"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Connection, Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import BACKEND_ROOT, Settings, get_settings  # noqa: E402
from app.core.db import create_db_engine  # noqa: E402


def alembic_config(database_url: str, connection: Connection | None = None) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    if connection is not None:
        config.attributes["connection"] = connection
    return config


@pytest.fixture(scope="session")
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    engine = create_db_engine(settings.database_url)
    command.upgrade(alembic_config(settings.database_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """One connection per test inside a transaction that is always rolled back."""
    with engine.connect() as conn:
        outer = conn.begin()
        try:
            yield conn
        finally:
            outer.rollback()


def _savepoint_session(connection: Connection) -> Session:
    # Commits and rollbacks become savepoint releases/rollbacks inside the outer transaction.
    return Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


@pytest.fixture
def db_session(connection: Connection) -> Iterator[Session]:
    session = _savepoint_session(connection)
    yield session
    session.close()


@pytest.fixture
def app(settings: Settings, connection: Connection) -> FastAPI:
    from app.main import create_app

    application = create_app(settings)
    # Every request gets its own session on the test connection, like production gets its own
    # session from the pool, so a rolled-back request does not discard test setup data.
    application.state.session_factory = lambda: _savepoint_session(connection)
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user_factory(db_session: Session, settings: Settings):
    from tests.factories import make_user

    def factory(**kwargs):
        return make_user(db_session, settings, **kwargs)

    return factory


@pytest.fixture
def auth_headers(user_factory, settings: Settings):
    """auth_headers(role) -> (headers, user) for a fresh active user with that role."""
    from tests.factories import bearer

    def factory(role, **kwargs):
        user = user_factory(role=role, **kwargs)
        return bearer(user, settings), user

    return factory
