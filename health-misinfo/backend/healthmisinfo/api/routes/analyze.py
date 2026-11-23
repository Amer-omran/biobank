from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from healthmisinfo import DISCLAIMER_AR, DISCLAIMER_EN
from healthmisinfo.api.deps import app_setting, get_current_user
from healthmisinfo.api.schemas import AnalysisOut, AnalysisSummary, AnalyzeIn, LanguageInfo, PredictionOut, label_name
from healthmisinfo.audit import audit
from healthmisinfo.config import get_settings
from healthmisinfo.db.models import Analysis, ExpertReview, ModelVersion, User
from healthmisinfo.db.session import get_db
from healthmisinfo.inference.service import ModelUnavailable, inference_service
from healthmisinfo.inference.similar import VERIFICATION_RESOURCES, similar_index
from healthmisinfo.labels import LABEL_NAMES, Label
from healthmisinfo.ratelimit import client_ip, enforce
from healthmisinfo.text.langdetect import detect_language
from healthmisinfo.text.normalize import normalize_for_model, sha256_text
from healthmisinfo.text.redact import redact_pii
from healthmisinfo.text.topics import tag_topic

router = APIRouter(prefix="/api/v1", tags=["analysis"])

DISCLAIMER = {"en": DISCLAIMER_EN, "ar": DISCLAIMER_AR}


def _as_dict(scores: list[float] | None) -> dict[str, float] | None:
    return None if scores is None else {LABEL_NAMES[i]: float(v) for i, v in enumerate(scores)}


def analysis_out(a: Analysis, include_reviews: bool = False, db: Session | None = None) -> AnalysisOut:
    pred = None
    if a.predicted_label is not None:
        pred = PredictionOut(
            label=a.predicted_label,
            label_name=LABEL_NAMES[a.predicted_label],
            display_label="NEEDS_REVIEW" if a.abstained else LABEL_NAMES[a.predicted_label],
            raw_scores=_as_dict(a.raw_scores) or {},
            calibrated_probabilities=_as_dict(a.calibrated_probabilities),
            confidence=a.confidence,
            is_calibrated=a.is_calibrated,
            abstained=a.abstained,
            abstention_threshold=(a.explanation or {}).get("_abstention_threshold"),
        )
    reviews = None
    if include_reviews and db is not None:
        reviews = [
            {
                "id": r.id,
                "reviewer_code": r.reviewer.reviewer_code,
                "label_name": LABEL_NAMES[r.label],
                "agrees_with_model": r.agrees_with_model,
                "evidence_urls": r.evidence_urls,
                "notes": r.notes,
                "is_adjudication": r.is_adjudication,
                "created_at": r.created_at,
            }
            for r in db.scalars(select(ExpertReview).where(ExpertReview.analysis_id == a.id).order_by(ExpertReview.created_at))
        ]
    expl = {k: v for k, v in (a.explanation or {}).items() if not k.startswith("_")}
    return AnalysisOut(
        id=a.id,
        created_at=a.created_at,
        status=a.status,
        model_state=(a.explanation or {}).get("_model_state"),
        language=LanguageInfo(
            detected=a.language_detected,
            confidence=a.language_confidence,
            used=a.language_used,
            details=(a.explanation or {}).get("_language_details", {}),
        ),
        warnings=(a.explanation or {}).get("_warnings", []),
        model=None
        if a.model_version is None
        else {"id": a.model_version.id, "version_tag": a.model_version.version_tag, "base_model": a.model_version.base_model},
        prediction=pred,
        explanation=expl,
        similar_claims=a.similar_claims or [],
        verification_resources=VERIFICATION_RESOURCES,
        health_topic=a.health_topic,
        review_status=a.review_status,
        final_label=a.final_label,
        final_label_name=label_name(a.final_label),
        text=a.text,
        redactions=a.redactions or {},
        disclaimer=DISCLAIMER,
        reviews=reviews,
    )


