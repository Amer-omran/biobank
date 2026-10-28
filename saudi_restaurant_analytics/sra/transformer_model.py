"""تجربة نموذج لغوي عربي من Hugging Face (اختياري).

هذا المكون اختياري تمامًا: إذا لم تُثبَّت مكتبة transformers أو لم يتوفر الإنترنت لتنزيل
النموذج، تبقى بقية المنصة تعمل بالمحلل القائم على القاموس.

لا نثق بأسماء الوسوم دون تحقق: نقرأ id2label من إعدادات النموذج، ونقبل النموذج فقط
إذا كانت وسومه قابلة للربط بوضوح بإيجابي/سلبي/محايد. نموذج وسومه LABEL_0 وLABEL_1
دون توثيق يُرفض، لأن ربطها بالتخمين قد يعكس النتائج.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config

LABEL_ALIASES = {
    "positive": "positive", "pos": "positive", "إيجابي": "positive",
    "negative": "negative", "neg": "negative", "سلبي": "negative",
    "neutral": "neutral", "neu": "neutral", "محايد": "neutral",
}


class TransformerUnavailable(RuntimeError):
    """تُرفع عندما لا يمكن تشغيل النموذج (مكتبة غير مثبتة، أو نموذج غير متاح، أو وسوم غير واضحة)."""


@dataclass
class TransformerPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


def map_model_labels(id2label: dict) -> dict[str, str]:
    """يربط وسوم النموذج بوسوم المنصة، أو يرفع خطأ إن كانت غير مفهومة."""
    mapping = {}
    for raw in id2label.values():
        key = str(raw).strip().lower()
        if key not in LABEL_ALIASES:
            raise TransformerUnavailable(
                f"وسم النموذج «{raw}» غير مفهوم. راجع بطاقة النموذج قبل استخدامه؛ "
                "لن نربط الوسوم بالتخمين."
            )
        mapping[str(raw)] = LABEL_ALIASES[key]
    return mapping


class TransformerSentimentModel:
    name = "transformers"

    def __init__(self, model_name: str = config.DEFAULT_TRANSFORMER_MODEL, pipeline=None,
                 id2label: dict | None = None, confidence_threshold: float = config.CONFIDENCE_THRESHOLD):
        """pipeline وid2label يُمرران في الاختبارات فقط؛ في الاستخدام العادي يُحمّل النموذج تلقائيًا."""
        self.model_name = model_name
        self.version = f"hf-{model_name}"
        self.confidence_threshold = confidence_threshold
        if pipeline is None:
            pipeline, id2label = self._load(model_name)
        self.pipeline = pipeline
        self.label_map = map_model_labels(id2label or {})

    @staticmethod
    def _load(model_name: str):
        try:
            from transformers import pipeline as hf_pipeline
        except ImportError as exc:
            raise TransformerUnavailable(
                "مكتبة transformers غير مثبتة. ثبّتها بالأمر: pip install -r requirements-optional.txt"
            ) from exc
        try:
            clf = hf_pipeline("text-classification", model=model_name, top_k=None, truncation=True)
        except Exception as exc:  # noqa: BLE001
            raise TransformerUnavailable(f"تعذر تحميل النموذج {model_name}: {exc}") from exc
        return clf, dict(clf.model.config.id2label)

    def predict(self, texts, batch_size: int = 16) -> list[TransformerPrediction]:
        texts = [str(t) for t in texts]
        if not texts:
            return []
        raw = self.pipeline(texts, batch_size=batch_size)
        results = []
        for scores in raw:
            if isinstance(scores, dict):  # بعض الإصدارات تُرجع أفضل وسم فقط
                scores = [scores]
            probabilities: dict[str, float] = {}
            for item in scores:
                label = self.label_map.get(str(item["label"]))
                if label is None:
                    raise TransformerUnavailable(f"أعاد النموذج وسمًا غير متوقع: {item['label']}")
                probabilities[label] = probabilities.get(label, 0.0) + float(item["score"])
            best = max(probabilities, key=probabilities.get)
            results.append(TransformerPrediction(best, round(probabilities[best], 4),
                                                 {k: round(v, 4) for k, v in probabilities.items()}))
        return results


def transformers_installed() -> bool:
    try:
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True
