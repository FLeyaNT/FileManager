from pydantic import BaseModel, ConfigDict, Field

from .files import FileOut
from .types import DirectoryId


class DirIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    parent_id: DirectoryId
    name: str = Field(min_length=1, max_length=255)


class DirListQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')

    directory_id: DirectoryId | None = None


class DirDeleteQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')

    directory_id: DirectoryId
    recursive: bool = False


class DirOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None


class DirContents(DirOut):
    directories: list[DirOut]
    files: list[FileOut]
