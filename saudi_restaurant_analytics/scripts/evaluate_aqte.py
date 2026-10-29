"""تقييم المنصة على مجموعة AQTE: الشعور العام، واكتشاف الجوانب، وشعور كل جانب.

الاستخدام:
    # تقييم محلل القاموس على ملف الاختبار
    python scripts/evaluate_aqte.py test_split.json

    # مقارنة القاموس بنموذج Scikit-learn مدرَّب على ملف التدريب
    python scripts/evaluate_aqte.py test_split.json --train train_split.json

    # تجربة سريعة على أول 300 مراجعة
    python scripts/evaluate_aqte.py test_split.json --limit 300

تنبيه منهجي: حسّن القاموس بناءً على أخطاء ملف التدريب، وشغّل التقييم النهائي على ملف
الاختبار مرة واحدة في النهاية، حتى تكون النتائج المعلنة غير متحيزة.
"""

import argparse
from pathlib import Path

import _path  # noqa: F401

from sra.aqte import evaluate, gold_overall, load_aqte, report_to_excel
from sra.dishes import DishExtractor
from sra.importer import ratings_to_labels
from sra.ml_model import SklearnSentimentModel, train_and_evaluate
from sra.sentiment import LexiconSentimentAnalyzer


def show_overall(title, models):
    print(f"\n=== الشعور العام مقارنةً بـ {title} ===")
    for name, m in models.items():
        print(f"  {name:8s}  Accuracy={m['accuracy']:.3f}  Macro-F1={m['macro_f1']:.3f}  (ن={m['n']})")


def main():
    parser = argparse.ArgumentParser(description="تقييم المنصة على AQTE")
    parser.add_argument("test", help="ملف الاختبار (test_split.json)")
    parser.add_argument("--train", help="ملف التدريب لتدريب نموذج Scikit-learn والمقارنة")
    parser.add_argument("--label-source", choices=["opinions", "rating"], default="opinions",
                        help="وسوم تدريب Scikit-learn: من آراء AQTE (افتراضي) أو من التقييم")
    parser.add_argument("--limit", type=int, default=None, help="تقييم أول N مراجعة فقط")
    parser.add_argument("--out", default=str(_path.ROOT / "data" / "aqte_evaluation.xlsx"))
    args = parser.parse_args()

    test = load_aqte(args.test)
    if args.limit:
        test = test.head(args.limit)
    print(f"مراجعات الاختبار: {len(test)}")

    model = None
    if args.train:
        train = load_aqte(args.train)
        if args.label_source == "rating":
            labels = ratings_to_labels(train["rate"].astype(float))
        else:
            labels = train["opinions"].map(gold_overall)
        keep = labels.notna()
        print(f"تدريب Scikit-learn على {int(keep.sum())} مراجعة (وسوم من {args.label_source})...")
        pipeline, meta = train_and_evaluate(train.loc[keep, "review_text"], labels[keep],
                                            label_source=f"aqte-{args.label_source}")
        model = SklearnSentimentModel(pipeline, meta)

    analyzer = LexiconSentimentAnalyzer(DishExtractor.from_csv())
    report = evaluate(test, analyzer, model)

    show_overall("آراء AQTE الموسومة", report["overall_vs_opinions"])
    if "overall_vs_rating" in report:
        show_overall("التقييم الرقمي", report["overall_vs_rating"])
    print("\n=== اكتشاف الجوانب (لكل جانب) ===")
    table = report["aspects"][["aspect_ar", "gold_mentions", "precision", "recall", "f1", "polarity_accuracy"]]
    print(table.to_string(index=False))
    m = report["aspects_micro"]
    print(f"\nإجمالي الجوانب: Precision={m['precision']:.3f}  Recall={m['recall']:.3f}  F1={m['f1']:.3f}  "
          f"دقة الشعور للجوانب المكتشفة={m['polarity_accuracy']:.3f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(report_to_excel(report))
    print(f"\nحُفظت النتائج التفصيلية في: {out}")


if __name__ == "__main__":
    main()
