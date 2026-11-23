"""Shared fixtures. Every test runs against a fresh, throw-away database and temp data directory."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="hmd-test-"))
os.environ["HMD_ENVIRONMENT"] = "test"
os.environ["HMD_DATABASE_URL"] = f"sqlite:///{_TMP / 'default.db'}"
os.environ["HMD_DATA_DIR"] = str(_TMP / "data")
os.environ["HMD_MODELS_DIR"] = str(_TMP / "models")
os.environ["HMD_RATE_LIMIT_ANALYZE"] = "1000"
os.environ["HMD_RATE_LIMIT_LOGIN"] = "1000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from healthmisinfo.config import get_settings  # noqa: E402
from healthmisinfo.data.registry import seed_registry  # noqa: E402
from healthmisinfo.db.models import Base  # noqa: E402
from healthmisinfo.db.session import SessionLocal, make_engine, set_engine  # noqa: E402
from healthmisinfo.ratelimit import limiter  # noqa: E402
from healthmisinfo.users import create_user  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
PASSWORD = "Test-Passw0rd!"


@pytest.fixture()
def engine(tmp_path):
    url = os.environ.get("HMD_TEST_POSTGRES_URL") if os.environ.get("HMD_TEST_USE_POSTGRES") else None
    eng = make_engine(url or f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    set_engine(eng)
    with SessionLocal() as db:
        seed_registry(db)
        db.commit()
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client(engine):
    from healthmisinfo.main import app

    limiter.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def users(db):
    out = {}
    for role, email in [("admin", "admin@test.local"), ("reviewer", "rev1@test.local"), ("reviewer", "rev2@test.local"), ("researcher", "res@test.local")]:
        u = create_user(db, email, f"{role} user", PASSWORD, role)
        out[email.split("@")[0]] = u
    db.commit()
    return out


def bearer(client, email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def auth(client, users):
    return {name: bearer(client, u.email) for name, u in users.items()}


@pytest.fixture()
def settings():
    return get_settings()
