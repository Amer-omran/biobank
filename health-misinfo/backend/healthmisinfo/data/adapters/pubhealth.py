"""PUBHEALTH adapter (github.com/neemakot/Health-Fact-Checking).

Expects the official TSV files (``train.tsv``, ``dev.tsv``, ``test.tsv``) placed manually in a
directory (Google Drive is not reachable from the build environment). The adapter verifies the real
columns and refuses to guess: a file without a ``label`` column is imported with no labels.
The original split name is preserved in ``extra.original_split``; the platform re-splits with
group awareness, and this is documented in the methodology.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from healthmisinfo.data.adapters.common import (
    SchemaError,
    clean_str,
    file_sha256,
    parse_url_list,
    require_columns,
)
from healthmisinfo.data.records import AdapterResult, RawRecord

FILES = {"train": "train.tsv", "dev": "dev.tsv", "test": "test.tsv"}


def load_pubhealth(directory: Path | str) -> AdapterResult:
    directory = Path(directory)
    present = {k: directory / f for k, f in FILES.items() if (directory / f).exists()}
    if not present:
        raise SchemaError(
            f"pubhealth: none of {list(FILES.values())} found in {directory}. Download PUBHEALTH from "
            "the official link in github.com/neemakot/Health-Fact-Checking/data/README.md and unzip it there."
        )
    records: list[RawRecord] = []
    rows_read = 0
    hashes = []
    notes = []
    schema: list[str] = []
    for split, p in present.items():
        df = pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)
        require_columns(df.columns, ["claim_id", "claim"], f"pubhealth/{p.name}")
        schema = sorted(set(schema) | set(df.columns))
        has_label = "label" in df.columns
        if not has_label:
            notes.append(f"{p.name}: no 'label' column – imported without labels")
        rows_read += len(df)
        hashes.append(file_sha256(p))
        for _, r in df.iterrows():
            records.append(
                RawRecord(
                    external_id=clean_str(r["claim_id"]),
                    language="en",
                    text=clean_str(r["claim"]),
                    original_label=clean_str(r["label"]) if has_label else None,
                    original_labels={"label": clean_str(r["label"]) if has_label else None},
                    source_category=clean_str(r.get("subjects")),
                    source_url=None,
                    evidence_urls=parse_url_list(r.get("sources")),
                    claim_date=clean_str(r.get("date_published")),
                    extra={
                        "original_split": split,
                        "fact_checkers": clean_str(r.get("fact_checkers")),
                        "has_explanation": bool(clean_str(r.get("explanation"))),
                    },
                )
            )
    combined = hashlib.sha256("".join(hashes).encode()).hexdigest()
    return AdapterResult(
        records=records,
        source_key="pubhealth",
        language="en",
        file_name=",".join(p.name for p in present.values()),
        file_sha256=combined,
        rows_read=rows_read,
        schema=schema,
        notes=notes,
    )
