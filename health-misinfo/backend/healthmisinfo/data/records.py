"""The neutral record format every dataset adapter emits."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawRecord:
    external_id: str | None
    language: str
    text: str | None  # None when the source does not distribute text (e.g. tweet IDs only)
    original_label: str | None = None
    original_labels: dict = field(default_factory=dict)  # multi-label sources, preserved verbatim
    source_category: str | None = None
    source_url: str | None = None
    evidence_urls: list[str] = field(default_factory=list)
    claim_date: str | None = None
    group_key: str | None = None  # researcher-provided link for translations/paraphrases
    extra: dict = field(default_factory=dict)


@dataclass
class AdapterResult:
    records: list[RawRecord]
    source_key: str
    language: str
    file_name: str
    file_sha256: str
    rows_read: int
    filtered_out: dict[str, int] = field(default_factory=dict)  # reason -> count (pre-import filters)
    schema: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
