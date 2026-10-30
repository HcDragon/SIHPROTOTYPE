import pytest
from sqlalchemy import func, select

from app.access.roles import Role
from app.audit.models import AuditLog
from app.core.config import load_settings
from app.seed.data import DEMO_DOMAIN, DEMO_USERS
from app.seed.service import SeedRefused, seed_demo_data
from app.users.models import User


def _counts(session):
    return (
        session.scalar(select(func.count()).select_from(User)),
        session.scalar(select(func.count()).where(AuditLog.action == "system.seed")),
    )


def test_seed_is_idempotent(db_session, settings):
    first = seed_demo_data(db_session, settings)
    after_first = _counts(db_session)
    second = seed_demo_data(db_session, settings)
    assert first.created == len(DEMO_USERS)
    assert second.created == 0 and second.existing == len(DEMO_USERS)
    assert _counts(db_session) == after_first  # no new users and no second seed audit entry


def test_every_role_plus_a_deactivated_user():
    active_roles = {u.role for u in DEMO_USERS if u.is_active}
    assert active_roles == set(Role)
    assert any(not u.is_active for u in DEMO_USERS)


def test_emails_are_fictional():
    assert all(u.email.endswith(f"@{DEMO_DOMAIN}") for u in DEMO_USERS)
    assert DEMO_DOMAIN.endswith("example.org")


def test_production_refused_and_writes_nothing(db_session, settings):
    production = load_settings(
        database_url=settings.database_url,
        jwt_secret="a-production-grade-secret-" + "z" * 32,
        app_env="production",
        argon2_time_cost=3,
        argon2_memory_cost=65536,
        argon2_parallelism=4,
    )
    before = _counts(db_session)
    with pytest.raises(SeedRefused):
        seed_demo_data(db_session, production)
    assert _counts(db_session) == before
