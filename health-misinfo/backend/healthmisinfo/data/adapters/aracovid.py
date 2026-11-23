"""AraCOVID19-MFH adapter (github.com/HadjAmeur/AraCovid19-MFH).

The official release contains tweet IDs and 10 label columns only – no text and no license file.
This adapter imports the labels verbatim (``original_labels``) with ``text=None`` so the dataset
can be inspected and counted, but such samples are never eligible for training.

If the research team lawfully hydrates tweets (X API credentials + compliance with X's terms) they
can pass a CSV with columns ``Tweet_ID,text`` via ``hydrated_path``; only then is text attached.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from healthmisinfo.data.adapters.common import clean_str, file_sha256, require_columns
from healthmisinfo.data.records import AdapterResult, RawRecord

LABEL_COLUMNS = [
    "Blame_Negative_Demoralizing_Speech",
    "Contains_Fake_Information",
    "Dialect",
    "Factual",
    "Give_Advice",
    "Hate_Speech",
    "News_or_Opinion",
    "Rise_Moral",
    "Talk_About_Cure_or_Vaccine",
    "Worth_Fact-checking",
]


def load_aracovid(path: Path | str, hydrated_path: Path | str | None = None) -> AdapterResult:
    path = Path(path)
    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)
    require_columns(df.columns, ["Tweet_ID", *LABEL_COLUMNS], "aracovid19_mfh")
    texts: dict[str, str] = {}
    notes = ["Text not distributed by the source; samples are not trainable without lawful hydration."]
    if hydrated_path:
        h = pd.read_csv(hydrated_path, dtype=str, keep_default_na=False)
        require_columns(h.columns, ["Tweet_ID", "text"], "aracovid19_mfh hydrated file")
        texts = {r["Tweet_ID"]: r["text"] for _, r in h.iterrows() if clean_str(r["text"])}
        notes.append(f"hydrated texts supplied for {len(texts)} tweet IDs")

    records = [
        RawRecord(
            external_id=r["Tweet_ID"],
            language="ar",
            text=texts.get(r["Tweet_ID"]),
            original_label=clean_str(r["Contains_Fake_Information"]),
            original_labels={c: clean_str(r[c]) for c in LABEL_COLUMNS},
            source_category="COVID-19 (tweets)",
            extra={"dialect": clean_str(r["Dialect"])},
        )
        for _, r in df.iterrows()
    ]
    return AdapterResult(
        records=records,
        source_key="aracovid19_mfh",
        language="ar",
        file_name=path.name,
        file_sha256=file_sha256(path),
        rows_read=len(df),
        schema=list(df.columns),
        notes=notes,
    )
