"""التحليلات الإحصائية: توزيع المشاعر، الوجبات، الجوانب، المقارنات، الاتجاهات، الكلمات.

قواعد العرض الأمينة:
- كل نسبة تُعرض مع بسطها ومقامها (مثل 12 من 40).
- لا يُرتب مطعم أو مدينة إلا إذا بلغ عدد تعليقاته الحد الأدنى (MIN_REVIEWS_FOR_RANKING).
- الترتيب يعتمد على الحد الأدنى لفترة ويلسون (Wilson) وليس النسبة الخام، حتى لا يتقدم
  مطعم بثلاثة تعليقات إيجابية على مطعم بمئتي تعليق.
- عدد مرات ذكر الوجبة مؤشر تفضيل مستنتج من التعليقات، وليس عدد مرات الشراء.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import pandas as pd

from . import config
from .importer import KNOWN_CITIES
from .text_processing import normalize_arabic, tokenize

STOPWORDS = {normalize_arabic(w) for w in (
    "من في على الى إلى عن و او أو ثم هذا هذه ذلك تلك اللي الي التي الذي هو هي انا أنا احنا نحن "
    "هم انت كان كانت يكون مع عند كل بعد قبل لما اذا إذا حتى قد لقد ان أن إن انه أنه يا شي شيء "
    "فيه فيها له لها لهم به بها عليه عليها مطعم المطعم طلبت طلبنا جيت جينا رحت رحنا والله الله "
    "مره مرة جدا كثير وايد واجد بس لكن ولكن مثل اول أول ثاني يوم اليوم وقت كذا هنا هناك ايضا أيضا "
    "the a an and or is was it this that to of in for on with"
).split()}
NEGATION_KEEP = {normalize_arabic(w) for w in ("لا", "ما", "مو", "مب", "مش", "ليس", "غير", "بدون", "مافي")}

SENTIMENT_COLUMNS = list(config.SENTIMENTS)


@dataclass
class Filters:
    dataset_ids: list[int] | None = None
    restaurants: list[str] | None = None
    cities: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    model_version: str | None = None  # None = أحدث تحليل لكل تعليق


def _where(f: Filters | None) -> tuple[str, str, list]:
    """يبني مصدر التحليل وشروط التصفية."""
    f = f or Filters()
    params: list = []
    source = "latest_analyses"
    conditions = ["1=1"]
    if f.model_version:
        source = "analyses"
        conditions.append("a.model_version = ?")
        params.append(f.model_version)
    if f.dataset_ids:
        conditions.append(f"r.dataset_id IN ({','.join('?' * len(f.dataset_ids))})")
        params.extend(int(i) for i in f.dataset_ids)
    if f.restaurants:
        conditions.append(f"r.restaurant_name IN ({','.join('?' * len(f.restaurants))})")
        params.extend(f.restaurants)
    if f.cities:
        conditions.append(f"r.city IN ({','.join('?' * len(f.cities))})")
        params.extend(f.cities)
    if f.start_date:
        conditions.append("r.review_date >= ?")
        params.append(str(f.start_date))
    if f.end_date:
        conditions.append("r.review_date <= ?")
        params.append(str(f.end_date))
    return source, " AND ".join(conditions), params


# ============================================================ جلب البيانات
def overview(conn) -> dict:
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "n_reviews": q("SELECT COUNT(*) FROM reviews"),
        "n_restaurants": q("SELECT COUNT(DISTINCT restaurant_key) FROM reviews WHERE restaurant_key != ''"),
        "n_datasets": q("SELECT COUNT(*) FROM datasets"),
        "n_analyzed": q("SELECT COUNT(DISTINCT review_id) FROM analyses"),
        "n_synthetic_reviews": q(
            "SELECT COUNT(*) FROM reviews r JOIN datasets d ON d.id = r.dataset_id WHERE d.is_synthetic = 1"),
        "n_with_date": q("SELECT COUNT(*) FROM reviews WHERE review_date IS NOT NULL"),
        "n_with_city": q("SELECT COUNT(*) FROM reviews WHERE city IS NOT NULL"),
        "n_with_rating": q("SELECT COUNT(*) FROM reviews WHERE original_rating IS NOT NULL"),
        "n_dishes": q("SELECT COUNT(*) FROM dishes WHERE is_active = 1"),
    }


def analyzed_reviews(conn, f: Filters | None = None) -> pd.DataFrame:
    source, where, params = _where(f)
    sql = f"""
        SELECT r.id AS review_id, r.text, r.clean_text, r.restaurant_name, r.city, r.review_date,
               r.original_rating, r.external_label, r.source, d.name AS dataset, d.is_synthetic,
               a.id AS analysis_id, a.sentiment, a.confidence, a.is_mixed, a.is_uncertain,
               a.positive_score, a.negative_score, a.cues, a.model_version, a.analyzed_at
        FROM reviews r
        JOIN {source} a ON a.review_id = r.id
        JOIN datasets d ON d.id = r.dataset_id
        WHERE {where} ORDER BY r.id"""
    return pd.read_sql_query(sql, conn, params=params)


def aspects_frame(conn, f: Filters | None = None) -> pd.DataFrame:
    source, where, params = _where(f)
    sql = f"""
        SELECT r.id AS review_id, r.restaurant_name, r.city, r.review_date, s.aspect, s.sentiment,
               s.score, s.confidence, s.evidence, s.has_opinion, ds.canonical_name AS dish
        FROM aspects s
        JOIN {source} a ON a.id = s.analysis_id
        JOIN reviews r ON r.id = a.review_id
        LEFT JOIN dishes ds ON ds.id = s.dish_id
        WHERE {where}"""
    return pd.read_sql_query(sql, conn, params=params)


def dishes_frame(conn, f: Filters | None = None) -> pd.DataFrame:
    source, where, params = _where(f)
    sql = f"""
        SELECT r.id AS review_id, r.restaurant_name, r.city, r.review_date, ds.canonical_name AS dish,
               ds.category, rd.matched_text, rd.sentiment, rd.evidence, r.text
        FROM review_dishes rd
        JOIN {source} a ON a.id = rd.analysis_id
        JOIN reviews r ON r.id = a.review_id
        JOIN dishes ds ON ds.id = rd.dish_id
        WHERE {where}"""
    return pd.read_sql_query(sql, conn, params=params)


def restaurants_list(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT restaurant_name FROM reviews WHERE restaurant_name IS NOT NULL ORDER BY 1")]


def cities_list(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT city FROM reviews WHERE city IS NOT NULL ORDER BY 1")]


def date_range(conn) -> tuple[str | None, str | None]:
    row = conn.execute("SELECT MIN(review_date), MAX(review_date) FROM reviews").fetchone()
    return row[0], row[1]


# ================================================================ الإحصاء
def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """فترة ثقة ويلسون 95% لنسبة k من n. مناسبة للعينات الصغيرة."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def fraction_text(k: int, n: int) -> str:
    """نص يوضح البسط والمقام: «12 من 40 (30.0%)»."""
    if n == 0:
        return "لا توجد بيانات"
    return f"{k} من {n} ({100 * k / n:.1f}%)"


