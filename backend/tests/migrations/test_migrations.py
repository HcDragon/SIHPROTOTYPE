"""Migrations on a fresh PostgreSQL database: reversible, and in sync with the models."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import app.db_models  # noqa: F401
from app.core.db import Base
from tests.conftest import alembic_config
from tests.db_utils import temporary_database

APP_TABLES = {"users", "refresh_tokens", "audit_logs"}


def _schema_snapshot(engine) -> dict:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    snapshot = {
        table: {
            "columns": sorted(
                (c["name"], str(c["type"]), c["nullable"]) for c in inspector.get_columns(table)
            ),
            "indexes": sorted(i["name"] for i in inspector.get_indexes(table)),
            "checks": sorted(c["name"] for c in inspector.get_check_constraints(table)),
        }
        for table in tables
    }
    with engine.connect() as conn:
        snapshot["triggers"] = sorted(
            conn.execute(
                text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal ORDER BY tgname")
            ).scalars()
        )
    return snapshot


def test_upgrade_downgrade_upgrade_on_fresh_database(settings):
    with temporary_database(settings.database_url) as url:
        engine = create_engine(url)
        config = alembic_config(url)
        try:
            command.upgrade(config, "head")
            first = _schema_snapshot(engine)
            assert set(first) >= APP_TABLES
            assert first["triggers"] == [
                "audit_logs_reject_truncate",
                "audit_logs_reject_update_delete",
            ]

            command.downgrade(config, "base")
            assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set()

            command.upgrade(config, "head")
            assert _schema_snapshot(engine) == first
        finally:
            engine.dispose()


def test_models_and_migrations_have_no_drift(settings):
    with temporary_database(settings.database_url) as url:
        engine = create_engine(url)
        try:
            command.upgrade(alembic_config(url), "head")
            with engine.connect() as conn:
                context = MigrationContext.configure(conn, opts={"compare_type": True})
                diff = compare_metadata(context, Base.metadata)
            assert diff == [], f"Models and migrations differ: {diff}"
        finally:
            engine.dispose()
