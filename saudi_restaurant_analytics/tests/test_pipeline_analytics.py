import pandas as pd
import pytest

from sra import analytics, config, database, demo_data, pipeline
from sra.analytics import Filters


@pytest.fixture
def loaded(conn):
    result = demo_data.load_demo_into_db(conn)
    counts = pipeline.analyze_reviews(conn)
    return conn, result, counts


def test_demo_data_is_marked_synthetic(loaded):
    conn, result, _ = loaded
    ds = database.list_datasets(conn)
    assert ds.iloc[0]["is_synthetic"] == 1
    assert result["inserted"] > 600 and result["duplicates_in_file"] == 1
    assert all("(تجريبي)" in n for n in analytics.restaurants_list(conn))


def test_analysis_counts_and_rerun_only_new(loaded):
    conn, result, counts = loaded
    assert counts["analyzed"] == result["inserted"]
    assert counts["positive"] + counts["negative"] + counts["neutral"] == counts["analyzed"]
    again = pipeline.analyze_reviews(conn, only_new=True)
    assert again["analyzed"] == 0
    assert database.integrity_report(conn)["foreign_key_violations"] == 0


def test_distribution_sums_to_total(loaded):
    conn, _, _ = loaded
    reviews = analytics.analyzed_reviews(conn)
    dist = analytics.sentiment_distribution(reviews)
    assert dist["count"].sum() == len(reviews)
    assert dist["pct"].sum() == pytest.approx(100, abs=0.2)
    assert all(" من " in t for t in dist["text"])


def test_restaurant_comparison_respects_min_reviews(loaded):
    conn, _, _ = loaded
    table = analytics.restaurant_comparison(analytics.analyzed_reviews(conn), min_reviews=20)
    small = table[table["restaurant_name"] == "مطعم الركن الصغير (تجريبي)"].iloc[0]
    assert not small["rankable"] and pd.isna(small["rank"])
    ranked = table[table["rankable"]].sort_values("rank")
    assert list(ranked["rank"]) == list(range(1, len(ranked) + 1))
    assert ranked["positive_ci_low"].is_monotonic_decreasing


def test_filters(loaded):
    conn, _, _ = loaded
    one = analytics.analyzed_reviews(conn, Filters(restaurants=["بيت المندي (تجريبي)"]))
    assert set(one["restaurant_name"]) == {"بيت المندي (تجريبي)"}
    dated = analytics.analyzed_reviews(conn, Filters(start_date="2024-06-01", end_date="2024-06-30"))
    assert dated["review_date"].between("2024-06-01", "2024-06-30").all()


def test_dishes_and_aspects(loaded):
    conn, _, _ = loaded
    dishes = analytics.dish_summary(analytics.dishes_frame(conn))
    assert dishes["mentions"].is_monotonic_decreasing
    assert (dishes[["positive", "negative", "neutral"]].sum(axis=1) == dishes["mentions"]).all()
    aspects = analytics.aspect_summary(analytics.aspects_frame(conn))
    assert set(aspects["aspect"]) <= {"food_quality", "price", "quantity", "service", "delivery",
                                      "cleanliness", "ambiance"}


def test_city_and_trend(loaded):
    conn, _, _ = loaded
    reviews = analytics.analyzed_reviews(conn)
    cities = analytics.city_comparison(reviews)
    assert "الرياض" in set(cities["city"])
    assert not cities[cities["city"] == "مكة المكرمة"]["enough_data"].iloc[0]
    trend = analytics.sentiment_trend(reviews)
    assert trend["n"].sum() == reviews["review_date"].notna().sum()


def test_keywords_and_topics(loaded):
    conn, _, _ = loaded
    texts = analytics.analyzed_reviews(conn)["clean_text"]
    words = analytics.top_keywords(texts, 10)
    assert len(words) == 10 and "من" not in set(words["term"])
    bigrams = analytics.top_keywords(["الأكل مو حلو", "مو حلو أبد"], 5, 2)
    assert "مو حلو" in set(bigrams["term"])
    assert len(analytics.extract_topics(texts.tolist(), n_topics=4)) == 4
    assert analytics.extract_topics(["قليل"]) == []


def test_wilson_interval():
    low, high = analytics.wilson_interval(3, 3)
    assert 0.4 < low < 0.5 and high == 1.0
    low_big, _ = analytics.wilson_interval(180, 200)
    assert low_big > low
    assert analytics.wilson_interval(0, 0) == (0.0, 0.0)
    assert analytics.fraction_text(12, 40) == "12 من 40 (30.0%)"


def test_agreement_with_labels(loaded):
    conn, _, _ = loaded
    agreement = analytics.agreement_with_labels(analytics.analyzed_reviews(conn))
    assert agreement["n"] > 600 and 0 <= agreement["accuracy"] <= 1


def test_pipeline_with_injected_model(conn):
    from sra.ml_model import SklearnPrediction

    class FakeModel:
        name = "fake"
        version = "fake-1"

        def predict(self, texts):
            return [SklearnPrediction("negative", 0.55, {}) for _ in texts]

    demo_data.load_demo_into_db(conn)
    counts = pipeline.analyze_reviews(conn, engine="sklearn", model=FakeModel())
    assert counts["negative"] == counts["analyzed"] == counts["uncertain"]
    assert counts["model_version"] == f"fake-1+{config.LEXICON_MODEL_VERSION}"
    assert conn.execute("SELECT COUNT(*) FROM aspects").fetchone()[0] > 0
