"""اختبارات تقييم AQTE على عينة بالبنية نفسها الظاهرة في عارض بيانات Hugging Face."""

import json

import pandas as pd
import pytest

from sra import aqte
from sra.aqte import CONFLICT, evaluate, gold_aspects, gold_overall, load_aqte, to_platform_csv

RECORDS = [
    {"place_id": "P1", "review_id": "R1", "rate": "5",
     "review_text": "حلو الاكل و حلو خبز التشباتي لذيذ كان بس ماعطوني الا بخمسة وانا كان ودي ب ٢٠",
     "opinions": [{"aspect": "الطعام", "avg_sentiment": 1, "quotes": "حلو الاكل"},
                  {"aspect": "الطعام", "avg_sentiment": 1, "quotes": "حلو خبز التشباتي لذيذ كان"},
                  {"aspect": "السعر", "avg_sentiment": 0, "quotes": "ماعطوني الا بخمسة وانا كان ودي ب ٢٠"}]},
    {"place_id": "P1", "review_id": "R2", "rate": "1",
     "review_text": "الخدمة سيئة جدا والاسعار غالية",
     "opinions": [{"aspect": "الخدمة", "avg_sentiment": -1, "quotes": "الخدمة سيئة جدا"},
                  {"aspect": "السعر", "avg_sentiment": -1, "quotes": "الاسعار غالية"}]},
    {"place_id": "P2", "review_id": "R3", "rate": "4",
     "review_text": "ممتاز جدا",
     "opinions": [{"aspect": "المطعم", "avg_sentiment": 1, "quotes": "ممتاز جدا"}]},
]


