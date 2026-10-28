import sqlite3

import pandas as pd
import pytest

from sra import database
from sra.importer import ColumnMapping, prepare_dataframe
from sra.sentiment import AspectResult, SentimentResult


def make_records(texts, restaurant="مطعم أ", date="2025-01-01"):
    df = pd.DataFrame({"t": texts, "r": restaurant, "d": date})
    return prepare_dataframe(df, ColumnMapping(text="t", restaurant="r", date="d"), dedupe=False).data


def test_schema_created_and_dishes_seeded(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"datasets", "reviews", "analyses", "aspects", "dishes", "review_dishes"} <= tables
    assert conn.execute("SELECT COUNT(*) FROM dishes").fetchone()[0] > 40
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_foreign_key_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO analyses (review_id, model_name, model_version, sentiment, confidence, analyzed_at)"
                     " VALUES (999, 'x', 'v', 'positive', 0.5, 'now')")


def test_check_constraints(conn):
    ds = database.get_or_create_dataset(conn, "x", "file")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO reviews (dataset_id, text, clean_text, text_hash, imported_at) VALUES (?,?,?,?,?)",
                     (ds, "   ", "", "h", "now"))


def test_dedupe_and_reimport(conn):
    ds = database.get_or_create_dataset(conn, "ملف", "file")
    records = make_records(["الأكل لذيذ", "الخدمة سيئة"])
    assert database.insert_reviews(conn, ds, records) == {"inserted": 2, "skipped_duplicates": 0}
    assert database.insert_reviews(conn, ds, records) == {"inserted": 0, "skipped_duplicates": 2}


def test_keep_duplicates_option(conn):
    ds = database.get_or_create_dataset(conn, "ملف", "file")
    records = make_records(["ممتاز", "ممتاز"])
    assert database.insert_reviews(conn, ds, records, keep_duplicates=True)["inserted"] == 2
    assert database.insert_reviews(conn, ds, make_records(["ممتاز"]), keep_duplicates=True)["inserted"] == 1


def test_restaurant_name_unified(conn):
    ds = database.get_or_create_dataset(conn, "ملف", "file")
    database.insert_reviews(conn, ds, make_records(["حلو"], restaurant="مطعم الأصالة"))
    database.insert_reviews(conn, ds, make_records(["زين"], restaurant="مطعم الاصالة"))
    names = {r[0] for r in conn.execute("SELECT restaurant_name FROM reviews")}
    assert names == {"مطعم الأصالة"}


def _result(version="v1"):
    return SentimentResult("positive", 0.8, False, False, 1.5, 0.0,
                           aspects=[AspectResult("food_quality", "positive", 1.5, 0.85, "الكبسة لذيذة", "كبسة")],
                           model_version=version)


def test_save_analysis_replaces_same_version_and_cascades(conn):
    ds = database.get_or_create_dataset(conn, "ملف", "file")
    database.insert_reviews(conn, ds, make_records(["الكبسة لذيذة"]))
    review_id = conn.execute("SELECT id FROM reviews").fetchone()[0]
    ids = database.dish_id_map(conn)
    database.save_analysis(conn, review_id, _result(), ids)
    database.save_analysis(conn, review_id, _result(), ids)
    assert conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM aspects").fetchone()[0] == 1
    assert conn.execute("SELECT dish_id FROM aspects").fetchone()[0] == ids["كبسة"]
    database.save_analysis(conn, review_id, _result("v2"), ids)
    assert conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 2
    database.delete_dataset(conn, ds)
    for table in ("reviews", "analyses", "aspects"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert database.integrity_report(conn) == {"foreign_key_violations": 0, "integrity": "ok"}


def test_sync_dishes_deactivates_removed(conn):
    from sra.dishes import Dish

    database.sync_dishes(conn, [Dish("كبسة", "سعودي", ["كبسه"])])
    active = [r["canonical_name"] for r in database.dish_records(conn)]
    assert active == ["كبسة"]
