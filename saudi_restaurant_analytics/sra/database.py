"""قاعدة بيانات SQLite: إنشاء الجداول تلقائيًا، وحفظ التعليقات ونتائج التحليل.

الجداول الأساسية:
- datasets: مجموعات البيانات المستوردة (ملف، بيانات تجريبية، API...).
- reviews: التعليقات ومصدرها وتاريخها والمطعم والمدينة والتقييم الأصلي.
- analyses: نتيجة تحليل كل تعليق ودرجة الثقة وإصدار النموذج وتاريخ التحليل.
- aspects: جوانب الرأي والشعور المرتبط بها والعبارة الداعمة.
- dishes: أسماء الوجبات الموحدة ومرادفاتها.
- review_dishes: ربط التحليل بالوجبات المذكورة في التعليق (علاقة متعدد-لمتعدد).

لا نخزن أسماء المستخدمين أو معرفاتهم أو أرقامهم.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config
from .dishes import Dish, load_dishes_csv
from .text_processing import normalize_arabic

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    source_type   TEXT NOT NULL,
    is_synthetic  INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0, 1)),
    description   TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id       INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    text             TEXT NOT NULL CHECK (length(trim(text)) > 0),
    clean_text       TEXT NOT NULL,
    text_hash        TEXT NOT NULL,
    dup_index        INTEGER NOT NULL DEFAULT 0,
    source           TEXT,
    review_date      TEXT,
    restaurant_name  TEXT,
    restaurant_key   TEXT NOT NULL DEFAULT '',
    city             TEXT,
    original_rating  REAL CHECK (original_rating IS NULL OR original_rating >= 0),
    external_label   TEXT CHECK (external_label IS NULL OR external_label IN ('positive','negative','neutral')),
    imported_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_reviews_dedupe
    ON reviews (dataset_id, restaurant_key, text_hash, IFNULL(review_date, ''), dup_index);
CREATE INDEX IF NOT EXISTS ix_reviews_restaurant ON reviews (restaurant_name);
CREATE INDEX IF NOT EXISTS ix_reviews_date ON reviews (review_date);

CREATE TABLE IF NOT EXISTS analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id       INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    model_name      TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    sentiment       TEXT NOT NULL CHECK (sentiment IN ('positive','negative','neutral')),
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    is_mixed        INTEGER NOT NULL DEFAULT 0 CHECK (is_mixed IN (0, 1)),
    is_uncertain    INTEGER NOT NULL DEFAULT 0 CHECK (is_uncertain IN (0, 1)),
    positive_score  REAL,
    negative_score  REAL,
    cues            TEXT,
    analyzed_at     TEXT NOT NULL,
    UNIQUE (review_id, model_version)
);
CREATE INDEX IF NOT EXISTS ix_analyses_review ON analyses (review_id);

CREATE TABLE IF NOT EXISTS dishes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name  TEXT NOT NULL UNIQUE,
    category        TEXT,
    synonyms        TEXT NOT NULL DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS aspects (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id  INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    aspect       TEXT NOT NULL CHECK (aspect IN ('food_quality','price','quantity','service',
                                                 'delivery','cleanliness','ambiance')),
    sentiment    TEXT NOT NULL CHECK (sentiment IN ('positive','negative','neutral')),
    score        REAL NOT NULL,
    confidence   REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence     TEXT NOT NULL,
    has_opinion  INTEGER NOT NULL DEFAULT 1 CHECK (has_opinion IN (0, 1)),
    dish_id      INTEGER REFERENCES dishes(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_aspects_analysis ON aspects (analysis_id);

CREATE TABLE IF NOT EXISTS review_dishes (
    analysis_id   INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    dish_id       INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    matched_text  TEXT NOT NULL,
    sentiment     TEXT NOT NULL CHECK (sentiment IN ('positive','negative','neutral')),
    evidence      TEXT NOT NULL,
    PRIMARY KEY (analysis_id, dish_id)
);

-- أحدث تحليل لكل تعليق (بغض النظر عن النموذج)
CREATE VIEW IF NOT EXISTS latest_analyses AS
    SELECT a.* FROM analyses a
    WHERE a.id = (SELECT MAX(id) FROM analyses b WHERE b.review_id = a.review_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """يفتح قاعدة البيانات (وينشئها مع الجداول عند أول تشغيل)."""
    path = Path(path) if path is not None else config.DB_PATH
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


@contextmanager
def session(path: Path | str | None = None):
    """استخدام آمن: يحفظ التغييرات عند النجاح ويتراجع عنها عند الخطأ ثم يغلق الاتصال."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection, dishes_csv: Path | str | None = None) -> None:
    conn.executescript(SCHEMA)
    count = conn.execute("SELECT COUNT(*) FROM dishes").fetchone()[0]
    csv_path = Path(dishes_csv) if dishes_csv else config.DISHES_CSV
    if count == 0 and csv_path.exists():
        sync_dishes(conn, load_dishes_csv(csv_path))
    conn.commit()


