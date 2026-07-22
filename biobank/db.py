"""Database layer for the biobank system.

A dependency-free SQLite store (standard library only) covering:

* users        – credentials with salted PBKDF2 password hashes and a role
* sessions     – opaque login tokens backing cookie-based auth
* samples      – the sample registry (fields mirror the lab data form)

Access control is enforced at the HTTP layer (see server.py); this module
provides the primitives and never trusts a plaintext password on disk.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from .options import (
    NUMERIC_FIELDS,
    OPTIONS,
    REQUIRED_FIELDS,
    SAMPLE_FIELDS,
)

PBKDF2_ITERATIONS = 200_000
SESSION_TTL_SECONDS = 8 * 60 * 60  # 8 hours

_SAMPLE_COLUMNS = ", ".join(SAMPLE_FIELDS)
_SAMPLE_PLACEHOLDERS = ", ".join("?" for _ in SAMPLE_FIELDS)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'staff')),
    salt          TEXT NOT NULL,
    pw_hash       TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token         TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lab_number    TEXT,
    sample_number TEXT,
    storage_date  TEXT,
    storage_method TEXT,
    freezer_no    TEXT,
    shelf_no      TEXT,
    plate_no      TEXT,
    area          TEXT NOT NULL,
    animal_type   TEXT NOT NULL,
    sample_type   TEXT NOT NULL,
    quantity_ml   REAL,
    concentration TEXT,
    disease       TEXT,
    strain        TEXT,
    isolated      TEXT,
    isolation_date TEXT,
    passage_number TEXT,
    department    TEXT NOT NULL,
    barcode       TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id    INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size         INTEGER NOT NULL,
    data         BLOB NOT NULL,
    uploaded_by  TEXT,
    uploaded_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_att_sample ON attachments(sample_id);

CREATE TABLE IF NOT EXISTS sample_numbers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id     INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    sample_number TEXT NOT NULL,
    added_by      TEXT,
    added_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sn_sample ON sample_numbers(sample_id);

CREATE TABLE IF NOT EXISTS barcodes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id        INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    sample_number_id INTEGER REFERENCES sample_numbers(id) ON DELETE CASCADE,
    barcode          TEXT NOT NULL,
    added_by         TEXT,
    added_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bc_sample ON barcodes(sample_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    username    TEXT,
    action      TEXT NOT NULL,
    sample_id   INTEGER,
    summary     TEXT,
    details     TEXT
);

CREATE INDEX IF NOT EXISTS idx_samples_dept ON samples(department);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_id ON audit_log(id);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Return (salt_hex, hash_hex) using salted PBKDF2-HMAC-SHA256."""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return salt, dk.hex()


