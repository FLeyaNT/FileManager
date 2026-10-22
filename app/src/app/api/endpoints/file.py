import logging

import pathlib
from typing import Any, Annotated

from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Path
)


logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path('D:/Dev/').resolve()

router = APIRouter(
    prefix='/file',
    tags=['File'],
)


def resolve_safe(user_path: str) -> pathlib.Path:
    target = (BASE_DIR / user_path).resolve()
    logger.debug(f'Filepath: {target}')
    if not target.is_relative_to(BASE_DIR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Доступ за пределы корня запрещен'
        )
    return target


def build_listings(user_path: str) -> list[dict[str, Any]]:
    target = resolve_safe(user_path)

    if not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Путь не найден'
        )
    if not target.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Это не директория'
        )

    items = []
    for entry in target.iterdir():
        stat = entry.stat()
        items.append(
            {
                'name': entry.name,
                'is_dir': entry.is_dir(),
                'size': stat.st_size if entry.is_file() else None,
                'modified': stat.st_mtime,
            }
        )
    return items

@router.get(
    "/",
    response_model=list[dict[str, Any]],
    status_code=status.HTTP_200_OK
)
async def list_root():
    return build_listings('')


@router.get(
    '/{file_path:path}',
    response_model=list[dict[str, Any]],
    status_code=status.HTTP_200_OK
)
async def list_files(
    file_path: Annotated[str, Path()]
):
    return build_listings(file_path)


