from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.db import SessionDep
from app.core.dependencies import SettingsDep
from app.core.errors import InvalidToken, NotAuthenticated
from app.core.security import decode_access_token
from app.users.models import User
from app.users.repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")


def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Authenticate the request and reload the user, so deactivation and role changes apply now."""
    if credentials is None:
        raise NotAuthenticated()
    claims = decode_access_token(credentials.credentials, settings)
    user = UserRepository(session).get(claims.user_id)
    if user is None or not user.is_active:
        raise InvalidToken()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