# ================================================================ datasets
def get_or_create_dataset(conn, name: str, source_type: str, is_synthetic: bool = False,
                          description: str | None = None) -> int:
    row = conn.execute("SELECT id FROM datasets WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO datasets (name, source_type, is_synthetic, description, created_at) VALUES (?,?,?,?,?)",
        (name, source_type, int(is_synthetic), description, now_iso()),
    )
    conn.commit()
    return cur.lastrowid


def list_datasets(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT d.id, d.name, d.source_type, d.is_synthetic, d.description, d.created_at,
                  COUNT(r.id) AS n_reviews
           FROM datasets d LEFT JOIN reviews r ON r.dataset_id = d.id
           GROUP BY d.id ORDER BY d.id""",
        conn,
    )


def delete_dataset(conn, dataset_id: int) -> None:
    """حذف مجموعة بيانات مع كل تعليقاتها وتحليلاتها (حذف متسلسل عبر المفاتيح الخارجية)."""
    conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    conn.commit()


# ================================================================= reviews
def _restaurant_names(conn) -> dict[str, str]:
    rows = conn.execute(
        "SELECT restaurant_key, MIN(restaurant_name) AS name FROM reviews "
        "WHERE restaurant_key != '' GROUP BY restaurant_key"
    ).fetchall()
    return {r["restaurant_key"]: r["name"] for r in rows}


def insert_reviews(conn, dataset_id: int, records: pd.DataFrame, keep_duplicates: bool = False) -> dict:
    """يدرج التعليقات المجهزة (من importer.prepare_dataframe).

    keep_duplicates=False: التعليق المطابق (النص+المطعم+التاريخ) يُتجاهل.
    keep_duplicates=True: يُحفظ كل تكرار برقم تكرار مختلف (dup_index).
    """
    known_names = _restaurant_names(conn)
    inserted = skipped = 0
    imported_at = now_iso()
    for rec in records.to_dict("records"):
        name = rec.get("restaurant_name") or None
        key = normalize_arabic(name) if name else ""
        if key:
            # توحيد كتابة اسم المطعم مع ما هو موجود مسبقًا
            name = known_names.setdefault(key, name)
        date = rec.get("review_date") or None
        base = (key, rec["text_hash"], date or "")
        dup_index = 0
        if keep_duplicates:
            # رقم التكرار التالي بعد أكبر رقم محفوظ (يشمل ما أُدرج في هذه الدفعة نفسها)
            last = conn.execute(
                "SELECT MAX(dup_index) FROM reviews WHERE dataset_id=? AND restaurant_key=? AND text_hash=? "
                "AND IFNULL(review_date,'')=?", (dataset_id, *base),
            ).fetchone()[0]
            dup_index = 0 if last is None else last + 1
        cur = conn.execute(
            """INSERT OR IGNORE INTO reviews
               (dataset_id, text, clean_text, text_hash, dup_index, source, review_date,
                restaurant_name, restaurant_key, city, original_rating, external_label, imported_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (dataset_id, rec["text"], rec["clean_text"], rec["text_hash"], dup_index,
             rec.get("source"), date, name, key, rec.get("city") or None,
             rec.get("original_rating"), rec.get("external_label"), imported_at),
        )
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return {"inserted": inserted, "skipped_duplicates": skipped}


def fetch_reviews(conn, dataset_ids=None, only_unanalyzed_for: str | None = None) -> pd.DataFrame:
    sql = "SELECT r.* FROM reviews r WHERE 1=1"
    params: list = []
    if dataset_ids:
        sql += f" AND r.dataset_id IN ({','.join('?' * len(dataset_ids))})"
        params.extend(int(i) for i in dataset_ids)
    if only_unanalyzed_for:
        sql += " AND NOT EXISTS (SELECT 1 FROM analyses a WHERE a.review_id = r.id AND a.model_version = ?)"
        params.append(only_unanalyzed_for)
    return pd.read_sql_query(sql + " ORDER BY r.id", conn, params=params)


# ================================================================== dishes
def sync_dishes(conn, dishes: list[Dish]) -> None:
    """يضيف الوجبات الجديدة ويحدّث المرادفات والفئة للموجودة. لا يحذف وجبات مرتبطة بتحليلات."""
    for d in dishes:
        conn.execute(
            """INSERT INTO dishes (canonical_name, category, synonyms) VALUES (?,?,?)
               ON CONFLICT(canonical_name) DO UPDATE SET category=excluded.category,
               synonyms=excluded.synonyms, is_active=1""",
            (d.canonical_name, d.category, "|".join(d.synonyms)),
        )
    names = [d.canonical_name for d in dishes]
    if names:
        conn.execute(
            f"UPDATE dishes SET is_active=0 WHERE canonical_name NOT IN ({','.join('?' * len(names))})",
            names,
        )
    conn.commit()


def dish_records(conn, active_only: bool = True) -> list[sqlite3.Row]:
    sql = "SELECT * FROM dishes" + (" WHERE is_active=1" if active_only else "") + " ORDER BY id"
    return conn.execute(sql).fetchall()


def dish_id_map(conn) -> dict[str, int]:
    return {r["canonical_name"]: r["id"] for r in conn.execute("SELECT id, canonical_name FROM dishes")}


# ================================================================ analyses
def save_analysis(conn, review_id: int, result, dish_ids: dict[str, int], commit: bool = True) -> int:
    """يحفظ نتيجة تحليل تعليق؛ إعادة التحليل بالإصدار نفسه تستبدل النتيجة السابقة."""
    conn.execute("DELETE FROM analyses WHERE review_id=? AND model_version=?",
                 (review_id, result.model_version))
    cur = conn.execute(
        """INSERT INTO analyses (review_id, model_name, model_version, sentiment, confidence,
                                 is_mixed, is_uncertain, positive_score, negative_score, cues, analyzed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (review_id, result.model_name, result.model_version, result.label, float(result.confidence),
         int(result.is_mixed), int(result.is_uncertain), result.positive_score, result.negative_score,
         "، ".join(result.cues), now_iso()),
    )
    analysis_id = cur.lastrowid
    for a in result.aspects:
        conn.execute(
            """INSERT INTO aspects (analysis_id, aspect, sentiment, score, confidence, evidence,
                                   has_opinion, dish_id) VALUES (?,?,?,?,?,?,?,?)""",
            (analysis_id, a.aspect, a.sentiment, a.score, a.confidence, a.evidence,
             int(a.has_opinion), dish_ids.get(a.dish) if a.dish else None),
        )
    for d in result.dishes:
        dish_id = dish_ids.get(d.dish)
        if dish_id is None:
            continue
        conn.execute(
            """INSERT OR IGNORE INTO review_dishes (analysis_id, dish_id, matched_text, sentiment, evidence)
               VALUES (?,?,?,?,?)""",
            (analysis_id, dish_id, d.matched_text, d.sentiment, d.evidence),
        )
    if commit:
        conn.commit()
    return analysis_id


def model_versions(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT model_version FROM analyses GROUP BY model_version ORDER BY MAX(id) DESC")]


def integrity_report(conn) -> dict:
    """فحص سلامة العلاقات: أي سجلات يتيمة تعني خللًا في المفاتيح الخارجية."""
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    return {
        "foreign_key_violations": len(fk_violations),
        "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
    }
