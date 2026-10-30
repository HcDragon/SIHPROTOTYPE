"""Domain errors and the handlers that render them in the standard error format."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import get_request_id

logger = logging.getLogger(__name__)

BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    message = "An unexpected error occurred."
    headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details if details is not None else {}
        super().__init__(self.message)


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested resource was not found."


class Conflict(AppError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class PermissionDenied(AppError):
    status_code = 403
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"
    message = "Authentication is required."
    headers = BEARER_CHALLENGE


class InvalidToken(AppError):
    status_code = 401
    code = "invalid_token"
    message = "The token is invalid or has expired."
    headers = BEARER_CHALLENGE


class InvalidCredentials(AppError):
    status_code = 401
    code = "invalid_credentials"
    message = "Invalid email or password."


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"
    message = "The request is invalid."


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "The service is temporarily unavailable."


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
            "request_id": get_request_id(),
        }
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=error_body(code, message, details), headers=headers
    )


def internal_error_response() -> JSONResponse:
    return error_response(500, AppError.code, AppError.message)


_HTTP_STATUS_CODES = {
    400: ("bad_request", "The request could not be processed."),
    401: (NotAuthenticated.code, NotAuthenticated.message),
    403: (PermissionDenied.code, PermissionDenied.message),
    404: (NotFound.code, NotFound.message),
    405: ("method_not_allowed", "This method is not allowed for this path."),
}


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Only location, message and type: never echo submitted values (they may be passwords).
    details = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return error_response(422, ValidationFailed.code, ValidationFailed.message, details)


async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _HTTP_STATUS_CODES.get(exc.status_code, ("http_error", "Request failed."))
    return error_response(exc.status_code, code, message, headers=getattr(exc, "headers", None))


async def _handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("Integrity error: %s", exc.orig.__class__.__name__ if exc.orig else "unknown")
    return error_response(409, Conflict.code, Conflict.message)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, _handle_integrity_error)  # type: ignore[arg-type]
