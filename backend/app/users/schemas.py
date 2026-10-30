import uuid

from pydantic import EmailStr, Field, model_validator

from app.access.roles import Role
from app.core.schemas import RequestModel, ResponseModel, UtcDatetime

MIN_PASSWORD_LENGTH = 12


class UserResponse(ResponseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: UtcDatetime
    updated_at: UtcDatetime


class UserCreate(RequestModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)


class UserUpdate(RequestModel):
    """Only name and role can change here; email and password cannot."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "UserUpdate":
        if self.full_name is None and self.role is None:
            raise ValueError("Provide at least one of full_name or role")
        return self