@router.post("/analyze", response_model=AnalysisOut, summary="Analyse a health claim (research prediction)")
def analyze(body: AnalyzeIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = get_settings()
    enforce(request, "analyze", s.rate_limit_analyze, s.rate_limit_window_seconds, identity=f"user:{user.id}")
    text = body.text.strip()
    if len(text) < s.min_text_chars:
        raise HTTPException(422, f"Text must be at least {s.min_text_chars} characters")
    if len(text) > s.max_text_chars:
        raise HTTPException(422, f"Text must be at most {s.max_text_chars} characters")

    t0 = time.perf_counter()
    lang = detect_language(text)
    warnings: list[str] = []
    if lang.language == "mixed":
        warnings.append("mixed_language")
    if body.model == "auto":
        use_lang = lang.supported_language
    else:
        use_lang = body.model
        if lang.supported_language and lang.supported_language != body.model:
            warnings.append("language_mismatch")
        if lang.language == "unsupported":
            warnings.append("unsupported_language_forced")

    pred = None
    model_state = None
    if use_lang is None:
        status = "unsupported_language"
    else:
        try:
            pred = inference_service.predict(db, text, use_lang, explain=body.explain)
            status = "completed"
            model_state = "ready"
        except ModelUnavailable as e:
            model_state = e.state
            status = "model_not_trained" if e.state in ("not_trained", "no_active_version") else "model_unavailable"

    similar = similar_index.search(db, normalize_for_model(text, use_lang), use_lang) if use_lang else []
    redacted, redactions = redact_pii(text)
    review_status = "not_required"
    if pred is not None and (
        (pred.abstained and app_setting(db, "auto_queue_abstained"))
        or (pred.predicted_label == Label.NEEDS_REVIEW and app_setting(db, "auto_queue_needs_review"))
    ):
        review_status = "pending"

    explanation = dict(pred.explanation) if pred else {}
    explanation.update(
        {
            "_model_state": model_state,
            "_warnings": warnings,
            "_language_details": lang.details,
            "_abstention_threshold": pred.abstention_threshold if pred else None,
        }
    )
    a = Analysis(
        user_id=user.id,
        text=redacted if app_setting(db, "store_analysis_text") else None,
        text_sha256=sha256_text(text),
        text_length=len(text),
        redactions=redactions,
        language_detected=lang.language,
        language_confidence=lang.confidence,
        language_used=use_lang,
        requested_model=body.model,
        model_version_id=pred.model_version_id if pred else None,
        status=status,
        predicted_label=pred.predicted_label if pred else None,
        raw_scores=pred.raw_scores if pred else None,
        calibrated_probabilities=pred.calibrated_probabilities if pred else None,
        is_calibrated=pred.is_calibrated if pred else False,
        confidence=pred.confidence if pred else None,
        abstained=pred.abstained if pred else False,
        explanation=explanation,
        similar_claims=similar,
        health_topic=tag_topic(text),
        review_status=review_status,
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )
    db.add(a)
    db.flush()
    audit(
        db,
        "analysis.create",
        "analysis",
        a.id,
        actor_id=user.id,
        details={"status": status, "language": use_lang, "model_version_id": a.model_version_id},
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(a)
    return analysis_out(a)


def _visible(q, user: User):
    return q if user.role in ("admin", "reviewer") else q.where(Analysis.user_id == user.id)


@router.get("/history", summary="Analysis history (own analyses; all for reviewers/admins)")
def history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    language: str | None = Query(None, pattern="^(ar|en)$"),
    status: str | None = Query(None, max_length=32),
    review_status: str | None = Query(None, max_length=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = _visible(select(Analysis), user)
    if language:
        q = q.where(Analysis.language_used == language)
    if status:
        q = q.where(Analysis.status == status)
    if review_status:
        q = q.where(Analysis.review_status == review_status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Analysis.created_at.desc(), Analysis.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    tags = dict(db.execute(select(ModelVersion.id, ModelVersion.version_tag)).all())
    items = [
        AnalysisSummary(
            id=a.id,
            created_at=a.created_at,
            status=a.status,
            language_detected=a.language_detected,
            language_used=a.language_used,
            predicted_label_name=label_name(a.predicted_label),
            confidence=a.confidence,
            is_calibrated=a.is_calibrated,
            abstained=a.abstained,
            review_status=a.review_status,
            final_label_name=label_name(a.final_label),
            model_version=tags.get(a.model_version_id),
            text_preview=(a.text or "")[:160] or None,
        )
        for a in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/history/{analysis_id}", response_model=AnalysisOut)
def history_item(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Analysis, analysis_id)
    if a is None or (user.role not in ("admin", "reviewer") and a.user_id != user.id):
        raise HTTPException(404, "Analysis not found")
    return analysis_out(a, include_reviews=True, db=db)


@router.post("/history/{analysis_id}/request-review", response_model=AnalysisOut, summary="Send an analysis to the expert review queue")
def request_review(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Analysis, analysis_id)
    if a is None or (user.role not in ("admin", "reviewer") and a.user_id != user.id):
        raise HTTPException(404, "Analysis not found")
    a.review_requested = True
    if a.review_status in ("not_required", "unreviewed"):
        a.review_status = "pending"
    audit(db, "analysis.review_requested", "analysis", a.id, actor_id=user.id)
    db.commit()
    return analysis_out(a, include_reviews=True, db=db)
