from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
    timedelta
)
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


_password_hash = PasswordHash.recommended()
DUMMY_HASH = _password_hash.hash('dummy-password-for-timing-protection')


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: int
    jti: UUID
    expires_at: datetime


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
        'jti': str(uuid4()),
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


def decode_access_token(token: str) -> AccessTokenClaims:
    payload = jwt.decode(
        token,
        settings.jwt.jwt_secret,
        algorithms=[settings.jwt.jwt_algorithm],
        options={'require': ['exp', 'iat', 'sub']},
    )
    user_id = int(payload['sub'])
    expires_at = int(payload['exp'])
    jti = payload.get('jti')
    if jti is None:
        issued_at = int(payload['iat'])
        token_id = uuid5(NAMESPACE_URL, f'filemanager:legacy:{user_id}:{issued_at}:{expires_at}')
    else:
        token_id = UUID(jti)
    return AccessTokenClaims(user_id, token_id, datetime.fromtimestamp(expires_at, UTC))
