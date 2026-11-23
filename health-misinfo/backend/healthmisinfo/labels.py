"""The 3-class label scheme used throughout the platform."""

from __future__ import annotations

from enum import IntEnum


class Label(IntEnum):
    SUPPORTED = 0
    MISLEADING = 1
    NEEDS_REVIEW = 2


LABEL_NAMES = [lab.name for lab in Label]  # index == id

LABEL_DESCRIPTIONS = {
    Label.SUPPORTED: {
        "en": "Supported by reliable evidence.",
        "ar": "مدعوم بأدلة موثوقة.",
    },
    Label.MISLEADING: {
        "en": "Contradicted by reliable evidence or demonstrably misleading.",
        "ar": "تناقضه أدلة موثوقة أو مضلل بشكل يمكن إثباته.",
    },
    Label.NEEDS_REVIEW: {
        "en": "Insufficient, conflicting, ambiguous, or unverified evidence.",
        "ar": "أدلة غير كافية أو متعارضة أو غامضة أو غير متحقق منها.",
    },
}

LABEL_AR = {Label.SUPPORTED: "مدعوم", Label.MISLEADING: "مضلل", Label.NEEDS_REVIEW: "يحتاج مراجعة"}


def parse_label(value: str | int) -> Label:
    if isinstance(value, int):
        return Label(value)
    v = str(value).strip().upper()
    if v.isdigit():
        return Label(int(v))
    return Label[v]
