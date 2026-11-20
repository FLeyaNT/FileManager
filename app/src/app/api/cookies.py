from fastapi import Response

from app.core.config import settings


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie.name,
        value=token,
        max_age=settings.jwt.access_token_ttl_minutes * 60,
        path='/',
        httponly=True,
        secure=settings.cookie.secure,
        samesite=settings.cookie.samesite
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.cookie.name,
        path='/',
        httponly=True,
        secure=settings.cookie.secure,
        samesite=settings.cookie.samesite
    )
