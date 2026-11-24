from __future__ import annotations

import json
import random
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from healthmisinfo.api.deps import get_viewer, require_admin, require_researcher
from healthmisinfo.api.schemas import QueueReviewIn, SourceUpdate, SplitIn, label_name
from healthmisinfo.audit import audit
from healthmisinfo.config import get_settings
from healthmisinfo.data.adapters.common import SchemaError
from healthmisinfo.data.adapters.generic import ColumnMapping, _read_frame, parse_generic
from healthmisinfo.data.pipeline import ImportError_, import_records, refresh_dataset
from healthmisinfo.data.registry import LabelMapper, load_mapping_file, mapping_path
from healthmisinfo.data.split import SplitError, build_splits
from healthmisinfo.db.models import Dataset, DatasetSample, SourceRegistry, User
from healthmisinfo.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["datasets"])

NAME_RE = r"^[A-Za-z0-9._-]{1,120}$"
VERSION_RE = r"^[A-Za-z0-9._-]{1,64}$"
TRUTHY = {"1", "true", "yes", "y", "t"}


def _dataset_dict(ds: Dataset, src: SourceRegistry | None) -> dict:
    st = ds.stats or {}
    return {
        "id": ds.id,
        "name": ds.name,
        "version": ds.version,
        "language": ds.language,
        "kind": ds.kind,
        "status": ds.status,
        "is_synthetic": ds.is_synthetic,
        "source_key": src.key if src else None,
        "source_name": src.name if src else None,
        "license_status": src.license_status if src else ("uploader_confirmed" if ds.params.get("license_confirmed_by_uploader") else "unconfirmed"),
        "file_name": ds.file_name,
        "file_sha256": ds.file_sha256,
        "label_mapping_version": ds.label_mapping_version,
        "row_count": ds.row_count,
        "imported_count": ds.imported_count,
        "rejected_count": ds.rejected_count,
        "duplicate_count": ds.duplicate_count,
        "eligible": st.get("eligible") if ds.kind == "import" else st.get("candidate_count"),
        "created_at": ds.created_at,
        "notes": ds.notes,
    }


async def _read_upload(file: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File exceeds {get_settings().max_upload_mb} MB")
    if not data:
        raise HTTPException(422, "Empty file")
    return data


@router.get("/datasets", summary="Datasets (imports and split versions) with statistics")
def list_datasets(
    kind: str | None = Query(None, pattern="^(import|split|curated)$"),
    include_synthetic: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_viewer),
):
    q = select(Dataset, SourceRegistry).join(SourceRegistry, SourceRegistry.id == Dataset.source_id, isouter=True)
    if kind:
        q = q.where(Dataset.kind == kind)
    if not include_synthetic:
        q = q.where(Dataset.is_synthetic.is_(False))
    rows = db.execute(q.order_by(Dataset.created_at.desc())).all()
    target = get_settings().target_samples_per_language
    progress = {}
    for lang in ("ar", "en"):
        base = (
            select(func.count(DatasetSample.id))
            .join(Dataset, Dataset.id == DatasetSample.dataset_id)
            .where(DatasetSample.language == lang, Dataset.kind == "import", Dataset.is_synthetic.is_(False))
        )
        eligible = db.scalar(base.where(DatasetSample.eligibility == "eligible")) or 0
        reviewed = db.scalar(base.where(DatasetSample.eligibility == "eligible", DatasetSample.final_label_source.in_(["human_review", "adjudication"]))) or 0
        progress[lang] = {
            "target": target,
            "eligible": eligible,
            "eligible_human_reviewed": reviewed,
            "imported": db.scalar(base) or 0,
            "shortfall": max(0, target - eligible),
        }
    return {"items": [_dataset_dict(d, s) for d, s in rows], "progress": progress}


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, db: Session = Depends(get_db), _: User = Depends(get_viewer)):
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(404, "Dataset not found")
    src = db.get(SourceRegistry, ds.source_id) if ds.source_id else None
    return {**_dataset_dict(ds, src), "params": ds.params, "stats": ds.stats}


