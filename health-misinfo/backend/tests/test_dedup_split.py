import numpy as np
import pytest

from healthmisinfo.data.dedup import GroupItem, compute_groups, near_duplicate_pairs
from healthmisinfo.data.split import SplitVerificationError, assign_and_verify
from healthmisinfo.data.synthetic import make_synthetic_split
from healthmisinfo.text.normalize import match_key_hash

from .conftest import FIXTURES


def test_near_duplicates_detected_and_distinct_claims_not():
    texts = [
        "Garlic cures influenza within one day",
        "Garlic cures influenza within one day!!",
        "Garlic cures the influenza within 1 day",
        "Vaccines are tested in clinical trials before approval",
    ]
    pairs = {(i, j) for i, j, _ in near_duplicate_pairs(texts, 0.8)}
    assert (0, 1) in pairs and (0, 2) in pairs
    assert not any(3 in p for p in pairs)


def test_compute_groups_links_by_hash_url_groupkey_and_similarity():
    items = [
        GroupItem(match_key_hash("Claim A about lemons curing colds"), "Claim A about lemons curing colds"),
        GroupItem(match_key_hash("claim a about lemons curing colds."), "claim a about lemons curing colds."),
        GroupItem(match_key_hash("Unrelated claim one"), "Unrelated claim one", source_url="https://fc/1"),
        GroupItem(match_key_hash("Totally different text"), "Totally different text", source_url="https://fc/1"),
        GroupItem(match_key_hash("English version"), "English version", group_key="pair-7"),
        GroupItem(match_key_hash("نسخة عربية"), "نسخة عربية", group_key="pair-7"),
        GroupItem(match_key_hash("Singleton"), "Singleton"),
    ]
    groups, stats = compute_groups(items)
    assert groups[0] == groups[1]
    assert groups[2] == groups[3]
    assert groups[4] == groups[5]
    assert len({groups[0], groups[2], groups[4], groups[6]}) == 4
    assert stats["exact_links"] == 1 and stats["source_url_links"] == 1 and stats["group_key_links"] == 1
    assert groups == compute_groups(items)[0]  # deterministic


def test_assign_and_verify_invariants():
    rng = np.random.default_rng(1)
    labels = rng.choice(3, size=300, p=[0.3, 0.5, 0.2])
    groups = np.array([f"g{i // 2}" for i in range(300)])  # pairs share a group
    assign, ver = assign_and_verify(labels, groups, seed=7)
    all_idx = np.concatenate(list(assign.values()))
    assert sorted(all_idx.tolist()) == list(range(300))
    assert ver["group_overlap"] == 0
    for split in ("train", "validation", "test"):
        assert all(n > 0 for n in ver["label_distribution"][split].values())
    assert 0.6 < ver["actual_ratios"]["train"] < 0.8
    assert 0.1 < ver["actual_ratios"]["test"] < 0.2
    again, _ = assign_and_verify(labels, groups, seed=7)
    assert all(np.array_equal(assign[k], again[k]) for k in assign)  # reproducible


@pytest.mark.filterwarnings("ignore:The least populated class:UserWarning")
def test_assign_refuses_when_a_class_cannot_cover_all_splits():
    labels = np.array([0] * 40 + [1] * 40 + [2] * 1)
    groups = np.array([f"g{i}" for i in range(81)])
    with pytest.raises(SplitVerificationError, match="missing a class"):
        assign_and_verify(labels, groups, seed=1)


def test_synthetic_split_manifest_is_flagged(tmp_path):
    m = make_synthetic_split(FIXTURES / "synthetic_claims_en.csv", "en", tmp_path / "s")
    assert m["synthetic"] is True and m["status"] == "valid" and m["group_overlap"] == 0
    assert sum(m["split_sizes"].values()) == 63
    with pytest.raises(ValueError):
        make_synthetic_split(FIXTURES / "arafacts_sample_schema.csv", "ar", tmp_path / "x")
