import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.access.roles import Role
from app.core.pagination import PageParams, SortSpec
from app.users.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True)
class UserFilters:
    role: Role | None = None
    is_active: bool | None = None


SORTABLE_COLUMNS = {
    "email": User.email,
    "full_name": User.full_name,
    "created_at": User.created_at,
}


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == normalize_email(email)))

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def count_active_with_role(self, role: Role) -> int:
        return self.session.scalar(
            select(func.count()).where(User.role == role.value, User.is_active.is_(True))
        )

    def list(
        self, filters: UserFilters, page: PageParams, sort: SortSpec
    ) -> tuple[list[User], int]:
        total = self.session.scalar(self._filtered(select(func.count()).select_from(User), filters))
        column = SORTABLE_COLUMNS[sort.field]
        order = column.desc() if sort.descending else column.asc()
        rows = self.session.scalars(
            self._filtered(select(User), filters)
            .order_by(order, User.id)
            .offset(page.offset)
            .limit(page.page_size)
        ).all()
        return list(rows), total or 0

    @staticmethod
    def _filtered[T: Select](query: T, filters: UserFilters) -> T:
        if filters.role is not None:
            query = query.where(User.role == filters.role.value)
        if filters.is_active is not None:
            query = query.where(User.is_active.is_(filters.is_active))
        return query
