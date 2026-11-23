"""Group-aware, stratified train/validation/test splitting with explicit verification.

* Candidates: eligible, non-synthetic samples of ONE language with a final label.
* Leakage groups are recomputed across all candidate datasets (exact + near duplicates, shared
  fact-check URL, researcher group keys) and every group is kept within a single split.
* ``StratifiedGroupKFold`` carves ≈15% test, then ≈15% validation from the remainder.
* Verification: disjoint groups across splits and all three classes present in every split.
  If verification fails a ``SplitError`` is raised with a full report – an invalid split is never
  written or registered.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from healthmisinfo.audit import audit
from healthmisinfo.config import get_settings
from healthmisinfo.data.dedup import DEFAULT_NEAR_DUP_THRESHOLD, GroupItem, compute_groups
from healthmisinfo.data.pipeline import ELIGIBLE
from healthmisinfo.db.models import Dataset, DatasetSample, SourceRegistry, SplitAssignment
from healthmisinfo.labels import LABEL_NAMES, Label
from healthmisinfo.text.normalize import NORMALIZATION_VERSION

SPLITS = ("train", "validation", "test")
CSV_COLUMNS = [
    "sample_id",
    "dataset_id",
    "source_key",
    "external_id",
    "group_id",
    "label",
    "label_name",
    "label_source",
    "health_topic",
    "text",
    "original_text",
]


class SplitError(ValueError):
    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


@dataclass
class SplitResult:
    dataset: Dataset | None
    report: dict
    files: dict[str, str] = field(default_factory=dict)


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _kfold_pick(labels, groups, frac: float, seed: int) -> np.ndarray:
    from sklearn.model_selection import StratifiedGroupKFold

    n_splits = max(2, round(1 / frac))
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    X = np.zeros((len(labels), 1))
    _, held = next(iter(sgkf.split(X, labels, groups)))
    return held


class SplitVerificationError(ValueError):
    def __init__(self, message: str, verification: dict):
        super().__init__(message)
        self.verification = verification


def assign_and_verify(labels: np.ndarray, groups: np.ndarray, seed: int, test_frac: float = 0.15, val_frac: float = 0.15):
    """Pure function: group-aware stratified assignment + verification. Raises SplitVerificationError."""
    idx = np.arange(len(labels))
    test_local = _kfold_pick(labels, groups, test_frac, seed)
    rest = np.setdiff1d(idx, test_local)
    val_local = rest[_kfold_pick(labels[rest], groups[rest], val_frac / (1 - test_frac), seed + 1)]
    train_local = np.setdiff1d(rest, val_local)
    assign = {"train": train_local, "validation": val_local, "test": test_local}
    gsets = {k: set(groups[v].tolist()) for k, v in assign.items()}
    overlap = (gsets["train"] & gsets["validation"]) | (gsets["train"] & gsets["test"]) | (gsets["validation"] & gsets["test"])
    verification = {
        "split_sizes": {k: int(len(v)) for k, v in assign.items()},
        "actual_ratios": {k: round(len(v) / len(labels), 4) for k, v in assign.items()},
        "label_distribution": {k: {LABEL_NAMES[c]: int((labels[v] == c).sum()) for c in Label} for k, v in assign.items()},
        "group_overlap": len(overlap),
    }
    if overlap:
        raise SplitVerificationError(f"{len(overlap)} group(s) appear in more than one split (leakage).", verification)
    empty = [f"{k}:{c}" for k, d in verification["label_distribution"].items() for c, n in d.items() if n == 0]
    if empty:
        raise SplitVerificationError(f"Split(s) missing a class: {empty}. Not forcing an invalid split.", verification)
    return assign, verification


def candidate_samples(db: Session, language: str, dataset_ids: list[int] | None, require_human_review: bool) -> list[DatasetSample]:
    q = (
        select(DatasetSample)
        .join(Dataset, Dataset.id == DatasetSample.dataset_id)
        .where(
            DatasetSample.language == language,
            DatasetSample.eligibility == ELIGIBLE,
            DatasetSample.is_synthetic.is_(False),
            Dataset.is_synthetic.is_(False),
            Dataset.kind == "import",
            DatasetSample.final_label.is_not(None),
        )
        .order_by(DatasetSample.id)
    )
    if dataset_ids:
        q = q.where(DatasetSample.dataset_id.in_(dataset_ids))
    rows = list(db.scalars(q))
    if require_human_review:
        rows = [s for s in rows if s.final_label_source in ("human_review", "adjudication")]
    return rows


def build_splits(
    db: Session,
    language: str,
    *,
    version: str,
    dataset_ids: list[int] | None = None,
    seed: int = 42,
    test_frac: float = 0.15,
    val_frac: float = 0.15,
    require_human_review: bool = False,
    near_dup_threshold: float = DEFAULT_NEAR_DUP_THRESHOLD,
    out_root: Path | None = None,
    created_by_id: int | None = None,
) -> SplitResult:
    if language not in ("ar", "en"):
        raise ValueError("language must be 'ar' or 'en'")
    name = f"{language}-split"
    if db.scalar(select(Dataset).where(Dataset.name == name, Dataset.version == version)):
        raise ValueError(f"Split {name} {version} already exists")

    settings = get_settings()
    samples = candidate_samples(db, language, dataset_ids, require_human_review)
    report: dict = {
        "language": language,
        "version": version,
        "seed": seed,
        "requested_ratios": {"train": round(1 - test_frac - val_frac, 3), "validation": val_frac, "test": test_frac},
        "require_human_review": require_human_review,
        "near_dup_threshold": near_dup_threshold,
        "normalization_version": NORMALIZATION_VERSION,
        "candidate_count": len(samples),
        "target_per_language": settings.target_samples_per_language,
        "shortfall_vs_target": max(0, settings.target_samples_per_language - len(samples)),
        "candidate_label_distribution": {LABEL_NAMES[k]: v for k, v in sorted(Counter(s.final_label for s in samples).items())},
        "problems": [],
    }
    # Exclusion overview across the language's import datasets (for the methodology chapter).
    excl = db.execute(
        select(DatasetSample.exclusion_reason, DatasetSample.eligibility)
        .join(Dataset, Dataset.id == DatasetSample.dataset_id)
        .where(DatasetSample.language == language, Dataset.kind == "import", Dataset.is_synthetic.is_(False))
    ).all()
    report["exclusion_overview"] = dict(Counter(f"{e}:{r}" for r, e in excl if e != ELIGIBLE))

    def fail(msg: str) -> None:
        report["problems"].append(msg)
        report["status"] = "invalid"
        audit(db, "split.failed", "split", f"{name}:{version}", actor_id=created_by_id, details=report)
        db.flush()
        raise SplitError(msg, report)

    if not samples:
        fail("No eligible labelled samples for this language (check label-mapping approval, license review and exclusions).")

    items = [GroupItem(s.match_key_hash, s.normalized_text or "", s.source_url, s.extra.get("group_key")) for s in samples]
    groups, gstats = compute_groups(items, near_dup_threshold)
    gstats.pop("max_similarity", None)
    report["grouping"] = gstats
    labels = np.array([s.final_label for s in samples])
    groups_arr = np.array(groups)

    present = set(labels.tolist())
    missing = [LABEL_NAMES[c] for c in Label if c not in present]
    if missing:
        fail(f"Class(es) {missing} have no eligible samples; a 3-class split is impossible.")
    groups_per_class = {LABEL_NAMES[c]: len(set(groups_arr[labels == c])) for c in present}
    report["groups_per_class"] = groups_per_class
    too_small = [c for c, n in groups_per_class.items() if n < 3]
    if too_small:
        fail(f"Class(es) {too_small} have fewer than 3 independent groups; cannot place them in all three splits.")

    try:
        assign, verification = assign_and_verify(labels, groups_arr, seed, test_frac, val_frac)
    except SplitVerificationError as e:
        report.update(e.verification)
        fail(str(e))
    report.update(verification)

    # Write files
    out_root = out_root or settings.data_dir / "processed"
    out_dir = out_root / language / version
    out_dir.mkdir(parents=True, exist_ok=True)
    source_keys = dict(db.execute(select(Dataset.id, SourceRegistry.key).join(SourceRegistry, SourceRegistry.id == Dataset.source_id, isouter=True)).all())
    files = {}
    for split_name, local in assign.items():
        p = out_dir / f"{split_name}.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            w.writeheader()
            for i in sorted(local.tolist(), key=lambda k: samples[k].id):
                s = samples[i]
                w.writerow(
                    {
                        "sample_id": s.id,
                        "dataset_id": s.dataset_id,
                        "source_key": source_keys.get(s.dataset_id) or "user_upload",
                        "external_id": s.external_id,
                        "group_id": groups[i],
                        "label": s.final_label,
                        "label_name": LABEL_NAMES[s.final_label],
                        "label_source": s.final_label_source,
                        "health_topic": s.health_topic,
                        "text": s.normalized_text,
                        "original_text": s.original_text,
                    }
                )
        files[split_name] = str(p)
    report["files"] = {k: {"path": v, "sha256": _sha256_file(Path(v))} for k, v in files.items()}
    report["data_sha256"] = hashlib.sha256("".join(report["files"][k]["sha256"] for k in SPLITS).encode()).hexdigest()
    report["status"] = "valid"
    (out_dir / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    ds = Dataset(
        name=name,
        version=version,
        language=language,
        kind="split",
        status="ready",
        file_name=str(out_dir),
        file_sha256=report["data_sha256"],
        row_count=len(samples),
        imported_count=len(samples),
        params={k: report[k] for k in ("seed", "requested_ratios", "require_human_review", "near_dup_threshold")} | {"dataset_ids": dataset_ids},
        stats=report,
        created_by_id=created_by_id,
    )
    db.add(ds)
    db.flush()
    db.add_all(
        SplitAssignment(
            split_dataset_id=ds.id,
            sample_id=samples[i].id,
            split=split_name,
            group_id=groups[i],
            label=int(samples[i].final_label),
        )
        for split_name, local in assign.items()
        for i in local.tolist()
    )
    audit(db, "split.created", "dataset", ds.id, actor_id=created_by_id, details={k: report[k] for k in ("split_sizes", "label_distribution", "data_sha256")})
    db.flush()
    return SplitResult(dataset=ds, report=report, files=files)
