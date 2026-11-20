from datetime import (
    UTC,
    datetime,
    timedelta
)

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


_password_hash = PasswordHash.recommended()
DUMMY_HASH = _password_hash.hash('dummy-password-for-timing-protection')


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(
    password: str,
    password_hash: str
) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        'sub': str(user_id),
        'iat': now,
        'exp': now + timedelta(
            minutes=settings.jwt.access_token_ttl_minutes
        )
    }
    return jwt.encode(
        payload=payload,
        key=settings.jwt.jwt_secret,
        algorithm=settings.jwt.jwt_algorithm
    )


def decode_access_token(token: str) -> int:
    payload = jwt.decode(
        token,
        settings.jwt.jwt_secret,
        algorithms=[settings.jwt.jwt_algorithm],
        options={'require': ['exp', 'iat', 'sub']},
    )
    return int(payload['sub'])
