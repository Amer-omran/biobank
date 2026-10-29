"""تحليل أخطاء المحلل على AQTE، لتحسين القاموس. استخدمه على ملف التدريب فقط.

الاستخدام:
    python scripts/error_analysis_aqte.py train_split.json --limit 2000

يحفظ ملف Excel فيه:
- كلمات مقترحة: كلمات متكررة في العبارات التي فاتت المحلل وليست في القاموس.
- جوانب فائتة: جوانب وسمتها AQTE ولم يكتشفها المحلل، مع العبارة.
- أخطاء شعور الجوانب، وأخطاء الشعور العام.

راجع المقترحات بنفسك قبل إضافتها إلى sra/lexicon.py؛ ليست كل كلمة متكررة كلمة رأي.
"""

import argparse
from pathlib import Path

import _path  # noqa: F401

from sra.aqte import error_analysis, errors_to_excel, load_aqte
from sra.dishes import DishExtractor
from sra.sentiment import LexiconSentimentAnalyzer


def main():
    parser = argparse.ArgumentParser(description="AQTE error analysis")
    parser.add_argument("file", help="train_split.json (do not use the test file here)")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--out", default=str(_path.ROOT / "data" / "aqte_error_analysis.xlsx"))
    args = parser.parse_args()
    if "test" in Path(args.file).name.lower():
        print("WARNING: this looks like the TEST file. Tuning the lexicon on it biases your final results.")
    df = load_aqte(args.file)
    if args.limit:
        df = df.sample(n=min(args.limit, len(df)), random_state=0)
    errors = error_analysis(df, LexiconSentimentAnalyzer(DishExtractor.from_csv()))
    print(f"Reviews analysed: {len(df)}")
    for key, frame in errors.items():
        print(f"  {key}: {len(frame)} rows")
    missed = errors["missed_aspects"]
    if not missed.empty:
        print("\nMissed aspect mentions per aspect:")
        print(missed["aspect"].value_counts().to_string())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(errors_to_excel(errors))
    print(f"\nSaved (Arabic, open in Excel): {out}")


if __name__ == "__main__":
    main()
