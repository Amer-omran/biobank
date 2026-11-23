"""Import → mapping → duplicates → reviews → eligibility → split, against a real (temp) database.

Records here are constructed in-test and marked TEST-ONLY; they live in a throw-away database."""

import json

import pytest
from sqlalchemy import select

from healthmisinfo.data.adapters.arafacts import load_arafacts
from healthmisinfo.data.pipeline import import_records, refresh_dataset, refresh_sample
from healthmisinfo.data.records import AdapterResult, RawRecord
from healthmisinfo.data.registry import LabelMapper
from healthmisinfo.data.split import SplitError, build_splits
from healthmisinfo.db.models import Annotation, AuditLog, DatasetSample, ExpertReview, SplitAssignment
from healthmisinfo.labels import Label

from .conftest import FIXTURES

TOPICS = [
    "influenza",
    "measles",
    "cholera",
    "diabetes",
    "malaria",
    "asthma",
    "rabies",
    "dengue",
    "polio",
    "mumps",
    "anemia",
    "scurvy",
    "rickets",
    "tetanus",
    "typhoid",
]
TEMPLATES = {
    "T": "TEST-ONLY verified statement number {i} that hygiene lowers {t} cases in region {i}",
    "F": "TEST-ONLY fabricated rumour {i}: kitchen spice {i} instantly eliminates {t} for everyone",
    "U": "TEST-ONLY unverified post {i} says supplement {i} might change {t} outcomes somehow",
}


def records(n_per_class=15, lang="en"):
    out = []
    for lab, tpl in TEMPLATES.items():
        for i in range(n_per_class):
            out.append(
                RawRecord(
                    external_id=f"{lab}{i}",
                    language=lang,
                    text=tpl.format(i=i, t=TOPICS[i % len(TOPICS)]),
                    original_label=lab,
                    source_url=f"https://fc.test/{lab}/{i}",
                )
            )
    return out


def result(recs, key="user_upload", lang="en"):
    return AdapterResult(records=recs, source_key=key, language=lang, file_name="t.csv", file_sha256="0" * 64, rows_read=len(recs))


MAPPER = LabelMapper.from_inline("user_upload", {"T": "SUPPORTED", "F": "MISLEADING", "U": "NEEDS_REVIEW"}, approved_by="R-TEST")


def test_import_marks_eligibility_and_writes_provenance(db):
    ds = import_records(db, result(records()), name="t", version="1", mapper=MAPPER, license_confirmed_by_uploader=True)
    db.commit()
    assert ds.stats["eligible"] == 45
    assert ds.stats["eligible_label_distribution"] == {"0": 15, "1": 15, "2": 15}
    assert db.scalar(select(AuditLog).where(AuditLog.action == "dataset.import")) is not None
    assert len(db.scalars(select(Annotation).where(Annotation.annotator_kind == "source_mapping")).all()) == 45
    s = db.scalars(select(DatasetSample)).first()
    assert s.original_text.startswith("TEST-ONLY") and s.normalized_text and s.match_key_hash


def test_license_unconfirmed_and_unapproved_mapping_block_training(db):
    ds = import_records(db, result(records(3)), name="nolic", version="1", mapper=MAPPER)
    assert ds.stats["eligible"] == 0
    assert ds.stats["exclusion_reasons"] == {"license_review_required": 9}
    ds2 = import_records(db, result(records(3)), name="nomap", version="1", mapper=None, license_confirmed_by_uploader=True)
    assert ds2.stats["exclusion_reasons"] == {"exact_duplicate": 9}  # same texts as previous dataset
    ds3 = import_records(
        db,
        result([RawRecord("x", "en", "TEST-ONLY a brand new claim about mumps", "T")]),
        name="nomap2",
        version="1",
        mapper=None,
        license_confirmed_by_uploader=True,
    )
    assert ds3.stats["exclusion_reasons"] == {"no_approved_label": 1}


def test_arafacts_import_is_pending_until_mapping_approved_and_license_verified(db, tmp_path):
    res = load_arafacts(FIXTURES / "arafacts_sample_schema.csv")
    ds = import_records(db, res, name="arafacts-health", version="fixture", mapper=LabelMapper.load("arafacts"))
    reasons = ds.stats["exclusion_reasons"]
    assert reasons.get("pending_mapping_approval") == 4  # SYN_1, SYN_3, SYN_5 (satire), SYN_6
    # SYN_2 differs from SYN_1 only by hamza spelling and punctuation -> same match key -> exact duplicate
    assert reasons.get("exact_duplicate") == 1
    # Approve the mapping (test copy) and re-run: AraFacts license is 'verified' in the registry.
    data = json.loads((FIXTURES.parents[2] / "data/registry/label_mappings/arafacts.json").read_text(encoding="utf-8"))
    for e in data["entries"]:
        e["status"], e["approved_by"] = "approved", "TEST"
    p = tmp_path / "arafacts.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    stats = refresh_dataset(db, ds, mapper=LabelMapper.load("arafacts", p))
    assert stats["eligible"] == 3  # SYN_1 MISLEADING, SYN_3 SUPPORTED, SYN_6 NEEDS_REVIEW
    assert stats["exclusion_reasons"].get("excluded_by_mapping") == 1  # satire


