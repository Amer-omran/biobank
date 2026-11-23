import numpy as np
import pytest

from healthmisinfo.ml.calibration import fit_temperature, risk_coverage, select_abstention_threshold, softmax
from healthmisinfo.ml.metrics import classification_metrics, expected_calibration_error, subgroup_metrics


def test_classification_metrics_known_values():
    y = [0, 0, 1, 1, 2, 2]
    p = [0, 1, 1, 1, 2, 0]
    m = classification_metrics(y, p)
    assert m["accuracy"] == pytest.approx(4 / 6)
    assert m["per_class"]["SUPPORTED"] == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "support": 2}
    assert m["per_class"]["MISLEADING"]["precision"] == pytest.approx(2 / 3)
    assert m["per_class"]["NEEDS_REVIEW"]["recall"] == pytest.approx(0.5)
    assert m["confusion_matrix"]["matrix"] == [[1, 1, 0], [0, 2, 0], [1, 0, 1]]
    assert m["macro_f1"] == pytest.approx(np.mean([0.5, 0.8, 2 / 3]))


def test_ece_zero_for_perfectly_calibrated_and_positive_when_overconfident():
    probs = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    assert expected_calibration_error(probs, [0, 1]) == 0
    over = np.array([[0.99, 0.005, 0.005]] * 10)
    y = [0] * 5 + [1] * 5
    assert expected_calibration_error(over, y) == pytest.approx(0.49, abs=1e-6)


def test_temperature_recovers_known_scale():
    rng = np.random.default_rng(0)
    n = 4000
    true_logits = rng.normal(size=(n, 3)) * 2
    y = np.array([rng.choice(3, p=softmax(true_logits[i : i + 1])[0]) for i in range(n)])
    overconfident = true_logits * 3.0  # a model whose logits are 3x too sharp
    t = fit_temperature(overconfident, y)
    assert t == pytest.approx(3.0, rel=0.15)
    assert expected_calibration_error(softmax(overconfident, t), y) < expected_calibration_error(softmax(overconfident), y)


def test_abstention_threshold_reports_whether_target_met():
    probs = np.array([[0.9, 0.05, 0.05]] * 50 + [[0.4, 0.35, 0.25]] * 50)
    y = np.array([0] * 50 + [1] * 50)
    res = select_abstention_threshold(probs, y, target_selective_accuracy=0.9, min_coverage=0.3)
    assert res["target_met"] is True and 0.4 < res["threshold"] <= 0.9 and res["validation_selective_accuracy"] == 1.0
    res2 = select_abstention_threshold(probs, 1 - (y > 0).astype(int), target_selective_accuracy=0.99, min_coverage=0.9)
    assert res2["target_met"] is False
    rc = risk_coverage(probs, y, [0.0, 0.95])
    assert rc[0]["coverage"] == 1.0 and rc[1]["coverage"] == 0.0 and rc[1]["selective_accuracy"] is None


def test_subgroups_flag_small_samples():
    out = subgroup_metrics([0, 1, 2, 0], [0, 1, 1, 0], ["covid19", "covid19", "other", None])
    assert out["covid19"]["n"] == 2 and out["covid19"]["small_sample_warning"] is True
    assert "(none)" in out
