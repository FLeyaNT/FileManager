import os
import stat

from anyio import Path

from app.core.exceptions import UnsafePathError


_FORBIDDEN_CHARS = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)
MAX_NAME_LENGTH = 255
MAX_DEPTH = 32
MAX_PATH_LENGTH = 250


def validate_name(name: str) -> str:
    if (
        not name
        or name in {".", ".."}
        or len(name) > MAX_NAME_LENGTH
        or any(ord(c) < 32 or ord(c) == 127 or c in _FORBIDDEN_CHARS for c in name)
        or name.endswith((" ", "."))
        or name.split(".")[0].upper() in _WINDOWS_RESERVED
    ):
        raise UnsafePathError("Недопустимое имя файла или папки")
    return name


def reject_link(info: os.stat_result) -> None:
    attributes = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or (
        attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise UnsafePathError('Ссылки в хранилище запрещены')


async def resolve_safe(root: Path, user_path: str) -> Path:
    parts = [p for p in user_path.replace("\\", "/").split("/") if p]
    if len(parts) > MAX_DEPTH:
        raise UnsafePathError("Слишком глубокая вложенность")
    for part in parts:
        validate_name(part)

    current = root
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = await current.lstat()
        except FileNotFoundError:
            break

        reject_link(info)
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise NotADirectoryError(str(current))

    target = await root.joinpath(*parts).resolve()
    if not target.is_relative_to(root):
        raise UnsafePathError("Путь выходит за пределы хранилища")
    return target


def to_relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()
