from pydantic import BaseModel, ConfigDict

from .types import DirectoryId, FileId, Filename


class FileIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    directory_id: DirectoryId
    filename: Filename
    content: str


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    directory_id: int
    filename: str
    size: int


class FileRenameIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    file_id: FileId
    new_name: str


class StorageUsageOut(BaseModel):
    used_bytes: int
    max_bytes: int
    remaining_bytes: int
    used_entries: int
    max_entries: int
    remaining_entries: int
