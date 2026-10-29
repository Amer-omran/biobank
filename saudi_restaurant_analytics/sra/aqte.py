"""تقييم المنصة على مجموعة بيانات AQTE (مراجعات مطاعم سعودية من Google Maps).

بنية السجل كما تظهر في عارض البيانات على Hugging Face:
    place_id, review_id, rate, review_text,
    opinions = [{"aspect": "الطعام", "avg_sentiment": 1, "quotes": "حلو الاكل"}, ...]

ملاحظات منهجية:
- AQTE فيها 29 فئة جوانب، والمنصة 7 جوانب. ربط الفئات في ASPECT_MAP قرار من الباحث
  يُذكر في التقرير ويمكن تعديله. الفئات العامة (المطعم، التجربة...) لا تُربط بجانب.
- avg_sentiment رقم بين 0 و1 في AQTE: صفر سلبي، 0.5 محايد، 1 إيجابي (القيم المرئية في عارض
  البيانات 0 و0.5 و1، ومثال «ماعطوني الا بخمسة...» شكوى قيمتها 0). يكتشف load_aqte المقياس تلقائيًا:
  إن وُجدت قيم سالبة فالمقياس من -1 إلى 1، وإلا فمن 0 إلى 1. كل قيمة تُحوَّل إلى مقياس موحد
  (signed_sentiment من -1 إلى 1) ويُحكم بإشارتها.
- الشعور العام «المرجعي» للمراجعة يُشتق بطريقتين ونقيس الاثنتين:
  1) من آراء AQTE الموسومة (مجموع avg_sentiment) — أقرب إلى نص المراجعة.
  2) من التقييم الرقمي rate (1-2 سلبي، 3 محايد، 4-5 إيجابي) — وسم تقريبي.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from . import config
from .importer import ratings_to_labels

# ربط فئات AQTE بجوانب المنصة (None = فئة عامة لا تقابل جانبًا محددًا)
ASPECT_MAP = {
    "الطعام": "food_quality", "المشروبات": "food_quality", "الجودة": "food_quality",
    "السعر": "price",
    "الكمية": "quantity",
    "الخدمة": "service", "طاقم العمل": "service", "التعامل": "service", "السرعة": "service",
    "الإدارة": "service", "التنظيم": "service",
    "الطلب عن بعد": "delivery", "التغليف": "delivery",
    "النظافة": "cleanliness", "الرائحة": "cleanliness",
    "الديكور": "ambiance", "الأجواء": "ambiance", "مواقف السيارات": "ambiance", "الترفيه": "ambiance",
    "المطعم": None, "التجربة": None, "التنوع": None, "التوفر": None, "الأمان": None,
    "المقهى": None, "المخبز": None, "الكافتيريا": None, "الفندق": None, "المتجر": None,
}
CONFLICT = "conflict"  # الجانب نفسه ورد بآراء إيجابية وسلبية في المراجعة نفسها


# ================================================================ القراءة
def _parse_opinions(value) -> list[dict]:
    if isinstance(value, str):
        value = json.loads(value) if value.strip() else []
    if isinstance(value, np.ndarray):
        value = value.tolist()
    return [dict(v) for v in (value or [])]


def load_aqte(source) -> pd.DataFrame:
    """يقرأ ملف AQTE بصيغة json (قائمة أو سطر لكل سجل) أو jsonl أو parquet أو csv."""
    path = Path(source)
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        df = pd.read_parquet(path)
    elif suffix == ".csv":
        df = pd.read_csv(path, dtype=str)
    else:
        text = path.read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
        if isinstance(data, dict):
            # بعض الملفات تغلف السجلات داخل مفتاح واحد مثل {"data": [...]}
            lists = [v for v in data.values() if isinstance(v, list)]
            if len(lists) != 1:
                raise ValueError("بنية JSON غير متوقعة: لم أجد قائمة سجلات واحدة.")
            data = lists[0]
        df = pd.DataFrame(data)
    required = {"review_text", "opinions"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"أعمدة AQTE المتوقعة غير موجودة: {sorted(missing)}. الأعمدة الموجودة: {list(df.columns)}")
    df = df.copy()
    df["opinions"] = df["opinions"].map(_parse_opinions)
    df["review_text"] = df["review_text"].fillna("").astype(str)
    df = df[df["review_text"].str.strip() != ""].reset_index(drop=True)
    scale, counts = detect_scale(df["opinions"])
    for opinions in df["opinions"]:
        for op in opinions:
            if op.get("avg_sentiment") is not None:
                value = float(op["avg_sentiment"])
                op["signed_sentiment"] = 2 * value - 1 if scale == "unit" else value
    df.attrs["sentiment_scale"] = scale
    df.attrs["sentiment_values"] = counts
    return df


def detect_scale(opinion_lists) -> tuple[str, dict]:
    """يحدد مقياس avg_sentiment: unit (0..1، و0.5 محايد) أو signed (-1..1، والصفر محايد)."""
    values = [float(op["avg_sentiment"]) for ops in opinion_lists for op in ops
              if op.get("avg_sentiment") is not None]
    counts = dict(sorted(pd.Series(values, dtype=float).round(3).value_counts().to_dict().items()))
    if not values:
        return "signed", counts
    if min(values) < 0:
        if max(values) > 1:
            raise ValueError(f"مقياس avg_sentiment غير متوقع: من {min(values)} إلى {max(values)}")
        return "signed", counts
    if max(values) > 1:
        raise ValueError(f"مقياس avg_sentiment غير متوقع: من {min(values)} إلى {max(values)}")
    return "unit", counts


def _signed(op: dict) -> float | None:
    """قيمة الشعور على المقياس الموحد. السجلات غير المقروءة بـ load_aqte تُعامل كمقياس -1..1."""
    value = op.get("signed_sentiment", op.get("avg_sentiment"))
    return None if value is None else float(value)


# ======================================================== الوسوم المرجعية
def polarity(value) -> str:
    number = float(value)
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "neutral"


def gold_aspects(opinions: list[dict], aspect_map: dict = ASPECT_MAP) -> dict[str, str]:
    """جوانب المنصة المذكورة في المراجعة وشعور كل منها حسب وسوم AQTE."""
    seen: dict[str, set[str]] = {}
    for op in opinions:
        aspect = aspect_map.get(str(op.get("aspect", "")).strip())
        value = _signed(op)
        if aspect is None or value is None:
            continue
        seen.setdefault(aspect, set()).add(polarity(value))
    result = {}
    for aspect, labels in seen.items():
        polar = labels - {"neutral"}
        if len(polar) > 1:
            result[aspect] = CONFLICT
        elif polar:
            result[aspect] = polar.pop()
        else:
            result[aspect] = "neutral"
    return result


def gold_overall(opinions: list[dict]) -> str | None:
    """الشعور العام من مجموع آراء AQTE (كل الفئات، بما فيها العامة)."""
    values = [v for v in (_signed(op) for op in opinions) if v is not None]
    if not values:
        return None
    return polarity(sum(values))


def to_platform_csv(df: pd.DataFrame) -> pd.DataFrame:
    """جدول جاهز للاستيراد في المنصة مع عمودي وسم مرجعيين."""
    out = pd.DataFrame({
        "review_text": df["review_text"],
        "place_id": df.get("place_id"),
        "rate": df.get("rate"),
        "gold_label": df["opinions"].map(gold_overall),
    })
    if "rate" in df:
        out["rating_label"] = ratings_to_labels(pd.to_numeric(df["rate"], errors="coerce"))
    if "review_id" in df:
        out.insert(0, "review_id", df["review_id"])
    return out


# ================================================================ التقييم
def _classification(gold: list[str], predicted: list[str]) -> dict:
    labels = [s for s in config.SENTIMENTS if s in set(gold) | set(predicted)]
    return {
        "n": len(gold),
        "accuracy": round(float(accuracy_score(gold, predicted)), 4),
        "macro_f1": round(float(f1_score(gold, predicted, labels=labels, average="macro", zero_division=0)), 4),
        "report": classification_report(gold, predicted, labels=labels, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(gold, predicted, labels=labels).tolist(),
        "labels": labels,
    }


def predicted_aspects(result) -> dict[str, str]:
    """جوانب المنصة التي ورد فيها رأي، مع جمع الدرجات إن تكرر الجانب في المراجعة."""
    totals: dict[str, list[float]] = {}
    for a in result.aspects:
        if a.has_opinion:
            totals.setdefault(a.aspect, []).append(a.score)
    out = {}
    for aspect, scores in totals.items():
        total = sum(scores)
        out[aspect] = "positive" if total > 0.2 else "negative" if total < -0.2 else "neutral"
    return out


def evaluate(df: pd.DataFrame, analyzer, sklearn_model=None) -> dict:
    """يقيّم الشعور العام واكتشاف الجوانب وشعورها على مراجعات AQTE."""
    results = [analyzer.analyze(t) for t in df["review_text"]]
    lexicon_overall = [r.label for r in results]
    report: dict = {"n_reviews": len(df)}

    gold_text = df["opinions"].map(gold_overall)
    mask = gold_text.notna().tolist()
    gold_list = [g for g, m in zip(gold_text, mask) if m]
    report["overall_vs_opinions"] = {
        "lexicon": _classification(gold_list, [p for p, m in zip(lexicon_overall, mask) if m]),
    }
    if "rate" in df:
        rating = ratings_to_labels(pd.to_numeric(df["rate"], errors="coerce"))
        rmask = rating.notna().tolist()
        report["overall_vs_rating"] = {
            "lexicon": _classification([g for g, m in zip(rating, rmask) if m],
                                       [p for p, m in zip(lexicon_overall, rmask) if m]),
        }
    if sklearn_model is not None:
        sk = [p.label for p in sklearn_model.predict(df["review_text"].tolist())]
        report["overall_vs_opinions"]["sklearn"] = _classification(gold_list, [p for p, m in zip(sk, mask) if m])
        if "rate" in df:
            report["overall_vs_rating"]["sklearn"] = _classification(
                [g for g, m in zip(rating, rmask) if m], [p for p, m in zip(sk, rmask) if m])

    # اكتشاف الجوانب: هل ذكرت المنصة الجانب نفسه الذي وسمته AQTE؟
    counts = {a: {"tp": 0, "fp": 0, "fn": 0, "polarity_correct": 0, "polarity_total": 0}
              for a in config.ASPECTS}
    for opinions, result in zip(df["opinions"], results):
        gold = gold_aspects(opinions)
        pred = predicted_aspects(result)
        for aspect in config.ASPECTS:
            in_gold, in_pred = aspect in gold, aspect in pred
            if in_gold and in_pred:
                counts[aspect]["tp"] += 1
                if gold[aspect] != CONFLICT:
                    counts[aspect]["polarity_total"] += 1
                    counts[aspect]["polarity_correct"] += int(gold[aspect] == pred[aspect])
            elif in_pred:
                counts[aspect]["fp"] += 1
            elif in_gold:
                counts[aspect]["fn"] += 1

    rows = []
    for aspect, c in counts.items():
        precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
        recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append({
            "aspect": aspect, "aspect_ar": config.ASPECT_AR[aspect],
            "gold_mentions": c["tp"] + c["fn"], "predicted_mentions": c["tp"] + c["fp"],
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "polarity_accuracy": round(c["polarity_correct"] / c["polarity_total"], 4) if c["polarity_total"] else None,
            "polarity_n": c["polarity_total"],
        })
    table = pd.DataFrame(rows)
    report["aspects"] = table
    tp = sum(c["tp"] for c in counts.values())
    fp = sum(c["fp"] for c in counts.values())
    fn = sum(c["fn"] for c in counts.values())
    micro_p = tp / (tp + fp) if tp + fp else 0.0
    micro_r = tp / (tp + fn) if tp + fn else 0.0
    report["aspects_micro"] = {
        "precision": round(micro_p, 4), "recall": round(micro_r, 4),
        "f1": round(2 * micro_p * micro_r / (micro_p + micro_r), 4) if micro_p + micro_r else 0.0,
        "polarity_accuracy": round(sum(c["polarity_correct"] for c in counts.values())
                                   / max(1, sum(c["polarity_total"] for c in counts.values())), 4),
    }
    report["predictions"] = pd.DataFrame({
        "review_text": df["review_text"],
        "gold_from_opinions": gold_text,
        "lexicon": lexicon_overall,
        "gold_aspects": df["opinions"].map(lambda o: json.dumps(gold_aspects(o), ensure_ascii=False)),
        "predicted_aspects": [json.dumps(predicted_aspects(r), ensure_ascii=False) for r in results],
        "cues": ["، ".join(r.cues) for r in results],
    })
    return report


def report_to_excel(report: dict) -> bytes:
    """يحفظ نتائج التقييم في ملف Excel بأوراق من اليمين لليسار."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_rows = []
        for target, models in (("آراء AQTE", report.get("overall_vs_opinions", {})),
                               ("التقييم الرقمي", report.get("overall_vs_rating", {}))):
            for model, m in models.items():
                summary_rows.append({"المرجع": target, "النموذج": model, "عدد المراجعات": m["n"],
                                     "Accuracy": m["accuracy"], "Macro-F1": m["macro_f1"]})
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="الشعور العام", index=False)
        report["aspects"].to_excel(writer, sheet_name="الجوانب", index=False)
        pd.DataFrame([report["aspects_micro"]]).to_excel(writer, sheet_name="الجوانب - إجمالي", index=False)
        report["predictions"].to_excel(writer, sheet_name="التنبؤات", index=False)
        for ws in writer.book.worksheets:
            ws.sheet_view.rightToLeft = True
    return buffer.getvalue()


