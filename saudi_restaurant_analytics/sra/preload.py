"""تحميل تلقائي لملفات البيانات الموجودة في data/preload عندما تكون قاعدة البيانات فارغة.

يفيد على الاستضافات التي تمسح القرص عند إعادة التشغيل (مثل Streamlit Community Cloud):
ضع ملف CSV أو Excel في data/preload فيُستورد ويُحلل تلقائيًا في أول تشغيل بقاعدة فارغة.
اسم مجموعة البيانات هو اسم الملف، والأعمدة تُختار بالاقتراح الآلي نفسه في صفحة الاستيراد.
"""

from __future__ import annotations

from pathlib import Path

from . import config, database, importer, pipeline

PRELOAD_DIR = config.DATA_DIR / "preload"
EXTENSIONS = {".csv", ".xlsx", ".xls", ".parquet", ".json", ".jsonl"}


def preload_files(folder: Path | str = PRELOAD_DIR) -> list[Path]:
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTENSIONS)


def preload_if_empty(conn, folder: Path | str = PRELOAD_DIR) -> list[dict]:
    """يستورد ملفات المجلد ويحللها إن لم توجد أي مجموعة بيانات في القاعدة. يُرجع ملخصًا لكل ملف."""
    files = preload_files(folder)
    if not files or not database.list_datasets(conn).empty:
        return []
    results = []
    for path in files:
        with open(path, "rb") as fh:
            df = importer.read_table(fh, path.name)
        mapping = importer.ColumnMapping(**importer.suggest_mapping(df))
        report = importer.prepare_dataframe(df, mapping, default_source="ملف مستورد")
        if not report.ok:
            results.append({"file": path.name, "inserted": 0, "analyzed": 0, "errors": report.errors})
            continue
        dataset_id = database.get_or_create_dataset(conn, path.stem, "file", False,
                                                    f"مستورد تلقائيًا من {path.name}")
        inserted = database.insert_reviews(conn, dataset_id, report.data)
        counts = pipeline.analyze_reviews(conn, [dataset_id], only_new=True)
        results.append({"file": path.name, "inserted": inserted["inserted"],
                        "analyzed": counts["analyzed"], "errors": []})
    return results
