import asyncio
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundError,
    UserAlreadyExistsError,
    AuthenticationError,
    StorageError,
)
from app.postgres.models import Directory, User
from app.postgres.repositories.user_repo import UserRepository
from app.core.security import hash_password, DUMMY_HASH, verify_password, create_access_token
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

    async def get_user(
        self,
        user_id: int
    ) -> User:
        user = await self._users.get(user_id)
        if not user:
            raise NotFoundError('Пользователь не найден')
        return user

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
