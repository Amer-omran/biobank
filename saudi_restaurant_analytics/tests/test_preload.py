import pandas as pd

from sra import database, preload


def test_preload_imports_and_analyzes_only_when_empty(tmp_path):
    folder = tmp_path / "preload"
    folder.mkdir()
    pd.DataFrame({
        "review_id": ["R1", "R2"],
        "review_text": ["الكبسة لذيذة والخدمة ممتازة", "الأكل بارد والسعر غالي"],
        "place_id": ["مطعم أ", "مطعم ب"],
        "gold_label": ["positive", "negative"],
    }).to_csv(folder / "train_split_platform.csv", index=False)
    conn = database.connect(tmp_path / "t.db")

    results = preload.preload_if_empty(conn, folder)
    assert results == [{"file": "train_split_platform.csv", "inserted": 2, "analyzed": 2, "errors": []}]
    assert list(database.list_datasets(conn)["name"]) == ["train_split_platform"]
    # لا يُعاد الاستيراد ما دامت القاعدة تحتوي بيانات
    assert preload.preload_if_empty(conn, folder) == []


def test_preload_without_folder_does_nothing(tmp_path):
    conn = database.connect(tmp_path / "t.db")
    assert preload.preload_if_empty(conn, tmp_path / "missing") == []
