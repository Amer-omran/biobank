"""Alembic migrations: upgrade, no drift vs. ORM models, downgrade. PostgreSQL runs when
HMD_TEST_POSTGRES_URL is set (e.g. postgresql+psycopg://user:pass@localhost:5432/hmd_test)."""

import os
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from alembic import command
from healthmisinfo.db.models import Base

BACKEND = Path(__file__).resolve().parents[1]
TABLES = {
    "users",
    "analyses",
    "datasets",
    "dataset_samples",
    "source_registry",
    "annotations",
    "expert_reviews",
    "model_versions",
    "training_runs",
    "audit_logs",
    "app_settings",
    "split_assignments",
}


def _cfg(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.attributes["database_url"] = url
    return cfg


def _clean(url: str) -> None:
    """Start from an empty schema (other tests may have used create_all on the same database)."""
    eng = create_engine(url)
    Base.metadata.drop_all(eng)
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    eng.dispose()


def _roundtrip(url: str):
    _clean(url)
    cfg = _cfg(url)
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    try:
        insp = inspect(eng)
        assert TABLES <= set(insp.get_table_names())
        idx = {i["name"] for i in insp.get_indexes("dataset_samples")}
        assert {"ix_samples_match_key", "ix_samples_group", "ix_samples_review_status"} <= idx
        with eng.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == [], f"ORM models and migrations differ: {diff}"
    finally:
        eng.dispose()
    command.downgrade(cfg, "base")
    eng = create_engine(url)
    assert not (TABLES & set(inspect(eng).get_table_names()))
    eng.dispose()


def test_migrations_sqlite(tmp_path):
    _roundtrip(f"sqlite:///{tmp_path / 'm.db'}")


@pytest.mark.skipif(not os.environ.get("HMD_TEST_POSTGRES_URL"), reason="HMD_TEST_POSTGRES_URL not set")
def test_migrations_postgres():
    _roundtrip(os.environ["HMD_TEST_POSTGRES_URL"])
