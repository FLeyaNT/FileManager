from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.utils.xml import XmlNode

from .types import DirectoryId, Filename
from .utils import _require_suffix


def validate_xml_filename(filename: str) -> str:
    return _require_suffix(filename, ".xml")


XmlFilename = Annotated[Filename, AfterValidator(validate_xml_filename)]


class XmlFileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory_id: DirectoryId
    filename: XmlFilename
    root: XmlNode


class XmlContent(BaseModel):
    root: XmlNode
