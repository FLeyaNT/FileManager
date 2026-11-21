import os
import stat
from typing import BinaryIO, Self

from anyio import Path

from app.api.schemas.files import StorageUsageOut
from app.core.exceptions import (
    FileTooLargeError,
    QuotaExceededError,
    StorageError,
    UnsafePathError,
)
from app.services.local_storage import LocalStorage
from app.utils.paths import reject_link


def raise_walk_error(error: OSError) -> None:
    raise error


class QuotaStorage(LocalStorage):

    def __init__(
        self,
        root: Path,
        chunk_size: int,
        *,
        byte_limit: int,
        entry_limit: int
    ) -> None:
        self._byte_limit = byte_limit
        self._entry_limit = entry_limit

        super().__init__(root, chunk_size)

    @classmethod
    async def create_with_limits(
        cls,
        root: Path,
        chunk_size: int,
        *,
        byte_limit: int,
        entry_limit: int,
    ) -> Self:
        resolved_root = await cls._resolve_root(root)
        return cls(
            resolved_root,
            chunk_size,
            byte_limit=byte_limit,
            entry_limit=entry_limit,
        )

    async def _scan_usage(
        self,
        enforce_limits: bool = False
    ) -> tuple[int, int]:
        used_bytes = 0
        used_entries = 0

        for folder, dirs, files in os.walk(
                self._root,
                followlinks=False,
                onerror=raise_walk_error,
        ):
            for name in dirs + files:
                try:
                    info = await (Path(folder) / name).lstat()
                except FileNotFoundError:
                    if enforce_limits:
                        raise
                    continue

                reject_link(info)
                used_entries += 1

                if stat.S_ISREG(info.st_mode):
                    used_bytes += info.st_size
                elif not stat.S_ISDIR(info.st_mode):
                    raise UnsafePathError(
                        "Недопустимый объект в хранилище"
                    )

                if enforce_limits and (
                        used_bytes > self._byte_limit
                        or used_entries > self._entry_limit
                ):
                    raise QuotaExceededError()

        return used_bytes, used_entries

    async def usage(self) -> StorageUsageOut:
        try:
            used_bytes, used_entries = await self._scan_usage()
        except OSError as exc:
            raise StorageError(
                'Не удалось посчитать использование хранилища'
            ) from exc

        return StorageUsageOut(
            used_bytes=used_bytes,
            max_bytes=self._byte_limit,
            remaining_bytes=max(0, self._byte_limit - used_bytes),
            used_entries=used_entries,
            max_entries=self._entry_limit,
            remaining_entries=max(0, self._entry_limit - used_entries)
        )

    async def _budget(self, target: Path) -> int:
        used_bytes, used_entries = await self._scan_usage(enforce_limits=True)
        root = Path(self._root)

        current = target
        while current != root:
            try:
                await current.lstat()
            except FileNotFoundError:
                used_entries += 1
            current = current.parent

        if used_entries > self._entry_limit:
            raise QuotaExceededError(
                'Превышен лимит файлов и папок'
            )

        return self._byte_limit - used_bytes

    async def _remaining(self, target: Path) -> int:
        try:
            return await self._budget(target)
        except OSError as exc:
            raise StorageError(
                'Не удалось проверить квоту'
            ) from exc

    async def _create_dir_at(self, target: Path) -> str:
        await self._remaining(target)
        return await super()._create_dir_at(target)

    async def _create_file_at(
            self,
            target: Path,
            src: BinaryIO,
            max_size: int
    ) -> tuple[str, int]:
        remaining = await self._remaining(target)
        try:
            return await super()._create_file_at(
                target=target,
                src=src,
                max_size=min(max_size, remaining)
            )
        except FileTooLargeError as exc:
            if remaining < max_size:
                raise QuotaExceededError() from exc
            raise

    async def remaining_capacity(self) -> tuple[int, int]:
        try:
            used_bytes, used_entries = await self._scan_usage(
                enforce_limits=True
            )
        except OSError as exc:
            raise StorageError("Не удалось проверить квоту") from exc

        return (
            self._byte_limit - used_bytes,
            self._entry_limit - used_entries,
        )

    async def replace_file(
        self, user_path: str, src: BinaryIO, max_size: int
    ) -> tuple[str, int]:
        target, info = await self.get_file_info(user_path)
        try:
            used_bytes, _ = await self._scan_usage()
        except OSError as exc:
            raise StorageError('Не удалось проверить квоту') from exc

        quota_limit = info.st_size + max(0, self._byte_limit - used_bytes)
        try:
            return await self._replace_file_at(
                target, src, min(max_size, quota_limit)
            )
        except FileTooLargeError as exc:
            if quota_limit < max_size:
                raise QuotaExceededError() from exc
            raise