# =========================================================== تحليل الأخطاء
def majority_baseline(gold: list[str]) -> dict:
    """خط الأساس: نموذج «غبي» يتنبأ دائمًا بالصنف الأكثر شيوعًا. أي نموذج مفيد يجب أن يتفوق عليه."""
    if not gold:
        return {"label": None, "accuracy": 0.0, "macro_f1": 0.0}
    label = max(set(gold), key=gold.count)
    return _classification(gold, [label] * len(gold)) | {"label": label}


def gold_aspect_quotes(opinions: list[dict], aspect_map: dict = ASPECT_MAP) -> dict[str, list[dict]]:
    """عبارات AQTE لكل جانب من جوانب المنصة (لمعرفة ما فات المحلل)."""
    out: dict[str, list[dict]] = {}
    for op in opinions:
        aspect = aspect_map.get(str(op.get("aspect", "")).strip())
        if aspect is not None:
            out.setdefault(aspect, []).append(op)
    return out


def _known_terms() -> set[str]:
    from .lexicon import get_lexicon

    lex = get_lexicon()
    return set(lex.opinions) | set(lex.aspect_single) | set(lex.conditional) | lex.negators | \
        set(lex.intensifiers) | set(lex.diminishers)


def error_analysis(df: pd.DataFrame, analyzer, top_terms: int = 30) -> dict[str, pd.DataFrame]:
    """يجمع أخطاء المحلل في جداول، ويقترح كلمات متكررة في العبارات الفائتة غير موجودة في القاموس.

    استخدمها على ملف التدريب فقط، ثم أضف المقترحات المناسبة إلى sra/lexicon.py بعد مراجعتها بنفسك.
    """
    from collections import Counter

    from .analytics import STOPWORDS
    from .text_processing import normalize_arabic, token_variants, tokenize

    known = _known_terms()
    missed_rows, polarity_rows, overall_rows = [], [], []
    missed_counter: dict[str, Counter] = {a: Counter() for a in config.ASPECTS}
    for text, opinions in zip(df["review_text"], df["opinions"]):
        result = analyzer.analyze(text)
        pred = predicted_aspects(result)
        gold = gold_aspects(opinions)
        quotes = gold_aspect_quotes(opinions)
        gold_label = gold_overall(opinions)
        if gold_label and gold_label != result.label:
            overall_rows.append({"review_text": text, "gold": gold_label, "predicted": result.label,
                                 "confidence": result.confidence, "cues": "، ".join(result.cues)})
        for aspect, label in gold.items():
            if aspect not in pred:
                for op in quotes.get(aspect, []):
                    quote = str(op.get("quotes", ""))
                    missed_rows.append({"aspect": aspect, "aqte_aspect": op.get("aspect"), "quote": quote,
                                        "avg_sentiment": op.get("avg_sentiment"), "review_text": text})
                    for tok in tokenize(quote):
                        norm = normalize_arabic(tok)
                        if len(norm) > 2 and norm not in STOPWORDS and not any(v in known for v in token_variants(norm)):
                            missed_counter[aspect][norm] += 1
            elif label != CONFLICT and pred[aspect] != label:
                polarity_rows.append({
                    "aspect": aspect, "gold": label, "predicted": pred[aspect],
                    "quotes": " | ".join(str(op.get("quotes", "")) for op in quotes.get(aspect, [])),
                    "cues": "، ".join(result.cues), "review_text": text,
                })
    suggestions = [{"aspect": a, "term": term, "count": n}
                   for a, counter in missed_counter.items() for term, n in counter.most_common(top_terms)]
    return {
        "missed_aspects": pd.DataFrame(missed_rows),
        "polarity_errors": pd.DataFrame(polarity_rows),
        "overall_errors": pd.DataFrame(overall_rows),
        "suggested_terms": pd.DataFrame(suggestions, columns=["aspect", "term", "count"]),
    }


def errors_to_excel(errors: dict[str, pd.DataFrame]) -> bytes:
    names = {"suggested_terms": "كلمات مقترحة", "missed_aspects": "جوانب فائتة",
             "polarity_errors": "أخطاء شعور الجوانب", "overall_errors": "أخطاء الشعور العام"}
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for key, sheet in names.items():
            frame = errors[key]
            (frame if not frame.empty else pd.DataFrame({"ملاحظة": ["لا توجد أخطاء"]})).to_excel(
                writer, sheet_name=sheet, index=False)
        for ws in writer.book.worksheets:
            ws.sheet_view.rightToLeft = True
    return buffer.getvalue()
