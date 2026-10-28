import pytest


def aspects_of(result):
    return {(a.aspect, a.sentiment) for a in result.aspects if a.has_opinion}


@pytest.mark.parametrize("text, expected", [
    ("الأكل لذيذ جدا", "positive"),
    ("ممتاز وأنصح فيه", "positive"),
    ("المطعم سيء والأكل بارد", "negative"),
    ("الأسعار غالية مرة", "negative"),
    ("حلوووو 😍", "positive"),
    ("ما شاء الله الأكل لذيذ", "positive"),
    ("👎👎", "negative"),
])
def test_overall_sentiment(analyzer, text, expected):
    assert analyzer.analyze(text).label == expected


@pytest.mark.parametrize("text", ["مو حلو", "ما عجبني الأكل", "ماعجبني", "لا أنصح فيه", "غير نظيف"])
def test_negation_flips_positive_to_negative(analyzer, text):
    assert analyzer.analyze(text).label == "negative"


def test_negated_negative_is_weak_positive(analyzer):
    result = analyzer.analyze("مو سيء")
    assert result.label == "positive"
    assert result.positive_score < analyzer.analyze("ممتاز").positive_score


def test_no_opinion_gives_uncertain_neutral(analyzer):
    result = analyzer.analyze("طلبت شاورما اليوم")
    assert result.label == "neutral" and result.is_uncertain


def test_multiple_aspects_get_correct_sentiment(analyzer):
    result = analyzer.analyze("الأكل لذيذ بس الخدمة بطيئة")
    assert {("food_quality", "positive"), ("service", "negative")} <= aspects_of(result)
    assert result.is_mixed


def test_aspects_without_punctuation(analyzer):
    result = analyzer.analyze("الأكل لذيذ والخدمة سيئة")
    assert aspects_of(result) == {("food_quality", "positive"), ("service", "negative")}


def test_coordinated_aspects_share_opinion(analyzer):
    result = analyzer.analyze("الأكل والخدمة ممتازين")
    assert aspects_of(result) == {("food_quality", "positive"), ("service", "positive")}


def test_implicit_aspects(analyzer):
    assert ("price", "negative") in aspects_of(analyzer.analyze("غالي"))
    assert ("cleanliness", "negative") in aspects_of(analyzer.analyze("المكان وسخ"))
    assert ("quantity", "positive") in aspects_of(analyzer.analyze("الكمية كبيرة وتشبع"))


def test_conditional_words_depend_on_aspect(analyzer):
    assert ("quantity", "positive") in aspects_of(analyzer.analyze("الحجم كبير"))
    assert ("price", "negative") in aspects_of(analyzer.analyze("الأسعار مرتفعة"))
    assert ("quantity", "negative") in aspects_of(analyzer.analyze("الكمية قليلة"))


def test_absence_negator(analyzer):
    assert ("cleanliness", "negative") in aspects_of(analyzer.analyze("مافي نظافة"))
    assert ("cleanliness", "negative") in aspects_of(analyzer.analyze("ما فيه نظافة أبد"))


def test_delivery_aspect(analyzer):
    result = analyzer.analyze("التوصيل تأخر ساعة والمندوب وقح")
    assert ("delivery", "negative") in aspects_of(result)


def test_dish_linked_to_aspect_and_sentiment(analyzer):
    result = analyzer.analyze("الكبسة لذيذة بس البرقر ماله طعم")
    dishes = {d.dish: d.sentiment for d in result.dishes}
    assert dishes == {"كبسة": "positive", "برجر": "negative"}
    linked = {(a.dish, a.sentiment) for a in result.aspects if a.dish}
    assert ("كبسة", "positive") in linked and ("برجر", "negative") in linked


def test_dish_sentiment_uses_clause_with_opinion(analyzer):
    result = analyzer.analyze("طلبت مندي، المندي لذيذ")
    assert [(d.dish, d.sentiment) for d in result.dishes] == [("مندي", "positive")]


def test_evidence_is_original_clause(analyzer):
    result = analyzer.analyze("الأكلُ لذيذٌ، لكن السعر غالي")
    evidence = {a.aspect: a.evidence for a in result.aspects}
    assert evidence["food_quality"] == "الأكلُ لذيذٌ"
    assert evidence["price"] == "السعر غالي"


def test_intensifier_attaches_to_nearest_opinion(analyzer):
    result = analyzer.analyze("مندي لذيذ مرة والأسعار معقولة")
    scores = {a.aspect: a.score for a in result.aspects}
    assert scores["food_quality"] > 1.5 and scores["price"] == pytest.approx(0.6)


def test_confidence_bounds_and_mixed_lowers_confidence(analyzer):
    clear = analyzer.analyze("الأكل لذيذ والخدمة ممتازة")
    mixed = analyzer.analyze("الأكل لذيذ والخدمة سيئة")
    for r in (clear, mixed):
        assert 0 <= r.confidence <= 1
    assert mixed.confidence < clear.confidence


def test_empty_text(analyzer):
    result = analyzer.analyze("")
    assert result.label == "neutral" and result.is_uncertain and result.aspects == []
