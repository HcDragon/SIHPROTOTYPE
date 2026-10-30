import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.access.dependencies import requires
from app.access.permissions import Permission
from app.access.roles import Role
from app.auth.dependencies import CurrentUser
from app.core.db import SessionDep
from app.core.dependencies import SettingsDep
from app.core.pagination import Page, PageParams, SortSpec, page_params, sort_param
from app.users.repository import UserFilters
from app.users.schemas import UserCreate, UserResponse, UserUpdate
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])

_MANAGE = {"target_type": "user", "target_param": "user_id"}


@router.get("", response_model=Page[UserResponse], **requires(Permission.USERS_READ))
def list_users(
    actor: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    page: Annotated[PageParams, Depends(page_params)],
    sort: Annotated[
        SortSpec, Depends(sort_param("email", "full_name", "created_at", default="email"))
    ],
    role: Annotated[Role | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> Page[UserResponse]:
    items, total = UserService(session, settings, actor).list(
        UserFilters(role=role, is_active=is_active), page, sort
    )
    return Page[UserResponse](
        items=[UserResponse.model_validate(u) for u in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/{user_id}", response_model=UserResponse, **requires(Permission.USERS_READ))
def get_user(
    user_id: uuid.UUID, actor: CurrentUser, session: SessionDep, settings: SettingsDep
) -> UserResponse:
    return UserResponse.model_validate(UserService(session, settings, actor).get(user_id))


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    **requires(Permission.USERS_MANAGE, audit_action="users.create", target_type="user"),
)
def create_user(
    payload: UserCreate, actor: CurrentUser, session: SessionDep, settings: SettingsDep
) -> UserResponse:
    return UserResponse.model_validate(UserService(session, settings, actor).create(payload))


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    **requires(Permission.USERS_MANAGE, audit_action="users.update", **_MANAGE),
)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    actor: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> UserResponse:
    user = UserService(session, settings, actor).update(user_id, payload)
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    **requires(Permission.USERS_MANAGE, audit_action="users.deactivate", **_MANAGE),
)
def deactivate_user(
    user_id: uuid.UUID, actor: CurrentUser, session: SessionDep, settings: SettingsDep
) -> UserResponse:
    return UserResponse.model_validate(UserService(session, settings, actor).deactivate(user_id))


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    **requires(Permission.USERS_MANAGE, audit_action="users.activate", **_MANAGE),
)
def activate_user(
    user_id: uuid.UUID, actor: CurrentUser, session: SessionDep, settings: SettingsDep
) -> UserResponse:
    return UserResponse.model_validate(UserService(session, settings, actor).activate(user_id))
