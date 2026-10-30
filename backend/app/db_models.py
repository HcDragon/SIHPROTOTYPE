"""Imports every model module so Base.metadata is complete (used by Alembic and tests)."""

import app.audit.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.users.models  # noqa: F401
