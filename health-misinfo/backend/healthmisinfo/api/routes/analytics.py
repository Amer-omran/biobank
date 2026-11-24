from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from healthmisinfo.api.deps import get_viewer
from healthmisinfo.db.models import Analysis, Dataset, DatasetSample, ExpertReview, ModelVersion, SourceRegistry, User
from healthmisinfo.db.session import get_db
from healthmisinfo.labels import LABEL_NAMES

router = APIRouter(prefix="/api/v1", tags=["analytics"])


def cohen_kappa(a: list[int], b: list[int]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def reviewer_agreement(db: Session) -> dict:
    """Pairwise agreement over items with >= 2 non-adjudication reviews (first two reviewers)."""
    rows = db.execute(
        select(ExpertReview.target_type, ExpertReview.analysis_id, ExpertReview.sample_id, ExpertReview.label, ExpertReview.created_at)
        .where(ExpertReview.is_adjudication.is_(False))
        .order_by(ExpertReview.created_at)
    ).all()
    by_item: dict[tuple, list[int]] = defaultdict(list)
    for t, aid, sid, label, _ in rows:
        by_item[(t, aid or sid)].append(label)
    pairs_a, pairs_b = [], []
    for labels in by_item.values():
        if len(labels) >= 2:
            for x, y in combinations(labels[:2], 2):
                pairs_a.append(x)
                pairs_b.append(y)
    n = len(pairs_a)
    return {
        "items_with_2plus_reviews": n,
        "percent_agreement": None if n == 0 else sum(x == y for x, y in zip(pairs_a, pairs_b, strict=True)) / n,
        "cohen_kappa": cohen_kappa(pairs_a, pairs_b),
        "note": "Computed from real reviews only; null when fewer than one doubly-reviewed item exists.",
    }


@router.get("/analytics", summary="Research analytics: dataset distribution, model metrics, analyses, reviews")
def analytics(db: Session = Depends(get_db), _: User = Depends(get_viewer)):
    real = (Dataset.kind == "import") & (Dataset.is_synthetic.is_(False))

    def grouped(col, *extra):
        q = (
            select(DatasetSample.language, col, func.count())
            .join(Dataset, Dataset.id == DatasetSample.dataset_id)
            .where(real, *extra)
            .group_by(DatasetSample.language, col)
        )
        out: dict[str, dict] = defaultdict(dict)
        for lang, k, n in db.execute(q):
            out[lang][str(k) if k is not None else "(none)"] = n
        return dict(out)

    eligible_labels = grouped(DatasetSample.final_label, DatasetSample.eligibility == "eligible")
    eligible_labels = {lang: {LABEL_NAMES[int(k)]: v for k, v in d.items() if k != "(none)"} for lang, d in eligible_labels.items()}
    by_source = defaultdict(dict)
    for key, elig, n in db.execute(
        select(SourceRegistry.key, DatasetSample.eligibility, func.count())
        .join(Dataset, Dataset.id == DatasetSample.dataset_id)
        .join(SourceRegistry, SourceRegistry.id == Dataset.source_id, isouter=True)
        .where(real)
        .group_by(SourceRegistry.key, DatasetSample.eligibility)
    ):
        by_source[key or "user_upload"][elig] = n

    splits = []
    for ds in db.scalars(select(Dataset).where(Dataset.kind == "split").order_by(Dataset.created_at.desc())):
        st = ds.stats or {}
        splits.append(
            {
                "id": ds.id,
                "language": ds.language,
                "version": ds.version,
                "split_sizes": st.get("split_sizes"),
                "label_distribution": st.get("label_distribution"),
                "grouping": st.get("grouping"),
                "created_at": ds.created_at,
            }
        )

    models = []
    for mv in db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())):
        t = mv.test_metrics or {}
        models.append(
            {
                "id": mv.id,
                "version_tag": mv.version_tag,
                "language": mv.language,
                "base_model": mv.base_model,
                "status": mv.status,
                "measured": True,
                "test": {k: t.get(k) for k in ("n", "accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1")},
                "per_class": t.get("per_class"),
                "confusion_matrix": t.get("confusion_matrix"),
                "calibration": t.get("calibration"),
                "selective": t.get("selective"),
                "subgroups": t.get("subgroups"),
            }
        )

    def count_by(col):
        return {str(k): n for k, n in db.execute(select(col, func.count()).group_by(col))}

    pred_counts = {LABEL_NAMES[int(k)]: v for k, v in count_by(Analysis.predicted_label).items() if k != "None"}
    return {
        "measured_results_available": bool(models),
        "datasets": {
            "imported_by_language": {lang: sum(d.values()) for lang, d in grouped(DatasetSample.eligibility).items()},
            "eligibility_by_language": grouped(DatasetSample.eligibility),
            "eligible_label_distribution": eligible_labels,
            "exclusion_reasons_by_language": grouped(DatasetSample.exclusion_reason, DatasetSample.exclusion_reason.is_not(None)),
            "health_topics_by_language": grouped(DatasetSample.health_topic, DatasetSample.eligibility == "eligible"),
            "by_source": dict(by_source),
        },
        "splits": splits,
        "models": models,
        "analyses": {
            "total": db.scalar(select(func.count(Analysis.id))) or 0,
            "by_status": count_by(Analysis.status),
            "by_language": count_by(Analysis.language_used),
            "by_predicted_label": pred_counts,
            "abstained": db.scalar(select(func.count(Analysis.id)).where(Analysis.abstained.is_(True))) or 0,
            "by_review_status": count_by(Analysis.review_status),
            "by_topic": count_by(Analysis.health_topic),
        },
        "reviews": {
            "total": db.scalar(select(func.count(ExpertReview.id))) or 0,
            "adjudications": db.scalar(select(func.count(ExpertReview.id)).where(ExpertReview.is_adjudication.is_(True))) or 0,
            "open_analyses": db.scalar(select(func.count(Analysis.id)).where(Analysis.review_status.in_(["pending", "in_review", "disagreement"]))) or 0,
            "open_samples": db.scalar(select(func.count(DatasetSample.id)).where(DatasetSample.review_status.in_(["pending", "in_review", "disagreement"])))
            or 0,
            "disagreements": (db.scalar(select(func.count(Analysis.id)).where(Analysis.review_status == "disagreement")) or 0)
            + (db.scalar(select(func.count(DatasetSample.id)).where(DatasetSample.review_status == "disagreement")) or 0),
            "agreement": reviewer_agreement(db),
        },
    }
