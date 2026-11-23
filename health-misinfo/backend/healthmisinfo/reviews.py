"""Human review resolution: agreement, disagreement tracking and adjudication.

Rules (documented in docs/ANNOTATION_GUIDELINES.md):

* An adjudication (by an admin) always decides the final label.
* Otherwise, any disagreement between human reviewers -> ``disagreement`` (no final label).
* For dataset samples, a human label that contradicts the source-mapped label is also a
  ``disagreement`` – the sample is withheld from training until adjudicated.
* Once ``reviews_required`` reviewers agree -> ``agreed`` and the human label is final.
* With fewer reviews -> ``in_review``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from healthmisinfo.db.models import ExpertReview


@dataclass
class Resolution:
    status: str
    final_label: int | None
    final_label_source: str | None


def resolve(
    reviews: Sequence[ExpertReview],
    reviews_required: int,
    source_label: int | None = None,
    pending_if_no_reviews: bool = False,
) -> Resolution:
    adjudications = sorted((r for r in reviews if r.is_adjudication), key=lambda r: (r.created_at, r.id))
    if adjudications:
        return Resolution("adjudicated", adjudications[-1].label, "adjudication")

    human = [r for r in reviews if not r.is_adjudication]
    if not human:
        if source_label is not None:
            return Resolution("unreviewed", source_label, "source_mapping")
        return Resolution("pending" if pending_if_no_reviews else "unreviewed", None, None)

    labels = {r.label for r in human}
    if len(labels) > 1:
        return Resolution("disagreement", None, None)
    (label,) = labels
    if source_label is not None and label != source_label:
        return Resolution("disagreement", None, None)
    distinct_reviewers = {r.reviewer_id for r in human}
    if len(distinct_reviewers) >= reviews_required:
        return Resolution("agreed", label, "human_review")
    # Not enough reviewers yet: keep the source label (if any) as provisional final label.
    if source_label is not None:
        return Resolution("in_review", source_label, "source_mapping")
    return Resolution("in_review", None, None)
