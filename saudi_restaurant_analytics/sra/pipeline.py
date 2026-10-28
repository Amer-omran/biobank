"""تشغيل التحليل على تعليقات قاعدة البيانات وحفظ النتائج.

المحركات المتاحة لتحديد الشعور العام:
- lexicon: المحلل القائم على القاموس (افتراضي، يعمل دائمًا).
- sklearn: نموذج التعلم الآلي بعد تدريبه.
- transformers: نموذج Hugging Face (اختياري).

جوانب الرأي واستخراج الوجبات تُنفذ دائمًا بالمحلل القائم على القاموس، لأن النماذج
الأخرى هنا تصنف التعليق كاملًا فقط. لذلك يُكتب في إصدار النموذج اسم المحركين معًا.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from . import config, database
from .dishes import DishExtractor
from .sentiment import LexiconSentimentAnalyzer, SentimentResult

ENGINES = {
    "lexicon": "القاموس والقواعد (يعمل دون تدريب)",
    "sklearn": "نموذج Scikit-learn المدرَّب",
    "transformers": "نموذج Hugging Face (اختياري)",
}


def build_analyzer(conn) -> LexiconSentimentAnalyzer:
    """محلل القاموس مع قاموس الوجبات النشط المخزن في قاعدة البيانات."""
    return LexiconSentimentAnalyzer(DishExtractor.from_records(database.dish_records(conn)))


def load_engine(engine: str):
    if engine == "sklearn":
        from .ml_model import SklearnSentimentModel

        return SklearnSentimentModel.load()
    if engine == "transformers":
        from .transformer_model import TransformerSentimentModel

        return TransformerSentimentModel()
    return None


def combine(lexicon_result: SentimentResult, prediction, model, threshold: float) -> SentimentResult:
    """يدمج حكم النموذج العام مع جوانب الرأي المستخرجة بالقاموس."""
    aspect_labels = {a.sentiment for a in lexicon_result.aspects if a.has_opinion}
    mixed = lexicon_result.is_mixed or {"positive", "negative"} <= aspect_labels
    return replace(
        lexicon_result,
        label=prediction.label,
        confidence=prediction.confidence,
        is_mixed=mixed,
        is_uncertain=prediction.confidence < threshold,
        model_name=model.name,
        model_version=f"{model.version}+{config.LEXICON_MODEL_VERSION}",
    )


def engine_version(engine: str, model=None) -> str:
    if model is None:
        return config.LEXICON_MODEL_VERSION
    return f"{model.version}+{config.LEXICON_MODEL_VERSION}"


def analyze_reviews(conn, dataset_ids=None, engine: str = "lexicon", only_new: bool = False,
                    progress: Callable[[int, int], None] | None = None, model=None,
                    batch_size: int = 64) -> dict:
    """يحلل التعليقات ويحفظ النتائج. model يُمرر في الاختبارات لتجنب تحميل نموذج حقيقي."""
    analyzer = build_analyzer(conn)
    if engine != "lexicon" and model is None:
        model = load_engine(engine)
    version = engine_version(engine, model)
    reviews = database.fetch_reviews(conn, dataset_ids, only_unanalyzed_for=version if only_new else None)
    dish_ids = database.dish_id_map(conn)
    total = len(reviews)
    counts = {"analyzed": 0, "positive": 0, "negative": 0, "neutral": 0, "uncertain": 0, "mixed": 0}

    rows = reviews.to_dict("records")
    for start in range(0, total, batch_size):
        batch = rows[start:start + batch_size]
        lexicon_results = [analyzer.analyze(r["text"]) for r in batch]
        if model is not None:
            predictions = model.predict([r["clean_text"] for r in batch])
            results = [combine(lr, p, model, config.CONFIDENCE_THRESHOLD)
                       for lr, p in zip(lexicon_results, predictions)]
        else:
            results = lexicon_results
        for review, result in zip(batch, results):
            database.save_analysis(conn, int(review["id"]), result, dish_ids, commit=False)
            counts["analyzed"] += 1
            counts[result.label] += 1
            counts["uncertain"] += int(result.is_uncertain)
            counts["mixed"] += int(result.is_mixed)
        conn.commit()
        if progress:
            progress(min(start + batch_size, total), total)
    counts["model_version"] = version
    return counts
