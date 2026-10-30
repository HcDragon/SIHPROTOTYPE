from fastapi import APIRouter, Response, status

from app.access.dependencies import requires_authentication
from app.access.permissions import permissions_for
from app.auth.dependencies import CurrentUser
from app.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.auth.service import AuthService
from app.core.db import SessionDep
from app.core.dependencies import SettingsDep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, summary="Log in with email and password")
def login(payload: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    return AuthService(session, settings).login(payload.email, payload.password)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate a refresh token")
def refresh(payload: RefreshRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    return AuthService(session, settings).refresh(payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke the session's refresh tokens",
    **requires_authentication(),
)
def logout(
    payload: LogoutRequest, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> Response:
    AuthService(session, settings).logout(user, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="The authenticated user",
    **requires_authentication(),
)
def me(user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role_enum,
        permissions=sorted(permissions_for(user.role)),
    )