class Database:
    """SQLite-backed store for users, sessions and samples."""

    def __init__(self, path: str = "biobank.db") -> None:
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate_samples()
        self._migrate_barcodes()
        self.conn.commit()
        self._lock = threading.RLock()

    def _migrate_samples(self) -> None:
        """Add any sample columns missing from an older database, in place."""
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(samples)").fetchall()}
        for field in SAMPLE_FIELDS:
            if field not in existing:
                col_type = "REAL" if field in NUMERIC_FIELDS else "TEXT"
                self.conn.execute(f"ALTER TABLE samples ADD COLUMN {field} {col_type}")
        self.conn.commit()

    def _migrate_barcodes(self) -> None:
        """Link barcodes to a specific sample number (add the column if missing)."""
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(barcodes)").fetchall()}
        if "sample_number_id" not in cols:
            self.conn.execute("ALTER TABLE barcodes ADD COLUMN sample_number_id INTEGER")
        # index created here (after the column exists) — not in SCHEMA, which runs
        # before this migration on databases upgraded from an older version.
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_bc_sn ON barcodes(sample_number_id)")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ----- users ----------------------------------------------------------

    def create_user(self, username: str, name: str, role: str, password: str) -> dict[str, Any]:
        if role not in ("admin", "staff"):
            raise ValueError("role must be 'admin' or 'staff'")
        salt, pw_hash = hash_password(password)
        with self._lock:
            try:
                cur = self.conn.execute(
                    "INSERT INTO users (username, name, role, salt, pw_hash, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (username, name, role, salt, pw_hash, _iso(_now())),
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"username '{username}' already exists")
            self.conn.commit()
            return self._user_public(cur.lastrowid)  # type: ignore[arg-type]

    def _user_public(self, user_id: int) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT id, username, name, role, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else {}

    def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._user_public(user_id) or None

    def count_admins(self) -> int:
        with self._lock:
            return self.conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE role = 'admin'"
            ).fetchone()["c"]

    def delete_user(self, user_id: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.conn.commit()
            return cur.rowcount > 0

    def update_password(self, user_id: int, new_password: str) -> None:
        salt, pw_hash = hash_password(new_password)
        with self._lock:
            self.conn.execute(
                "UPDATE users SET salt = ?, pw_hash = ? WHERE id = ?", (salt, pw_hash, user_id)
            )
            self.conn.commit()

    def verify_credentials(self, username: str, password: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        if row is None:
            # Still run a hash to reduce timing signal on unknown usernames.
            hash_password(password)
            return None
        _, candidate = hash_password(password, row["salt"])
        if not hmac.compare_digest(candidate, row["pw_hash"]):
            return None
        return {"id": row["id"], "username": row["username"], "name": row["name"], "role": row["role"]}

    def count_users(self) -> int:
        with self._lock:
            return self.conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, username, name, role, created_at FROM users ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    # ----- sessions -------------------------------------------------------

    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        expires = now.timestamp() + SESSION_TTL_SECONDS
        with self._lock:
            self.conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user_id, _iso(now), _iso(datetime.fromtimestamp(expires, timezone.utc))),
            )
            self.conn.commit()
        return token

    def get_session_user(self, token: Optional[str]) -> Optional[dict[str, Any]]:
        if not token:
            return None
        with self._lock:
            row = self.conn.execute(
                "SELECT s.expires_at, u.id, u.username, u.name, u.role "
                "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
                (token,),
            ).fetchone()
            if row is None:
                return None
            if datetime.fromisoformat(row["expires_at"]) < _now():
                self.conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                self.conn.commit()
                return None
        return {"id": row["id"], "username": row["username"], "name": row["name"], "role": row["role"]}

    def delete_session(self, token: Optional[str]) -> None:
        if not token:
            return
        with self._lock:
            self.conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            self.conn.commit()

    # ----- samples --------------------------------------------------------

    def create_sample(self, data: dict[str, Any], created_by: Optional[str] = None) -> dict[str, Any]:
        values: list[Any] = []
        for field in SAMPLE_FIELDS:
            v = data.get(field)
            if isinstance(v, str):
                v = v.strip() or None
            if field in REQUIRED_FIELDS and not v:
                raise ValueError(f"'{field}' is required")
            if field in NUMERIC_FIELDS and v not in (None, ""):
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise ValueError(f"'{field}' must be a number")
            values.append(v)
        with self._lock:
            now = _iso(_now())
            cur = self.conn.execute(
                f"INSERT INTO samples ({_SAMPLE_COLUMNS}, created_by, created_at) "
                f"VALUES ({_SAMPLE_PLACEHOLDERS}, ?, ?)",
                (*values, created_by, now),
            )
            sid = cur.lastrowid
            # seed the primary sample number (and its barcode) as tree rows
            row = self.conn.execute(
                "SELECT sample_number, barcode FROM samples WHERE id = ?", (sid,)
            ).fetchone()
            if row["sample_number"]:
                snc = self.conn.execute(
                    "INSERT INTO sample_numbers (sample_id, sample_number, added_by, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    (sid, row["sample_number"], created_by, now),
                )
                if row["barcode"]:
                    self.conn.execute(
                        "INSERT INTO barcodes (sample_id, sample_number_id, barcode, added_by, added_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (sid, snc.lastrowid, row["barcode"], created_by, now),
                    )
            self.conn.commit()
            return self.get_sample(sid)  # type: ignore[arg-type]

    def update_sample(self, sample_id: int, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Partial update: only the provided (whitelisted) fields are changed."""
        columns: list[str] = []
        values: list[Any] = []
        for field in SAMPLE_FIELDS:
            if field not in data:
                continue
            v = data[field]
            if isinstance(v, str):
                v = v.strip() or None
            if field in REQUIRED_FIELDS and not v:
                raise ValueError(f"'{field}' is required")
            if field in NUMERIC_FIELDS and v not in (None, ""):
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise ValueError(f"'{field}' must be a number")
            columns.append(field)
            values.append(v)
        if not columns:
            return self.get_sample(sample_id)
        with self._lock:
            cur = self.conn.execute(
                f"UPDATE samples SET {', '.join(c + ' = ?' for c in columns)} WHERE id = ?",
                (*values, sample_id),
            )
            self.conn.commit()
            if cur.rowcount == 0:
                return None
            return self.get_sample(sample_id)

    def get_sample(self, sample_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
        return dict(row) if row else None

    def list_samples(
        self, department: Optional[str] = None, search: Optional[str] = None
    ) -> list[dict[str, Any]]:
        query = ("SELECT s.*, "
                 "(SELECT COUNT(*) FROM attachments a WHERE a.sample_id = s.id) AS attachments, "
                 "(SELECT COUNT(*) FROM barcodes b WHERE b.sample_id = s.id) AS barcode_count, "
                 "(SELECT COUNT(*) FROM sample_numbers n WHERE n.sample_id = s.id) AS sample_number_count, "
                 "(SELECT GROUP_CONCAT(barcode, ', ') FROM barcodes b WHERE b.sample_id = s.id) AS barcodes_text "
                 "FROM samples s")
        clauses: list[str] = []
        params: list[Any] = []
        if department:
            clauses.append("department = ?")
            params.append(department)
        if search:
            like = f"%{search.lower()}%"
            searchable = [f for f in SAMPLE_FIELDS if f not in NUMERIC_FIELDS]
            clauses.append("(" + " OR ".join(f"LOWER(IFNULL({f},'')) LIKE ?" for f in searchable) + ")")
            params.extend([like] * len(searchable))
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC"
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def delete_sample(self, sample_id: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM samples WHERE id = ?", (sample_id,))
            self.conn.commit()
            return cur.rowcount > 0

    # ----- attachments ----------------------------------------------------

    def add_attachment(
        self, sample_id: int, filename: str, data: bytes, uploaded_by: Optional[str],
        content_type: str = "application/pdf",
    ) -> dict[str, Any]:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO attachments (sample_id, filename, content_type, size, data, "
                "uploaded_by, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sample_id, filename, content_type, len(data), sqlite3.Binary(data),
                 uploaded_by, _iso(_now())),
            )
            self.conn.commit()
            return self.get_attachment_meta(cur.lastrowid)  # type: ignore[arg-type]

    def _attachment_meta_cols(self) -> str:
        return "id, sample_id, filename, content_type, size, uploaded_by, uploaded_at"

    def get_attachment_meta(self, att_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute(
                f"SELECT {self._attachment_meta_cols()} FROM attachments WHERE id = ?", (att_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_attachment(self, att_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM attachments WHERE id = ?", (att_id,)).fetchone()
        return dict(row) if row else None

    def list_attachments(self, sample_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                f"SELECT {self._attachment_meta_cols()} FROM attachments WHERE sample_id = ? ORDER BY id",
                (sample_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_attachment(self, att_id: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
            self.conn.commit()
            return cur.rowcount > 0

    # ----- barcodes (multiple per sample) ---------------------------------

    def add_barcode(self, sample_number_id: int, barcode: str, added_by: Optional[str]) -> dict[str, Any]:
        """Add a barcode that belongs to a specific sample number."""
        with self._lock:
            sn = self.conn.execute(
                "SELECT sample_id FROM sample_numbers WHERE id = ?", (sample_number_id,)
            ).fetchone()
            if sn is None:
                raise ValueError("sample number not found")
            cur = self.conn.execute(
                "INSERT INTO barcodes (sample_id, sample_number_id, barcode, added_by, added_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (sn["sample_id"], sample_number_id, barcode, added_by, _iso(_now())),
            )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM barcodes WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)

    def sample_structure(self, sample_id: int) -> Optional[dict[str, Any]]:
        """Return sample numbers each with their barcodes; seed the primary once."""
        with self._lock:
            sample = self.conn.execute(
                "SELECT sample_number, barcode FROM samples WHERE id = ?", (sample_id,)
            ).fetchone()
            if sample is None:
                return None
            nums = self.conn.execute(
                "SELECT * FROM sample_numbers WHERE sample_id = ? ORDER BY id", (sample_id,)
            ).fetchall()
            if not nums and sample["sample_number"]:
                cur = self.conn.execute(
                    "INSERT INTO sample_numbers (sample_id, sample_number, added_by, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    (sample_id, sample["sample_number"], None, _iso(_now())),
                )
                primary_id = cur.lastrowid
                if sample["barcode"]:
                    self.conn.execute(
                        "INSERT INTO barcodes (sample_id, sample_number_id, barcode, added_by, added_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (sample_id, primary_id, sample["barcode"], None, _iso(_now())),
                    )
                self.conn.commit()
                nums = self.conn.execute(
                    "SELECT * FROM sample_numbers WHERE sample_id = ? ORDER BY id", (sample_id,)
                ).fetchall()
            numbers = []
            for n in nums:
                bcs = self.conn.execute(
                    "SELECT * FROM barcodes WHERE sample_number_id = ? ORDER BY id", (n["id"],)
                ).fetchall()
                d = dict(n)
                d["barcodes"] = [dict(b) for b in bcs]
                numbers.append(d)
            unassigned = self.conn.execute(
                "SELECT * FROM barcodes WHERE sample_id = ? AND sample_number_id IS NULL ORDER BY id",
                (sample_id,),
            ).fetchall()
        return {"sample_numbers": numbers, "unassigned_barcodes": [dict(b) for b in unassigned]}

    def get_barcode(self, barcode_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM barcodes WHERE id = ?", (barcode_id,)).fetchone()
        return dict(row) if row else None

    def delete_barcode(self, barcode_id: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM barcodes WHERE id = ?", (barcode_id,))
            self.conn.commit()
            return cur.rowcount > 0

    # ----- sample numbers (multiple per sample) ---------------------------

    def add_sample_number(self, sample_id: int, sample_number: str, added_by: Optional[str]) -> dict[str, Any]:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO sample_numbers (sample_id, sample_number, added_by, added_at) "
                "VALUES (?, ?, ?, ?)",
                (sample_id, sample_number, added_by, _iso(_now())),
            )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM sample_numbers WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)

    def list_sample_numbers(self, sample_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM sample_numbers WHERE sample_id = ? ORDER BY id", (sample_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_sample_number(self, row_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM sample_numbers WHERE id = ?", (row_id,)).fetchone()
        return dict(row) if row else None

    def delete_sample_number(self, row_id: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM sample_numbers WHERE id = ?", (row_id,))
            self.conn.commit()
            return cur.rowcount > 0

    # ----- audit log ------------------------------------------------------

    def add_audit(
        self, username: Optional[str], action: str, sample_id: Optional[int],
        summary: str, details: Optional[str] = None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO audit_log (ts, username, action, sample_id, summary, details) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_iso(_now()), username, action, sample_id, summary, details),
            )
            self.conn.commit()

    def list_audit(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ----- stats ----------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self.conn.execute("SELECT COUNT(*) AS c FROM samples").fetchone()["c"]

            def group(field: str) -> dict[str, int]:
                return {
                    r[field]: r["c"]
                    for r in self.conn.execute(
                        f"SELECT {field}, COUNT(*) AS c FROM samples "
                        f"WHERE {field} IS NOT NULL AND {field} <> '' GROUP BY {field}"
                    ).fetchall()
                }

            return {
                "total": total,
                "by_department": group("department"),
                "by_sample_type": group("sample_type"),
                "by_animal_type": group("animal_type"),
            }
