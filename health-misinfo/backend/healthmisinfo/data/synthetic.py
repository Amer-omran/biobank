"""Build a SYNTHETIC split from a fixture CSV – for pipeline smoke tests only.

The manifest is flagged ``synthetic: true``; ``ml/train.py`` refuses it unless explicitly run as a
smoke test, and ``ml/registry.py`` refuses to register any model trained on it.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from healthmisinfo.data.split import CSV_COLUMNS, SPLITS, assign_and_verify
from healthmisinfo.labels import LABEL_NAMES, Label
from healthmisinfo.text.normalize import normalize_for_model
from healthmisinfo.text.topics import tag_topic


def make_synthetic_split(fixture_csv: Path, language: str, out_dir: Path, seed: int = 42) -> dict:
    with Path(fixture_csv).open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or any(r.get("is_synthetic", "").lower() != "true" for r in rows):
        raise ValueError("make_synthetic_split only accepts fixtures where every row has is_synthetic=true")
    labels = np.array([int(Label[r["label"]]) for r in rows])
    groups = np.array([r.get("group_key") or r["id"] for r in rows])
    assign, verification = assign_and_verify(labels, groups, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, idxs in assign.items():
        p = out_dir / f"{name}.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            w.writeheader()
            for i in sorted(idxs.tolist()):
                r = rows[i]
                w.writerow(
                    {
                        "sample_id": r["id"],
                        "dataset_id": "",
                        "source_key": "synthetic_fixture",
                        "external_id": r["id"],
                        "group_id": groups[i],
                        "label": int(labels[i]),
                        "label_name": LABEL_NAMES[labels[i]],
                        "label_source": "synthetic",
                        "health_topic": tag_topic(r["text"]),
                        "text": normalize_for_model(r["text"], language),
                        "original_text": r["text"],
                    }
                )
        files[name] = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    manifest = {
        "status": "valid",
        "synthetic": True,
        "language": language,
        "version": f"synthetic-{Path(fixture_csv).stem}-s{seed}",
        "seed": seed,
        "files": files,
        "data_sha256": hashlib.sha256("".join(files[k]["sha256"] for k in SPLITS).encode()).hexdigest(),
        **verification,
        "candidate_count": len(rows),
        "note": "SYNTHETIC FIXTURE SPLIT - software smoke tests only",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
