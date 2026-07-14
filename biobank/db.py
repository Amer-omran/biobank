"""Database layer for the biobank system.

A thin wrapper around sqlite3 that manages the schema and provides
CRUD helpers for donors and samples. Kept dependency-free on purpose so
the whole project runs with a stock Python install.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS donors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL UNIQUE,
    full_name   TEXT    NOT NULL,
    birth_year  INTEGER,
    sex         TEXT    CHECK (sex IN ('M', 'F', 'O') OR sex IS NULL),
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id      INTEGER NOT NULL REFERENCES donors(id) ON DELETE CASCADE,
    sample_type   TEXT    NOT NULL,
    volume_ml     REAL,
    storage_temp  INTEGER,
    location      TEXT,
    status        TEXT    NOT NULL DEFAULT 'stored'
                          CHECK (status IN ('stored', 'in_use', 'depleted', 'discarded')),
    collected_at  TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_samples_donor ON samples(donor_id);
CREATE INDEX IF NOT EXISTS idx_samples_status ON samples(status);
"""

SAMPLE_STATUSES = ("stored", "in_use", "depleted", "discarded")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """SQLite-backed store for donors and samples."""

    def __init__(self, path: str = "biobank.db") -> None:
        self.path = path
        # The HTTP server serves each request on its own thread, so the
        # connection is shared across threads and guarded by a lock.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._lock = threading.RLock()

    def close(self) -> None:
        self.conn.close()

    # ----- donors ---------------------------------------------------------

    def create_donor(
        self,
        code: str,
        full_name: str,
        birth_year: Optional[int] = None,
        sex: Optional[str] = None,
    ) -> dict[str, Any]:
        if not code or not code.strip():
            raise ValueError("donor 'code' is required")
        if not full_name or not full_name.strip():
            raise ValueError("donor 'full_name' is required")
        if sex is not None and sex not in ("M", "F", "O"):
            raise ValueError("donor 'sex' must be one of M, F, O")
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO donors (code, full_name, birth_year, sex, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (code.strip(), full_name.strip(), birth_year, sex, _now()),
            )
            self.conn.commit()
            return self.get_donor(cur.lastrowid)  # type: ignore[arg-type]

    def get_donor(self, donor_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM donors WHERE id = ?", (donor_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_donors(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM donors ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_donor(self, donor_id: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM donors WHERE id = ?", (donor_id,))
            self.conn.commit()
            return cur.rowcount > 0

    # ----- samples --------------------------------------------------------

    def create_sample(
        self,
        donor_id: int,
        sample_type: str,
        volume_ml: Optional[float] = None,
        storage_temp: Optional[int] = None,
        location: Optional[str] = None,
        collected_at: Optional[str] = None,
    ) -> dict[str, Any]:
        if self.get_donor(donor_id) is None:
            raise ValueError(f"donor {donor_id} does not exist")
        if not sample_type or not sample_type.strip():
            raise ValueError("sample 'sample_type' is required")
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO samples "
                "(donor_id, sample_type, volume_ml, storage_temp, location, "
                " collected_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    donor_id,
                    sample_type.strip(),
                    volume_ml,
                    storage_temp,
                    location,
                    collected_at or _now(),
                    _now(),
                ),
            )
            self.conn.commit()
            return self.get_sample(cur.lastrowid)  # type: ignore[arg-type]

    def get_sample(self, sample_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM samples WHERE id = ?", (sample_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_samples(
        self, donor_id: Optional[int] = None, status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM samples"
        clauses: list[str] = []
        params: list[Any] = []
        if donor_id is not None:
            clauses.append("donor_id = ?")
            params.append(donor_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC"
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def update_sample_status(self, sample_id: int, status: str) -> Optional[dict[str, Any]]:
        if status not in SAMPLE_STATUSES:
            raise ValueError(f"status must be one of {', '.join(SAMPLE_STATUSES)}")
        with self._lock:
            cur = self.conn.execute(
                "UPDATE samples SET status = ? WHERE id = ?", (status, sample_id)
            )
            self.conn.commit()
            if cur.rowcount == 0:
                return None
            return self.get_sample(sample_id)

    def delete_sample(self, sample_id: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM samples WHERE id = ?", (sample_id,))
            self.conn.commit()
            return cur.rowcount > 0

    # ----- stats ----------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        with self._lock:
            donors = self.conn.execute("SELECT COUNT(*) AS c FROM donors").fetchone()["c"]
            samples = self.conn.execute("SELECT COUNT(*) AS c FROM samples").fetchone()["c"]
            by_status = {
                r["status"]: r["c"]
                for r in self.conn.execute(
                    "SELECT status, COUNT(*) AS c FROM samples GROUP BY status"
                ).fetchall()
            }
            by_type = {
                r["sample_type"]: r["c"]
                for r in self.conn.execute(
                    "SELECT sample_type, COUNT(*) AS c FROM samples GROUP BY sample_type"
                ).fetchall()
            }
        return {
            "donors": donors,
            "samples": samples,
            "samples_by_status": by_status,
            "samples_by_type": by_type,
        }
