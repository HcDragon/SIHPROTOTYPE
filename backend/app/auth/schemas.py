import uuid

from pydantic import EmailStr, Field

from app.access.permissions import Permission
from app.access.roles import Role
from app.core.schemas import RequestModel, ResponseModel


class LoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class RefreshRequest(RequestModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(RequestModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class TokenResponse(ResponseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 (OAuth token type, not a secret)
    expires_in: int = Field(description="Access token lifetime in seconds.")


class CurrentUserResponse(ResponseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    permissions: list[Permission]
