from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from healthmisinfo.api.deps import app_setting, get_current_user, require_reviewer
from healthmisinfo.api.schemas import ReviewIn, ReviewOut, label_name
from healthmisinfo.audit import audit
from healthmisinfo.data.pipeline import refresh_sample
from healthmisinfo.db.models import Analysis, Dataset, DatasetSample, ExpertReview, SourceRegistry, User
from healthmisinfo.db.session import get_db
from healthmisinfo.labels import LABEL_NAMES, Label
from healthmisinfo.reviews import resolve

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])

OPEN_STATUSES = ("pending", "in_review", "disagreement")


def _review_out(r: ExpertReview, target_status: str | None = None, target_final: int | None = None) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        target_type=r.target_type,
        target_id=r.analysis_id if r.target_type == "analysis" else r.sample_id,
        reviewer_code=r.reviewer.reviewer_code,
        label_name=LABEL_NAMES[r.label],
        agrees_with_model=r.agrees_with_model,
        evidence_urls=r.evidence_urls or [],
        notes=r.notes,
        is_adjudication=r.is_adjudication,
        created_at=r.created_at,
        target_review_status=target_status,
        target_final_label_name=label_name(target_final),
    )


@router.post("", response_model=ReviewOut, summary="Submit an expert review or an adjudication")
def submit_review(body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require_reviewer)):
    if body.is_adjudication and user.role != "admin":
        raise HTTPException(403, "Only administrators can adjudicate")
    label = int(Label[body.label])
    required = int(app_setting(db, "reviews_required"))
    filt = ExpertReview.analysis_id == body.target_id if body.target_type == "analysis" else ExpertReview.sample_id == body.target_id

    if not body.is_adjudication:
        dup = db.scalar(select(ExpertReview.id).where(filt, ExpertReview.reviewer_id == user.id, ExpertReview.is_adjudication.is_(False)))
        if dup:
            raise HTTPException(409, "You have already reviewed this item")

    if body.target_type == "analysis":
        a = db.get(Analysis, body.target_id)
        if a is None:
            raise HTTPException(404, "Analysis not found")
        r = ExpertReview(
            target_type="analysis",
            analysis_id=a.id,
            reviewer_id=user.id,
            label=label,
            agrees_with_model=None if a.predicted_label is None else (label == a.predicted_label),
            evidence_urls=[str(u) for u in body.evidence_urls],
            notes=body.notes,
            is_adjudication=body.is_adjudication,
            guideline_version=body.guideline_version,
        )
        db.add(r)
        db.flush()
        res = resolve(list(db.scalars(select(ExpertReview).where(ExpertReview.analysis_id == a.id))), required)
        a.review_status, a.final_label = res.status, res.final_label
        status, final = a.review_status, a.final_label
    else:
        s = db.get(DatasetSample, body.target_id)
        if s is None:
            raise HTTPException(404, "Sample not found")
        if not s.text_available:
            raise HTTPException(422, "Sample has no text to review")
        r = ExpertReview(
            target_type="sample",
            sample_id=s.id,
            reviewer_id=user.id,
            label=label,
            agrees_with_model=None,
            evidence_urls=[str(u) for u in body.evidence_urls],
            notes=body.notes,
            is_adjudication=body.is_adjudication,
            guideline_version=body.guideline_version,
        )
        db.add(r)
        db.flush()
        refresh_sample(db, s, required)
        status, final = s.review_status, s.final_label
    audit(
        db,
        "review.adjudicate" if body.is_adjudication else "review.create",
        body.target_type,
        body.target_id,
        actor_id=user.id,
        details={"label": body.label, "resulting_status": status, "evidence_urls": len(body.evidence_urls)},
    )
    db.commit()
    db.refresh(r)
    return _review_out(r, status, final)


@router.get("/pending", summary="Items awaiting expert review (excludes items you already reviewed)")
def pending(
    target_type: str = Query("analysis", pattern="^(analysis|sample)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
):
    mine = select(ExpertReview.analysis_id if target_type == "analysis" else ExpertReview.sample_id).where(
        ExpertReview.reviewer_id == user.id, ExpertReview.is_adjudication.is_(False)
    )
    if target_type == "analysis":
        q = select(Analysis).where(Analysis.review_status.in_(OPEN_STATUSES))
        if user.role != "admin":
            q = q.where(Analysis.id.not_in(mine))
        total = db.scalar(select(func.count()).select_from(q.subquery()))
        rows = db.scalars(q.order_by(Analysis.created_at).offset((page - 1) * page_size).limit(page_size)).all()
        items = []
        for a in rows:
            revs = list(db.scalars(select(ExpertReview).where(ExpertReview.analysis_id == a.id)))
            items.append(
                {
                    "target_type": "analysis",
                    "target_id": a.id,
                    "text": a.text,
                    "language": a.language_used or a.language_detected,
                    "status": a.status,
                    "predicted_label_name": label_name(a.predicted_label),
                    "abstained": a.abstained,
                    "confidence": a.confidence,
                    "is_calibrated": a.is_calibrated,
                    "review_status": a.review_status,
                    "review_count": len(revs),
                    "already_reviewed_by_me": any(r.reviewer_id == user.id for r in revs),
                    # Blind review: individual labels are only visible to adjudicators (admins).
                    "reviews": [_review_out(r).model_dump() for r in revs] if user.role == "admin" else None,
                    "created_at": a.created_at,
                }
            )
    else:
        q = (
            select(DatasetSample, Dataset, SourceRegistry)
            .join(Dataset, Dataset.id == DatasetSample.dataset_id)
            .join(SourceRegistry, SourceRegistry.id == Dataset.source_id, isouter=True)
            .where(
                DatasetSample.text_available.is_(True),
                or_(DatasetSample.review_status.in_(OPEN_STATUSES), DatasetSample.exclusion_reason == "label_conflict"),
            )
        )
        if user.role != "admin":
            q = q.where(DatasetSample.id.not_in(mine))
        total = db.scalar(select(func.count()).select_from(q.subquery()))
        rows = db.execute(q.order_by(DatasetSample.id).offset((page - 1) * page_size).limit(page_size)).all()
        items = []
        for s, ds, src in rows:
            revs = list(db.scalars(select(ExpertReview).where(ExpertReview.sample_id == s.id)))
            items.append(
                {
                    "target_type": "sample",
                    "target_id": s.id,
                    "text": s.original_text,
                    "language": s.language,
                    "dataset": f"{ds.name}@{ds.version}",
                    "is_synthetic": ds.is_synthetic,
                    "source_key": src.key if src else "user_upload",
                    "original_label": s.original_label,
                    "mapped_label_name": label_name(s.mapped_label),
                    "mapping_status": s.mapping_status,
                    "fact_check_url": s.source_url,
                    "evidence_urls": s.evidence_urls,
                    "exclusion_reason": s.exclusion_reason,
                    "review_status": s.review_status,
                    "review_count": len(revs),
                    "already_reviewed_by_me": any(r.reviewer_id == user.id for r in revs),
                    "reviews": [_review_out(r).model_dump() for r in revs] if user.role == "admin" else None,
                }
            )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("", summary="Reviews of one item (admins see all; others see their own)")
def list_reviews(
    target_type: str = Query(..., pattern="^(analysis|sample)$"),
    target_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filt = ExpertReview.analysis_id == target_id if target_type == "analysis" else ExpertReview.sample_id == target_id
    q = select(ExpertReview).where(filt).order_by(ExpertReview.created_at)
    if user.role != "admin":
        q = q.where(ExpertReview.reviewer_id == user.id)
    return {"items": [_review_out(r) for r in db.scalars(q)]}
