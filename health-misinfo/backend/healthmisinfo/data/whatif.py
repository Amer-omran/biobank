"""What-if analysis: label distribution and split feasibility IF every *proposed* mapping entry of a
source were approved as proposed. Reads real files, modifies nothing, approves nothing.

    python -m healthmisinfo.data.whatif --source arafacts --file "../data/raw/arafacts/Dataset/AraFacts 2/AraFacts 2.csv"
"""

from __future__ import annotations

import argparse
import json
import warnings
from collections import Counter

import numpy as np

from healthmisinfo.data.adapters.arafacts import load_arafacts
from healthmisinfo.data.adapters.pubhealth import load_pubhealth
from healthmisinfo.data.dedup import GroupItem, compute_groups
from healthmisinfo.data.pipeline import MIN_TRAIN_CHARS
from healthmisinfo.data.registry import load_mapping_file
from healthmisinfo.data.split import SplitVerificationError, assign_and_verify
from healthmisinfo.labels import Label
from healthmisinfo.text.normalize import match_key_hash, normalize_for_model


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["arafacts", "pubhealth"], required=True)
    ap.add_argument("--file", required=True, help="AraFacts CSV or PUBHEALTH directory")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)
    res = load_arafacts(a.file) if a.source == "arafacts" else load_pubhealth(a.file)
    ci = a.source == "pubhealth"
    entries = {(e["original"].lower() if ci else e["original"]): e for e in load_mapping_file(a.source)["entries"]}
    rows = [r for r in res.records if r.text and len(normalize_for_model(r.text, r.language)) >= MIN_TRAIN_CHARS]
    tgt = [entries.get(((r.original_label or "").lower() if ci else r.original_label), {}).get("proposed_label", "UNLISTED") for r in rows]
    out = {"hypothetical": "all proposed entries approved as proposed", "rows_with_text": len(rows), "targets": dict(Counter(tgt))}
    out["by_ambiguity"] = {
        f"{k[0]}:{k[1]}": v
        for k, v in Counter(
            (entries.get(((r.original_label or "").lower() if ci else r.original_label), {}).get("ambiguity", "?"), t) for r, t in zip(rows, tgt, strict=True)
        ).items()
    }
    keep = [(r, t) for r, t in zip(rows, tgt, strict=True) if t in Label.__members__]
    labels = np.array([int(Label[t]) for _, t in keep])
    groups, st = compute_groups([GroupItem(match_key_hash(r.text), normalize_for_model(r.text, r.language), r.source_url) for r, _ in keep])
    out["groups"] = {"groups": st["groups"], "multi_member_groups": st["multi_member_groups"]}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, ver = assign_and_verify(labels, np.array(groups), seed=a.seed)
        out["split"] = {"feasible": True, **ver}
    except SplitVerificationError as e:
        out["split"] = {"feasible": False, "reason": str(e), **e.verification}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
