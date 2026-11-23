"""Generic CSV / JSON adapter with explicit column mapping and schema validation.

Used by the API upload endpoint and the CLI. Every row error is reported with its row number;
rows that fail validation are rejected (not silently fixed).
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field

import pandas as pd

from healthmisinfo.data.adapters.common import SchemaError, bytes_sha256, clean_str, parse_url_list
from healthmisinfo.data.records import AdapterResult, RawRecord

SUPPORTED_LANGUAGES = {"ar", "en"}


@dataclass
class ColumnMapping:
    text: str = "text"
    label: str | None = "label"
    id: str | None = None
    language: str | None = None  # column name; if None the fixed dataset language is used
    source_url: str | None = None
    evidence_urls: str | None = None
    category: str | None = None
    date: str | None = None
    group_key: str | None = None


@dataclass
class GenericParseResult:
    adapter: AdapterResult
    row_errors: list[dict] = field(default_factory=list)


def _read_frame(data: bytes, file_name: str) -> pd.DataFrame:
    name = file_name.lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
        if name.endswith(".tsv"):
            return pd.read_csv(io.BytesIO(data), sep="\t", dtype=str, keep_default_na=False)
        if name.endswith(".jsonl"):
            rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
            return pd.DataFrame(rows).astype(str)
        if name.endswith(".json"):
            obj = json.loads(data.decode("utf-8"))
            if isinstance(obj, dict):
                obj = obj.get("records") or obj.get("data") or obj.get("samples")
            if not isinstance(obj, list):
                raise SchemaError("JSON must be a list of objects or {'records': [...]}")
            return pd.DataFrame(obj).astype(str)
    except (UnicodeDecodeError, json.JSONDecodeError, pd.errors.ParserError) as e:
        raise SchemaError(f"Could not parse {file_name}: {e}") from e
    raise SchemaError("Unsupported file type; use .csv, .tsv, .json or .jsonl")


def parse_generic(
    data: bytes,
    file_name: str,
    language: str,
    columns: ColumnMapping,
    source_key: str = "user_upload",
    max_text_chars: int = 5000,
) -> GenericParseResult:
    if language not in SUPPORTED_LANGUAGES and not columns.language:
        raise SchemaError(f"language must be one of {sorted(SUPPORTED_LANGUAGES)}")
    df = _read_frame(data, file_name)
    df = df.replace({"nan": "", "None": ""})
    needed = [
        c
        for c in [
            columns.text,
            columns.label,
            columns.id,
            columns.language,
            columns.source_url,
            columns.evidence_urls,
            columns.category,
            columns.date,
            columns.group_key,
        ]
        if c
    ]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise SchemaError(f"Missing column(s) {missing}; file has {list(df.columns)}")

    records: list[RawRecord] = []
    errors: list[dict] = []
    for i, r in enumerate(df.to_dict(orient="records"), start=1):
        text = clean_str(r.get(columns.text))
        lang = (clean_str(r.get(columns.language)) or "").strip().lower() if columns.language else language
        if text is None:
            errors.append({"row": i, "error": "empty text"})
            continue
        if len(text) > max_text_chars:
            errors.append({"row": i, "error": f"text longer than {max_text_chars} characters"})
            continue
        if lang not in SUPPORTED_LANGUAGES:
            errors.append({"row": i, "error": f"unsupported language {lang!r}"})
            continue
        records.append(
            RawRecord(
                external_id=clean_str(r.get(columns.id)) if columns.id else str(i),
                language=lang,
                text=text,
                original_label=clean_str(r.get(columns.label)) if columns.label else None,
                original_labels={columns.label: clean_str(r.get(columns.label))} if columns.label else {},
                source_category=clean_str(r.get(columns.category)) if columns.category else None,
                source_url=clean_str(r.get(columns.source_url)) if columns.source_url else None,
                evidence_urls=parse_url_list(r.get(columns.evidence_urls)) if columns.evidence_urls else [],
                claim_date=clean_str(r.get(columns.date)) if columns.date else None,
                group_key=clean_str(r.get(columns.group_key)) if columns.group_key else None,
                extra={k: v for k, v in r.items() if k not in needed and clean_str(v) is not None and k != "is_synthetic"},
            )
        )
    langs = {rec.language for rec in records} or {language}
    result = AdapterResult(
        records=records,
        source_key=source_key,
        language=langs.pop() if len(langs) == 1 else "multi",
        file_name=file_name,
        file_sha256=bytes_sha256(data),
        rows_read=len(df),
        schema=list(df.columns),
    )
    return GenericParseResult(adapter=result, row_errors=errors)
