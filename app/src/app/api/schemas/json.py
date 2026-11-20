from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, JsonValue

from .types import DirectoryId, Filename
from .utils import _require_suffix


def validate_json_filename(filename: str) -> str:
    return _require_suffix(filename, '.json')


JsonFilename = Annotated[Filename, AfterValidator(validate_json_filename)]


class JsonFileIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    directory_id: DirectoryId
    filename: JsonFilename
    data: JsonValue


class JsonContent(BaseModel):
    data: JsonValue
