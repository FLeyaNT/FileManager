from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.core.config import settings
from app.utils.postgres import (
    check_pg_conn,
    close_pg_conn
)


@asynccontextmanager
async def lifespan(
    _: FastAPI
) -> AsyncGenerator[None, None]:
    await check_pg_conn()

    yield

    await close_pg_conn()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.fastapi.title,
        lifespan=lifespan
    )

    return app
