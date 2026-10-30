"""Idempotent demo seeding: creates missing demo users, never modifies existing ones."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.config import Settings
from app.core.security import hash_password
from app.seed.data import DEMO_USERS
from app.users.models import User
from app.users.repository import UserRepository


class SeedRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedResult:
    created: int
    existing: int


def seed_demo_data(session: Session, settings: Settings) -> SeedResult:
    if settings.is_production:
        raise SeedRefused("Refusing to seed demo data when APP_ENV is production.")

    users = UserRepository(session)
    created = 0
    for demo in DEMO_USERS:
        if users.get_by_email(demo.email) is not None:
            continue
        users.add(
            User(
                id=uuid.uuid4(),
                email=demo.email,
                full_name=demo.full_name,
                role=demo.role.value,
                password_hash=hash_password(settings.demo_password, settings),
                is_active=demo.is_active,
            )
        )
        created += 1

    if created:
        AuditService(session).record(
            "system.seed", target_type="system", details={"users_created": created}
        )
    return SeedResult(created=created, existing=len(DEMO_USERS) - created)
