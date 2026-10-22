import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.postgres.config import async_engine


logger = logging.getLogger(__name__)


async def check_pg_conn() -> None:
    try:
        async with asyncio.timeout(2):
            async with async_engine.connect() as conn:
                await conn.execute(text('SELECT 1'))
    except TimeoutError:
        logger.warning('DB health check timed out')
    except (SQLAlchemyError, OSError) as e:
        logger.warning('DB health check failed: %s', e)

    logger.info('DB successfully connected')


async def close_pg_conn() -> None:
    await async_engine.dispose()
