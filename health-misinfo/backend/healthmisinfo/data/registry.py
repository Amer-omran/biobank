"""Source registry + label-mapping loading. Mappings are applied ONLY for approved entries."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from healthmisinfo.config import get_settings
from healthmisinfo.db.models import SourceRegistry
from healthmisinfo.labels import Label

# mapping_status values stored on dataset_samples
MAPPED = "mapped"
PENDING_APPROVAL = "pending_mapping_approval"
EXCLUDED_BY_MAPPING = "excluded_by_mapping"
UNMAPPED = "unmapped_label"
NO_LABEL = "no_label"
NO_MAPPING_DEFINED = "no_mapping_defined"


def sources_file() -> Path:
    return get_settings().registry_dir / "sources.json"


def load_sources() -> dict:
    return json.loads(sources_file().read_text(encoding="utf-8"))


def seed_registry(db: Session) -> list[str]:
    """Upsert the JSON registry into the source_registry table. Never downgrades a human review."""
    data = load_sources()
    keys = []
    for src in data["sources"]:
        row = db.scalar(select(SourceRegistry).where(SourceRegistry.key == src["key"]))
        if row is None:
            row = SourceRegistry(key=src["key"])
            db.add(row)
        elif row.reviewed_by_id is not None:
            # A human has reviewed/changed the license status in the app; keep their decision.
            keys.append(src["key"])
            continue
        row.name = src["name"]
        row.languages = src.get("languages", [])
        row.official_url = src.get("official_url")
        row.paper_url = src.get("paper_url")
        row.access_method = src.get("access_method")
        row.verified_revision = src.get("verified_revision")
        row.license_name = src.get("license_name")
        row.license_url = src.get("license_url")
        row.license_evidence = src.get("license_evidence")
        row.license_status = src.get("license_status", "unknown")
        row.commercial_use_allowed = src.get("commercial_use_allowed")
        row.redistribution_allowed = src.get("redistribution_allowed")
        row.attribution_required = src.get("attribution_required")
        row.text_available = bool(src.get("text_available"))
        row.citation = src.get("citation")
        row.training_use_status = src.get("training_use_status", "unknown")
        row.notes = src.get("notes", [])
        row.details = {k: src.get(k) for k in ("verified_file_sha256", "schema_verified", "schema_documented", "observed_counts") if k in src}
        row.registry_version = data.get("registry_version")
        keys.append(src["key"])
    db.flush()
    return keys


def mapping_path(source_key: str) -> Path:
    return get_settings().registry_dir / "label_mappings" / f"{source_key}.json"


@dataclass
class LabelMapper:
    source_key: str
    version: str
    sha256: str
    maps_from_field: str
    entries: dict[str, dict] = field(default_factory=dict)
    case_insensitive: bool = False

    @classmethod
    def load(cls, source_key: str, path: Path | None = None) -> LabelMapper:
        p = path or mapping_path(source_key)
        raw = p.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        ci = source_key == "pubhealth" or bool(data.get("case_insensitive"))
        entries = {}
        for e in data.get("entries", []):
            key = e["original"].strip()
            if ci:
                key = key.lower()
            if key in entries:
                raise ValueError(f"Duplicate mapping entry for {e['original']!r} in {p}")
            if e["proposed_label"] != "EXCLUDE" and e["proposed_label"] not in Label.__members__:
                raise ValueError(f"Invalid target label {e['proposed_label']!r} in {p}")
            if e["status"] not in {"proposed", "approved", "rejected"}:
                raise ValueError(f"Invalid status {e['status']!r} in {p}")
            if e["status"] == "approved" and not (e.get("approved_by") or data.get("approved_by")):
                raise ValueError(f"Approved entry {e['original']!r} lacks approved_by in {p}")
            entries[key] = e
        return cls(
            source_key=source_key,
            version=data["mapping_version"],
            sha256=hashlib.sha256(raw).hexdigest(),
            maps_from_field=data.get("maps_from_field", "label"),
            entries=entries,
            case_insensitive=ci,
        )

    @classmethod
    def from_inline(cls, source_key: str, mapping: dict[str, str], approved_by: str) -> LabelMapper:
        """Mapping supplied at upload time by an authenticated user (recorded as approved by them)."""
        entries = {}
        for orig, target in mapping.items():
            target = str(target).strip().upper()
            if target != "EXCLUDE" and target not in Label.__members__:
                raise ValueError(f"Invalid target label {target!r} for {orig!r}")
            entries[str(orig).strip()] = {
                "original": orig,
                "proposed_label": target,
                "status": "approved",
                "approved_by": approved_by,
                "rationale": "inline mapping supplied at import",
            }
        payload = json.dumps(entries, sort_keys=True, ensure_ascii=False).encode()
        return cls(
            source_key=source_key,
            version=f"inline-{hashlib.sha256(payload).hexdigest()[:12]}",
            sha256=hashlib.sha256(payload).hexdigest(),
            maps_from_field="label",
            entries=entries,
        )

    def apply(self, original_label: str | None) -> tuple[int | None, str]:
        if original_label is None or str(original_label).strip() == "":
            return None, NO_LABEL
        if not self.entries:
            return None, NO_MAPPING_DEFINED
        key = str(original_label).strip()
        if self.case_insensitive:
            key = key.lower()
        e = self.entries.get(key)
        if e is None:
            return None, UNMAPPED
        if e["status"] != "approved":
            return None, PENDING_APPROVAL
        if e["proposed_label"] == "EXCLUDE":
            return None, EXCLUDED_BY_MAPPING
        return int(Label[e["proposed_label"]]), MAPPED

    def summary(self) -> dict:
        statuses: dict[str, int] = {}
        for e in self.entries.values():
            statuses[e["status"]] = statuses.get(e["status"], 0) + 1
        return {
            "source_key": self.source_key,
            "mapping_version": self.version,
            "sha256": self.sha256,
            "entries": len(self.entries),
            "entry_status_counts": statuses,
        }


def load_mapping_file(source_key: str) -> dict:
    return json.loads(mapping_path(source_key).read_text(encoding="utf-8"))


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
