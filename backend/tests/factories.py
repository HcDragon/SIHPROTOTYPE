"""Test data builders. All data is fictional."""

import uuid

from sqlalchemy.orm import Session

from app.access.roles import Role
from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.users.models import User

DEFAULT_PASSWORD = "correct-horse-battery-staple"


def make_user(
    session: Session,
    settings: Settings,
    *,
    role: Role = Role.AUDITOR,
    email: str | None = None,
    full_name: str = "Test Person",
    password: str = DEFAULT_PASSWORD,
    is_active: bool = True,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email or f"{role.value}.{uuid.uuid4().hex[:8]}@flowguard.example.org",
        full_name=full_name,
        password_hash=hash_password(password, settings),
        role=role.value,
        is_active=is_active,
    )
    session.add(user)
    session.commit()  # releases a savepoint; the test's outer transaction still rolls back
    return user


def bearer(user: User, settings: Settings) -> dict[str, str]:
    token, _ = create_access_token(user.id, user.role, settings)
    return {"Authorization": f"Bearer {token}"}
