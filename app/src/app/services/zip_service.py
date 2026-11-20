import stat
from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from anyio import Path as AsyncPath
from anyio import to_thread

from app.core.config import FilesConfig
from app.core.exceptions import (
    ArchiveLimitError,
    FileTooLargeError,
    InvalidDocumentError,
    NotFoundError,
    PathConflictError,
    StorageError,
    UnsafePathError,
)
from app.postgres.models import File
from app.postgres.models.enums.operation_type import OperationType
from app.postgres.repositories.file_repo import FileRepository
from app.services.quota_storage import QuotaStorage
from app.utils.paths import MAX_DEPTH, reject_link
from app.utils.zip import extract_zip, validate_zip_name


class ZipService:
    def __init__(
        self, storage: QuotaStorage, limits: FilesConfig, files: FileRepository
    ) -> None:
        self._storage = storage
        self._limits = limits
        self._files = files

    async def _walk_source(
        self, target: AsyncPath, entry_name: str, depth: int
    ) -> AsyncIterator[tuple[AsyncPath, str, bool]]:
        if depth > MAX_DEPTH:
            raise UnsafePathError("Слишком глубокая вложенность")
        validate_zip_name(target.name)

        try:
            info = await target.lstat()
            reject_link(info)
            if stat.S_ISREG(info.st_mode):
                yield target, entry_name, False
            elif stat.S_ISDIR(info.st_mode):
                yield target, entry_name, True
                async for child in target.iterdir():
                    async for entry in self._walk_source(
                        child, f"{entry_name}/{child.name}", depth + 1
                    ):
                        yield entry
            else:
                raise UnsafePathError("Недопустимый объект для архивации")
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise NotFoundError("Файл или папка не найдены") from exc
        except OSError as exc:
            raise StorageError("Не удалось прочитать источник ZIP") from exc

    async def _iter_entries(
        self, sources: list[int | str]
    ) -> AsyncIterator[tuple[AsyncPath, str, bool]]:
        for source in sources:
            if isinstance(source, str):
                target = await self._storage.get_directory(source)
                relative = self._storage.relative(target)
                await self._files.directories.get(path='' if relative == '.' else relative)
            else:
                _, path = await self._files.get(source)
                target, _ = await self._storage.get_file_info(path)
            relative = self._storage.relative(target)
            if relative == ".":
                raise UnsafePathError("Выбери файл или папку внутри хранилища")

            depth = relative.count("/") + 1
            async for entry in self._walk_source(target, target.name, depth):
                yield entry

    async def create(
        self, sources: list[int | str], directory_id: int, filename: str
    ) -> tuple[File, int]:
        _, directory_path = await self._files.directories.get(directory_id=directory_id)
        archive_path = await self._storage.child_path(directory_path, filename)
        if len(sources) > self._limits.zip_max_entries:
            raise ArchiveLimitError("Слишком много файлов для ZIP")

        max_size = self._limits.max_file_size
        names: set[str] = set()
        total = 0
        catalog = {path: file for file, path in await self._files.list_with_paths()}
        source_files: dict[int, File] = {}
        file_count = 0

        with BytesIO() as buffer:
            with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
                async for target, entry_name, is_dir in self._iter_entries(sources):
                    key = entry_name.casefold()
                    if key in names:
                        raise InvalidDocumentError(
                            "Выбранные объекты имеют одинаковые пути в архиве"
                        )
                    if len(names) >= self._limits.zip_max_entries:
                        raise ArchiveLimitError("Слишком много записей в архиве")
                    names.add(key)

                    if is_dir:
                        await to_thread.run_sync(archive.mkdir, entry_name)
                    else:
                        location = self._storage.relative(target)
                        source_file = catalog.get(location)
                        if source_file is None:
                            raise NotFoundError('Файл не найден в каталоге')
                        _, data = await self._storage.read_file(location, max_size)
                        total += len(data)
                        if total > self._limits.zip_max_total_size:
                            raise ArchiveLimitError()
                        if buffer.tell() + len(data) > max_size:
                            raise FileTooLargeError()

                        await to_thread.run_sync(archive.writestr, entry_name, data)
                        source_files[source_file.id] = source_file
                        file_count += 1

                    if buffer.tell() > max_size:
                        raise FileTooLargeError()

            if buffer.tell() > max_size:
                raise FileTooLargeError()

            buffer.seek(0)
            async with self._storage.staged_creation(
                archive_path, buffer, max_size
            ) as (_, size):
                archive_file = await self._files.upsert(directory_id, filename, size)
                for source_file in source_files.values():
                    self._files.record(OperationType.READ, source_file)
                self._files.record(OperationType.ARCHIVE, archive_file)
                await self._files.commit()

        return archive_file, file_count

    async def extract(
        self, file_id: int, directory_id: int, name: str | None = None
    ) -> tuple[int, list[File]]:
        archive_file, archive_location = await self._files.get(file_id)
        _, parent_location = await self._files.directories.get(directory_id=directory_id)
        if not archive_file.filename.casefold().endswith('.zip'):
            raise InvalidDocumentError('Ожидается файл с расширением .zip')

        folder_name = name
        if folder_name is None:
            folder_name = archive_file.filename[:-len('.zip')].rstrip(' .') or 'archive'
        relative = await self._storage.child_path(parent_location, folder_name)
        target = await self._storage.resolve(relative)
        if await target.exists():
            raise PathConflictError()

        _, raw = await self._storage.read_file(
            archive_location, self._limits.max_file_size
        )
        free_bytes, free_entries = await self._storage.remaining_capacity()
        files, folders = await to_thread.run_sync(
            extract_zip,
            raw,
            Path(target),
            relative,
            self._limits,
            free_bytes,
            free_entries,
        )
        extracted_files: list[File] = []
        async with self._storage.undo_created(relative, directory=True):
            extracted_directory = await self._files.directories.create(directory_id, folder_name)
            folders.update(path.rpartition('/')[0] for path in files)
            directories = await self._files.directories.ensure_paths(sorted(folders))
            self._files.record(OperationType.EXTRACT, archive_file)
            for path in files:
                _, info = await self._storage.get_file_info(path)
                parent, _, filename = path.rpartition('/')
                file = await self._files.upsert(directories[parent], filename, info.st_size)
                extracted_files.append(file)
                self._files.record(OperationType.CREATE, file)
            await self._files.commit()
        return extracted_directory.id, extracted_files
