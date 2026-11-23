"""AraFacts adapter (gitlab.com/bigirqu/AraFacts, CC BY-NC 4.0).

* Keeps the claim text and the fact-checker's ORIGINAL label (``source_label``) verbatim; the
  authors' ``normalized_label`` and categories are preserved in ``extra``/``original_labels``.
* Health filter: ``normalized_category == 'Health'`` (default). This is the authors' own topical
  normalization; it is recorded in the dataset params.
* ``claim_urls`` (links to social-media posts spreading the claim, which identify individual
  accounts) are NOT stored – only their count – to avoid storing personal data.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from healthmisinfo.data.adapters.common import clean_str, file_sha256, parse_url_list, require_columns, safe_url
from healthmisinfo.data.records import AdapterResult, RawRecord

REQUIRED = [
    "ClaimID",
    "claim",
    "source",
    "date",
    "source_label",
    "normalized_label",
    "source_category",
    "normalized_category",
    "source_url",
    "evidence_urls",
    "claim_type",
]
CLAIM_TYPES = {0: "text", 1: "image", 2: "video"}


def load_arafacts(path: Path | str, categories: list[str] | None = ("Health",)) -> AdapterResult:
    path = Path(path)
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    require_columns(df.columns, REQUIRED, "arafacts")
    rows_read = len(df)
    filtered: dict[str, int] = {}
    if categories:
        mask = df["normalized_category"].isin(list(categories))
        filtered["category_not_selected"] = int((~mask).sum())
        df = df[mask]

    evidence_cols = [c for c in df.columns if c.startswith("evidence_urls")]
    records: list[RawRecord] = []
    for _, r in df.iterrows():
        evidence: list[str] = []
        for c in evidence_cols:
            for u in parse_url_list(r.get(c)):
                if u not in evidence:
                    evidence.append(u)
        claim_type_raw = clean_str(r.get("claim_type"))
        try:
            claim_type = CLAIM_TYPES.get(int(float(claim_type_raw))) if claim_type_raw else None
        except ValueError:
            claim_type = None
        records.append(
            RawRecord(
                external_id=clean_str(r["ClaimID"]),
                language="ar",
                text=clean_str(r["claim"]),
                original_label=clean_str(r["source_label"]),
                original_labels={
                    "source_label": clean_str(r["source_label"]),
                    "normalized_label": clean_str(r["normalized_label"]),
                },
                source_category=clean_str(r["source_category"]),
                source_url=safe_url(r["source_url"]),
                evidence_urls=evidence,
                claim_date=clean_str(r["date"]),
                extra={
                    "fact_checker": clean_str(r["source"]),
                    "normalized_category": clean_str(r["normalized_category"]),
                    "claim_type": claim_type,
                    "claim_url_count": len(parse_url_list(r.get("claim_urls"))),
                    "has_description": bool(clean_str(r.get("description"))),
                },
            )
        )
    return AdapterResult(
        records=records,
        source_key="arafacts",
        language="ar",
        file_name=path.name,
        file_sha256=file_sha256(path),
        rows_read=rows_read,
        filtered_out=filtered,
        schema=list(df.columns),
        notes=[f"category filter: {list(categories) if categories else 'none'}"],
    )
