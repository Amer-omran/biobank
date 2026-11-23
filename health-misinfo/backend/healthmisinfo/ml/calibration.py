"""Temperature scaling and abstention-threshold selection – fitted on VALIDATION data only."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.metrics import f1_score

from healthmisinfo.ml.metrics import brier_score, expected_calibration_error, negative_log_likelihood


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = np.asarray(logits, dtype=float) / float(temperature)
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(logits: np.ndarray, y_true: Sequence[int]) -> float:
    """Single scalar T > 0 minimising validation NLL (Guo et al., 2017)."""
    logits = np.asarray(logits, dtype=float)
    y = np.asarray(y_true, dtype=int)
    if len(y) == 0:
        raise ValueError("Cannot fit temperature on an empty validation set")

    def nll(log_t: float) -> float:
        return negative_log_likelihood(softmax(logits, np.exp(log_t)), y)

    res = minimize_scalar(nll, bounds=(np.log(0.05), np.log(20.0)), method="bounded")
    return float(np.exp(res.x))


def calibration_report(logits: np.ndarray, y_true: Sequence[int], temperature: float) -> dict:
    raw = softmax(logits, 1.0)
    cal = softmax(logits, temperature)
    return {
        "temperature": temperature,
        "ece_raw": expected_calibration_error(raw, y_true),
        "ece_calibrated": expected_calibration_error(cal, y_true),
        "nll_raw": negative_log_likelihood(raw, y_true),
        "nll_calibrated": negative_log_likelihood(cal, y_true),
        "brier_raw": brier_score(raw, y_true),
        "brier_calibrated": brier_score(cal, y_true),
    }


def risk_coverage(probs: np.ndarray, y_true: Sequence[int], thresholds: Sequence[float]) -> list[dict]:
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y_true, dtype=int)
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    rows = []
    for t in thresholds:
        keep = conf >= t
        cov = float(keep.mean()) if len(y) else 0.0
        if keep.any():
            acc = float((pred[keep] == y[keep]).mean())
            mf1 = float(f1_score(y[keep], pred[keep], labels=list(range(probs.shape[1])), average="macro", zero_division=0))
        else:
            acc, mf1 = None, None
        rows.append({"threshold": round(float(t), 4), "coverage": cov, "selective_accuracy": acc, "selective_macro_f1": mf1})
    return rows


def select_abstention_threshold(
    probs_val: np.ndarray,
    y_val: Sequence[int],
    target_selective_accuracy: float = 0.90,
    min_coverage: float = 0.30,
) -> dict:
    """Smallest threshold whose validation selective accuracy reaches the target while keeping at
    least ``min_coverage``. If no threshold qualifies, choose the one with the best selective
    accuracy subject to coverage and report ``target_met = False`` (no silent success)."""
    k = np.asarray(probs_val).shape[1]
    grid = np.round(np.arange(np.ceil(100 / k) / 100, 0.995, 0.01), 2)  # from just above chance (1/k)
    curve = risk_coverage(probs_val, y_val, grid)
    feasible = [r for r in curve if r["coverage"] >= min_coverage and r["selective_accuracy"] is not None]
    chosen = None
    target_met = False
    for r in feasible:
        if r["selective_accuracy"] >= target_selective_accuracy:
            chosen, target_met = r, True
            break
    if chosen is None and feasible:
        chosen = max(feasible, key=lambda r: (r["selective_accuracy"], r["coverage"]))
    return {
        "threshold": chosen["threshold"] if chosen else None,
        "target_selective_accuracy": target_selective_accuracy,
        "min_coverage": min_coverage,
        "target_met": target_met,
        "validation_coverage": chosen["coverage"] if chosen else None,
        "validation_selective_accuracy": chosen["selective_accuracy"] if chosen else None,
        "fitted_on": "validation",
        "curve": curve,
    }
