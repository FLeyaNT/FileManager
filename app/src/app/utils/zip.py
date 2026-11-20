import stat
import struct
import zlib
from collections.abc import Callable, Iterator
from io import BytesIO
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from app.core.config import FilesConfig
from app.core.exceptions import (
    ArchiveLimitError,
    InvalidDocumentError,
    PathConflictError,
    QuotaExceededError,
    StorageError,
    UnsafePathError,
)
from app.utils.json import decode_json
from app.utils.paths import MAX_DEPTH, validate_name
from app.utils.xml import decode_xml


_ZIP_READ_ERRORS = (
    BadZipFile,
    EOFError,
    UnicodeError,
    RuntimeError,
    struct.error,
    zlib.error,
)


def validate_zip_name(name: str) -> None:
    validate_name(name)
    if PureWindowsPath(name).is_reserved():
        raise UnsafePathError("Недопустимое имя внутри ZIP")


def _plan(
    archive: ZipFile,
    limits: FilesConfig,
    *,
    destination_rel: str = "",
    free_bytes: int | None = None,
    free_entries: int | None = None,
) -> list[tuple[ZipInfo, tuple[str, ...]]]:
    members = archive.infolist()
    if len(members) > limits.zip_max_entries:
        raise ArchiveLimitError("Слишком много записей в архиве")

    plan: list[tuple[ZipInfo, tuple[str, ...]]] = []
    paths: dict[tuple[str, ...], tuple[tuple[str, ...], bool]] = {}
    explicit: set[tuple[str, ...]] = set()
    total = 0

    for info in members:
        raw = info.orig_filename
        is_dir = raw.endswith("/")
        parts = tuple(raw.removesuffix("/").split("/"))

        if "\\" in raw or "\x00" in raw:
            raise UnsafePathError("Недопустимый путь внутри ZIP")

        for part in parts:
            validate_zip_name(part)

        relative = "/".join(parts)
        if destination_rel:
            relative = f"{destination_rel}/{relative}"
        if relative.count("/") + 1 > MAX_DEPTH or len(relative) > 255:
            raise UnsafePathError("Слишком длинный путь внутри ZIP")

        mode = stat.S_IFMT(info.external_attr >> 16)
        expected_mode = stat.S_IFDIR if is_dir else stat.S_IFREG
        if mode not in (0, expected_mode):
            raise InvalidDocumentError(
                "Ссылки и специальные записи ZIP запрещены"
            )
        if info.flag_bits & 1:
            raise InvalidDocumentError("Зашифрованные ZIP не поддерживаются")
        if info.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
            raise InvalidDocumentError("Неподдерживаемый метод сжатия ZIP")
        if is_dir and info.file_size != 0:
            raise InvalidDocumentError("Запись каталога содержит данные")

        key = tuple(part.casefold() for part in parts)
        if key in explicit:
            raise InvalidDocumentError("ZIP содержит повторяющиеся пути")
        explicit.add(key)

        for length in range(1, len(parts) + 1):
            prefix = parts[:length]
            entry = (prefix, length < len(parts) or is_dir)
            if paths.setdefault(key[:length], entry) != entry:
                raise InvalidDocumentError("Конфликт имён внутри ZIP")

        total += info.file_size
        if (
            info.file_size > limits.max_file_size
            or total > limits.zip_max_total_size
            or info.file_size > info.compress_size * limits.zip_max_ratio
        ):
            raise ArchiveLimitError()

        if (free_bytes is not None and total > free_bytes) or (
            free_entries is not None and len(paths) + 1 > free_entries
        ):
            raise QuotaExceededError()

        plan.append((info, parts))

    # При распаковке папка назначения занимает запись даже для пустого ZIP.
    if free_entries is not None and free_entries < 1:
        raise QuotaExceededError()

    return plan


def _read_member(
    archive: ZipFile, info: ZipInfo, chunk_size: int
) -> Iterator[bytes]:
    # The plan has already checked this size against all archive limits.
    remaining = info.file_size
    with archive.open(info) as src:
        while chunk := src.read(chunk_size):
            remaining -= len(chunk)
            if remaining < 0:
                raise ArchiveLimitError()
            yield chunk

    if remaining != 0:
        raise InvalidDocumentError("Некорректный размер записи ZIP")


def _document_decoder(filename: str) -> Callable[[bytes], object] | None:
    filename = filename.casefold()
    if filename.endswith(".json"):
        return decode_json
    if filename.endswith(".xml"):
        return decode_xml
    return None


def validate_zip(raw: bytes, limits: FilesConfig) -> None:
    try:
        with ZipFile(BytesIO(raw), "r") as archive:
            for info, parts in _plan(archive, limits):
                # Reading each member checks its local header and CRC.
                chunks = _read_member(archive, info, limits.chunk_size)
                decoder = None if info.is_dir() else _document_decoder(parts[-1])
                if decoder is None:
                    for _ in chunks:
                        pass
                else:
                    decoder(b"".join(chunks))
    except _ZIP_READ_ERRORS as exc:
        raise InvalidDocumentError("Некорректный ZIP-архив") from exc


def extract_zip(
    raw: bytes,
    destination: Path,
    destination_rel: str,
    limits: FilesConfig,
    free_bytes: int,
    free_entries: int,
) -> tuple[list[str], set[str]]:
    try:
        with ZipFile(BytesIO(raw), "r") as archive:
            plan = _plan(
                archive,
                limits,
                destination_rel=destination_rel,
                free_bytes=free_bytes,
                free_entries=free_entries,
            )

            with TemporaryDirectory(
                dir=destination.parent, prefix=".fm-zip-"
            ) as tmp:
                stage = Path(tmp) / "payload"
                stage.mkdir()
                files: list[str] = []
                directories = {destination_rel}

                for info, parts in plan:
                    target = stage.joinpath(*parts)
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        directories.add('/'.join((destination_rel, *parts)))
                        continue

                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as dst:
                        for chunk in _read_member(archive, info, limits.chunk_size):
                            dst.write(chunk)

                    decoder = _document_decoder(target.name)
                    if decoder is not None:
                        decoder(target.read_bytes())

                    files.append("/".join((destination_rel, *parts)))

                if destination.exists():
                    raise PathConflictError()

                stage.rename(destination)
                return files, directories

    except _ZIP_READ_ERRORS as exc:
        raise InvalidDocumentError("Некорректный ZIP-архив") from exc
    except FileExistsError as exc:
        raise PathConflictError() from exc
    except OSError as exc:
        raise StorageError("Не удалось распаковать ZIP") from exc
