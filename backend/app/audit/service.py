"""Recording and querying audit entries. Every state-changing service records here."""

from typing import Any, Protocol

from pydantic_core import to_jsonable_python
from sqlalchemy.orm import Session

from app.access.permissions import Permission, authorize
from app.audit.models import AuditLog, AuditOutcome
from app.audit.repository import AuditFilters, AuditRepository
from app.core.clock import utcnow
from app.core.errors import ValidationFailed
from app.core.logging import is_sensitive_key
from app.core.pagination import PageParams, SortSpec
from app.core.request_id import get_request_id


class AuditActor(Protocol):
    id: Any
    role: str


def scrub(value: Any) -> Any:
    """Drop sensitive keys (passwords, hashes, tokens, secrets) at any depth."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not is_sensitive_key(str(k))}
    if isinstance(value, list | tuple):
        return [scrub(v) for v in value]
    return value


def _prepare(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    return scrub(to_jsonable_python(payload))


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AuditRepository(session)

    def record(
        self,
        action: str,
        *,
        actor: AuditActor | None = None,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        target_type: str | None = None,
        target_id: Any = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Add an entry to the current transaction; it is saved or discarded with the change."""
        entry = AuditLog(
            occurred_at=utcnow(),
            actor_id=actor.id if actor is not None else None,
            actor_role=actor.role if actor is not None else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            outcome=outcome.value,
            before=_prepare(before),
            after=_prepare(after),
            details=_prepare(details),
            request_id=get_request_id(),
        )
        return self.repository.add(entry)

    def record_security_event(self, action: str, **kwargs: Any) -> AuditLog:
        """Record and commit immediately, for rejected requests whose transaction will roll back.

        Only call this before the request has changed any other data (failed login, denied
        permission, refresh-token reuse), so the commit cannot save half-finished work.
        """
        entry = self.record(action, **kwargs)
        self.session.commit()
        return entry

    def query(
        self, actor: AuditActor, filters: AuditFilters, page: PageParams, sort: SortSpec
    ) -> tuple[list[AuditLog], int]:
        authorize(actor, Permission.AUDIT_READ)
        start, end = filters.occurred_from, filters.occurred_to
        if start is not None and end is not None and start > end:
            raise ValidationFailed(
                details=[
                    {
                        "loc": ["query", "from"],
                        "msg": "'from' must not be later than 'to'.",
                        "type": "time_range",
                    }
                ]
            )
        return self.repository.list(filters, page, sort)
