import asyncio
import logging
from datetime import UTC, datetime

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    UserAlreadyExistsError,
    AuthenticationError,
    StorageError,
)
from app.postgres.models import Directory, User
from app.postgres.repositories.revoked_token_repo import RevokedTokenRepository
from app.postgres.repositories.user_repo import UserRepository
from app.core.security import (
    AccessTokenClaims,
    DUMMY_HASH,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.services.user_dirs import UserDirectories


logger = logging.getLogger(__name__)


class AuthService:

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        user_dirs: UserDirectories
    ) -> None:
        self._session = session
        self._users = user_repo
        self._dirs = user_dirs
        self._revoked_tokens = RevokedTokenRepository(session)

    @staticmethod
    def _read_token(token: str | None) -> AccessTokenClaims | None:
        if token is None:
            return None
        try:
            return decode_access_token(token)
        except (jwt.PyJWTError, ValueError, OverflowError):
            return None

    async def authenticate(self, token: str | None) -> User:
        claims = self._read_token(token)
        if claims is None or await self._revoked_tokens.contains(claims.jti):
            raise AuthenticationError('Не удалось проверить учётные данные')

        user = await self._users.get(claims.user_id)
        if user is None or claims.expires_at <= datetime.now(UTC):
            raise AuthenticationError('Не удалось проверить учётные данные')
        return user

    async def logout(self, token: str | None) -> None:
        claims = self._read_token(token)
        if claims is None:
            return
        await self._revoked_tokens.add(claims.jti, claims.expires_at)
        await self._session.commit()

    async def register(
        self,
        username: str,
        password: str
    ) -> User:
        password_hash = await asyncio.to_thread(
            hash_password,
            password
        )
        # noinspection PyArgumentList
        user = User(
            username=username,
            password_hash=password_hash
        )
        self._users.add(user)

        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            raise UserAlreadyExistsError from None

        user_id = user.id
        try:
            await self._dirs.create_personal_dir(user_id)
        except OSError as exc:
            await self._session.rollback()
            logger.exception("Не удалось создать папку пользователя %s", user_id)
            raise StorageError from exc

        try:
            # noinspection PyArgumentList
            self._session.add(Directory(owner_id=user_id, name=''))
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            await self._dirs.remove_empty(user_id)
            raise

        return user

    async def login(
        self,
        username: str,
        password: str
    ) -> str:
        user = await self._users.get_by_username(username)

        stored_hash = user.password_hash if user else DUMMY_HASH
        password_ok = await asyncio.to_thread(
            verify_password,
            password,
            stored_hash
        )

        if user is None or not password_ok:
            raise AuthenticationError

        return create_access_token(user.id)
