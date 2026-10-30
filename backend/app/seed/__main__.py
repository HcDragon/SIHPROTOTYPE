"""Seed fictional demo data: uv run python -m app.seed"""

import sys

from sqlalchemy.orm import Session

from app.core.config import ConfigurationError, get_settings
from app.core.db import create_db_engine
from app.seed.data import DEMO_USERS
from app.seed.service import SeedRefused, seed_demo_data


def main() -> int:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1
    engine = create_db_engine(settings.database_url)
    try:
        with Session(engine) as session, session.begin():
            result = seed_demo_data(session, settings)
    except SeedRefused as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(f"Demo users created: {result.created}, already present: {result.existing}")
    print("Demo logins (password: the DEMO_PASSWORD value from your .env):")
    for demo in DEMO_USERS:
        note = "" if demo.is_active else "  [deactivated: cannot log in]"
        print(f"  {demo.role.value:<28} {demo.email}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
