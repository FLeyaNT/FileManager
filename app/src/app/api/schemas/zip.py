from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from .files import FileOut
from .types import DirectoryId, FileId, Filename, RelPath
from .utils import _require_suffix


def validate_zip_filename(filename: str) -> str:
    return _require_suffix(filename, ".zip")


ZipFilename = Annotated[Filename, AfterValidator(validate_zip_filename)]


class ArchiveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[FileId | RelPath] = Field(
        min_length=1,
        max_length=100,
        description="ID файлов и пути к папкам внутри личного хранилища",
    )
    directory_id: DirectoryId
    filename: ZipFilename


class ArchiveExtract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: FileId
    directory_id: DirectoryId = Field(description="ID родительской папки для распаковки")
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Имя новой папки. По умолчанию используется имя архива без расширения",
    )


class ArchiveOut(FileOut):
    files: int


class ExtractOut(BaseModel):
    directory_id: int = Field(description="ID папки, созданной при распаковке")
    files: list[FileOut]
