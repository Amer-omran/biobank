"""Conservative text normalization.

Two functions with different purposes:

* ``normalize_for_model`` – the text fed to the classifier (training AND inference). It is
  conservative: Unicode NFKC, removal of invisible/bidi control characters and Arabic tatweel,
  Arabic diacritics (tashkeel) removal, URL / e-mail / @mention placeholders, whitespace collapse.
  The original text is always stored alongside it.
* ``match_key`` – an aggressive key used ONLY for duplicate detection (never shown, never fed to a
  model): lower-casing, punctuation removal and Arabic orthographic unification.

``NORMALIZATION_VERSION`` is stored with every dataset and model so the exact transformation is
traceable.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

NORMALIZATION_VERSION = "norm-v1"

_INVISIBLE = re.compile("[​-‏‪-‮⁦-⁩﻿­]")
_TATWEEL = "ـ"
_TASHKEEL = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ]")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_MENTION = re.compile(r"(?<![\w@])@\w{1,30}")
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

_AR_UNIFY = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
    }
)

PLACEHOLDERS = {
    "ar": {"url": "[رابط]", "email": "[بريد]", "mention": "[مستخدم]"},
    "en": {"url": "[URL]", "email": "[EMAIL]", "mention": "[USER]"},
}


def normalize_for_model(text: str, language: str = "en") -> str:
    if text is None:
        return ""
    ph = PLACEHOLDERS.get(language, PLACEHOLDERS["en"])
    t = unicodedata.normalize("NFKC", str(text))
    t = _INVISIBLE.sub("", t)
    t = _EMAIL.sub(f" {ph['email']} ", t)
    t = _URL.sub(f" {ph['url']} ", t)
    t = _MENTION.sub(f" {ph['mention']} ", t)
    t = t.replace(_TATWEEL, "")
    t = _TASHKEEL.sub("", t)
    t = _WS.sub(" ", t).strip()
    return t


def match_key(text: str) -> str:
    """Aggressive key for duplicate detection only."""
    t = normalize_for_model(text, "en")
    t = t.lower().translate(_AR_UNIFY)
    for ph in ("[url]", "[email]", "[user]"):
        t = t.replace(ph, " ")
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t


def match_key_hash(text: str) -> str:
    return hashlib.sha256(match_key(text).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
