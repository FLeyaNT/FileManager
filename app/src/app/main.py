import logging

import uvicorn

from .create_app import create_app
from .core.config import settings


logging.basicConfig(
    level=settings.logging.log_level_value,
    format=settings.logging.log_format
)

app = create_app()


if __name__ == '__main__':
    uvicorn.run(
        app='app.main:app',
        host=settings.run.host,
        port=settings.run.port,
        reload=settings.run.reload,
        reload_dirs=['src']
    )
