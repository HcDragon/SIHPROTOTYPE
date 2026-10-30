"""Read-only audit log API. There is deliberately no endpoint that modifies entries."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.access.dependencies import requires
from app.access.permissions import Permission
from app.audit.models import AuditOutcome
from app.audit.repository import AuditFilters
from app.audit.schemas import AuditLogResponse
from app.audit.service import AuditService
from app.auth.dependencies import CurrentUser
from app.core.db import SessionDep
from app.core.pagination import Page, PageParams, SortSpec, page_params, sort_param
from app.core.schemas import UtcDatetime

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get(
    "",
    response_model=Page[AuditLogResponse],
    summary="Query audit entries (newest first by default)",
    **requires(Permission.AUDIT_READ),
)
def list_audit_logs(
    actor: CurrentUser,
    session: SessionDep,
    page: Annotated[PageParams, Depends(page_params)],
    sort: Annotated[SortSpec, Depends(sort_param("occurred_at", "action", default="-occurred_at"))],
    actor_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    target_type: Annotated[str | None, Query(max_length=50)] = None,
    target_id: Annotated[str | None, Query(max_length=64)] = None,
    outcome: Annotated[AuditOutcome | None, Query()] = None,
    occurred_from: Annotated[UtcDatetime | None, Query(alias="from")] = None,
    occurred_to: Annotated[UtcDatetime | None, Query(alias="to")] = None,
) -> Page[AuditLogResponse]:
    filters = AuditFilters(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome.value if outcome else None,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    items, total = AuditService(session).query(actor, filters, page, sort)
    return Page[AuditLogResponse](
        items=[AuditLogResponse.model_validate(entry) for entry in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )
