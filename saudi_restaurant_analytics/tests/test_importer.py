import io

import pandas as pd
import pytest

from sra import importer
from sra.importer import ColumnMapping, prepare_dataframe, read_table, suggest_mapping


class Upload(io.BytesIO):
    def __init__(self, data, name):
        super().__init__(data)
        self.name = name


def test_read_csv_utf8_and_cp1256():
    content = "التعليق,المطعم\nالأكل لذيذ,مطعم أ\n"
    for enc in ("utf-8-sig", "cp1256"):
        df = read_table(Upload(content.encode(enc), "f.csv"))
        assert list(df.columns) == ["التعليق", "المطعم"] and df.iloc[0, 0] == "الأكل لذيذ"


def test_read_csv_semicolon_delimiter():
    df = read_table(Upload("نص;تقييم\nممتاز;5\n".encode("utf-8"), "f.csv"))
    assert list(df.columns) == ["نص", "تقييم"]


def test_read_excel(tmp_path):
    path = tmp_path / "f.xlsx"
    pd.DataFrame({"review": ["حلو"], "stars": [5]}).to_excel(path, index=False)
    assert read_table(path).iloc[0]["review"] == "حلو"


def test_unsupported_and_empty_files():
    with pytest.raises(ValueError):
        read_table(Upload(b"x", "f.pdf"))
    with pytest.raises(ValueError):
        read_table(Upload(b"", "f.csv"))


def test_nested_columns_are_stringified():
    df = importer.stringify_nested(pd.DataFrame({"t": ["a"], "triplets": [[{"aspect": "اكل"}]]}))
    assert df.iloc[0]["triplets"] == '[{"aspect": "اكل"}]'


def test_suggest_mapping_by_name_and_content():
    df = pd.DataFrame({"Review Text": ["الأكل لذيذ جدا"], "Restaurant": ["أ"], "date": ["2025-01-01"],
                       "Rating": [4], "City": ["جدة"]})
    s = suggest_mapping(df)
    assert s["text"] == "Review Text" and s["restaurant"] == "Restaurant" and s["rating"] == "Rating"
    unnamed = pd.DataFrame({"c1": ["1", "2"], "c2": ["الكبسة لذيذة جدا والخدمة ممتازة", "سيء"]})
    assert suggest_mapping(unnamed)["text"] == "c2"


def test_prepare_validates_and_reports():
    df = pd.DataFrame({
        "t": ["الأكل لذيذ", "", None, "الأكل لذيذ", "الخدمة سيئة 0551234567", "رائع"],
        "d": ["2025-01-05", "2025-01-05", "x", "2025-01-05", "not a date", "05/02/2025"],
        "r": ["4", "5", "3", "4", "عشرة", "15"],
        "c": ["جده", "Riyadh", "الرياض", "جده", "قرية ما", None],
        "l": ["positive", "neg", "محايد", "positive", "سلبي", "???"],
    })
    report = prepare_dataframe(df, ColumnMapping(text="t", date="d", rating="r", city="c", label="l"))
    assert report.total_rows == 6
    assert report.empty_text_rows == 2
    assert report.duplicate_rows == 1
    assert report.valid_rows == 3
    assert report.invalid_dates == 1
    assert report.invalid_ratings == 2
    assert report.unknown_labels == 1
    assert report.unrecognized_cities == 1
    data = report.data
    assert data.iloc[0]["city"] == "جدة"
    assert "0551234567" not in " ".join(data["text"])
    assert set(data["external_label"].dropna()) == {"positive", "negative"}
    assert report.ok


def test_missing_column_is_error():
    report = prepare_dataframe(pd.DataFrame({"a": ["x"]}), ColumnMapping(text="غير موجود"))
    assert not report.ok and report.errors


def test_ratings_to_labels():
    labels = importer.ratings_to_labels(pd.Series([1, 2, 3, 4, 5, None]))
    assert labels.tolist() == ["negative", "negative", "neutral", "positive", "positive", None]
    assert importer.ratings_to_labels(pd.Series([2, 9]), max_rating=10).tolist() == ["negative", "positive"]


def test_all_empty_texts_is_error():
    report = prepare_dataframe(pd.DataFrame({"t": ["", None, " "]}), ColumnMapping(text="t"))
    assert not report.ok and report.empty_text_rows == 3 and report.valid_rows == 0
