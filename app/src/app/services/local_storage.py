import logging
import asyncio
import errno
import stat
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from os import scandir, stat_result
from os.path import samestat
from pathlib import Path as SyncPath, PureWindowsPath
from shutil import copy2, rmtree
from tempfile import NamedTemporaryFile, mkdtemp
from typing import BinaryIO

from anyio import Path, AsyncFile, CancelScope, to_thread

from app.core.exceptions import (
    PathConflictError,
    StorageError,
    UnsafePathError,
    FileTooLargeError,
    NotFoundError
)
from app.utils.paths import MAX_DEPTH, resolve_safe, to_relative, reject_link, validate_name

logger = logging.getLogger(__name__)


class LocalStorage:

    def __init__(
        self,
        root: Path,
        chunk_size: int
    ) -> None:
        self._root = root
        self._chunk_size = chunk_size

    @staticmethod
    async def create(root: Path, chunk_size: int) -> 'LocalStorage':
        resolved_root = await LocalStorage._resolve_root(root)
        return LocalStorage(resolved_root, chunk_size)

    @staticmethod
    async def _resolve_root(root: Path) -> Path:
        try:
            info = await root.lstat()
            reject_link(info)
            if not stat.S_ISDIR(info.st_mode):
                raise StorageError("Личное хранилище не является папкой")
            return await root.resolve(strict=True)
        except OSError as exc:
            raise StorageError("Не удалось открыть личное хранилище") from exc

    async def resolve(self, user_path: str) -> Path:
        try:
            return await resolve_safe(self._root, user_path)
        except NotADirectoryError as exc:
            raise PathConflictError() from exc
        except OSError as exc:
            raise StorageError("Не удалось проверить путь") from exc

    def relative(self, path: Path) -> str:
        return to_relative(self._root, path)

    async def child_path(self, directory: str, name: str) -> str:
        validate_name(name)
        parent = await self.get_directory(directory)
        return self.relative(parent / name)

    async def get_file_info(self, user_path: str) -> tuple[Path, stat_result]:
        try:
            target = await self.resolve(user_path)
            info = await target.lstat()
            reject_link(info)
        except (FileNotFoundError, NotADirectoryError, PathConflictError) as exc:
            raise NotFoundError('Файл не найден') from exc
        except OSError as exc:
            raise StorageError('Не удалось проверить файл') from exc

        if not stat.S_ISREG(info.st_mode):
            raise NotFoundError('Файл не найден')
        return target, info

    async def rename_file(
        self, user_path: str, new_name: str
    ) -> tuple[str, int]:
        validate_name(new_name)
        if PureWindowsPath(new_name).is_reserved():
            raise UnsafePathError('Недопустимое имя файла')

        source, info = await self.get_file_info(user_path)
        target = source.with_name(new_name)
        relative = self.relative(target)
        if len(relative) > 255:
            raise UnsafePathError('Слишком длинный путь к файлу')

        try:
            try:
                existing = await target.lstat()
            except FileNotFoundError:
                existing = None

            if existing is not None:
                reject_link(existing)
                if target != source or not samestat(info, existing):
                    raise PathConflictError()

            if source.name != new_name:
                await source.rename(target)
        except FileExistsError as exc:
            raise PathConflictError() from exc
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise NotFoundError('Файл не найден') from exc
        except OSError as exc:
            raise StorageError('Не удалось переименовать файл') from exc

        return relative, info.st_size

    async def replace_file(
        self, user_path: str, src: BinaryIO, max_size: int
    ) -> tuple[str, int]:
        target, _ = await self.get_file_info(user_path)
        return await self._replace_file_at(target, src, max_size)

    async def _replace_file_at(
        self, target: Path, src: BinaryIO, max_size: int
    ) -> tuple[str, int]:
        try:
            size = await to_thread.run_sync(
                self._write_replacement, target, src, max_size
            )
        except OSError as exc:
            raise StorageError('Не удалось заменить содержимое файла') from exc
        return self.relative(target), size

    def _write_replacement(self, target: Path, src: BinaryIO, max_size: int) -> int:
        temporary: SyncPath | None = None
        size = 0
        try:
            with NamedTemporaryFile(
                mode='wb', dir=target.parent, prefix='.fm-replace-', delete=False
            ) as dst:
                temporary = SyncPath(dst.name)
                while chunk := src.read(self._chunk_size):
                    size += len(chunk)
                    if size > max_size:
                        raise FileTooLargeError()
                    dst.write(chunk)

            temporary.replace(target)
            temporary = None
            return size
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    async def file_inventory(self, user_path: str = '') -> list[tuple[str, int]]:
        target = await self.get_directory(user_path)
        try:
            return await to_thread.run_sync(self._inventory, target)
        except OSError as exc:
            raise StorageError('Не удалось прочитать содержимое папки') from exc

    def _inventory(self, target: Path) -> list[tuple[str, int]]:
        root = SyncPath(self._root)
        pending = [SyncPath(target)]
        files: list[tuple[str, int]] = []
        while pending:
            with scandir(pending.pop()) as entries:
                for entry in entries:
                    path = SyncPath(entry.path)
                    relative = path.relative_to(root)
                    if len(relative.parts) > MAX_DEPTH:
                        continue
                    info = path.lstat()
                    try:
                        validate_name(entry.name)
                        reject_link(info)
                    except UnsafePathError:
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(path)
                    elif stat.S_ISREG(info.st_mode):
                        files.append((relative.as_posix(), info.st_size))
        return sorted(files)

    async def get_directory(self, user_path: str) -> Path:
        try:
            target = await self.resolve(user_path)
            info = await target.lstat()
            reject_link(info)
        except (FileNotFoundError, NotADirectoryError, PathConflictError) as exc:
            raise NotFoundError('Папка не найдена') from exc
        except OSError as exc:
            raise StorageError('Не удалось проверить папку') from exc
        if not stat.S_ISDIR(info.st_mode):
            raise NotFoundError('Папка не найдена')
        return target

    async def _backup_location(self) -> Path:
        try:
            directory = await to_thread.run_sync(partial(
                mkdtemp, prefix='.fm-rollback-', dir=self._root.parent
            ))
        except OSError as exc:
            raise StorageError('Не удалось подготовить файловую операцию') from exc
        return Path(directory) / 'original'

    @staticmethod
    async def _cleanup_backup(backup: Path) -> None:
        with CancelScope(shield=True):
            try:
                await to_thread.run_sync(rmtree, backup.parent)
            except OSError:
                logger.exception('Не удалось очистить временную папку %s', backup.parent)

    @asynccontextmanager
    async def _restore_on_error(
        self, target: Path, backup: Path, *, overwrite: bool = False
    ) -> AsyncIterator[None]:
        try:
            yield
        except BaseException:
            with CancelScope(shield=True):
                try:
                    if overwrite:
                        await backup.replace(target)
                    else:
                        await backup.rename(target)
                except OSError as exc:
                    logger.exception('Не удалось восстановить %s из %s', target, backup)
                    raise StorageError('Не удалось восстановить исходный файл или папку') from exc
            await self._cleanup_backup(backup)
            raise
        else:
            await self._cleanup_backup(backup)

    @asynccontextmanager
    async def staged_replacement(
        self, user_path: str, src: BinaryIO, max_size: int
    ) -> AsyncIterator[tuple[str, int]]:
        target, _ = await self.get_file_info(user_path)
        backup = await self._backup_location()
        try:
            await to_thread.run_sync(copy2, target, backup)
        except OSError as exc:
            await self._cleanup_backup(backup)
            raise StorageError('Не удалось сохранить исходное содержимое файла') from exc
        try:
            result = await self.replace_file(user_path, src, max_size)
        except BaseException:
            await self._cleanup_backup(backup)
            raise

        async with self._restore_on_error(target, backup, overwrite=True):
            yield result

    @asynccontextmanager
    async def staged_deletion(
        self, user_path: str, *, directory: bool = False, recursive: bool = False
    ) -> AsyncIterator[tuple[str, list[tuple[str, int]]]]:
        inventory: list[tuple[str, int]] = []
        if directory:
            target = await self.get_directory(user_path)
            if target == self._root:
                raise UnsafePathError('Нельзя удалить корень хранилища')
            if not recursive:
                async for _ in target.iterdir():
                    raise PathConflictError('Папка не пуста')
            else:
                inventory = await self.file_inventory(user_path)
        else:
            target, _ = await self.get_file_info(user_path)

        backup = await self._backup_location()
        try:
            await target.rename(backup)
        except (FileNotFoundError, NotADirectoryError) as exc:
            await self._cleanup_backup(backup)
            raise NotFoundError('Файл или папка не найдены') from exc
        except OSError as exc:
            await self._cleanup_backup(backup)
            raise StorageError('Не удалось удалить файл или папку') from exc

        async with self._restore_on_error(target, backup):
            yield self.relative(target), inventory

    @asynccontextmanager
    async def undo_created(
        self, user_path: str, *, directory: bool = False
    ) -> AsyncIterator[None]:
        try:
            yield
        except BaseException:
            with CancelScope(shield=True):
                if directory:
                    await self.delete_dir(user_path, recursive=True)
                else:
                    await self.delete_file(user_path)
            raise

    @asynccontextmanager
    async def staged_creation(
        self, user_path: str, src: BinaryIO, max_size: int
    ) -> AsyncIterator[tuple[str, int]]:
        target = await self._new_target(user_path)
        async with self._undo_new_directories(target.parent):
            path, size = await self._create_file_at(target, src, max_size)
            async with self.undo_created(path):
                yield path, size

    @asynccontextmanager
    async def staged_directory_creation(self, user_path: str) -> AsyncIterator[str]:
        target = await self._new_target(user_path)
        async with self._undo_new_directories(target):
            yield await self._create_dir_at(target)

    @asynccontextmanager
    async def _undo_new_directories(self, target: Path) -> AsyncIterator[None]:
        missing_parents: list[Path] = []
        while target != self._root and not await target.exists():
            missing_parents.append(target)
            target = target.parent

        try:
            yield
        except BaseException:
            with CancelScope(shield=True):
                for parent in missing_parents:
                    try:
                        await parent.rmdir()
                    except FileNotFoundError:
                        continue
                    except OSError:
                        logger.exception('Не удалось удалить временную папку %s', parent)
                        break
            raise

    async def _create_dir_at(self, target: Path) -> str:
        try:
            await target.mkdir(parents=True)
        except (FileExistsError, NotADirectoryError) as exc:
            raise PathConflictError() from exc
        except OSError as exc:
            logger.exception(
                "Не удалось создать папку %s",
                self.relative(target),
            )
            raise StorageError() from exc

        return self.relative(target)

    async def _new_target(self, user_path: str) -> Path:
        target = await self.resolve(user_path)
        if target == self._root:
            raise UnsafePathError('Не указан путь')
        if await target.exists():
            raise PathConflictError()
        return target

    async def _create_file_at(
            self,
            target: Path,
            src: BinaryIO,
            max_size: int
    ) -> tuple[str, int]:
        try:
            await target.parent.mkdir(parents=True, exist_ok=True)
            dst = await target.open('xb')
        except (FileExistsError, NotADirectoryError) as exc:
            raise PathConflictError from exc
        except OSError as exc:
            logger.exception(
                'Не удалось создать файл %s',
                self.relative(target)
            )
            raise StorageError from exc

        return await self._write_file(
            src=src,
            dst=dst,
            max_size=max_size,
            target=target
        )

    async def create_dir(self, user_path: str) -> str:
        target = await self._new_target(user_path)
        return await self._create_dir_at(target)

    async def create_file(
        self,
        user_path: str,
        src: BinaryIO,
        max_size: int
    ) -> tuple[str, int]:
        target = await self._new_target(user_path)
        return await self._create_file_at(target, src, max_size)

    async def _write_file(
        self,
        src: BinaryIO,
        dst: AsyncFile[bytes],
        max_size: int,
        target: Path
    ) -> tuple[str, int]:
        size = 0
        try:
            async with dst:
                while chunk := await asyncio.to_thread(
                    src.read, self._chunk_size
                ):
                    size += len(chunk)
                    if size > max_size:
                        raise FileTooLargeError()
                    await dst.write(chunk)
        except BaseException as exc:
            await target.unlink(missing_ok=True)
            if isinstance(exc, OSError):
                logger.exception(
                    'Не удалось записать файл %s',
                    self.relative(target)
                )
                raise StorageError from exc
            raise

        return self.relative(target), size

    async def read_file(
        self,
        user_path: str,
        max_size: int
    ) -> tuple[str, bytes]:
        try:
            target = await self.resolve(user_path)
            info = await target.lstat()
            reject_link(info)

            if not stat.S_ISREG(info.st_mode):
                raise NotFoundError('Файл не найден')

            if info.st_size > max_size:
                raise FileTooLargeError()

            async with await target.open('rb') as src:
                data = await src.read(max_size + 1)
        except (FileNotFoundError, NotADirectoryError, PathConflictError) as exc:
            raise NotFoundError('Файл не найден') from exc
        except OSError as exc:
            raise StorageError('Не удалось прочитать файл') from exc

        if len(data) > max_size:
            raise FileTooLargeError()

        return self.relative(target), data

    async def delete_file(self, user_path: str) -> None:
        try:
            target = await self.resolve(user_path)
            info = await target.lstat()
            reject_link(info)

            if not stat.S_ISREG(info.st_mode):
                raise NotFoundError('Файл не найден')

            await target.unlink()
        except (
            FileNotFoundError,
            NotADirectoryError,
            IsADirectoryError,
            PathConflictError,
        ) as exc:
            raise NotFoundError('Файл не найден') from exc
        except OSError as exc:
            raise StorageError('Не удалось удалить файл') from exc

    async def delete_dir(self, user_path: str, *, recursive: bool = False) -> None:
        try:
            target = await self.resolve(user_path)
            if target == self._root:
                raise UnsafePathError('Нельзя удалить корень хранилища')

            info = await target.lstat()
            reject_link(info)
            if not stat.S_ISDIR(info.st_mode):
                raise NotFoundError('Папка не найдена')

            if recursive:
                await to_thread.run_sync(rmtree, target)
            else:
                await target.rmdir()
        except (FileNotFoundError, NotADirectoryError, PathConflictError) as exc:
            raise NotFoundError('Папка не найдена') from exc
        except OSError as exc:
            if not recursive and exc.errno in (errno.ENOTEMPTY, errno.EEXIST):
                raise PathConflictError('Папка не пуста') from exc
            raise StorageError('Не удалось удалить папку') from exc
