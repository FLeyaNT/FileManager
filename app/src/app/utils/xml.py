import re
from reprlib import recursive_repr
from typing import Annotated
from xml.etree.ElementTree import Element, ParseError, TreeBuilder, tostring

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import DefusedXMLParser
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from app.core.exceptions import InvalidDocumentError


MAX_XML_DEPTH = 64
MAX_XML_NODES = 10_000

_INVALID_XML_CHARS = re.compile(
    r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]"
)


def validate_xml_text(value: str) -> str:
    if _INVALID_XML_CHARS.search(value):
        raise ValueError(
            'Текст содержит символы, недопустимые в XML'
        )
    return value


def validate_xml_attribute(value: str) -> str:
    if value == 'xmlns':
        raise ValueError(
            'Пространства имен XML е поддерживаются'
        )
    return value


XmlName = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$",
        max_length=128,
    ),
]
XmlAttributeName = Annotated[XmlName, AfterValidator(validate_xml_attribute)]
XmlText = Annotated[str, AfterValidator(validate_xml_text)]


class XmlNode(BaseModel):
    model_config = ConfigDict(extra='forbid')

    tag: XmlName
    attrib: dict[XmlAttributeName, XmlText] = Field(default_factory=dict)
    text: XmlText | None = None
    tail: XmlText | None = None
    children: list["XmlNode"] = Field(default_factory=list)


class _LimitedTreeBuilder(TreeBuilder):

    def __init__(self) -> None:
        super().__init__()
        self._depth = 0
        self._nodes = 0

    def start(self, tag: str, attrs: dict[str, str]) -> Element:
        self._depth += 1
        self._nodes += 1

        if self._depth > MAX_XML_DEPTH or self._nodes > MAX_XML_NODES:
            raise ValueError("Документ превышает лимит глубины или элементов")

        return super().start(tag, attrs)

    def end(self, tag: str) -> Element:
        element = super().end(tag)
        self._depth -= 1
        return element

    def start_ns(self, prefix: str, uri: str) -> None:
        raise ValueError("Пространства имён XML не поддерживаются")


def _add_node(
    builder: _LimitedTreeBuilder,
    node: XmlNode
) -> None:
    builder.start(node.tag, node.attrib)
    if node.text is not None:
        builder.data(node.text)

    for child in node.children:
        _add_node(builder, child)
        if child.tail is not None:
            builder.data(child.tail)

    builder.end(node.tag)


def encode_xml(root: XmlNode) -> bytes:
    try:
        if root.tail is not None:
            raise ValueError(
                'У корневого элемента не может быть tail'
            )

        builder = _LimitedTreeBuilder()
        _add_node(builder, root)
        return tostring(
            builder.close(),
            encoding='utf-8',
            xml_declaration=True
        )
    except ValueError as exc:
        raise InvalidDocumentError(str(exc)) from exc


def _to_node(element: Element) -> XmlNode:
    return XmlNode(
        tag=element.tag,
        attrib=element.attrib,
        text=element.text,
        tail=element.tail,
        children=[_to_node(child) for child in element]
    )


def decode_xml(raw: bytes) -> XmlNode:
    try:
        parser = DefusedXMLParser(
            target=_LimitedTreeBuilder(),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True
        )
        parser.feed(raw)
        return _to_node(parser.close())
    except (DefusedXmlException, ParseError, ValueError, LookupError) as exc:
        raise InvalidDocumentError(
            'Файл содержит некорректный или неподдерживаемый XML'
        ) from exc
