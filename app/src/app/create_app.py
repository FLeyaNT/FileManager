from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles

from app.api.api import router
from app.api.deps.auth import verify_origin
from app.api.handlers import register_exception_handlers
from app.api.middlewares.body_limit import BodyLimitMiddleware
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
        lifespan=lifespan,
        dependencies=[Depends(verify_origin)]
    )

    # PyCharm may flag Starlette's ParamSpec for this middleware factory.
    # noinspection PyTypeChecker
    app.add_middleware(
        BodyLimitMiddleware,
        max_bytes=settings.files.max_request_size,
    )

    register_exception_handlers(app)

    app.include_router(router)

    frontend = Path(__file__).resolve().parents[3] / 'frontend' / 'dist'
    if (frontend / 'index.html').is_file():
        app.mount('/', StaticFiles(directory=frontend, html=True), name='frontend')

    return app
