"""تدريب نموذج Scikit-learn من التعليقات الموسومة في قاعدة البيانات.

الاستخدام:
    python scripts/train_model.py                 # يستخدم عمود الوسم إن وُجد
    python scripts/train_model.py --from-ratings  # يشتق الوسوم من التقييم (1-5)
"""

import argparse

import _path  # noqa: F401

from sra import database
from sra.importer import ratings_to_labels
from sra.ml_model import save_model, train_and_evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-ratings", action="store_true", help="اشتقاق الوسوم من التقييم الرقمي")
    parser.add_argument("--rating-max", type=float, default=5.0)
    args = parser.parse_args()
    with database.session() as conn:
        reviews = database.fetch_reviews(conn)
        synthetic_ids = {r["id"] for r in conn.execute("SELECT id FROM datasets WHERE is_synthetic=1")}
    if args.from_ratings:
        reviews["label"] = ratings_to_labels(reviews["original_rating"], args.rating_max)
        source = "ratings"
    else:
        reviews["label"] = reviews["external_label"]
        source = "labels"
    data = reviews.dropna(subset=["label"])
    if data.empty:
        raise SystemExit("لا توجد تعليقات موسومة. استورد بيانات بعمود وسم أو استخدم --from-ratings.")
    synthetic = bool(data["dataset_id"].isin(synthetic_ids).any())
    model, meta = train_and_evaluate(data["clean_text"], data["label"], data_is_synthetic=synthetic,
                                     label_source=source)
    save_model(model, meta)
    m = meta["metrics"]
    print(f"تم التدريب على {meta['n_samples']} تعليقًا. الدقة على بيانات الاختبار: {m['accuracy']}، "
          f"Macro-F1: {m['macro_f1']} (اختبار: {m['n_test']})")
    if synthetic:
        print("تنبيه: جزء من بيانات التدريب اصطناعي؛ هذه الأرقام لا تعبر عن أداء حقيقي.")


if __name__ == "__main__":
    main()
