from typing import Annotated

from fastapi import APIRouter, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.util.preloaded import sql_util

from app.api.cookies import set_auth_cookie, clear_auth_cookie
from app.api.schemas.auth import LoginRequest, UserCreate, UserOut
from app.api.deps.auth import AuthServiceDep, CurrentUser


router = APIRouter(prefix='/auth', tags=['Auth'])


@router.post(
    '/register',
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED
)
async def register(
    body: UserCreate,
    auth: AuthServiceDep
):
    return await auth.register(
        body.username,
        body.password
    )


@router.post(
    '/login',
    status_code=status.HTTP_204_NO_CONTENT
)
async def login(
    body: LoginRequest,
    auth: AuthServiceDep,
    response: Response
):
    token = await auth.login(
        body.username,
        body.password
    )
    set_auth_cookie(response, token)


@router.post(
    '/logout',
    status_code=status.HTTP_204_NO_CONTENT
)
async def logout(response: Response):
    clear_auth_cookie(response)


@router.get(
    '/me',
    response_model=UserOut
)
async def me(user: CurrentUser):
    return user
