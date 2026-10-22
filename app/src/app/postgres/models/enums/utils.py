import enum
from typing import Any


def enum_values(enum_cls: type[enum.Enum]) -> list[Any]:
    return [member.value for member in enum_cls]
