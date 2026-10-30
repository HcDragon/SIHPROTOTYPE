"""Database readiness: reachability and whether the schema is at the latest migration."""

import logging
from dataclasses import dataclass
from functools import lru_cache

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.core.config import BACKEND_ROOT

logger = logging.getLogger(__name__)

STATEMENT_TIMEOUT_MS = 2000


@dataclass(frozen=True)
class DatabaseStatus:
    database: str  # "ok" | "unavailable"
    migrations: str  # "current" | "pending" | "unknown"

    @property
    def healthy(self) -> bool:
        return self.database == "ok" and self.migrations == "current"


@lru_cache
def head_revisions() -> frozenset[str]:
    script = ScriptDirectory.from_config(Config(str(BACKEND_ROOT / "alembic.ini")))
    return frozenset(script.get_heads())


def check_database(engine: Engine) -> DatabaseStatus:
    try:
        with engine.connect() as conn:
            conn.execute(text(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}"))
            conn.execute(text("SELECT 1"))
            try:
                current = frozenset(
                    conn.execute(text("SELECT version_num FROM alembic_version")).scalars()
                )
            except ProgrammingError:
                current = frozenset()  # alembic_version table missing: nothing applied yet
            conn.rollback()
    except DBAPIError as exc:
        # Log the driver error class only; messages can contain host and user names.
        logger.warning("Database health check failed: %s", type(exc.orig).__name__)
        return DatabaseStatus(database="unavailable", migrations="unknown")

    migrations = "current" if current == head_revisions() else "pending"
    return DatabaseStatus(database="ok", migrations=migrations)
