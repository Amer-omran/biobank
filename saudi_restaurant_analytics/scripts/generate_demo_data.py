"""توليد ملف CSV للبيانات التجريبية الاصطناعية (لتجربة صفحة الاستيراد).

الاستخدام:
    python scripts/generate_demo_data.py
"""

import _path  # noqa: F401

from sra.demo_data import generate_demo_reviews


def main():
    out = _path.ROOT / "data" / "sample" / "demo_reviews_synthetic.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = generate_demo_reviews()
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"تم إنشاء {len(df)} تعليقًا تجريبيًا اصطناعيًا في: {out}")
    print("تنبيه: هذه بيانات مولدة آليًا وليست آراء عملاء حقيقيين.")


if __name__ == "__main__":
    main()
