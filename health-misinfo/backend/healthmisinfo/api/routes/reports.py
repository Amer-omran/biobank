"""CSV / PDF exports. Measured results come only from registered models' stored evaluation files;
illustrative content is printed in a separate, explicitly labelled section."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from healthmisinfo.api.deps import get_viewer, is_guest
from healthmisinfo.api.routes.analytics import reviewer_agreement
from healthmisinfo.db.models import Analysis, AuditLog, Dataset, DatasetSample, ExpertReview, ModelVersion, SourceRegistry, User
from healthmisinfo.db.session import get_db
from healthmisinfo.inference.service import SLOTS, inference_service
from healthmisinfo.labels import LABEL_DESCRIPTIONS, LABEL_NAMES, Label
from healthmisinfo.reports.render import PdfReport, to_csv

router = APIRouter(prefix="/api/v1", tags=["reports"])

REPORT_TYPES = {
    "summary": {"formats": ["pdf"], "description": "Platform status, data, measured results (if any) and illustrative label examples"},
    "analyses": {"formats": ["csv", "pdf"], "description": "Analysis history with predictions and review status"},
    "dataset": {"formats": ["csv", "pdf"], "description": "Samples of one dataset with provenance, mapping and eligibility", "requires": "dataset_id"},
    "evaluation": {"formats": ["csv", "pdf"], "description": "Measured held-out test metrics of one registered model", "requires": "model_id"},
    "reviews": {"formats": ["csv"], "description": "Expert reviews (pseudonymous reviewer codes)"},
    "sources": {"formats": ["csv"], "description": "Provenance & license registry"},
    "audit": {"formats": ["csv"], "description": "Audit log (admin only)"},
}

PUBLIC_REPORT_TYPES = {"summary", "sources", "evaluation"}  # aggregate / non-personal only

ILLUSTRATIVE = [
    ("SUPPORTED", "Washing hands with soap reduces the spread of many infections."),
    ("MISLEADING", "Drinking hot water with lemon cures viral infections."),
    ("NEEDS_REVIEW", "A newly marketed herbal supplement improves immunity in older adults."),
]


def _file(data: bytes, name: str, media: str) -> Response:
    return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S")


@router.get("/reports", summary="List report types, or download one with ?type=...&format=csv|pdf")
def reports(
    type: str | None = Query(None, pattern="^(summary|analyses|dataset|evaluation|reviews|sources|audit)$"),
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    dataset_id: int | None = None,
    model_id: int | None = None,
    limit: int = Query(5000, ge=1, le=100000),
    db: Session = Depends(get_db),
    user: User = Depends(get_viewer),
):
    if type is None:
        return {
            "types": {k: v for k, v in REPORT_TYPES.items() if not is_guest(user) or k in PUBLIC_REPORT_TYPES},
            "models": [{"id": m.id, "version_tag": m.version_tag, "language": m.language} for m in db.scalars(select(ModelVersion))],
            "datasets": [
                {"id": d.id, "name": d.name, "version": d.version, "kind": d.kind, "is_synthetic": d.is_synthetic} for d in db.scalars(select(Dataset))
            ],
        }
    if format not in REPORT_TYPES[type]["formats"]:
        raise HTTPException(422, f"Format {format} not available for {type}")
    if is_guest(user) and type not in PUBLIC_REPORT_TYPES:
        raise HTTPException(401, "Sign in to download this report")
    if type == "audit" and user.role != "admin":
        raise HTTPException(403, "Audit export requires admin")
    return _RENDERERS[type](db, user, format, dataset_id=dataset_id, model_id=model_id, limit=limit)


def _report_analyses(db, user, fmt, limit, **_):
    q = select(Analysis).order_by(Analysis.created_at.desc()).limit(limit)
    if user.role not in ("admin", "reviewer"):
        q = q.where(Analysis.user_id == user.id)
    rows = db.scalars(q).all()
    tags = dict(db.execute(select(ModelVersion.id, ModelVersion.version_tag)).all())
    header = [
        "id",
        "created_at",
        "status",
        "language_detected",
        "language_used",
        "model_version",
        "predicted_label",
        "abstained",
        "is_calibrated",
        "confidence_calibrated",
        "raw_scores_uncalibrated",
        "review_status",
        "final_label",
        "health_topic",
        "text_redacted",
    ]
    data = [
        [
            a.id,
            a.created_at.isoformat(),
            a.status,
            a.language_detected,
            a.language_used,
            tags.get(a.model_version_id),
            LABEL_NAMES[a.predicted_label] if a.predicted_label is not None else "",
            a.abstained,
            a.is_calibrated,
            a.confidence,
            a.raw_scores,
            a.review_status,
            LABEL_NAMES[a.final_label] if a.final_label is not None else "",
            a.health_topic,
            a.text,
        ]
        for a in rows
    ]
    if fmt == "csv":
        return _file(to_csv(header, data), f"analyses_{_stamp()}.csv", "text/csv; charset=utf-8")
    pdf = PdfReport("Analysis history")
    pdf.p(
        "Each row is a research prediction produced by a registered model, or an explicit 'model_not_trained' "
        "record when no model was available. Raw scores are uncalibrated.",
        pdf.note,
    )
    pdf.table(
        ["ID", "Date", "Status", "Lang", "Prediction", "Abstained", "Review", "Text"],
        [
            [
                a.id,
                a.created_at.strftime("%Y-%m-%d"),
                a.status,
                a.language_used or a.language_detected,
                LABEL_NAMES[a.predicted_label] if a.predicted_label is not None else "—",
                "yes" if a.abstained else "no",
                a.review_status,
                (a.text or "")[:90],
            ]
            for a in rows[:500]
        ],
        col_widths=[30, 55, 70, 30, 70, 45, 60, 165],
    )
    return _file(pdf.render(), f"analyses_{_stamp()}.pdf", "application/pdf")


def _report_dataset(db, user, fmt, dataset_id, limit, **_):
    ds = db.get(Dataset, dataset_id) if dataset_id else None
    if ds is None:
        raise HTTPException(404, "dataset_id required / not found")
    src = db.get(SourceRegistry, ds.source_id) if ds.source_id else None
    samples = db.scalars(select(DatasetSample).where(DatasetSample.dataset_id == ds.id).order_by(DatasetSample.row_number).limit(limit)).all()
    if fmt == "csv":
        header = [
            "sample_id",
            "row",
            "external_id",
            "language",
            "original_label",
            "mapping_status",
            "mapped_label",
            "final_label",
            "final_label_source",
            "eligibility",
            "exclusion_reason",
            "review_status",
            "health_topic",
            "group_id",
            "duplicate_of_id",
            "fact_check_url",
            "evidence_urls",
            "original_text",
        ]
        data = [
            [
                s.id,
                s.row_number,
                s.external_id,
                s.language,
                s.original_label,
                s.mapping_status,
                LABEL_NAMES[s.mapped_label] if s.mapped_label is not None else "",
                LABEL_NAMES[s.final_label] if s.final_label is not None else "",
                s.final_label_source,
                s.eligibility,
                s.exclusion_reason,
                s.review_status,
                s.health_topic,
                s.group_id,
                s.duplicate_of_id,
                s.source_url,
                " ".join(s.evidence_urls or []),
                s.original_text,
            ]
            for s in samples
        ]
        return _file(to_csv(header, data), f"dataset_{ds.name}_{ds.version}.csv", "text/csv; charset=utf-8")
    st = ds.stats or {}
    pdf = PdfReport(f"Dataset report — {ds.name} @ {ds.version}")
    if ds.is_synthetic:
        pdf.p("SYNTHETIC FIXTURE DATASET — for software testing only; never used for training or results.", pdf.banner)
    pdf.table(
        ["Field", "Value"],
        [
            ["Language", ds.language],
            ["Kind", ds.kind],
            ["Source", f"{src.name} ({src.key})" if src else "user upload"],
            ["License", f"{src.license_name} — status: {src.license_status}" if src else ds.params.get("license_note") or "uploader-declared"],
            ["File / SHA-256", f"{ds.file_name} / {ds.file_sha256}"],
            ["Label mapping", ds.label_mapping_version or "none"],
            ["Rows read / imported / rejected", f"{ds.row_count} / {ds.imported_count} / {ds.rejected_count}"],
            ["Eligible for training", st.get("eligible")],
            ["Eligible & human-reviewed", st.get("eligible_human_reviewed")],
        ],
        col_widths=[150, 370],
    )
    pdf.space()
    for title, key in [
        ("Eligibility", "eligibility"),
        ("Exclusion reasons", "exclusion_reasons"),
        ("Mapping status", "mapping_status"),
        ("Eligible label distribution", "eligible_label_distribution"),
        ("Health topics (heuristic)", "health_topics"),
    ]:
        d = st.get(key) or {}
        if key == "eligible_label_distribution":
            d = {LABEL_NAMES[int(k)]: v for k, v in d.items()}
        pdf.p(title, pdf.h2)
        pdf.table(["Value", "Count"], [[k, v] for k, v in d.items()] or [["(none)", 0]], col_widths=[300, 100])
    return _file(pdf.render(), f"dataset_{ds.name}_{ds.version}.pdf", "application/pdf")


def _report_evaluation(db, user, fmt, model_id, **_):
    mv = db.get(ModelVersion, model_id) if model_id else None
    if mv is None:
        raise HTTPException(404, "model_id required / not found. No measured results exist without a registered model.")
    t = mv.test_metrics or {}
    if fmt == "csv":
        rows = [["overall", k, t.get(k)] for k in ("n", "accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1")]
        for cls, m in (t.get("per_class") or {}).items():
            rows += [[cls, k, v] for k, v in m.items()]
        cm = (t.get("confusion_matrix") or {}).get("matrix") or []
        for i, r in enumerate(cm):
            rows += [[f"confusion_true_{LABEL_NAMES[i]}", f"pred_{LABEL_NAMES[j]}", v] for j, v in enumerate(r)]
        return _file(to_csv(["scope", "metric", "value"], rows), f"evaluation_{mv.version_tag}.csv", "text/csv; charset=utf-8")
    pdf = PdfReport(f"Evaluation report — {mv.version_tag}")
    pdf.p("MEASURED RESULTS — held-out test split, evaluated once after model selection. Source: evaluation.json of the registered run.", pdf.measured)
    pdf.space()
    pdf.table(
        ["Metric", "Value"],
        [
            [k, f"{t.get(k):.4f}" if isinstance(t.get(k), float) else t.get(k)]
            for k in ("n", "accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1")
        ],
        col_widths=[200, 200],
    )
    pdf.p("Per-class", pdf.h2)
    pdf.table(
        ["Class", "Precision", "Recall", "F1", "Support"],
        [[c, f"{m['precision']:.4f}", f"{m['recall']:.4f}", f"{m['f1']:.4f}", m["support"]] for c, m in (t.get("per_class") or {}).items()],
    )
    cm = (t.get("confusion_matrix") or {}).get("matrix")
    if cm:
        pdf.p("Confusion matrix (rows = true, columns = predicted)", pdf.h2)
        pdf.table(["", *LABEL_NAMES], [[LABEL_NAMES[i], *r] for i, r in enumerate(cm)])
    cal = t.get("calibration") or {}
    pdf.p("Calibration", pdf.h2)
    pdf.p(
        f"Temperature {mv.temperature}; test ECE raw {cal.get('ece_raw')} → calibrated {cal.get('ece_calibrated')}; "
        f"abstention threshold {mv.abstention_threshold} (selected on validation)."
    )
    return _file(pdf.render(), f"evaluation_{mv.version_tag}.pdf", "application/pdf")


def _report_reviews(db, user, fmt, limit, **_):
    rows = db.scalars(select(ExpertReview).order_by(ExpertReview.created_at.desc()).limit(limit)).all()
    data = [
        [
            r.id,
            r.created_at.isoformat(),
            r.target_type,
            r.analysis_id or r.sample_id,
            r.reviewer.reviewer_code,
            LABEL_NAMES[r.label],
            r.agrees_with_model,
            r.is_adjudication,
            r.guideline_version,
            " ".join(r.evidence_urls or []),
            r.notes,
        ]
        for r in rows
    ]
    header = [
        "id",
        "created_at",
        "target_type",
        "target_id",
        "reviewer_code",
        "label",
        "agrees_with_model",
        "is_adjudication",
        "guideline_version",
        "evidence_urls",
        "notes",
    ]
    return _file(to_csv(header, data), f"reviews_{_stamp()}.csv", "text/csv; charset=utf-8")


def _report_sources(db, user, fmt, **_):
    rows = db.scalars(select(SourceRegistry)).all()
    header = [
        "key",
        "name",
        "official_url",
        "license_name",
        "license_status",
        "commercial_use_allowed",
        "redistribution_allowed",
        "text_available",
        "training_use_status",
        "verified_revision",
        "citation",
    ]
    data = [
        [
            s.key,
            s.name,
            s.official_url,
            s.license_name,
            s.license_status,
            s.commercial_use_allowed,
            s.redistribution_allowed,
            s.text_available,
            s.training_use_status,
            s.verified_revision,
            s.citation,
        ]
        for s in rows
    ]
    return _file(to_csv(header, data), f"sources_{_stamp()}.csv", "text/csv; charset=utf-8")


def _report_audit(db, user, fmt, limit, **_):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    data = [[r.id, r.created_at.isoformat(), r.actor_id, r.action, r.entity_type, r.entity_id, r.details] for r in rows]
    return _file(
        to_csv(["id", "created_at", "actor_id", "action", "entity_type", "entity_id", "details"], data), f"audit_{_stamp()}.csv", "text/csv; charset=utf-8"
    )


def _report_summary(db, user, fmt, **_):
    pdf = PdfReport("AI-Powered Detection of Health Rumors and Misinformation — platform summary")
    pdf.p("1. Model status", pdf.h2)
    pdf.table(
        ["Language", "Base model", "State", "Active version"],
        [
            [st["language"], st["base_model"], st["state"], (st["active_version"] or {}).get("version_tag", "—")]
            for st in (inference_service.slot_status(db, lang) for lang in SLOTS)
        ],
    )
    pdf.space()
    pdf.p("2. Measured results", pdf.h2)
    models = db.scalars(select(ModelVersion)).all()
    if not models:
        pdf.p(
            "NO MEASURED RESULTS: no model has been trained, evaluated on a held-out test set and registered. "
            "No accuracy or F1 figures exist for this platform yet.",
            pdf.banner,
        )
    else:
        pdf.p("MEASURED RESULTS (held-out test splits):", pdf.measured)
        pdf.table(
            ["Model", "Lang", "n", "Accuracy", "Macro-F1", "Macro-P", "Macro-R"],
            [
                [
                    m.version_tag,
                    m.language,
                    (m.test_metrics or {}).get("n"),
                    *[f"{(m.test_metrics or {}).get(k, 0):.4f}" for k in ("accuracy", "macro_f1", "macro_precision", "macro_recall")],
                ]
                for m in models
            ],
        )
    pdf.p("3. Data", pdf.h2)
    pdf.table(
        ["Dataset", "Lang", "Kind", "Synthetic", "Rows", "Eligible"],
        [
            [
                f"{d.name}@{d.version}",
                d.language,
                d.kind,
                "yes" if d.is_synthetic else "no",
                d.imported_count,
                (d.stats or {}).get("eligible", (d.stats or {}).get("candidate_count")),
            ]
            for d in db.scalars(select(Dataset))
        ],
    )
    ag = reviewer_agreement(db)
    pdf.p(
        f"Reviewer agreement: {ag['items_with_2plus_reviews']} doubly-reviewed items; percent agreement {ag['percent_agreement']}; "
        f"Cohen's kappa {ag['cohen_kappa']}."
    )
    pdf.space(10)
    pdf.p("4. ILLUSTRATIVE EXAMPLES — NOT MEASURED, NOT MODEL OUTPUT", pdf.h2)
    pdf.p(
        "The sentences below were written by the authors to explain the label scheme. They are not predictions, "
        "not dataset samples, and carry no evidential weight.",
        pdf.banner,
    )
    pdf.table(
        ["Label", "Definition", "Illustrative claim (written for explanation)"],
        [[lbl, LABEL_DESCRIPTIONS[Label[lbl]]["en"], ex] for lbl, ex in ILLUSTRATIVE],
        col_widths=[80, 200, 240],
    )
    return _file(pdf.render(), f"summary_{_stamp()}.pdf", "application/pdf")


_RENDERERS = {
    "summary": _report_summary,
    "analyses": _report_analyses,
    "dataset": _report_dataset,
    "evaluation": _report_evaluation,
    "reviews": _report_reviews,
    "sources": _report_sources,
    "audit": _report_audit,
}
