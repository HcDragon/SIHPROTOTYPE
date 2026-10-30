"""Super Admin user administration. Every change is audited with before/after values."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.access.dependencies import authorize
from app.access.permissions import Permission
from app.access.roles import Role
from app.audit.service import AuditService
from app.auth.service import AuthService
from app.core.config import Settings
from app.core.errors import Conflict, NotFound
from app.core.pagination import PageParams, SortSpec
from app.core.security import hash_password
from app.users.models import User
from app.users.repository import UserFilters, UserRepository, normalize_email
from app.users.schemas import UserCreate, UserUpdate

AUDIT_TARGET = "user"


def snapshot(user: User) -> dict[str, Any]:
    """Fields recorded in the audit log. Never includes the password hash."""
    return {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
    }


class UserService:
    def __init__(self, session: Session, settings: Settings, actor: User) -> None:
        self.session = session
        self.settings = settings
        self.actor = actor
        self.users = UserRepository(session)
        self.audit = AuditService(session)

    def list(
        self, filters: UserFilters, page: PageParams, sort: SortSpec
    ) -> tuple[list[User], int]:
        authorize(self.actor, Permission.USERS_READ)
        return self.users.list(filters, page, sort)

    def get(self, user_id: uuid.UUID) -> User:
        authorize(self.actor, Permission.USERS_READ)
        return self._get(user_id)

    def create(self, data: UserCreate) -> User:
        authorize(self.actor, Permission.USERS_MANAGE)
        email = normalize_email(data.email)
        if self.users.get_by_email(email) is not None:
            raise Conflict("A user with this email already exists.")
        user = self.users.add(
            User(
                id=uuid.uuid4(),
                email=email,
                full_name=data.full_name,
                role=data.role.value,
                password_hash=hash_password(data.password, self.settings),
                is_active=True,
            )
        )
        self._record("users.create", user, before=None)
        return user

    def update(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        authorize(self.actor, Permission.USERS_MANAGE)
        user = self._get(user_id)
        before = snapshot(user)
        if data.role is not None and data.role.value != user.role:
            if user.id == self.actor.id:
                raise Conflict("You cannot change your own role.")
            self._ensure_super_admin_remains(user)
            user.role = data.role.value
        if data.full_name is not None:
            user.full_name = data.full_name
        self.session.flush()
        self._record("users.update", user, before=before)
        return user

    def deactivate(self, user_id: uuid.UUID) -> User:
        authorize(self.actor, Permission.USERS_MANAGE)
        user = self._get(user_id)
        if user.id == self.actor.id:
            raise Conflict("You cannot deactivate your own account.")
        if not user.is_active:
            return user
        self._ensure_super_admin_remains(user)
        before = snapshot(user)
        user.is_active = False
        AuthService(self.session, self.settings).revoke_all(user.id)
        self.session.flush()
        self._record("users.deactivate", user, before=before)
        return user

    def activate(self, user_id: uuid.UUID) -> User:
        authorize(self.actor, Permission.USERS_MANAGE)
        user = self._get(user_id)
        if user.is_active:
            return user
        before = snapshot(user)
        user.is_active = True
        self.session.flush()
        self._record("users.activate", user, before=before)
        return user

    def _get(self, user_id: uuid.UUID) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFound()
        return user

    def _ensure_super_admin_remains(self, user: User) -> None:
        """Reject a change that removes the last active Super Admin."""
        removing_super_admin = user.role == Role.SUPER_ADMIN.value and user.is_active
        if removing_super_admin and self.users.count_active_with_role(Role.SUPER_ADMIN) <= 1:
            raise Conflict("At least one active Super Admin must remain.")

    def _record(self, action: str, user: User, before: dict[str, Any] | None) -> None:
        self.audit.record(
            action,
            actor=self.actor,
            target_type=AUDIT_TARGET,
            target_id=user.id,
            before=before,
            after=snapshot(user),
        )
