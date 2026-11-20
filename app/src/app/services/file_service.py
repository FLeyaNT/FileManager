from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from typing import BinaryIO, Any

from anyio import CancelScope, to_thread
from pydantic import JsonValue

from app.core.config import FilesConfig
from app.core.exceptions import FileTooLargeError, InvalidDocumentError, PathConflictError
from app.postgres.models import Directory, File, Operation
from app.postgres.models.enums.operation_type import OperationType
from app.postgres.repositories.file_repo import FileRepository
from app.services.local_storage import LocalStorage
from app.utils.json import encode_json, decode_json
from app.utils.paths import validate_name
from app.utils.xml import XmlNode, encode_xml, decode_xml
from app.utils.zip import validate_zip


class FileService:

    def __init__(
        self,
        storage: LocalStorage,
        limits: FilesConfig,
        files: FileRepository,
    ) -> None:
        self._storage = storage
        self._limits = limits
        self._max_file_size = limits.max_file_size
        self._files = files
        self._directories = files.directories

    async def get_file(self, file_id: int) -> File:
        file, _ = await self._files.get(file_id)
        return file

    async def list_files(self) -> list[File]:
        return await self._files.list_files()

    async def list_directory(self, directory_id: int | None) -> dict[str, Any]:
        directory, _ = await self._directories.get(directory_id=directory_id)
        children = await self._directories.list_children(directory.id)
        files = await self._files.list_in(directory.id)
        return {
            'id': directory.id,
            'name': directory.name,
            'parent_id': directory.parent_id,
            'directories': children,
            'files': files,
        }

    async def list_operations(self, limit: int) -> list[Operation]:
        return await self._files.list_operations(limit)

    async def delete_file(self, file_id: int) -> None:
        file, location = await self._files.get(file_id)
        async with self._storage.staged_deletion(location):
            self._files.record(OperationType.DELETE, file)
            await self._files.remove(file)
            await self._files.commit()

    async def delete_dir(self, directory_id: int, *, recursive: bool = False) -> None:
        directory, location = await self._directories.get(directory_id=directory_id)
        async with self._storage.staged_deletion(
            location, directory=True, recursive=recursive
        ) as (_, inventory):
            files = {
                file_path: file for file, file_path in await self._files.list_under(directory.id, location)
            }
            if not recursive and (files or await self._directories.list_children(directory.id)):
                raise PathConflictError('Папка не пуста')

            untracked = [(file_path, size) for file_path, size in inventory if file_path not in files]
            if untracked:
                directories = await self._directories.ensure_paths(
                    file_path.rpartition('/')[0] for file_path, _ in untracked
                )
                for file_path, size in untracked:
                    parent, _, name = file_path.rpartition('/')
                    files[file_path] = await self._files.upsert(directories[parent], name, size)

            for file in files.values():
                self._files.record(OperationType.DELETE, file)
                await self._files.remove(file)
            await self._directories.remove(directory)
            await self._files.commit()

    async def create_dir(self, parent_id: int, name: str) -> Directory:
        path = await self._new_child_path(parent_id, name)
        async with self._storage.staged_directory_creation(path):
            directory = await self._directories.create(parent_id, name)
            await self._files.commit()
        return directory

    async def _new_child_path(self, directory_id: int, name: str) -> str:
        _, directory_path = await self._directories.get(directory_id=directory_id)
        return await self._storage.child_path(directory_path, name)

    async def _create_file(self, directory_id: int, path: str, src: BinaryIO) -> File:
        async with self._storage.staged_creation(path, src, self._max_file_size) as (location, size):
            filename = location.rsplit('/', 1)[-1]
            file = await self._files.upsert(directory_id, filename, size)
            self._files.record(OperationType.CREATE, file)
            await self._files.commit()
        return file

    async def upload_file(
        self,
        directory_id: int,
        filename: str,
        src: BinaryIO
    ) -> File:
        path = await self._new_child_path(directory_id, filename)
        async with self._checked_content(src, self._file_format(filename)) as checked:
            return await self._create_file(directory_id, path, checked)

    @staticmethod
    def _file_format(name: str) -> str | None:
        _, dot, extension = name.casefold().rpartition('.')
        if dot and extension in ('json', 'xml', 'zip'):
            return extension
        return None

    async def _validate_format(self, file_format: str, raw: bytes) -> None:
        if len(raw) > self._max_file_size:
            raise FileTooLargeError()

        if file_format == 'json':
            await to_thread.run_sync(decode_json, raw)
        elif file_format == 'xml':
            await to_thread.run_sync(decode_xml, raw)
        elif file_format == 'zip':
            await to_thread.run_sync(validate_zip, raw, self._limits)

    @asynccontextmanager
    async def _checked_content(
        self, src: BinaryIO, file_format: str | None
    ) -> AsyncIterator[BinaryIO]:
        if file_format is None:
            yield src
            return

        raw = await to_thread.run_sync(src.read, self._max_file_size + 1)
        await self._validate_format(file_format, raw)

        with BytesIO(raw) as checked:
            yield checked

    async def rename_file(self, file_id: int, new_name: str) -> File:
        validate_name(new_name)
        file, previous_path = await self._files.get(file_id)
        previous_name = file.filename
        new_format = self._file_format(new_name)
        if new_format != self._file_format(previous_name) and isinstance(new_format, str):
            _, raw = await self._storage.read_file(previous_path, self._max_file_size)
            await self._validate_format(new_format, raw)

        path, size = await self._storage.rename_file(previous_path, new_name)
        if path != previous_path:
            try:
                file.filename = new_name
                file.size = size
                self._files.record(OperationType.MODIFY, file)
                await self._files.commit()
            except BaseException:
                with CancelScope(shield=True):
                    await self._storage.rename_file(path, previous_name)
                raise
        return file

    async def replace_file(self, file_id: int, src: BinaryIO) -> File:
        file, location = await self._files.get(file_id)
        async with self._checked_content(src, self._file_format(file.filename)) as checked:
            async with self._storage.staged_replacement(
                location, checked, self._max_file_size
            ) as (_, size):
                file.size = size
                file.updated_at = datetime.now(UTC)
                self._files.record(OperationType.MODIFY, file)
                await self._files.commit()
        return file

    async def create_text_file(
        self,
        directory_id: int,
        filename: str,
        content: str
    ) -> File:
        path = await self._new_child_path(directory_id, filename)
        if len(content) > self._max_file_size:
            raise FileTooLargeError()

        try:
            data = content.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise InvalidDocumentError(
                'Текст содержит недопустимые символы'
            )

        file_format = self._file_format(filename)
        if file_format is not None:
            await self._validate_format(file_format, data)

        with BytesIO(data) as src:
            return await self._create_file(directory_id, path, src)

    async def create_json_file(
        self,
        directory_id: int,
        filename: str,
        data: JsonValue
    ) -> File:
        path = await self._new_child_path(directory_id, filename)
        try:
            raw = await to_thread.run_sync(encode_json, data)
        except (ValueError, RecursionError) as exc:
            raise InvalidDocumentError(
                'Некорректные данные JSON'
            ) from exc

        if len(raw) > self._max_file_size:
            raise FileTooLargeError()

        with BytesIO(raw) as src:
            return await self._create_file(directory_id, path, src)


    async def read_json_file(
        self,
        file_id: int,
    ) -> JsonValue:
        file, location = await self._files.get(file_id)
        if self._file_format(file.filename) != 'json':
            raise InvalidDocumentError('Ожидается файл с расширением .json')
        _, raw = await self._storage.read_file(
            user_path=location,
            max_size=self._max_file_size
        )

        data = await to_thread.run_sync(decode_json, raw)
        self._files.record(OperationType.READ, file)
        await self._files.commit()
        return data

    async def create_xml_file(
        self,
        directory_id: int,
        filename: str,
        root: XmlNode
    ) -> File:
        path = await self._new_child_path(directory_id, filename)
        raw = await to_thread.run_sync(encode_xml, root)
        if len(raw) > self._max_file_size:
            raise FileTooLargeError()

        with BytesIO(raw) as src:
            return await self._create_file(directory_id, path, src)

    async def read_xml_file(
        self,
        file_id: int,
    ) -> XmlNode:
        file, location = await self._files.get(file_id)
        if self._file_format(file.filename) != 'xml':
            raise InvalidDocumentError('Ожидается файл с расширением .xml')
        _, raw = await self._storage.read_file(
            user_path=location,
            max_size=self._max_file_size
        )
        root = await to_thread.run_sync(decode_xml, raw)
        self._files.record(OperationType.READ, file)
        await self._files.commit()
        return root

    async def download_file(self, file_id: int) -> tuple[str, bytes]:
        file, location = await self._files.get(file_id)
        _, raw = await self._storage.read_file(location, self._max_file_size)
        self._files.record(OperationType.READ, file)
        await self._files.commit()
        return file.filename, raw
