import json
from math import isfinite

from pydantic import JsonValue

from app.core.exceptions import InvalidDocumentError

MAX_JSON_DEPTH = 64


def validate_json(
    data: JsonValue,
    depth: int = 0
) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError('Слишком большая вложенность')

    if isinstance(data, str):
        data.encode('utf-8')
    elif isinstance(data, float):
        if not isfinite(data):
            raise ValueError('Неконечное число')
    elif isinstance(data, list):
        for child in data:
            validate_json(child, depth + 1)
    elif isinstance(data, dict):
        for key, child in data.items():
            key.encode('utf-8')
            validate_json(child, depth + 1)


def encode_json(data: JsonValue) -> bytes:
    validate_json(data)
    return json.dumps(
        data,
        ensure_ascii=False,
        allow_nan=False
    ).encode('utf-8')


def decode_json(raw: bytes) -> JsonValue:
    try:
        data: JsonValue = json.loads(raw.decode('utf-8'))
        validate_json(data)
        return data
    except (ValueError, RecursionError) as exc:
        raise InvalidDocumentError('Файл содержит некорректный JSON') from exc