def test_reviews_disagreement_and_adjudication_control_eligibility(db, users):
    ds = import_records(db, result(records(2)), name="rv", version="1", mapper=MAPPER, license_confirmed_by_uploader=True)
    s = db.scalars(select(DatasetSample).where(DatasetSample.dataset_id == ds.id, DatasetSample.original_label == "F")).first()
    assert s.eligibility == "eligible" and s.final_label == Label.MISLEADING

    db.add(ExpertReview(target_type="sample", sample_id=s.id, reviewer_id=users["rev1"].id, label=int(Label.MISLEADING)))
    db.flush()
    refresh_sample(db, s, reviews_required=2)
    assert s.review_status == "in_review" and s.eligibility == "eligible"

    db.add(ExpertReview(target_type="sample", sample_id=s.id, reviewer_id=users["rev2"].id, label=int(Label.NEEDS_REVIEW)))
    db.flush()
    refresh_sample(db, s, reviews_required=2)
    assert s.review_status == "disagreement" and s.final_label is None
    assert (s.eligibility, s.exclusion_reason) == ("pending", "review_disagreement")

    db.add(ExpertReview(target_type="sample", sample_id=s.id, reviewer_id=users["admin"].id, label=int(Label.NEEDS_REVIEW), is_adjudication=True))
    db.flush()
    refresh_sample(db, s, reviews_required=2)
    assert s.review_status == "adjudicated" and s.final_label == Label.NEEDS_REVIEW and s.final_label_source == "adjudication"
    assert s.eligibility == "eligible"


def test_label_conflict_between_duplicates_is_withheld(db):
    a = import_records(
        db,
        result([RawRecord("1", "en", "TEST-ONLY lemon water cures every cold", "F")]),
        name="c1",
        version="1",
        mapper=MAPPER,
        license_confirmed_by_uploader=True,
    )
    import_records(
        db,
        result([RawRecord("2", "en", "test-only: Lemon water cures every cold!", "T")]),
        name="c2",
        version="1",
        mapper=MAPPER,
        license_confirmed_by_uploader=True,
    )
    stats = refresh_dataset(db, a)
    assert stats["exclusion_reasons"] == {"label_conflict": 1}


def test_build_splits_success_and_reproducibility(db, tmp_path):
    import_records(db, result(records(20)), name="sp", version="1", mapper=MAPPER, license_confirmed_by_uploader=True)
    res = build_splits(db, "en", version="v1", seed=3, out_root=tmp_path)
    r = res.report
    assert r["status"] == "valid" and r["group_overlap"] == 0
    assert sum(r["split_sizes"].values()) == 60
    assert r["shortfall_vs_target"] == 3000 - 60
    for split in ("train", "validation", "test"):
        assert all(v > 0 for v in r["label_distribution"][split].values())
        assert (tmp_path / "en" / "v1" / f"{split}.csv").exists()
    assert len(db.scalars(select(SplitAssignment)).all()) == 60
    res2 = build_splits(db, "en", version="v2", seed=3, out_root=tmp_path)
    assert res2.report["files"]["test"]["sha256"] == r["files"]["test"]["sha256"]
    with pytest.raises(ValueError, match="already exists"):
        build_splits(db, "en", version="v1", out_root=tmp_path)


def test_build_splits_refuses_invalid(db, tmp_path):
    with pytest.raises(SplitError, match="No eligible"):
        build_splits(db, "ar", version="e", out_root=tmp_path)
    recs = [r for r in records(15) if r.original_label != "U"] + records(15)[-2:]  # only 2 NEEDS_REVIEW
    import_records(db, result(recs), name="few", version="1", mapper=MAPPER, license_confirmed_by_uploader=True)
    with pytest.raises(SplitError) as e:
        build_splits(db, "en", version="bad", out_root=tmp_path)
    assert "fewer than 3 independent groups" in str(e.value)
    assert e.value.report["status"] == "invalid"
    assert not (tmp_path / "en" / "bad").exists()
    assert db.scalar(select(AuditLog).where(AuditLog.action == "split.failed")) is not None


def test_synthetic_never_eligible_or_split(db, tmp_path):
    ds = import_records(db, result(records(20)), name="syn", version="1", mapper=MAPPER, is_synthetic=True, license_confirmed_by_uploader=True)
    assert ds.stats["eligible"] == 0 and ds.stats["exclusion_reasons"] == {"synthetic_fixture": 60}
    with pytest.raises(SplitError):
        build_splits(db, "en", version="s", out_root=tmp_path)


def test_binary_scheme_drops_needs_review_and_splits_two_classes(db, tmp_path):
    recs = [r for r in records(20) if r.original_label != "U"] + records(20)[-2:]  # only 2 NEEDS_REVIEW
    import_records(db, result(recs), name="bin", version="1", mapper=MAPPER, license_confirmed_by_uploader=True)
    with pytest.raises(SplitError):
        build_splits(db, "en", version="three", out_root=tmp_path)  # 3-class impossible
    rep = build_splits(db, "en", version="bin", out_root=tmp_path, label_scheme="binary").report
    assert rep["status"] == "valid" and rep["label_scheme"] == "binary"
    assert rep["excluded_by_label_scheme"] == 2
    assert all(set(d) == {"SUPPORTED", "MISLEADING"} for d in rep["label_distribution"].values())
