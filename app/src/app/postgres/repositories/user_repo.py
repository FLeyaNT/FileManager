from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User


class UserRepository:

    def __init__(
        self,
        session: AsyncSession
    ) -> None:
        self._session = session

    async def get(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_username(
        self,
        username: str
    ) -> User | None:
        stmt = (
            select(User)
            .where(User.username == username)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, user: User) -> None:
        self._session.add(user)
