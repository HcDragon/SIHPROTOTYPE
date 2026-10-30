"""Audit log persistence. Append and read only: there is deliberately no update or delete."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.core.pagination import PageParams, SortSpec


@dataclass(frozen=True)
class AuditFilters:
    actor_id: uuid.UUID | None = None
    action: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    outcome: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None


SORTABLE_COLUMNS = {"occurred_at": AuditLog.occurred_at, "action": AuditLog.action}


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entry: AuditLog) -> AuditLog:
        self.session.add(entry)
        self.session.flush()
        return entry

    def list(
        self, filters: AuditFilters, page: PageParams, sort: SortSpec
    ) -> tuple[list[AuditLog], int]:
        query = self._filtered(select(AuditLog), filters)
        total = self.session.scalar(
            self._filtered(select(func.count()).select_from(AuditLog), filters)
        )
        column = SORTABLE_COLUMNS[sort.field]
        order = column.desc() if sort.descending else column.asc()
        tiebreak = AuditLog.id.desc() if sort.descending else AuditLog.id.asc()
        rows = self.session.scalars(
            query.order_by(order, tiebreak).offset(page.offset).limit(page.page_size)
        ).all()
        return list(rows), total or 0

    @staticmethod
    def _filtered[T: Select](query: T, filters: AuditFilters) -> T:
        if filters.actor_id is not None:
            query = query.where(AuditLog.actor_id == filters.actor_id)
        if filters.action is not None:
            query = query.where(AuditLog.action == filters.action)
        if filters.target_type is not None:
            query = query.where(AuditLog.target_type == filters.target_type)
        if filters.target_id is not None:
            query = query.where(AuditLog.target_id == filters.target_id)
        if filters.outcome is not None:
            query = query.where(AuditLog.outcome == filters.outcome)
        if filters.occurred_from is not None:
            query = query.where(AuditLog.occurred_at >= filters.occurred_from)
        if filters.occurred_to is not None:
            query = query.where(AuditLog.occurred_at <= filters.occurred_to)
        return query
