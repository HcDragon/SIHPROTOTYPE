import uuid
from typing import Any

from app.access.roles import Role
from app.audit.models import AuditOutcome
from app.core.schemas import ResponseModel, UtcDatetime


class AuditLogResponse(ResponseModel):
    id: int
    occurred_at: UtcDatetime
    actor_id: uuid.UUID | None
    actor_role: Role | None
    action: str
    target_type: str | None
    target_id: str | None
    outcome: AuditOutcome
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    details: dict[str, Any] | None
    request_id: str | None