def test_load_json_list_jsonl_wrapped_and_parquet(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(RECORDS, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "b.json").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in RECORDS), encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps({"data": RECORDS}, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(RECORDS).to_parquet(tmp_path / "d.parquet")
    for name in ("a.json", "b.json", "c.json", "d.parquet"):
        df = load_aqte(tmp_path / name)
        assert len(df) == 3 and df.iloc[0]["opinions"][0]["aspect"] == "الطعام"


def test_missing_columns_error(tmp_path):
    (tmp_path / "x.json").write_text('[{"text": "a"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="review_text"):
        load_aqte(tmp_path / "x.json")


def test_gold_aspects_mapping_and_conflict():
    assert gold_aspects(RECORDS[0]["opinions"]) == {"food_quality": "positive", "price": "neutral"}
    assert gold_aspects(RECORDS[2]["opinions"]) == {}  # «المطعم» فئة عامة
    mixed = [{"aspect": "الخدمة", "avg_sentiment": 1}, {"aspect": "طاقم العمل", "avg_sentiment": -0.5}]
    assert gold_aspects(mixed) == {"service": CONFLICT}


def test_gold_overall():
    assert gold_overall(RECORDS[0]["opinions"]) == "positive"
    assert gold_overall(RECORDS[1]["opinions"]) == "negative"
    assert gold_overall([]) is None


def test_every_aqte_category_is_mapped_explicitly():
    categories = ["الطعام", "المطعم", "الخدمة", "السعر", "طاقم العمل", "النظافة", "المشروبات", "الديكور",
                  "التعامل", "التجربة", "الجودة", "الأجواء", "الكمية", "السرعة", "الطلب عن بعد", "الإدارة",
                  "التنوع", "مواقف السيارات", "التغليف", "المقهى", "التنظيم", "الرائحة", "التوفر", "الترفيه",
                  "الأمان", "المخبز", "الكافتيريا", "الفندق", "المتجر"]
    assert len(categories) == 29 and set(categories) == set(aqte.ASPECT_MAP)


def test_platform_csv():
    table = to_platform_csv(pd.DataFrame(RECORDS).assign(opinions=lambda d: d["opinions"]))
    assert list(table.columns) == ["review_id", "review_text", "place_id", "rate", "gold_label", "rating_label"]
    assert table["gold_label"].tolist() == ["positive", "negative", "positive"]
    assert table["rating_label"].tolist() == ["positive", "negative", "positive"]


def test_evaluate_end_to_end(analyzer, tmp_path):
    (tmp_path / "t.json").write_text(json.dumps(RECORDS, ensure_ascii=False), encoding="utf-8")
    report = evaluate(load_aqte(tmp_path / "t.json"), analyzer)
    assert report["n_reviews"] == 3
    assert report["overall_vs_opinions"]["lexicon"]["n"] == 3
    aspects = report["aspects"].set_index("aspect")
    assert aspects.loc["service", "recall"] == 1.0 and aspects.loc["service", "polarity_accuracy"] == 1.0
    assert aspects.loc["food_quality", "gold_mentions"] == 1
    assert 0 <= report["aspects_micro"]["f1"] <= 1
    assert aqte.report_to_excel(report)[:2] == b"PK"


def test_majority_baseline():
    base = aqte.majority_baseline(["positive"] * 7 + ["negative"] * 3)
    assert base["label"] == "positive" and base["accuracy"] == 0.7


def test_error_analysis(analyzer):
    df = pd.DataFrame([
        {"review_text": "العمالة محترفين والطاولات نظيفة",
         "opinions": [{"aspect": "طاقم العمل", "avg_sentiment": 1, "quotes": "العمالة محترفين"},
                      {"aspect": "النظافة", "avg_sentiment": 1, "quotes": "الطاولات نظيفة"}]},
        {"review_text": "الخدمة ممتازة", "opinions": [{"aspect": "الخدمة", "avg_sentiment": -1, "quotes": "الخدمة ممتازة"}]},
    ])
    errors = aqte.error_analysis(df, analyzer)
    assert set(errors) == {"missed_aspects", "polarity_errors", "overall_errors", "suggested_terms"}
    assert "service" in set(errors["missed_aspects"]["aspect"])
    # «العمالة» معروفة (تطابق «عمال»)؛ الناقص هو كلمة الرأي «محترفين»
    assert "محترفين" in set(errors["suggested_terms"]["term"])
    assert len(errors["polarity_errors"]) == 1
    assert aqte.errors_to_excel(errors)[:2] == b"PK"


UNIT_SCALE = [  # المقياس الظاهر في AQTE: 0 سلبي، 0.5 محايد، 1 إيجابي
    {"review_text": "اكلهم سيء", "rate": "1",
     "opinions": [{"aspect": "الطعام", "avg_sentiment": 0, "quotes": "اكلهم سيء"}]},
    {"review_text": "السعر عادي", "rate": "3",
     "opinions": [{"aspect": "السعر", "avg_sentiment": 0.5, "quotes": "السعر عادي"}]},
    {"review_text": "حلو الاكل", "rate": "5",
     "opinions": [{"aspect": "الطعام", "avg_sentiment": 1, "quotes": "حلو الاكل"}]},
]


def test_unit_scale_detected_and_zero_is_negative(tmp_path):
    (tmp_path / "u.json").write_text(json.dumps(UNIT_SCALE, ensure_ascii=False), encoding="utf-8")
    df = load_aqte(tmp_path / "u.json")
    assert df.attrs["sentiment_scale"] == "unit"
    assert df.attrs["sentiment_values"] == {0.0: 1, 0.5: 1, 1.0: 1}
    assert [gold_overall(o) for o in df["opinions"]] == ["negative", "neutral", "positive"]
    assert gold_aspects(df.iloc[0]["opinions"]) == {"food_quality": "negative"}
    assert gold_aspects(df.iloc[1]["opinions"]) == {"price": "neutral"}


def test_signed_scale_still_supported(tmp_path):
    (tmp_path / "s.json").write_text(json.dumps(RECORDS, ensure_ascii=False), encoding="utf-8")
    df = load_aqte(tmp_path / "s.json")
    assert df.attrs["sentiment_scale"] == "signed"
    assert gold_overall(df.iloc[1]["opinions"]) == "negative"


def test_unexpected_scale_rejected(tmp_path):
    bad = [{"review_text": "x", "opinions": [{"aspect": "الطعام", "avg_sentiment": 4}]}]
    (tmp_path / "b.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="مقياس"):
        load_aqte(tmp_path / "b.json")
