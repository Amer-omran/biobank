"""Transparent, dependency-free language identification for the two supported languages.

The platform only supports Arabic (``ar``) and English (``en``). Detection is script based
(Arabic-script vs Latin letters) plus an English function-word check so that other Latin-script
languages (e.g. French, common in Maghreb health rumors) are reported as ``unsupported`` instead of
being silently sent to the English model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_AR = re.compile("[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
_LAT = re.compile("[A-Za-zÀ-ɏ]")
_TOKEN = re.compile(r"[A-Za-zÀ-ɏ']+")

_EN = set(
    "the a an and or of to in on for with is are was were be been it this that these those not no "
    "you your we our they their he she his her i my can will would should could does do did has have "
    "had from by at as about than then if but so because what which who how when why all any more most "
    "cure cures causes cause vaccine vaccines virus disease health doctors people".split()
)
_OTHER_LATIN = set(
    "le la les des du un une et est sont pour avec dans sur pas que qui ce cette ces au aux "
    "el los las del por para con una es son que como pero muy "
    "der die das und ist nicht mit ein eine den dem zu von".split()
)


@dataclass
class LanguageResult:
    language: str  # "ar" | "en" | "mixed" | "unsupported" | "unknown"
    confidence: float
    supported_language: str | None  # the model language to use, if any
    details: dict = field(default_factory=dict)


def detect_language(text: str) -> LanguageResult:
    ar = len(_AR.findall(text or ""))
    lat = len(_LAT.findall(text or ""))
    total = ar + lat
    details = {"arabic_letters": ar, "latin_letters": lat}
    if total < 3:
        return LanguageResult("unknown", 0.0, None, details)
    ar_ratio = ar / total
    details["arabic_ratio"] = round(ar_ratio, 3)

    if ar_ratio >= 0.8:
        return LanguageResult("ar", round(ar_ratio, 3), "ar", details)

    if ar_ratio <= 0.2:
        tokens = [t.lower() for t in _TOKEN.findall(text)]
        en_hits = sum(t in _EN for t in tokens)
        other_hits = sum(t in _OTHER_LATIN for t in tokens)
        details.update({"english_function_words": en_hits, "other_latin_function_words": other_hits})
        if len(tokens) >= 4 and other_hits > en_hits:
            return LanguageResult("unsupported", round(1 - ar_ratio, 3), None, details)
        return LanguageResult("en", round(1 - ar_ratio, 3), "en", details)

    dominant = "ar" if ar_ratio >= 0.5 else "en"
    return LanguageResult("mixed", round(max(ar_ratio, 1 - ar_ratio), 3), dominant, details)
