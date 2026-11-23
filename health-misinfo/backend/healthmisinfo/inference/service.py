"""Inference over ACTIVE, registered checkpoints only.

If no active model exists for a language, or torch/transformers are not installed, or the
checkpoint is missing, ``ModelUnavailable`` is raised and the API reports an explicit
``model_not_trained`` / ``model_unavailable`` state. There is no fallback predictor.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from healthmisinfo.db.models import ModelVersion
from healthmisinfo.labels import LABEL_NAMES
from healthmisinfo.ml.calibration import softmax
from healthmisinfo.text.normalize import normalize_for_model

SLOTS = {
    "ar": {"base_model": "aubmindlab/bert-base-arabertv02", "display": {"en": "Arabic — AraBERT v02", "ar": "العربية — AraBERT v02"}},
    "en": {"base_model": "FacebookAI/xlm-roberta-base", "display": {"en": "English — XLM-RoBERTa base", "ar": "الإنجليزية — XLM-RoBERTa base"}},
}
MAX_EXPLAIN_WORDS = 48


class ModelUnavailable(RuntimeError):
    def __init__(self, state: str, message: str):
        super().__init__(message)
        self.state = state


@dataclass
class Prediction:
    model_version_id: int
    version_tag: str
    predicted_label: int
    raw_scores: list[float]
    calibrated_probabilities: list[float] | None
    confidence: float | None
    is_calibrated: bool
    abstained: bool
    abstention_threshold: float | None
    explanation: dict


def runtime_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401

        return True
    except Exception:
        return False


class _Loaded:
    def __init__(self, mv: ModelVersion):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(mv.checkpoint_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(mv.checkpoint_path)
        self.model.eval()
        self.torch = torch
        self.max_length = 128
        self.lock = threading.Lock()

    def logits(self, texts: list[str]) -> np.ndarray:
        with self.lock, self.torch.inference_mode():
            enc = self.tokenizer(texts, truncation=True, max_length=self.max_length, padding=True, return_tensors="pt")
            return self.model(**enc).logits.float().cpu().numpy()


class InferenceService:
    def __init__(self) -> None:
        self._cache: dict[int, _Loaded] = {}
        self._errors: dict[int, str] = {}
        self._lock = threading.Lock()

    def active_version(self, db: Session, language: str) -> ModelVersion | None:
        return db.scalar(select(ModelVersion).where(ModelVersion.language == language, ModelVersion.status == "active"))

    def slot_status(self, db: Session, language: str) -> dict:
        mv = self.active_version(db, language)
        registered = db.scalar(select(ModelVersion.id).where(ModelVersion.language == language).limit(1))
        if mv is None:
            state = "not_trained" if registered is None else "no_active_version"
        elif not Path(mv.checkpoint_path).is_dir():
            state = "checkpoint_missing"
        elif not runtime_available():
            state = "runtime_unavailable"
        elif mv.id in self._errors:
            state = "load_error"
        else:
            state = "ready"
        return {
            "language": language,
            "base_model": SLOTS[language]["base_model"],
            "display_name": SLOTS[language]["display"],
            "state": state,
            "active_version": None
            if mv is None
            else {
                "id": mv.id,
                "version_tag": mv.version_tag,
                "is_calibrated": mv.is_calibrated,
                "temperature": mv.temperature,
                "abstention_threshold": mv.abstention_threshold,
                "test_macro_f1": (mv.test_metrics or {}).get("macro_f1"),
                "test_accuracy": (mv.test_metrics or {}).get("accuracy"),
                "activated_at": mv.activated_at.isoformat() if mv.activated_at else None,
            },
            "load_error": self._errors.get(mv.id) if mv else None,
        }

    def _get(self, mv: ModelVersion) -> _Loaded:
        with self._lock:
            if mv.id not in self._cache:
                try:
                    self._cache[mv.id] = _Loaded(mv)
                    self._errors.pop(mv.id, None)
                except Exception as e:  # pragma: no cover - depends on checkpoint
                    self._errors[mv.id] = f"{type(e).__name__}: {e}"
                    raise ModelUnavailable("load_error", f"Failed to load checkpoint: {e}") from e
            return self._cache[mv.id]

    def predict(self, db: Session, text: str, language: str, explain: bool = True) -> Prediction:
        status = self.slot_status(db, language)
        if status["state"] != "ready":
            raise ModelUnavailable(status["state"], f"No usable model for language '{language}': {status['state']}")
        mv = self.active_version(db, language)
        loaded = self._get(mv)
        norm = normalize_for_model(text, language)
        logits = loaded.logits([norm])
        raw = softmax(logits, 1.0)[0]
        pred = int(raw.argmax())
        calibrated = None
        confidence = None
        abstained = False
        if mv.is_calibrated and mv.temperature:
            calibrated = softmax(logits, mv.temperature)[0]
            confidence = float(calibrated.max())
            if mv.abstention_threshold is not None:
                abstained = confidence < mv.abstention_threshold
        explanation = self._occlusion(loaded, norm, pred, float(raw[pred])) if explain else {}
        return Prediction(
            model_version_id=mv.id,
            version_tag=mv.version_tag,
            predicted_label=pred,
            raw_scores=[round(float(x), 6) for x in raw],
            calibrated_probabilities=None if calibrated is None else [round(float(x), 6) for x in calibrated],
            confidence=None if confidence is None else round(confidence, 6),
            is_calibrated=calibrated is not None,
            abstained=abstained,
            abstention_threshold=mv.abstention_threshold,
            explanation=explanation,
        )

    @staticmethod
    def _occlusion(loaded: _Loaded, text: str, pred: int, base: float) -> dict:
        """Leave-one-word-out attribution: drop in the predicted-class (raw) score when a word is
        removed. Approximate and model-centric – it explains the model, not the truth of the claim."""
        words = text.split()
        if len(words) < 2:
            return {"method": "leave_one_word_out", "tokens": [], "note": "text too short to attribute"}
        idxs = list(range(min(len(words), MAX_EXPLAIN_WORDS)))
        variants = [" ".join(w for j, w in enumerate(words) if j != i) for i in idxs]
        probs = softmax(loaded.logits(variants), 1.0)[:, pred]
        contrib = [(words[i], round(base - float(p), 5)) for i, p in zip(idxs, probs, strict=True)]
        top = sorted(contrib, key=lambda x: abs(x[1]), reverse=True)[:8]
        return {
            "method": "leave_one_word_out",
            "target_label": LABEL_NAMES[pred],
            "tokens": [{"token": w, "importance": s} for w, s in top],
            "words_considered": len(idxs),
            "note": "Positive importance = the word pushed the model toward its prediction. "
            "This explains model behaviour only; it is not evidence about the claim.",
        }


inference_service = InferenceService()
