import json

import pytest

from healthmisinfo.data.registry import (
    EXCLUDED_BY_MAPPING,
    MAPPED,
    NO_LABEL,
    PENDING_APPROVAL,
    UNMAPPED,
    LabelMapper,
    load_sources,
)
from healthmisinfo.labels import Label


def test_registry_has_required_sources_with_license_fields():
    data = load_sources()
    keys = {s["key"] for s in data["sources"]}
    assert {"arafacts", "aracovid19_mfh", "pubhealth", "moh_sa_open_data", "who", "pubmed"} <= keys
    for s in data["sources"]:
        assert s["license_status"] in {"verified", "unclear_needs_review", "unknown", "not_a_dataset"}
        assert "license_evidence" in s and "training_use_status" in s
    by = {s["key"]: s for s in data["sources"]}
    assert by["aracovid19_mfh"]["text_available"] is False
    assert by["aracovid19_mfh"]["license_status"] == "unclear_needs_review"


def test_shipped_mappings_are_unapproved_proposals():
    """Nothing is approved on the researchers' behalf: every shipped entry is 'proposed'."""
    for key in ("arafacts", "pubhealth"):
        m = LabelMapper.load(key)
        assert m.summary()["entry_status_counts"] == {"proposed": len(m.entries)}
        label, status = m.apply(next(iter(m.entries)))
        assert label is None and status == PENDING_APPROVAL
    assert LabelMapper.load("aracovid19_mfh").entries == {}


def test_mapper_statuses(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(
        json.dumps(
            {
                "mapping_version": "t1",
                "maps_from_field": "label",
                "entries": [
                    {"original": "false", "proposed_label": "MISLEADING", "status": "approved", "approved_by": "Dr X"},
                    {"original": "satire", "proposed_label": "EXCLUDE", "status": "approved", "approved_by": "Dr X"},
                    {"original": "mixture", "proposed_label": "NEEDS_REVIEW", "status": "proposed"},
                ],
            }
        ),
        encoding="utf-8",
    )
    m = LabelMapper.load("custom", p)
    assert m.apply("false") == (int(Label.MISLEADING), MAPPED)
    assert m.apply("satire") == (None, EXCLUDED_BY_MAPPING)
    assert m.apply("mixture") == (None, PENDING_APPROVAL)
    assert m.apply("unknown") == (None, UNMAPPED)
    assert m.apply("") == (None, NO_LABEL)


def test_approved_entry_requires_approver(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"mapping_version": "t", "entries": [{"original": "x", "proposed_label": "SUPPORTED", "status": "approved"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="approved_by"):
        LabelMapper.load("custom", p)


def test_inline_mapping_validates_targets():
    m = LabelMapper.from_inline("user_upload", {"T": "supported", "F": "MISLEADING"}, approved_by="R-0001")
    assert m.apply("T") == (0, MAPPED)
    with pytest.raises(ValueError):
        LabelMapper.from_inline("user_upload", {"T": "TRUE"}, approved_by="R-0001")