@router.get("/datasets/{dataset_id}/samples")
def list_samples(
    dataset_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    eligibility: str | None = Query(None, max_length=16),
    exclusion_reason: str | None = Query(None, max_length=128),
    review_status: str | None = Query(None, max_length=20),
    q: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_viewer),
):
    query = select(DatasetSample).where(DatasetSample.dataset_id == dataset_id)
    if eligibility:
        query = query.where(DatasetSample.eligibility == eligibility)
    if exclusion_reason:
        query = query.where(DatasetSample.exclusion_reason == exclusion_reason)
    if review_status:
        query = query.where(DatasetSample.review_status == review_status)
    if q:
        like = f"%{q}%"
        query = query.where(or_(DatasetSample.original_text.ilike(like), DatasetSample.external_id.ilike(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(DatasetSample.row_number).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [
            {
                "id": s.id,
                "row_number": s.row_number,
                "external_id": s.external_id,
                "language": s.language,
                "text": s.original_text,
                "text_available": s.text_available,
                "original_label": s.original_label,
                "original_labels": s.original_labels,
                "mapping_status": s.mapping_status,
                "mapped_label_name": label_name(s.mapped_label),
                "final_label_name": label_name(s.final_label),
                "final_label_source": s.final_label_source,
                "eligibility": s.eligibility,
                "exclusion_reason": s.exclusion_reason,
                "review_status": s.review_status,
                "health_topic": s.health_topic,
                "group_id": s.group_id,
                "duplicate_of_id": s.duplicate_of_id,
                "near_duplicate_score": s.near_duplicate_score,
                "source_url": s.source_url,
                "evidence_urls": s.evidence_urls,
            }
            for s in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/datasets/preview", summary="Inspect an upload: columns, sample rows and distinct label values")
async def preview(
    file: UploadFile = File(...),
    label_column: str | None = Form(None),
    _: User = Depends(require_researcher),
):
    data = await _read_upload(file)
    try:
        df = _read_frame(data, file.filename or "upload.csv")
    except SchemaError as e:
        raise HTTPException(422, str(e))
    out = {
        "file_name": file.filename,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "head": df.head(5).to_dict(orient="records"),
        "declares_synthetic": bool("is_synthetic" in df.columns and df["is_synthetic"].astype(str).str.lower().isin(TRUTHY).any()),
    }
    if label_column and label_column in df.columns:
        out["label_values"] = df[label_column].astype(str).value_counts().head(100).to_dict()
    return out


@router.post("/datasets/import", summary="Import a CSV/TSV/JSON/JSONL dataset with provenance and schema validation")
async def import_dataset(
    file: UploadFile = File(...),
    name: str = Form(..., pattern=NAME_RE),
    version: str = Form(..., pattern=VERSION_RE),
    language: str = Form(..., pattern="^(ar|en)$"),
    source_key: str = Form("user_upload", max_length=64),
    text_column: str = Form("text", max_length=128),
    label_column: str | None = Form("label", max_length=128),
    id_column: str | None = Form(None, max_length=128),
    source_url_column: str | None = Form(None, max_length=128),
    evidence_urls_column: str | None = Form(None, max_length=128),
    category_column: str | None = Form(None, max_length=128),
    date_column: str | None = Form(None, max_length=128),
    group_key_column: str | None = Form(None, max_length=128),
    label_mapping: str | None = Form(None, description='JSON object {"original label": "SUPPORTED|MISLEADING|NEEDS_REVIEW|EXCLUDE"}'),
    use_registry_mapping: bool = Form(False),
    is_synthetic: bool = Form(False),
    license_confirmed: bool = Form(False),
    license_note: str | None = Form(None, max_length=2000),
    notes: str | None = Form(None, max_length=4000),
    db: Session = Depends(get_db),
    user: User = Depends(require_researcher),
):
    data = await _read_upload(file)
    src = None
    if source_key != "user_upload":
        src = db.scalar(select(SourceRegistry).where(SourceRegistry.key == source_key))
        if src is None:
            raise HTTPException(422, f"Unknown source_key {source_key!r}; register it first or use 'user_upload'")

    mapper = None
    if label_mapping and use_registry_mapping:
        raise HTTPException(422, "Provide either an inline label_mapping or use_registry_mapping, not both")
    if label_mapping:
        try:
            mapping = json.loads(label_mapping)
            if not isinstance(mapping, dict):
                raise ValueError("label_mapping must be a JSON object")
            mapper = LabelMapper.from_inline(source_key, mapping, approved_by=user.reviewer_code)
        except (ValueError, json.JSONDecodeError) as e:
            raise HTTPException(422, f"Invalid label_mapping: {e}")
    elif use_registry_mapping:
        if not mapping_path(source_key).exists():
            raise HTTPException(422, f"No registry label mapping exists for {source_key!r}")
        try:
            mapper = LabelMapper.load(source_key)
        except ValueError as e:
            raise HTTPException(422, f"Registry mapping invalid: {e}")

    cols = ColumnMapping(
        text=text_column,
        label=label_column or None,
        id=id_column or None,
        source_url=source_url_column or None,
        evidence_urls=evidence_urls_column or None,
        category=category_column or None,
        date=date_column or None,
        group_key=group_key_column or None,
    )
    try:
        parsed = parse_generic(data, file.filename or "upload.csv", language, cols, source_key=source_key)
        df = _read_frame(data, file.filename or "upload.csv")
    except SchemaError as e:
        raise HTTPException(422, str(e))
    if "is_synthetic" in df.columns and df["is_synthetic"].astype(str).str.lower().isin(TRUTHY).any() and not is_synthetic:
        raise HTTPException(
            422, "File declares synthetic rows (is_synthetic column). Import it with is_synthetic=true; synthetic data is never mixed into real datasets."
        )
    if not parsed.adapter.records:
        raise HTTPException(422, {"message": "No valid rows", "row_errors": parsed.row_errors[:50]})
    try:
        ds = import_records(
            db,
            parsed.adapter,
            name=name,
            version=version,
            mapper=mapper,
            is_synthetic=is_synthetic,
            created_by_id=user.id,
            params={
                "adapter": "generic",
                "columns": cols.__dict__,
                "license_note": license_note,
                "mapping_origin": "inline" if label_mapping else ("registry" if use_registry_mapping else None),
            },
            notes=notes,
            rejected_rows=len(parsed.row_errors),
            row_errors=parsed.row_errors,
            license_confirmed_by_uploader=license_confirmed and src is None,
        )
    except ImportError_ as e:
        raise HTTPException(409, str(e))
    db.commit()
    return {**_dataset_dict(ds, src), "stats": ds.stats, "row_errors": parsed.row_errors[:50]}


@router.post("/datasets/{dataset_id}/refresh", summary="Re-apply the registry label mapping, duplicates, reviews and eligibility (admin)")
def refresh(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    ds = db.get(Dataset, dataset_id)
    if ds is None or ds.kind != "import":
        raise HTTPException(404, "Import dataset not found")
    mapper = None
    src = db.get(SourceRegistry, ds.source_id) if ds.source_id else None
    if src and ds.params.get("mapping_origin") != "inline" and mapping_path(src.key).exists():
        try:
            mapper = LabelMapper.load(src.key)
        except ValueError as e:
            raise HTTPException(422, f"Registry mapping invalid: {e}")
    stats = refresh_dataset(db, ds, mapper=mapper)
    audit(db, "dataset.refresh", "dataset", ds.id, actor_id=user.id, details={"mapping_version": ds.label_mapping_version, "eligible": stats["eligible"]})
    db.commit()
    return {**_dataset_dict(ds, src), "stats": stats}


@router.post("/datasets/{dataset_id}/queue-review", summary="Queue a reproducible random sample of items for expert review")
def queue_review(dataset_id: int, body: QueueReviewIn, db: Session = Depends(get_db), user: User = Depends(require_researcher)):
    ds = db.get(Dataset, dataset_id)
    if ds is None or ds.kind != "import":
        raise HTTPException(404, "Import dataset not found")
    q = select(DatasetSample.id).where(
        DatasetSample.dataset_id == ds.id,
        DatasetSample.text_available.is_(True),
        DatasetSample.review_status == "unreviewed",
    )
    if body.only_eligible:
        q = q.where(DatasetSample.eligibility.in_(["eligible", "pending"]))
    ids = sorted(db.scalars(q).all())
    chosen = random.Random(body.seed).sample(ids, min(body.count, len(ids)))
    for s in db.scalars(select(DatasetSample).where(DatasetSample.id.in_(chosen))):
        s.review_status = "pending"
    audit(db, "dataset.queue_review", "dataset", ds.id, actor_id=user.id, details={"queued": len(chosen), "seed": body.seed})
    db.commit()
    return {"queued": len(chosen), "available": len(ids)}


@router.post("/datasets/splits", summary="Build a verified, group-aware 70/15/15 split for one language (admin)")
def make_split(body: SplitIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        res = build_splits(
            db,
            body.language,
            version=body.version,
            dataset_ids=body.dataset_ids,
            seed=body.seed,
            require_human_review=body.require_human_review,
            near_dup_threshold=body.near_dup_threshold,
            label_scheme=body.label_scheme,
            created_by_id=user.id,
        )
    except SplitError as e:
        db.commit()  # persist the audit record of the failed attempt
        raise HTTPException(422, {"message": str(e), "report": e.report})
    except ValueError as e:
        raise HTTPException(409, str(e))
    db.commit()
    return {"dataset_id": res.dataset.id, "report": res.report}


# ------------------------------------------------------------------ source registry


def _source_dict(s: SourceRegistry) -> dict:
    mp = mapping_path(s.key)
    mapping = None
    if mp.exists():
        try:
            m = LabelMapper.load(s.key)
            mapping = m.summary()
        except ValueError as e:
            mapping = {"error": str(e)}
    return {
        "key": s.key,
        "name": s.name,
        "languages": s.languages,
        "official_url": s.official_url,
        "paper_url": s.paper_url,
        "access_method": s.access_method,
        "verified_revision": s.verified_revision,
        "license_name": s.license_name,
        "license_url": s.license_url,
        "license_evidence": s.license_evidence,
        "license_status": s.license_status,
        "commercial_use_allowed": s.commercial_use_allowed,
        "redistribution_allowed": s.redistribution_allowed,
        "attribution_required": s.attribution_required,
        "text_available": s.text_available,
        "citation": s.citation,
        "training_use_status": s.training_use_status,
        "notes": s.notes,
        "details": s.details,
        "label_mapping": mapping,
        "reviewed_at": s.reviewed_at,
        "registry_version": s.registry_version,
    }


@router.get("/sources", summary="Dataset provenance & license registry")
def list_sources(db: Session = Depends(get_db), _: User = Depends(get_viewer)):
    return {"items": [_source_dict(s) for s in db.scalars(select(SourceRegistry).order_by(SourceRegistry.id))]}


@router.get("/sources/{key}/mapping", summary="Full proposed/approved label mapping for a source")
def get_mapping(key: str, _: User = Depends(get_viewer)):
    if not mapping_path(key).exists():
        raise HTTPException(404, "No label mapping file for this source")
    return load_mapping_file(key)


@router.patch("/sources/{key}", summary="Record a human license review (admin)")
def update_source(key: str, body: SourceUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    s = db.scalar(select(SourceRegistry).where(SourceRegistry.key == key))
    if s is None:
        raise HTTPException(404, "Source not found")
    before = s.license_status
    s.license_status = body.license_status
    s.license_evidence = f"{body.license_evidence}\n[reviewed by {user.reviewer_code} at {datetime.now(UTC).isoformat()}; previous status: {before}]"
    s.reviewed_by_id = user.id
    s.reviewed_at = datetime.now(UTC)
    audit(db, "source.license_review", "source", s.key, actor_id=user.id, details={"from": before, "to": body.license_status})
    db.commit()
    return _source_dict(s)
