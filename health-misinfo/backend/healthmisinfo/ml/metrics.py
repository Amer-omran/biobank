"""Evaluation metrics. All numbers reported by the platform come from these functions applied to
real model outputs on a held-out split – nothing here fabricates or smooths results."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from healthmisinfo.labels import LABEL_NAMES

LABELS = [0, 1, 2]


def classification_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    mp, mr, mf, _ = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)
    return {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)) if len(y_true) else 0.0,
        "macro_precision": float(mp),
        "macro_recall": float(mr),
        "macro_f1": float(mf),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="weighted", zero_division=0)),
        "per_class": {
            LABEL_NAMES[c]: {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f[i]),
                "support": int(s[i]),
            }
            for i, c in enumerate(LABELS)
        },
        "confusion_matrix": {
            "labels": LABEL_NAMES,
            "rows_are": "true label",
            "columns_are": "predicted label",
            "matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
        },
        "true_distribution": {LABEL_NAMES[k]: int(v) for k, v in sorted(Counter(y_true.tolist()).items())},
        "predicted_distribution": {LABEL_NAMES[k]: int(v) for k, v in sorted(Counter(y_pred.tolist()).items())},
    }


def expected_calibration_error(probs: np.ndarray, y_true: Sequence[int], n_bins: int = 15) -> float:
    probs = np.asarray(probs, dtype=float)
    y_true = np.asarray(y_true, dtype=int)
    if len(y_true) == 0:
        return 0.0
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    correct = (pred == y_true).astype(float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:], strict=True):
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def brier_score(probs: np.ndarray, y_true: Sequence[int]) -> float:
    probs = np.asarray(probs, dtype=float)
    y_true = np.asarray(y_true, dtype=int)
    if len(y_true) == 0:
        return 0.0
    onehot = np.eye(probs.shape[1])[y_true]
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def negative_log_likelihood(probs: np.ndarray, y_true: Sequence[int]) -> float:
    probs = np.clip(np.asarray(probs, dtype=float), 1e-12, 1.0)
    y_true = np.asarray(y_true, dtype=int)
    return float(-np.mean(np.log(probs[np.arange(len(y_true)), y_true]))) if len(y_true) else 0.0


def subgroup_metrics(y_true: Sequence[int], y_pred: Sequence[int], groups: Sequence[str], min_n: int = 1) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    groups = np.asarray([g or "(none)" for g in groups])
    out = {}
    for g in sorted(set(groups.tolist())):
        m = groups == g
        n = int(m.sum())
        if n < min_n:
            continue
        out[g] = {
            "n": n,
            "accuracy": float(accuracy_score(y_true[m], y_pred[m])),
            "macro_f1": float(f1_score(y_true[m], y_pred[m], labels=LABELS, average="macro", zero_division=0)),
            "true_distribution": {LABEL_NAMES[k]: int(v) for k, v in sorted(Counter(y_true[m].tolist()).items())},
            "small_sample_warning": n < 30,
        }
    return out
