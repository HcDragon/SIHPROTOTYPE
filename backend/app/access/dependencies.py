"""Backend permission enforcement for endpoints (layer 1) and services (layer 2)."""

from typing import Any

from fastapi import Depends, Request

from app.access.permissions import Permission, authorize, has_permission
from app.audit.models import AuditOutcome
from app.audit.service import AuditService
from app.auth.dependencies import CurrentUser
from app.core.db import SessionDep
from app.core.errors import PermissionDenied

__all__ = [
    "AUTHENTICATED",
    "PERMISSION_EXTENSION",
    "authorize",
    "requires",
    "requires_authentication",
]

PERMISSION_EXTENSION = "x-permission"
AUTHENTICATED = "authenticated"


def requires(
    permission: Permission,
    *,
    audit_action: str | None = None,
    target_type: str | None = None,
    target_param: str | None = None,
) -> dict[str, Any]:
    """Route options that enforce a permission and document it in OpenAPI.

    Usage: ``@router.post("", **requires(Permission.USERS_MANAGE, audit_action="users.create"))``
    Write endpoints pass ``audit_action`` so denied attempts are recorded.
    """

    def check_permission(user: CurrentUser, session: SessionDep, request: Request) -> None:
        if has_permission(user.role, permission):
            return
        if audit_action is not None:
            # Committed before raising: nothing else has been changed in this request yet.
            AuditService(session).record_security_event(
                audit_action,
                actor=user,
                outcome=AuditOutcome.DENIED,
                target_type=target_type,
                target_id=request.path_params.get(target_param) if target_param else None,
                details={"required_permission": permission.value},
            )
        raise PermissionDenied()

    return {
        "dependencies": [Depends(check_permission)],
        "openapi_extra": {PERMISSION_EXTENSION: permission.value},
    }


def requires_authentication() -> dict[str, Any]:
    """Route options for endpoints any authenticated user may call."""
    return {"openapi_extra": {PERMISSION_EXTENSION: AUTHENTICATED}}
