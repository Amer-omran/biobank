"""تحويل ملف AQTE إلى CSV جاهز للاستيراد في المنصة، مع عمودي وسم مرجعيين.

الاستخدام:
    python scripts/prepare_aqte.py test_split.json
    python scripts/prepare_aqte.py train_split.json --out data/aqte_train.csv

الأعمدة الناتجة:
    review_text  نص المراجعة          -> «عمود التعليقات»
    place_id     معرّف المطعم          -> «عمود اسم المطعم»
    rate         التقييم 1-5           -> «عمود التقييم الرقمي»
    gold_label   الشعور من آراء AQTE   -> «عمود الوسم» (موصى به)
    rating_label الشعور من التقييم    (للمقارنة فقط)
"""

import argparse
from pathlib import Path

import _path  # noqa: F401

from sra.aqte import load_aqte, to_platform_csv


def main():
    parser = argparse.ArgumentParser(description="تحويل AQTE إلى CSV للمنصة")
    parser.add_argument("file", help="مسار test_split.json أو train_split.json")
    parser.add_argument("--out", default=None, help="مسار ملف CSV الناتج")
    args = parser.parse_args()
    df = load_aqte(args.file)
    out = Path(args.out) if args.out else Path(args.file).with_name(Path(args.file).stem + "_platform.csv")
    table = to_platform_csv(df)
    table.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"تم تحويل {len(table)} مراجعة إلى: {out}")
    print("توزيع الشعور من آراء AQTE:", table["gold_label"].value_counts(dropna=False).to_dict())
    print("المصدر: مجموعة AQTE (رخصة CC BY 4.0) — اذكرها في مراجع تقريرك.")


if __name__ == "__main__":
    main()
