from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie

from app.core.exceptions import ForbiddenOriginError
from app.postgres.models import User
from .session import SessionDep
from app.services.auth_service import AuthService
from ...core.config import settings
from ...postgres.repositories.user_repo import UserRepository
from ...services.user_dirs import UserDirectories

cookie_scheme = APIKeyCookie(
    name=settings.cookie.name,
    auto_error=False,
    description='JWT в HttpOnly-cookie'
)
AccessCookie = Annotated[str | None, Depends(cookie_scheme)]

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


async def verify_origin(request: Request) -> None:
    if request.method not in _UNSAFE_METHODS:
        return
    origin = request.headers.get('origin')
    if origin and origin not in settings.allowed_origins:
        raise ForbiddenOriginError


@lru_cache(maxsize=1)
def get_user_dirs() -> UserDirectories:
    return UserDirectories(settings.storage_root)

UserDirsDep = Annotated[UserDirectories, Depends(get_user_dirs)]


def get_auth_service(
    session: SessionDep,
    user_dirs: UserDirsDep
) -> AuthService:
    return AuthService(
        session=session,
        user_repo=UserRepository(session),
        user_dirs=user_dirs
    )

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    token: AccessCookie,
    auth: AuthServiceDep,
) -> User:
    return await auth.authenticate(token)

CurrentUser = Annotated[User, Depends(get_current_user)]