def counts_table(df: pd.DataFrame, group: list[str] | None = None) -> pd.DataFrame:
    """جدول أعداد المشاعر مع المقام والنسب لكل مجموعة."""
    if df.empty:
        cols = (group or []) + ["n"] + SENTIMENT_COLUMNS + ["positive_pct", "negative_pct", "neutral_pct"]
        return pd.DataFrame(columns=cols)
    if group:
        table = pd.crosstab([df[g] for g in group], df["sentiment"])
    else:
        table = df["sentiment"].value_counts().to_frame().T
    for s in SENTIMENT_COLUMNS:
        if s not in table.columns:
            table[s] = 0
    table = table[SENTIMENT_COLUMNS].copy()
    table.insert(0, "n", table.sum(axis=1))
    for s in SENTIMENT_COLUMNS:
        table[f"{s}_pct"] = (100 * table[s] / table["n"]).round(1)
    table = table.reset_index(drop=not group)
    table.columns.name = None
    return table


def sentiment_distribution(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(df)
    for s in SENTIMENT_COLUMNS:
        k = int((df["sentiment"] == s).sum()) if n else 0
        rows.append({"sentiment": s, "label": config.SENTIMENT_AR[s], "count": k, "total": n,
                     "pct": round(100 * k / n, 1) if n else 0.0, "text": fraction_text(k, n)})
    return pd.DataFrame(rows)


def aspect_summary(aspects: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """ملخص الجوانب: نحسب فقط الجوانب التي ورد فيها رأي فعلي (has_opinion=1)."""
    data = aspects[aspects["has_opinion"] == 1] if not aspects.empty else aspects
    group = [by, "aspect"] if by else ["aspect"]
    table = counts_table(data, group)
    if not table.empty:
        table["aspect_ar"] = table["aspect"].map(config.ASPECT_AR)
    return table


def satisfaction_highlights(aspects: pd.DataFrame, min_mentions: int = 5) -> dict[str, pd.DataFrame]:
    """أبرز جوانب الرضا والشكاوى (مع حد أدنى لعدد الإشارات)."""
    table = aspect_summary(aspects)
    if table.empty:
        return {"strengths": table, "complaints": table}
    enough = table[table["n"] >= min_mentions]
    return {
        "strengths": enough.sort_values(["positive_pct", "n"], ascending=False),
        "complaints": enough.sort_values(["negative_pct", "n"], ascending=False),
    }


def dish_summary(dishes: pd.DataFrame) -> pd.DataFrame:
    """لكل وجبة: عدد التعليقات التي ذكرتها، وتوزيع الشعور تجاهها."""
    if dishes.empty:
        return pd.DataFrame(columns=["dish", "category", "mentions", *SENTIMENT_COLUMNS,
                                     "positive_pct", "negative_pct", "neutral_pct"])
    table = counts_table(dishes, ["dish"]).rename(columns={"n": "mentions"})
    categories = dishes.drop_duplicates("dish").set_index("dish")["category"]
    table.insert(1, "category", table["dish"].map(categories))
    return table.sort_values("mentions", ascending=False).reset_index(drop=True)


def restaurant_comparison(reviews: pd.DataFrame, min_reviews: int = config.MIN_REVIEWS_FOR_RANKING) -> pd.DataFrame:
    """مقارنة المطاعم؛ يُرتب فقط من بلغ الحد الأدنى من التعليقات."""
    data = reviews.dropna(subset=["restaurant_name"])
    table = counts_table(data, ["restaurant_name"])
    if table.empty:
        return table
    bounds = table.apply(lambda r: wilson_interval(int(r["positive"]), int(r["n"])), axis=1)
    table["positive_ci_low"] = bounds.map(lambda b: round(100 * b[0], 1))
    table["positive_ci_high"] = bounds.map(lambda b: round(100 * b[1], 1))
    table["rankable"] = table["n"] >= min_reviews
    table["positive_text"] = table.apply(lambda r: fraction_text(int(r["positive"]), int(r["n"])), axis=1)
    ranked = table[table["rankable"]].sort_values("positive_ci_low", ascending=False)
    table["rank"] = pd.Series(range(1, len(ranked) + 1), index=ranked.index)
    return table.sort_values(["rankable", "positive_ci_low"], ascending=[False, False]).reset_index(drop=True)


def restaurant_aspect_matrix(aspects: pd.DataFrame, restaurants: list[str] | None = None) -> pd.DataFrame:
    data = aspects.dropna(subset=["restaurant_name"])
    if restaurants:
        data = data[data["restaurant_name"].isin(restaurants)]
    table = aspect_summary(data, by="restaurant_name")
    if not table.empty:
        table["positive_text"] = table.apply(lambda r: fraction_text(int(r["positive"]), int(r["n"])), axis=1)
        table["negative_text"] = table.apply(lambda r: fraction_text(int(r["negative"]), int(r["n"])), axis=1)
    return table


def city_comparison(reviews: pd.DataFrame, min_reviews: int = config.MIN_REVIEWS_FOR_RANKING) -> pd.DataFrame:
    """مقارنة المدن الموثوقة فقط (أسماء مدن معروفة وموحدة)."""
    data = reviews[reviews["city"].isin(KNOWN_CITIES.keys())]
    table = counts_table(data, ["city"])
    if table.empty:
        return table
    table["enough_data"] = table["n"] >= min_reviews
    table["positive_text"] = table.apply(lambda r: fraction_text(int(r["positive"]), int(r["n"])), axis=1)
    return table.sort_values("n", ascending=False).reset_index(drop=True)


def sentiment_trend(reviews: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """توزيع المشاعر حسب الفترة (شهر M أو ربع Q أو أسبوع W)."""
    data = reviews.dropna(subset=["review_date"]).copy()
    if data.empty:
        return pd.DataFrame(columns=["period", "n", *SENTIMENT_COLUMNS])
    data["period"] = pd.to_datetime(data["review_date"]).dt.to_period(freq).astype(str)
    return counts_table(data, ["period"]).sort_values("period").reset_index(drop=True)


# ======================================================= الكلمات والموضوعات
def _keyword_tokens(text: str) -> list[str]:
    tokens = []
    for raw in tokenize(text):
        t = normalize_arabic(raw)
        if t.startswith("وال") and len(t) > 4:  # «والطعم» تُحسب مع «الطعم»
            t = t[1:]
        if len(t) > 1 and not t.isdigit() and t not in ("!", "؟", "?"):
            tokens.append(t)
    return tokens


def top_keywords(texts, n: int = 25, ngram: int = 1) -> pd.DataFrame:
    """أكثر الكلمات أو العبارات تكرارًا. في العبارات الثنائية نُبقي النفي (مو حلو)."""
    counter: Counter = Counter()
    for text in texts:
        tokens = _keyword_tokens(text)
        if ngram == 1:
            counter.update(t for t in tokens if t not in STOPWORDS and t not in NEGATION_KEEP)
        else:
            for i in range(len(tokens) - ngram + 1):
                gram = tokens[i:i + ngram]
                # العبارة لا تنتهي بكلمة شائعة، ولا تبدأ بها إلا إذا كانت أداة نفي
                if gram[-1] in STOPWORDS or (gram[0] in STOPWORDS and gram[0] not in NEGATION_KEEP):
                    continue
                counter[" ".join(gram)] += 1
    return pd.DataFrame(counter.most_common(n), columns=["term", "count"])


def extract_topics(texts, n_topics: int = 5, n_words: int = 8, min_docs: int = 30) -> list[list[str]]:
    """استخراج موضوعات تقريبية بطريقة NMF. يحتاج عددًا كافيًا من التعليقات."""
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [t for t in texts if t]
    if len(texts) < min_docs:
        return []
    vectorizer = TfidfVectorizer(
        preprocessor=lambda t: " ".join(w for w in _keyword_tokens(t) if w not in STOPWORDS),
        token_pattern=r"(?u)\b\w\w+\b", max_df=0.8, min_df=2,
    )
    matrix = vectorizer.fit_transform(texts)
    if matrix.shape[1] < n_topics:
        return []
    n_topics = min(n_topics, matrix.shape[0] - 1, matrix.shape[1])
    model = NMF(n_components=n_topics, random_state=0, init="nndsvda", max_iter=400)
    model.fit(matrix)
    words = vectorizer.get_feature_names_out()
    return [[words[i] for i in comp.argsort()[::-1][:n_words]] for comp in model.components_]


def agreement_with_labels(reviews: pd.DataFrame) -> dict | None:
    """مقارنة نتائج التحليل بالوسوم الأصلية في البيانات (إن وُجدت)."""
    data = reviews.dropna(subset=["external_label"])
    if data.empty:
        return None
    from sklearn.metrics import classification_report, confusion_matrix

    labels = [s for s in SENTIMENT_COLUMNS if s in set(data["external_label"]) | set(data["sentiment"])]
    return {
        "n": len(data),
        "accuracy": round(float((data["external_label"] == data["sentiment"]).mean()), 4),
        "report": classification_report(data["external_label"], data["sentiment"], labels=labels,
                                        output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(data["external_label"], data["sentiment"], labels=labels).tolist(),
        "labels": labels,
    }
