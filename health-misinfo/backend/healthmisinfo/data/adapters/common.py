from __future__ import annotations

import ast
import hashlib
from pathlib import Path


class SchemaError(ValueError):
    """Raised when an input file does not have the columns an adapter requires."""


def file_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_url_list(value) -> list[str]:
    """Parse URL lists stored as Python tuple/list literals ("('a', 'b')"), JSON, or delimited text.

    Uses ``ast.literal_eval`` (literals only, no code execution)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "()", "[]"}:
        return []
    if s[0] in "([":
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, str):
                parsed = [parsed]
            return [str(v).strip() for v in parsed if str(v).strip()]
        except (ValueError, SyntaxError):
            pass
    for sep in ("|", ";", ",", " "):
        if sep in s:
            return [p.strip() for p in s.split(sep) if p.strip().startswith("http")]
    return [s] if s.startswith("http") else []


def clean_str(value) -> str | None:
    if value is None:
        return None
    s = str(value)
    if s.strip().lower() in {"", "nan", "none", "null"}:
        return None
    return s


def require_columns(columns, required: list[str], adapter: str) -> None:
    missing = [c for c in required if c not in columns]
    if missing:
        raise SchemaError(f"{adapter}: missing required column(s) {missing}; found {list(columns)}")
