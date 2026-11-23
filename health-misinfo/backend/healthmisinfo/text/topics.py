"""Heuristic, bilingual health-topic tagger used for subgroup evaluation and filtering.

This is a transparent keyword lexicon, NOT a trained classifier. Its output is a coarse grouping
for analysis ("which topics does the model do worse on?") and must be described as heuristic in any
report. Keywords are matched on the duplicate-detection key (Arabic letters unified, lower-cased).
"""

from __future__ import annotations

from healthmisinfo.text.normalize import match_key

TOPIC_VERSION = "topics-v1"

# Order matters: first match wins (more specific topics first).
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "covid19": ["كورونا", "كوفيد", "covid", "coronavirus", "sars-cov", "اوميكرون", "omicron", "متحور"],
    "vaccines": ["لقاح", "تطعيم", "مطعوم", "vaccin", "immuniz", "mrna", "booster", "جرعه"],
    "cancer": ["سرطان", "ورم", "اورام", "cancer", "tumor", "tumour", "chemotherapy", "كيماوي"],
    "chronic_disease": [
        "سكري",
        "السكر",
        "ضغط الدم",
        "القلب",
        "كوليسترول",
        "كلي",
        "diabetes",
        "insulin",
        "hypertension",
        "blood pressure",
        "heart",
        "cholesterol",
        "kidney",
        "stroke",
        "جلطه",
    ],
    "mental_health": ["اكتئاب", "قلق", "نفسي", "انتحار", "depress", "anxiety", "mental", "suicide", "autism", "توحد"],
    "maternal_child": ["حامل", "حمل", "رضيع", "اطفال", "طفل", "ولاده", "pregnan", "infant", "baby", "breastfe", "children"],
    "nutrition_diet": [
        "غذاء",
        "اغذيه",
        "طعام",
        "حميه",
        "رجيم",
        "فيتامين",
        "سكر",
        "ماء",
        "ثوم",
        "ليمون",
        "عسل",
        "diet",
        "food",
        "vitamin",
        "nutrition",
        "sugar",
        "garlic",
        "lemon",
        "honey",
        "fasting",
        "صيام",
    ],
    "alternative_medicine": ["اعشاب", "عشبه", "طب بديل", "حجامه", "herbal", "homeopath", "natural remedy", "detox"],
    "infectious_disease": [
        "فيروس",
        "بكتيريا",
        "عدوى",
        "وباء",
        "جائحه",
        "انفلونزا",
        "حصبه",
        "ملاريا",
        "ايدز",
        "جدري",
        "virus",
        "bacteria",
        "infection",
        "epidemic",
        "pandemic",
        "flu",
        "influenza",
        "measles",
        "malaria",
        "hiv",
        "monkeypox",
        "mpox",
        "ebola",
        "cholera",
        "كوليرا",
    ],
    "medication_treatment": ["دواء", "علاج", "مضاد حيوي", "حبوب", "drug", "medicine", "treatment", "antibiotic", "pill", "ivermectin", "hydroxychloroquine"],
}

_KEYS = {topic: [match_key(k) for k in kws] for topic, kws in TOPIC_KEYWORDS.items()}


def tag_topic(text: str) -> str:
    key = f" {match_key(text or '')} "
    for topic, kws in _KEYS.items():
        for kw in kws:
            if kw and kw in key:
                return topic
    return "other"
