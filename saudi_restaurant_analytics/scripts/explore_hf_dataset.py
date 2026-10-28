"""فحص مجموعة بيانات Hugging Face وتصديرها إلى CSV قبل الاستيراد.

الاستخدام:
    python scripts/explore_hf_dataset.py
    python scripts/explore_hf_dataset.py --repo bayandashnan/AQTE-Arabic-Quote-Triplet-Extraction --split train

يطبع الأعمدة الفعلية وأنواعها وأمثلة منها والوسوم، ثم يحفظ CSV في data/hf_export/.
بعدها افتح صفحة «استيراد البيانات» واختر الأعمدة المناسبة بنفسك.
"""

import argparse
import json

import _path  # noqa: F401

from sra.hf_dataset import DEFAULT_DATASET, explore_and_export


def main():
    parser = argparse.ArgumentParser(description="استكشاف مجموعة بيانات Hugging Face")
    parser.add_argument("--repo", default=DEFAULT_DATASET)
    parser.add_argument("--split", default=None)
    parser.add_argument("--out", default=str(_path.ROOT / "data" / "hf_export"))
    args = parser.parse_args()
    summary = explore_and_export(args.repo, args.out, args.split)
    for split, profile in summary["splits"].items():
        print(f"\n=== القسم: {split} — عدد الصفوف: {profile['n_rows']}")
        for col in profile["columns"]:
            print(f"- {col['name']} | النوع: {col['dtype']} ({col['python_type']}) | "
                  f"فارغ: {col['nulls']} | قيم مختلفة: {col['unique']} | نسبة العربية: {col['arabic_share']}")
            for ex in col["examples"]:
                print(f"    مثال: {ex[:150]}")
            if "value_counts" in col:
                print(f"    القيم: {col['value_counts']}")
        print("الأعمدة المقترحة (للمراجعة فقط):", profile["suggested_mapping"])
        print("تم الحفظ في:", profile["exported_to"])
    if summary["class_label_names"]:
        print("\nأسماء الوسوم (ClassLabel):", json.dumps(summary["class_label_names"], ensure_ascii=False))
    print("\nتنبيه: تحقق من أن محتوى المجموعة مناسب لتحليل مراجعات المطاعم قبل استخدامه في البحث.")


if __name__ == "__main__":
    main()
