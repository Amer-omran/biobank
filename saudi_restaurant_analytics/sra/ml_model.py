"""نموذج تعلم آلي أساسي لتصنيف المشاعر باستخدام Scikit-learn.

النموذج: TF-IDF على مقاطع الحروف (char n-grams) والكلمات + انحدار لوجستي.
مقاطع الحروف مناسبة للعامية لأنها تتحمل اختلاف الإملاء (حلو/حلوه/حلوو).

يحتاج النموذج إلى بيانات موسومة: إما عمود وسم في الملف المستورد، أو وسوم تقريبية
مشتقة من التقييم الرقمي. نتائج التقييم على البيانات التجريبية الاصطناعية لا تعبّر
عن أداء حقيقي، لأن تلك البيانات مولدة من قوالب محدودة.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

from . import config
from .text_processing import clean_text, normalize_arabic

MIN_SAMPLES_PER_CLASS = 5


def _preprocess(text: str) -> str:
    return normalize_arabic(clean_text(text))


@dataclass
class SklearnPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


def build_pipeline() -> Pipeline:
    features = FeatureUnion([
        ("chars", TfidfVectorizer(preprocessor=_preprocess, analyzer="char_wb", ngram_range=(2, 5),
                                  min_df=1, sublinear_tf=True)),
        # token_pattern يحتفظ بالكلمات القصيرة مثل «لا» و«ما» و«مو» (مهمة للنفي)
        ("words", TfidfVectorizer(preprocessor=_preprocess, analyzer="word", ngram_range=(1, 2),
                                  token_pattern=r"(?u)\b\w+\b", min_df=1, sublinear_tf=True)),
    ])
    return Pipeline([
        ("features", features),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])


def _check_labels(labels) -> None:
    values, counts = np.unique(np.asarray(labels), return_counts=True)
    unknown = set(values) - set(config.SENTIMENTS)
    if unknown:
        raise ValueError(f"وسوم غير مدعومة: {sorted(unknown)}. المسموح: positive/negative/neutral")
    if len(values) < 2:
        raise ValueError("يحتاج التدريب إلى صنفين مختلفين على الأقل (مثل إيجابي وسلبي).")
    small = {v: int(c) for v, c in zip(values, counts) if c < MIN_SAMPLES_PER_CLASS}
    if small:
        raise ValueError(f"عدد الأمثلة قليل جدًا لبعض الأصناف (الحد الأدنى {MIN_SAMPLES_PER_CLASS}): {small}")


def train_and_evaluate(texts, labels, test_size: float = 0.2, random_state: int = 42,
                       data_is_synthetic: bool = False, label_source: str = "labels") -> tuple[Pipeline, dict]:
    """يقسم البيانات إلى تدريب واختبار، ويدرب، ويقيس الأداء على بيانات الاختبار فقط.

    بعد القياس يُعاد تدريب النموذج على كامل البيانات للاستخدام الفعلي.
    """
    texts = [str(t) for t in texts]
    labels = [str(lbl) for lbl in labels]
    _check_labels(labels)
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_size, random_state=random_state, stratify=labels
    )
    model = build_pipeline().fit(x_train, y_train)
    predicted = model.predict(x_test)
    classes = sorted(set(labels))
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, predicted)), 4),
        "macro_f1": round(float(f1_score(y_test, predicted, average="macro")), 4),
        "report": classification_report(y_test, predicted, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, predicted, labels=classes).tolist(),
        "classes": classes,
        "n_train": len(x_train),
        "n_test": len(x_test),
    }
    final_model = build_pipeline().fit(texts, labels)
    metadata = {
        "model_name": "sklearn",
        "model_version": "sklearn-tfidf-lr-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_samples": len(texts),
        "label_distribution": {c: labels.count(c) for c in classes},
        "label_source": label_source,
        "data_is_synthetic": bool(data_is_synthetic),
        "metrics": metrics,
    }
    return final_model, metadata


def save_model(model: Pipeline, metadata: dict, model_path: Path = config.SKLEARN_MODEL_PATH,
               meta_path: Path = config.SKLEARN_META_PATH) -> None:
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    Path(meta_path).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def load_metadata(meta_path: Path = config.SKLEARN_META_PATH) -> dict | None:
    path = Path(meta_path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class SklearnSentimentModel:
    """غلاف للنموذج المدرَّب يُرجع الوسم ودرجة الثقة (أعلى احتمال)."""

    name = "sklearn"

    def __init__(self, model: Pipeline, metadata: dict,
                 confidence_threshold: float = config.CONFIDENCE_THRESHOLD):
        self.model = model
        self.metadata = metadata
        self.version = metadata["model_version"]
        self.confidence_threshold = confidence_threshold

    @classmethod
    def load(cls, model_path: Path = config.SKLEARN_MODEL_PATH,
             meta_path: Path = config.SKLEARN_META_PATH) -> "SklearnSentimentModel":
        if not Path(model_path).exists():
            raise FileNotFoundError("لا يوجد نموذج مدرَّب بعد. درّب النموذج من صفحة «النموذج والتقييم».")
        metadata = load_metadata(meta_path) or {"model_version": "sklearn-unknown"}
        return cls(joblib.load(model_path), metadata)

    def predict(self, texts) -> list[SklearnPrediction]:
        texts = [str(t) for t in texts]
        if not texts:
            return []
        probabilities = self.model.predict_proba(texts)
        classes = list(self.model.classes_)
        results = []
        for row in probabilities:
            best = int(np.argmax(row))
            results.append(SklearnPrediction(
                label=classes[best],
                confidence=round(float(row[best]), 4),
                probabilities={c: round(float(p), 4) for c, p in zip(classes, row)},
            ))
        return results
