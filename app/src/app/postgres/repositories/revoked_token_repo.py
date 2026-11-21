from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.postgres.models import revoked_tokens


class RevokedTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def contains(self, jti: UUID) -> bool:
        query = select(exists().where(revoked_tokens.c.jti == jti))
        return bool(await self._session.scalar(query))

    async def add(self, jti: UUID, expires_at: datetime) -> None:
        query = (
            insert(revoked_tokens)
            .values(jti=jti, expires_at=expires_at)
            .on_conflict_do_nothing(index_elements=[revoked_tokens.c.jti])
        )
        await self._session.execute(query)

    async def delete_expired(self) -> None:
        await self._session.execute(
            delete(revoked_tokens).where(revoked_tokens.c.expires_at <= datetime.now(UTC))
        )
