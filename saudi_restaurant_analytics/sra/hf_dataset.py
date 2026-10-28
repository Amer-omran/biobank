"""استكشاف مجموعات بيانات Hugging Face قبل استيرادها.

القاعدة: لا نفترض أسماء الأعمدة أو الوسوم. نفحص البنية الفعلية أولًا (الأعمدة،
أنواعها، أمثلة، القيم المتكررة، وأسماء الوسوم إن كانت ClassLabel)، ثم نصدّر البيانات
إلى CSV مسطح يستورده المستخدم من صفحة الاستيراد مع اختيار الأعمدة يدويًا.

يحتاج هذا الملف إلى مكتبة datasets (ضمن requirements-optional.txt) وإلى اتصال بموقع
huggingface.co.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .importer import stringify_nested, suggest_mapping
from .text_processing import contains_arabic

DEFAULT_DATASET = "bayandashnan/AQTE-Arabic-Quote-Triplet-Extraction"


def profile_dataframe(df: pd.DataFrame, max_examples: int = 3, max_categories: int = 15) -> dict:
    """وصف بنية جدول: الأعمدة وأنواعها والقيم الفارغة والأمثلة والقيم الأكثر تكرارًا."""
    flat = stringify_nested(df)
    columns = []
    for col in df.columns:
        series = flat[col]
        non_null = series.dropna()
        sample_raw = df[col].dropna().head(1).tolist()
        info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "python_type": type(sample_raw[0]).__name__ if sample_raw else None,
            "non_null": int(non_null.shape[0]),
            "nulls": int(series.isna().sum()),
            "unique": int(non_null.astype(str).nunique()),
            "arabic_share": round(float(non_null.astype(str).map(contains_arabic).mean()), 3) if len(non_null) else 0.0,
            "mean_length": round(float(non_null.astype(str).str.len().mean()), 1) if len(non_null) else 0.0,
            "examples": [str(v)[:300] for v in non_null.head(max_examples)],
        }
        if 0 < info["unique"] <= max_categories:
            info["value_counts"] = non_null.astype(str).value_counts().to_dict()
        columns.append(info)
    return {"n_rows": len(df), "columns": columns, "suggested_mapping": suggest_mapping(flat)}


def load_hf_dataset(repo_id: str = DEFAULT_DATASET, split: str | None = None):
    """يحمّل المجموعة عبر مكتبة datasets ويُرجع {اسم القسم: DataFrame} وأسماء الوسوم."""
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("مكتبة datasets غير مثبتة: pip install -r requirements-optional.txt") from exc
    loaded = load_dataset(repo_id, split=split) if split else load_dataset(repo_id)
    splits = {split: loaded} if split else dict(loaded)
    frames, label_names = {}, {}
    for name, ds in splits.items():
        frames[name] = ds.to_pandas()
        for feature_name, feature in ds.features.items():
            names = getattr(feature, "names", None)  # ClassLabel
            if names:
                label_names[feature_name] = list(names)
    return frames, label_names


def explore_and_export(repo_id: str = DEFAULT_DATASET, output_dir: Path | str = "data/hf_export",
                       split: str | None = None) -> dict:
    """يفحص المجموعة ويطبع وصفها، ويصدّر كل قسم إلى CSV بترميز UTF-8."""
    frames, label_names = load_hf_dataset(repo_id, split)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {"repo_id": repo_id, "splits": {}, "class_label_names": label_names}
    for name, df in frames.items():
        profile = profile_dataframe(df)
        path = output_dir / f"{repo_id.replace('/', '__')}__{name}.csv"
        stringify_nested(df).to_csv(path, index=False, encoding="utf-8-sig")
        profile["exported_to"] = str(path)
        summary["splits"][name] = profile
    (output_dir / "profile.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
