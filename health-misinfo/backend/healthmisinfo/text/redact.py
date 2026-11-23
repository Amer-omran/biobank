"""Minimal PII redaction applied before an analysed text is stored.

Users submit *claims*, not patient records, but people paste messages that may contain phone
numbers, e-mails or account handles. These are replaced before persistence. This is a best-effort
filter, not a guarantee; see docs/PRIVACY_SECURITY.md.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(?<!\w)\+?[\d٠-٩][\d٠-٩\s\-()]{7,}[\d٠-٩](?!\w)")
_MENTION = re.compile(r"(?<![\w@])@\w{1,30}")
_NATIONAL_ID = re.compile(r"(?<!\d)\d{10}(?!\d)")


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}

    def sub(pattern: re.Pattern, repl: str, t: str, key: str) -> str:
        new, n = pattern.subn(repl, t)
        if n:
            counts[key] = counts.get(key, 0) + n
        return new

    t = sub(_EMAIL, "[EMAIL]", text, "email")
    t = sub(_MENTION, "[USER]", t, "mention")
    t = sub(_NATIONAL_ID, "[ID]", t, "id_number")
    t = sub(_PHONE, "[PHONE]", t, "phone")
    return t, counts
