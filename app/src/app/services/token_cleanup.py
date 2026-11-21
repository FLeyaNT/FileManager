import logging

from anyio import sleep
from sqlalchemy.exc import SQLAlchemyError

from app.postgres.config import AsyncSessionLocal
from app.postgres.repositories.revoked_token_repo import RevokedTokenRepository


logger = logging.getLogger(__name__)


async def clean_expired_tokens(interval_seconds: int) -> None:
    while True:
        try:
            async with AsyncSessionLocal.begin() as session:
                await RevokedTokenRepository(session).delete_expired()
        except (SQLAlchemyError, OSError):
            logger.exception('Не удалось очистить просроченные записи об отозванных токенах')
        await sleep(interval_seconds)
