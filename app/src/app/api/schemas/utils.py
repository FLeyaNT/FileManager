def _require_suffix(value: str, suffix: str) -> str:
    if not value.lower().endswith(suffix):
        raise ValueError(f"Ожидается файл с расширением {suffix}")
    return value