"""Import adapter output into the database and (re)compute labels, duplicates and eligibility.

Every exclusion carries a machine-readable ``exclusion_reason``; nothing is deleted. Re-running
``refresh_dataset`` after a label-mapping approval, a license review or new human reviews is
idempotent.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from healthmisinfo.audit import audit
from healthmisinfo.config import get_settings
from healthmisinfo.data.dedup import GroupItem, compute_groups
from healthmisinfo.data.records import AdapterResult
from healthmisinfo.data.registry import (
    MAPPED,
    NO_LABEL,
    NO_MAPPING_DEFINED,
    PENDING_APPROVAL,
    LabelMapper,
)
from healthmisinfo.db.models import Annotation, Dataset, DatasetSample, ExpertReview, SourceRegistry
from healthmisinfo.reviews import resolve
from healthmisinfo.text.normalize import NORMALIZATION_VERSION, match_key_hash, normalize_for_model
from healthmisinfo.text.topics import TOPIC_VERSION, tag_topic

MIN_TRAIN_CHARS = 10
NEAR_DUP_MAX_ROWS_AT_IMPORT = 20000

# eligibility values
ELIGIBLE = "eligible"
EXCLUDED = "excluded"
PENDING = "pending"


class ImportError_(ValueError):
    pass


def _chunks(seq, n=500):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def import_records(
    db: Session,
    result: AdapterResult,
    *,
    name: str,
    version: str,
    mapper: LabelMapper | None,
    is_synthetic: bool = False,
    created_by_id: int | None = None,
    params: dict | None = None,
    notes: str | None = None,
    rejected_rows: int = 0,
    row_errors: list[dict] | None = None,
    license_confirmed_by_uploader: bool = False,
) -> Dataset:
    if db.scalar(select(Dataset).where(Dataset.name == name, Dataset.version == version)):
        raise ImportError_(f"Dataset {name!r} version {version!r} already exists; use a new version")

    source = db.scalar(select(SourceRegistry).where(SourceRegistry.key == result.source_key))
    ds = Dataset(
        name=name,
        version=version,
        language=result.language,
        kind="import",
        status="processing",
        is_synthetic=is_synthetic,
        source_id=source.id if source else None,
        file_name=result.file_name,
        file_sha256=result.file_sha256,
        label_mapping_version=mapper.version if mapper else None,
        label_mapping_sha256=mapper.sha256 if mapper else None,
        row_count=result.rows_read,
        rejected_count=rejected_rows,
        params={
            **(params or {}),
            "source_key": result.source_key,
            "normalization_version": NORMALIZATION_VERSION,
            "topic_version": TOPIC_VERSION,
            "pre_import_filters": result.filtered_out,
            "adapter_notes": result.notes,
            "schema": result.schema,
            "row_errors": (row_errors or [])[:200],
            "license_confirmed_by_uploader": license_confirmed_by_uploader,
            "mapping": mapper.summary() if mapper else None,
        },
        notes=notes,
        created_by_id=created_by_id,
    )
    db.add(ds)
    db.flush()

    samples: list[DatasetSample] = []
    for i, rec in enumerate(result.records, start=1):
        has_text = rec.text is not None and rec.text.strip() != ""
        if mapper:
            mapped, mstatus = mapper.apply(rec.original_label)
        else:
            mapped, mstatus = None, (NO_MAPPING_DEFINED if rec.original_label else NO_LABEL)
        extra = dict(rec.extra)
        if rec.group_key:
            extra["group_key"] = rec.group_key
        samples.append(
            DatasetSample(
                dataset_id=ds.id,
                row_number=i,
                external_id=(rec.external_id or "")[:128] or None,
                language=rec.language,
                text_available=has_text,
                original_text=rec.text if has_text else None,
                normalized_text=normalize_for_model(rec.text, rec.language) if has_text else None,
                match_key_hash=match_key_hash(rec.text) if has_text else None,
                original_label=(rec.original_label or None) and rec.original_label[:255],
                original_labels=rec.original_labels,
                mapped_label=mapped,
                mapping_status=mstatus,
                health_topic=tag_topic(rec.text) if has_text else None,
                source_category=(rec.source_category or None) and rec.source_category[:128],
                source_url=rec.source_url,
                evidence_urls=rec.evidence_urls,
                claim_date=(rec.claim_date or None) and rec.claim_date[:40],
                is_synthetic=is_synthetic,
                extra=extra,
            )
        )
    db.add_all(samples)
    db.flush()

    if mapper:
        db.add_all(
            Annotation(
                sample_id=s.id,
                annotator_kind="source_mapping",
                label=s.mapped_label,
                mapping_version=mapper.version,
                rationale=f"{mapper.maps_from_field}={s.original_label}",
            )
            for s in samples
            if s.mapping_status == MAPPED
        )

    # Within-dataset leakage groups (re-computed across datasets at split time).
    with_text = [s for s in samples if s.text_available]
    if 0 < len(with_text) <= NEAR_DUP_MAX_ROWS_AT_IMPORT:
        groups, gstats = compute_groups([GroupItem(s.match_key_hash, s.normalized_text, s.source_url, s.extra.get("group_key")) for s in with_text])
        for s, g, sim in zip(with_text, groups, gstats.pop("max_similarity"), strict=True):
            s.group_id = g
            s.near_duplicate_score = round(sim, 4) if sim else None
        ds.params = {**ds.params, "import_grouping": gstats}

    refresh_dataset(db, ds)
    ds.status = "ready"
    ds.imported_count = len(samples)
    audit(
        db,
        "dataset.import",
        "dataset",
        ds.id,
        actor_id=created_by_id,
        details={
            "name": name,
            "version": version,
            "source_key": result.source_key,
            "file_sha256": result.file_sha256,
            "rows_read": result.rows_read,
            "imported": len(samples),
            "rejected": rejected_rows,
            "is_synthetic": is_synthetic,
            "mapping_version": mapper.version if mapper else None,
        },
    )
    db.flush()
    return ds


def _license_ok(db: Session, ds: Dataset) -> bool:
    if ds.source_id is None:
        return bool(ds.params.get("license_confirmed_by_uploader"))
    src = db.get(SourceRegistry, ds.source_id)
    return src is not None and src.license_status == "verified"


def refresh_dataset(db: Session, ds: Dataset, mapper: LabelMapper | None = None) -> dict:
    """Re-apply mapping (optional), duplicates, review resolution and eligibility for a dataset."""
    settings = get_settings()
    samples = list(db.scalars(select(DatasetSample).where(DatasetSample.dataset_id == ds.id)))
    by_id = {s.id: s for s in samples}

    if mapper is not None:
        changed = 0
        for s in samples:
            new_label, new_status = mapper.apply(s.original_label)
            if (new_label, new_status) != (s.mapped_label, s.mapping_status):
                s.mapped_label, s.mapping_status = new_label, new_status
                changed += 1
                if new_status == MAPPED:
                    db.add(
                        Annotation(
                            sample_id=s.id,
                            annotator_kind="source_mapping",
                            label=new_label,
                            mapping_version=mapper.version,
                            rationale=f"{mapper.maps_from_field}={s.original_label}",
                        )
                    )
        ds.label_mapping_version = mapper.version
        ds.label_mapping_sha256 = mapper.sha256
        ds.params = {**ds.params, "mapping": mapper.summary(), "last_remap_changed": changed}

    # Exact duplicates against earlier samples (same language, same synthetic-ness).
    hashes = sorted({s.match_key_hash for s in samples if s.match_key_hash})
    canonical: dict[str, int] = {}
    all_members: dict[str, list[tuple[int, int | None, str | None]]] = defaultdict(list)
    for chunk in _chunks(hashes):
        rows = db.execute(
            select(
                DatasetSample.id,
                DatasetSample.match_key_hash,
                DatasetSample.mapped_label,
                DatasetSample.final_label_source,
            ).where(
                DatasetSample.match_key_hash.in_(chunk),
                DatasetSample.language == ds.language if ds.language != "multi" else true(),
                DatasetSample.is_synthetic == ds.is_synthetic,
            )
        ).all()
        for sid, h, ml, fls in rows:
            all_members[h].append((sid, ml, fls))
            if h not in canonical or sid < canonical[h]:
                canonical[h] = sid
    for s in samples:
        if s.match_key_hash and canonical.get(s.match_key_hash, s.id) != s.id:
            s.duplicate_of_id = canonical[s.match_key_hash]
        else:
            s.duplicate_of_id = None

    # Reviews for this dataset's samples (bulk).
    reviews_by_sample: dict[int, list[ExpertReview]] = defaultdict(list)
    ids = list(by_id)
    for chunk in _chunks(ids):
        for r in db.scalars(select(ExpertReview).where(ExpertReview.sample_id.in_(chunk))):
            reviews_by_sample[r.sample_id].append(r)

    for s in samples:
        res = resolve(
            reviews_by_sample.get(s.id, []),
            settings.reviews_required,
            source_label=s.mapped_label if s.mapping_status == MAPPED else None,
        )
        if res.status == "unreviewed" and s.review_status == "pending":
            res.status = "pending"
        s.review_status = res.status
        s.final_label = res.final_label
        s.final_label_source = res.final_label_source

    license_ok = _license_ok(db, ds)
    for s in samples:
        conflict = False
        if s.match_key_hash and s.duplicate_of_id is None and s.final_label_source == "source_mapping":
            labels = {ml for (_, ml, fls) in all_members.get(s.match_key_hash, []) if ml is not None}
            conflict = len(labels) > 1
        s.eligibility, s.exclusion_reason = _eligibility(s, ds, license_ok, conflict)

    stats = dataset_stats(samples)
    ds.stats = stats
    ds.duplicate_count = stats["exclusion_reasons"].get("exact_duplicate", 0)
    db.flush()
    return stats


def refresh_sample(db: Session, s: DatasetSample, reviews_required: int) -> None:
    """Recompute review resolution and eligibility for one sample (after a new review)."""
    ds = db.get(Dataset, s.dataset_id)
    reviews = list(db.scalars(select(ExpertReview).where(ExpertReview.sample_id == s.id)))
    res = resolve(reviews, reviews_required, source_label=s.mapped_label if s.mapping_status == MAPPED else None)
    if res.status == "unreviewed" and s.review_status == "pending":
        res.status = "pending"
    s.review_status, s.final_label, s.final_label_source = res.status, res.final_label, res.final_label_source
    conflict = False
    if s.match_key_hash and s.duplicate_of_id is None and s.final_label_source == "source_mapping":
        labels = set(
            db.scalars(
                select(DatasetSample.mapped_label).where(
                    DatasetSample.match_key_hash == s.match_key_hash,
                    DatasetSample.language == s.language,
                    DatasetSample.is_synthetic == s.is_synthetic,
                    DatasetSample.mapped_label.is_not(None),
                )
            )
        )
        conflict = len(labels) > 1
    s.eligibility, s.exclusion_reason = _eligibility(s, ds, _license_ok(db, ds), conflict)
    db.flush()


def _eligibility(s: DatasetSample, ds: Dataset, license_ok: bool, conflict: bool) -> tuple[str, str | None]:
    if ds.is_synthetic or s.is_synthetic:
        return EXCLUDED, "synthetic_fixture"
    if not s.text_available:
        return EXCLUDED, "text_unavailable"
    if len(s.normalized_text or "") < MIN_TRAIN_CHARS:
        return EXCLUDED, "text_too_short"
    if s.duplicate_of_id is not None:
        return EXCLUDED, "exact_duplicate"
    if s.review_status == "disagreement":
        return PENDING, "review_disagreement"
    if s.final_label is None:
        if s.mapping_status == PENDING_APPROVAL:
            return PENDING, "pending_mapping_approval"
        if s.mapping_status == "excluded_by_mapping":
            return EXCLUDED, "excluded_by_mapping"
        return PENDING, "no_approved_label"
    if conflict:
        return PENDING, "label_conflict"
    if not license_ok:
        return PENDING, "license_review_required"
    return ELIGIBLE, None


def dataset_stats(samples: list[DatasetSample]) -> dict:
    lengths = [len(s.original_text) for s in samples if s.original_text]
    final = Counter(s.final_label for s in samples if s.eligibility == ELIGIBLE)
    return {
        "total": len(samples),
        "eligible": sum(1 for s in samples if s.eligibility == ELIGIBLE),
        "eligible_human_reviewed": sum(1 for s in samples if s.eligibility == ELIGIBLE and s.final_label_source in ("human_review", "adjudication")),
        "eligibility": dict(Counter(s.eligibility for s in samples)),
        "exclusion_reasons": dict(Counter(s.exclusion_reason for s in samples if s.exclusion_reason)),
        "mapping_status": dict(Counter(s.mapping_status for s in samples)),
        "original_labels": dict(Counter(s.original_label or "(none)" for s in samples).most_common(60)),
        "eligible_label_distribution": {str(k): v for k, v in sorted(final.items())},
        "review_status": dict(Counter(s.review_status for s in samples)),
        "health_topics": dict(Counter(s.health_topic or "(no text)" for s in samples)),
        "text_available": sum(1 for s in samples if s.text_available),
        "text_length": {
            "min": min(lengths) if lengths else None,
            "max": max(lengths) if lengths else None,
            "mean": round(sum(lengths) / len(lengths), 1) if lengths else None,
        },
        "groups": len({s.group_id for s in samples if s.group_id}),
    }
