"""مولد بيانات تجريبية اصطناعية باللغة العربية لتجربة الواجهة.

⚠️ هذه البيانات مولدة آليًا من قوالب، وأسماء المطاعم فيها خيالية. لا تمثل آراء عملاء
حقيقيين ولا تصلح نتائجها كنتائج بحثية. الغرض الوحيد منها اختبار المنصة عند عدم توفر
بيانات حقيقية.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pandas as pd

DEMO_DATASET_NAME = "بيانات تجريبية اصطناعية"
DEMO_DESCRIPTION = ("بيانات مولدة آليًا من قوالب لأغراض تجربة الواجهة فقط. "
                    "أسماء المطاعم خيالية، والنتائج ليست نتائج بحثية فعلية.")

# لكل مطعم: المدينة، الوجبات، واحتمال الرأي الإيجابي لكل جانب، وعدد التعليقات
RESTAURANTS = {
    "مطعم الواحة (تجريبي)": ("الرياض", ["كبسة", "مندي", "جريش", "قرصان"],
                             {"food_quality": .8, "price": .6, "quantity": .8, "service": .7,
                              "delivery": .5, "cleanliness": .8, "ambiance": .7}, 140),
    "بيت المندي (تجريبي)": ("جدة", ["مندي", "مظبي", "مضغوط"],
                            {"food_quality": .85, "price": .4, "quantity": .7, "service": .45,
                             "delivery": .35, "cleanliness": .6, "ambiance": .5}, 130),
    "برجر الحي (تجريبي)": ("الرياض", ["برجر", "بطاطس", "دجاج مقلي"],
                           {"food_quality": .55, "price": .7, "quantity": .4, "service": .6,
                            "delivery": .7, "cleanliness": .5, "ambiance": .5}, 120),
    "مشويات السراة (تجريبي)": ("أبها", ["مشاوي", "شيش طاووق", "كباب", "حمص"],
                               {"food_quality": .75, "price": .55, "quantity": .75, "service": .8,
                                "delivery": .5, "cleanliness": .75, "ambiance": .85}, 90),
    "مطبخ البحر (تجريبي)": ("الدمام", ["سمك", "روبيان", "سلطة"],
                            {"food_quality": .5, "price": .3, "quantity": .5, "service": .5,
                             "delivery": .4, "cleanliness": .4, "ambiance": .6}, 80),
    "مقهى النخيل (تجريبي)": ("المدينة المنورة", ["قهوة سعودية", "لقيمات", "كنافة", "تشيز كيك"],
                             {"food_quality": .7, "price": .5, "quantity": .6, "service": .75,
                              "delivery": .6, "cleanliness": .8, "ambiance": .9}, 60),
    # مطعم بعدد قليل من التعليقات لتوضيح قاعدة «لا ترتيب مع بيانات غير كافية»
    "مطعم الركن الصغير (تجريبي)": ("مكة المكرمة", ["شاورما", "فلافل"],
                                   {"food_quality": .95, "price": .9, "quantity": .9, "service": .9,
                                    "delivery": .9, "cleanliness": .9, "ambiance": .9}, 8),
}

FRAGMENTS = {
    "food_quality": {
        "positive": ["{dish} لذيذ مرة", "{dish} طعمه رهيب", "{dish} طازج ويفتح النفس",
                     "الأكل لذيذ والطعم ممتاز", "{dish} ممتاز ما عليه كلام", "{dish} حلووو"],
        "negative": ["{dish} ماصخ وماله طعم", "الأكل بارد", "{dish} محروق", "اللحم قاسي وناشف",
                     "{dish} مو طازج", "ما عجبني طعم {dish}"],
    },
    "price": {
        "positive": ["الأسعار معقولة", "السعر مناسب جدا", "يستاهل كل ريال", "الأسعار رخيصة"],
        "negative": ["الأسعار غالية مرة", "السعر مبالغ فيه", "حرام الفلوس", "الفاتورة غالية"],
    },
    "quantity": {
        "positive": ["الكمية كبيرة وتشبع", "الكمية وافية", "الصحن وافي ويشبع"],
        "negative": ["الكمية قليلة", "الحجم صغير", "الكمية ما تشبع"],
    },
    "service": {
        "positive": ["الموظفين بشوشين ومتعاونين", "الخدمة سريعة", "الموظفين ما قصروا",
                     "التعامل راقي ومحترم"],
        "negative": ["الخدمة بطيئة", "الموظف تعامله سيء", "طول الانتظار", "الكاشير وقح"],
    },
    "delivery": {
        "positive": ["التوصيل سريع ووصل ساخن", "المندوب محترم ووصل في الوقت", "التوصيل ممتاز"],
        "negative": ["التوصيل تأخر ساعة", "وصل الطلب بارد", "المندوب تأخر كثير"],
    },
    "cleanliness": {
        "positive": ["المكان نظيف", "الحمامات نظيفة", "النظافة ممتازة"],
        "negative": ["الطاولات وسخة", "مافي نظافة", "شفت حشرات بالمكان"],
    },
    "ambiance": {
        "positive": ["الجلسات رايقة والديكور جميل", "الأجواء هادية", "الجلسات مريحة"],
        "negative": ["المكان زحمة وفيه إزعاج", "الجلسات ضيقة", "المكان مزعج"],
    },
}
NEUTRAL_OPENERS = ["طلبت {dish}", "جربت {dish} اليوم", "زرنا المطعم مع العائلة", "طلبنا من التطبيق",
                   "زيارة ثانية للمطعم", ""]
CLOSERS = {
    "positive": ["أنصح فيه 👍", "أكيد برجع", "😍", "", ""],
    "negative": ["ما أنصح فيه", "آخر مرة 👎", "", ""],
}


def _compose(rng: random.Random, dishes: list[str], profile: dict) -> tuple[str, str, float]:
    """يركّب تعليقًا من 1 إلى 3 جوانب، ويُرجع (النص، الوسم المقصود، التقييم)."""
    n_aspects = rng.choices([1, 2, 3], weights=[0.45, 0.4, 0.15])[0]
    aspects = rng.sample(list(FRAGMENTS), n_aspects)
    if "food_quality" not in aspects and rng.random() < 0.5:
        aspects[0] = "food_quality"
    aspects = list(dict.fromkeys(aspects))
    dish = rng.choice(dishes)
    parts, net = [], 0
    previous = None
    for aspect in aspects:
        sentiment = "positive" if rng.random() < profile[aspect] else "negative"
        net += 1 if sentiment == "positive" else -1
        fragment = rng.choice(FRAGMENTS[aspect][sentiment]).format(dish=dish)
        if previous is None:
            parts.append(fragment)
        elif previous != sentiment:
            parts.append(rng.choice([" بس ", " لكن ", "، بس "]) + fragment)
        else:
            parts.append(rng.choice([" و", "، ", " و"]) + fragment)
        previous = sentiment
    opener = rng.choice(NEUTRAL_OPENERS).format(dish=dish)
    text = "".join(parts)
    if opener:
        text = opener + "، " + text
    if net > 0:
        label = "positive"
    elif net < 0:
        label = "negative"
    else:
        label = "neutral"
    closer = rng.choice(CLOSERS.get(label, [""]))
    if closer:
        text = text + " " + closer
    rating = {"positive": rng.choice([4, 5, 5]), "negative": rng.choice([1, 2, 2]),
              "neutral": rng.choice([3, 3, 4, 2])}[label]
    return text, label, float(rating)


def generate_demo_reviews(seed: int = 7, start: date = date(2024, 1, 1), days: int = 540) -> pd.DataFrame:
    """يولد جدول تعليقات تجريبية قابلًا للتكرار (البذرة نفسها = البيانات نفسها)."""
    rng = random.Random(seed)
    rows = []
    for name, (city, dishes, profile, count) in RESTAURANTS.items():
        for _ in range(count):
            text, label, rating = _compose(rng, dishes, profile)
            day = start + timedelta(days=rng.randrange(days))
            rows.append({
                "التعليق": text,
                "المطعم": name,
                "المدينة": city,
                "التاريخ": day.isoformat(),
                "التقييم": rating,
                "المصدر": "بيانات تجريبية اصطناعية",
                "الوسم_المولد": label,
            })
    # بعض التعليقات المحايدة دون رأي، وتعليق مكرر عمدًا، ورابط، لاختبار المعالجة
    rows.append({"التعليق": "طلبت كبسة اليوم", "المطعم": "مطعم الواحة (تجريبي)", "المدينة": "الرياض",
                 "التاريخ": "2024-06-01", "التقييم": 3.0, "المصدر": "بيانات تجريبية اصطناعية",
                 "الوسم_المولد": "neutral"})
    rows.append(dict(rows[0]))
    rows.append({"التعليق": "الأكل لذيذ والخدمة سريعة https://example.com/review",
                 "المطعم": "برجر الحي (تجريبي)", "المدينة": "الرياض", "التاريخ": "2024-07-15",
                 "التقييم": 5.0, "المصدر": "بيانات تجريبية اصطناعية", "الوسم_المولد": "positive"})
    df = pd.DataFrame(rows)
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def load_demo_into_db(conn) -> dict:
    """يولد البيانات التجريبية ويستوردها كمجموعة بيانات معلَّمة بأنها اصطناعية."""
    from . import database
    from .importer import ColumnMapping, prepare_dataframe

    df = generate_demo_reviews()
    mapping = ColumnMapping(text="التعليق", restaurant="المطعم", date="التاريخ", rating="التقييم",
                            city="المدينة", label="الوسم_المولد", source="المصدر")
    report = prepare_dataframe(df, mapping, dedupe=True)
    dataset_id = database.get_or_create_dataset(conn, DEMO_DATASET_NAME, "demo", True, DEMO_DESCRIPTION)
    result = database.insert_reviews(conn, dataset_id, report.data)
    result["dataset_id"] = dataset_id
    result["duplicates_in_file"] = report.duplicate_rows
    return result
