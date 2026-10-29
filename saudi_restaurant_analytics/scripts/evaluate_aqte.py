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

from sra.aqte import evaluate, gold_overall, load_aqte, majority_baseline, report_to_excel
from sra.dishes import DishExtractor
from sra.importer import ratings_to_labels
from sra.ml_model import SklearnSentimentModel, train_and_evaluate
from sra.sentiment import LexiconSentimentAnalyzer


LABEL_EN = {"positive": "pos", "negative": "neg", "neutral": "neu"}


def show_overall(title, models, baseline):
    # الطباعة بالإنجليزية لأن موجه أوامر ويندوز لا يعرض العربية غالبًا؛ التفاصيل العربية في ملف Excel
    print(f"\n=== Overall sentiment vs {title} ===")
    print(f"  baseline  Accuracy={baseline['accuracy']:.3f}  Macro-F1={baseline['macro_f1']:.3f}"
          f"  (always predicts '{baseline['label']}')")
    for name, m in models.items():
        print(f"  {name:8s}  Accuracy={m['accuracy']:.3f}  Macro-F1={m['macro_f1']:.3f}  (n={m['n']})")
        per_class = "  ".join(f"{LABEL_EN[c]}: F1={m['report'][c]['f1-score']:.2f} n={int(m['report'][c]['support'])}"
                              for c in m["labels"])
        print(f"            {per_class}")
        header = "gold\\pred " + " ".join(f"{LABEL_EN[c]:>6s}" for c in m["labels"])
        print("            " + header)
        for c, row in zip(m["labels"], m["confusion_matrix"]):
            print("            " + f"{LABEL_EN[c]:>9s} " + " ".join(f"{v:6d}" for v in row))


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
    print(f"Reviews: {len(test)}")
    scale = test.attrs.get("sentiment_scale")
    meaning = "0=neg, 0.5=neu, 1=pos" if scale == "unit" else "-1=neg, 0=neu, 1=pos"
    print(f"avg_sentiment scale detected: {scale} ({meaning}); values seen: {test.attrs.get('sentiment_values')}")

    model = None
    if args.train:
        train = load_aqte(args.train)
        if args.label_source == "rating":
            labels = ratings_to_labels(train["rate"].astype(float))
        else:
            labels = train["opinions"].map(gold_overall)
        keep = labels.notna()
        print(f"Training scikit-learn on {int(keep.sum())} reviews (labels: {args.label_source})...")
        pipeline, meta = train_and_evaluate(train.loc[keep, "review_text"], labels[keep],
                                            label_source=f"aqte-{args.label_source}")
        model = SklearnSentimentModel(pipeline, meta)

    analyzer = LexiconSentimentAnalyzer(DishExtractor.from_csv())
    report = evaluate(test, analyzer, model)

    gold_op = [g for g in test["opinions"].map(gold_overall) if g]
    show_overall("AQTE opinions", report["overall_vs_opinions"], majority_baseline(gold_op))
    if "overall_vs_rating" in report:
        gold_rt = [g for g in ratings_to_labels(test["rate"].astype(float)) if g]
        show_overall("star rating", report["overall_vs_rating"], majority_baseline(gold_rt))
    print("\n=== Aspect detection (per aspect) ===")
    table = report["aspects"][["aspect", "gold_mentions", "precision", "recall", "f1", "polarity_accuracy"]]
    print(table.to_string(index=False))
    m = report["aspects_micro"]
    print(f"\nAll aspects: Precision={m['precision']:.3f}  Recall={m['recall']:.3f}  F1={m['f1']:.3f}  "
          f"polarity accuracy on detected aspects={m['polarity_accuracy']:.3f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(report_to_excel(report))
    print(f"\nDetailed results (Arabic) saved to: {out}")


if __name__ == "__main__":
    main()
