from typing import Annotated

from fastapi import Depends
from sqlalchemy import text

from app.core.config import settings
from app.postgres.repositories.file_repo import FileRepository
from .auth import CurrentUser, UserDirsDep
from app.services.file_service import FileService
from .session import SessionDep
from ...core.exceptions import StorageBusyError
from ...services.quota_storage import QuotaStorage
from ...services.zip_service import ZipService


async def get_quota_storage(
    user: CurrentUser,
    dirs: UserDirsDep,
) -> QuotaStorage:
    return await QuotaStorage.create_with_limits(
        root=dirs.path(user.id),
        chunk_size=settings.files.chunk_size,
        byte_limit=settings.files.max_user_size,
        entry_limit=settings.files.max_user_entries,
    )


QuotaStorageDep = Annotated[QuotaStorage, Depends(get_quota_storage)]


async def _lock_storage(session: SessionDep, user_id: int, *, shared: bool) -> None:
    query = (
        'SELECT pg_try_advisory_xact_lock_shared(:namespace, :user_id)'
        if shared else 'SELECT pg_try_advisory_xact_lock(:namespace, :user_id)'
    )
    locked = await session.scalar(
        text(query), {'namespace': 41812, 'user_id': user_id}
    )
    if not locked:
        raise StorageBusyError()


async def get_storage(user: CurrentUser, dirs: UserDirsDep, session: SessionDep) -> QuotaStorage:
    await _lock_storage(session, user.id, shared=False)
    return await get_quota_storage(user, dirs)

StorageDep = Annotated[QuotaStorage, Depends(get_storage)]


async def get_read_storage(user: CurrentUser, dirs: UserDirsDep, session: SessionDep) -> QuotaStorage:
    await _lock_storage(session, user.id, shared=True)
    return await get_quota_storage(user, dirs)


ReadStorageDep = Annotated[QuotaStorage, Depends(get_read_storage)]


def get_file_repository(user: CurrentUser, session: SessionDep) -> FileRepository:
    return FileRepository(session, user.id)


FileRepositoryDep = Annotated[FileRepository, Depends(get_file_repository)]


def get_file_service(
    storage: StorageDep,
    files: FileRepositoryDep,
) -> FileService:
    return FileService(
        storage=storage,
        limits=settings.files,
        files=files,
    )

FileServiceDep = Annotated[FileService, Depends(get_file_service)]


def get_read_file_service(
    storage: ReadStorageDep,
    files: FileRepositoryDep,
) -> FileService:
    return get_file_service(storage, files)

ReadFileServiceDep = Annotated[
    FileService, Depends(get_read_file_service)
]


def get_zip_service(storage: StorageDep, files: FileRepositoryDep) -> ZipService:
    return ZipService(storage, settings.files, files)


ZipServiceDep = Annotated[ZipService, Depends(get_zip_service)]
