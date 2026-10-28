"""اختبار دخان للواجهة: كل صفحة يجب أن تعمل دون أخطاء، بقاعدة فارغة وبقاعدة فيها بيانات."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from sra import config, database, demo_data, pipeline

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["home", "import_data", "sentiment_page", "dishes_page", "compare_page", "reports_page",
         "model_page", "dictionary_page"]


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "ui.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    # لا نلمس نموذج المستخدم المدرب أثناء الاختبار
    monkeypatch.setattr(config, "SKLEARN_META_PATH", tmp_path / "meta.json")
    st.cache_resource.clear()
    yield path
    st.cache_resource.clear()


def run_page(name):
    at = AppTest.from_file(str(ROOT / "ui_pages" / f"{name}.py"), default_timeout=60)
    at.run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_with_empty_database(temp_db, page):
    at = run_page(page)
    assert not at.exception, at.exception


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_with_demo_data(temp_db, page):
    with database.session(temp_db) as conn:
        demo_data.load_demo_into_db(conn)
        pipeline.analyze_reviews(conn)
    at = run_page(page)
    assert not at.exception, at.exception


def test_home_demo_button_loads_data(temp_db):
    at = run_page("home")
    at.button[0].click().run()
    assert not at.exception
    with database.session(temp_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] > 600
