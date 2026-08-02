"""HTTP server for the biobank system.

Exposes a cookie-authenticated JSON API and serves the web UI, built on the
standard library's http.server. Access control is enforced here:

* every /api endpoint except /login and /health requires a valid session;
* only administrators may delete records, import spreadsheets, list users,
  and set the restricted fields (barcode, freezer/shelf/plate numbers);
* staff may view everything and create records for the non-restricted fields.

Run with:  python -m biobank.server      # http://127.0.0.1:8000

Environment:
    BIOBANK_DB              sqlite path (default: biobank.db)
    BIOBANK_PORT            port (default: 8000)
    BIOBANK_SEED_PASSWORD   password for seeded admin/staff accounts
                            (default: printed on first run)
"""

from __future__ import annotations

import json
import os
import re
from http import cookies as http_cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

from .db import Database
from .importer import parse_file
from .options import OPTIONS, RESTRICTED_FIELDS, SAMPLE_FIELDS

COOKIE_NAME = "bb_session"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

Route = tuple[str, "re.Pattern[str]", str, bool]  # method, pattern, handler-name, admin_only


class AuthError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class BiobankHandler(BaseHTTPRequestHandler):
    db: Database
    routes: list[Route] = []

    # ----- low-level helpers ---------------------------------------------

    def _send_json(self, status: int, payload: Any, cookie: Optional[str] = None) -> None:
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str, content_type: str) -> None:
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except OSError:
            self._send_json(404, {"error": "not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_bytes(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(length) if length else b""

    def _read_json(self) -> dict[str, Any]:
        raw = self._read_bytes()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _cookie_token(self) -> Optional[str]:
        header = self.headers.get("Cookie")
        if not header:
            return None
        jar = http_cookies.SimpleCookie()
        try:
            jar.load(header)
        except http_cookies.CookieError:
            return None
        morsel = jar.get(COOKIE_NAME)
        return morsel.value if morsel else None

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query)

    # ----- dispatch -------------------------------------------------------

    def _dispatch(self, method: str) -> None:
        path = urlparse(self.path).path
        for route_method, pattern, handler_name, admin_only in self.routes:
            if route_method != method:
                continue
            match = pattern.fullmatch(path)
            if not match:
                continue
            handler = getattr(self, handler_name)
            try:
                user = None
                if handler_name not in ("h_index", "h_static", "h_health", "h_login"):
                    user = self.db.get_session_user(self._cookie_token())
                    if user is None:
                        raise AuthError(401, "authentication required")
                    if admin_only and user["role"] != "admin":
                        raise AuthError(403, "administrator access required")
                handler(match, user)
            except AuthError as exc:
                self._send_json(exc.status, {"error": str(exc)})
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                self._send_json(500, {"error": str(exc)})
            return
        self._send_json(404, {"error": "not found"})

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def log_message(self, *args: Any) -> None:
        if os.environ.get("BIOBANK_VERBOSE"):
            super().log_message(*args)

    # ----- static ---------------------------------------------------------

    def h_index(self, match: "re.Match[str]", user: Any) -> None:
        self._send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")

    def h_static(self, match: "re.Match[str]", user: Any) -> None:
        name = match.group("name")
        if "/" in name or ".." in name:
            self._send_json(404, {"error": "not found"})
            return
        ext = name.rsplit(".", 1)[-1].lower()
        ctype = {"js": "application/javascript", "css": "text/css", "html": "text/html"}.get(
            ext, "application/octet-stream"
        )
        self._send_file(os.path.join(STATIC_DIR, name), ctype + "; charset=utf-8")

    def h_health(self, match: "re.Match[str]", user: Any) -> None:
        self._send_json(200, {"status": "ok"})

    # ----- auth -----------------------------------------------------------

    def h_login(self, match: "re.Match[str]", user: Any) -> None:
        body = self._read_json()
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", ""))
        account = self.db.verify_credentials(username, password)
        if account is None:
            self._send_json(401, {"error": "wrong username or password"})
            return
        token = self.db.create_session(account["id"])
        cookie = (
            f"{COOKIE_NAME}={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age={8*60*60}"
        )
        self._send_json(200, {"user": self._public_user(account)}, cookie=cookie)

    def h_logout(self, match: "re.Match[str]", user: Any) -> None:
        self.db.delete_session(self._cookie_token())
        cookie = f"{COOKIE_NAME}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0"
        self._send_json(200, {"ok": True}, cookie=cookie)

    def h_me(self, match: "re.Match[str]", user: Any) -> None:
        self._send_json(200, {"user": self._public_user(user)})

    @staticmethod
    def _public_user(user: dict[str, Any]) -> dict[str, Any]:
        return {"username": user["username"], "name": user["name"], "role": user["role"]}

    # ----- reference data -------------------------------------------------

    def h_options(self, match: "re.Match[str]", user: Any) -> None:
        self._send_json(200, {
            "options": OPTIONS,
            "fields": SAMPLE_FIELDS,
            "restricted": RESTRICTED_FIELDS,
        })

    def h_users(self, match: "re.Match[str]", user: Any) -> None:
        self._send_json(200, {"users": self.db.list_users()})

    def h_create_user(self, match: "re.Match[str]", user: Any) -> None:
        body = self._read_json()
        username = str(body.get("username", "")).strip()
        name = str(body.get("name", "")).strip()
        role = str(body.get("role", "")).strip()
        password = str(body.get("password", ""))
        if not username:
            raise ValueError("username is required")
        if not name:
            raise ValueError("name is required")
        if role not in ("admin", "staff"):
            raise ValueError("role must be 'admin' or 'staff'")
        if len(password) < 6:
            raise ValueError("password must be at least 6 characters")
        self._send_json(201, self.db.create_user(username, name, role, password))

    def h_delete_user(self, match: "re.Match[str]", user: Any) -> None:
        target = self.db.get_user(int(match.group("id")))
        if target is None:
            self._send_json(404, {"error": "user not found"})
            return
        if target["id"] == user["id"]:
            raise ValueError("you cannot delete your own account")
        if target["role"] == "admin" and self.db.count_admins() <= 1:
            raise ValueError("cannot delete the last administrator")
        self._send_json(200, {"deleted": self.db.delete_user(target["id"])})

    # ----- samples --------------------------------------------------------

    def h_list_samples(self, match: "re.Match[str]", user: Any) -> None:
        q = self._query()
        samples = self.db.list_samples(
            department=q.get("department", [None])[0],
            search=q.get("search", [None])[0],
        )
        self._send_json(200, {"samples": samples})

    def h_create_sample(self, match: "re.Match[str]", user: Any) -> None:
        data = {k: v for k, v in self._read_json().items() if k in SAMPLE_FIELDS}
        if user["role"] != "admin":
            for field in RESTRICTED_FIELDS:  # staff may not set these
                data.pop(field, None)
        sample = self.db.create_sample(data, created_by=user["username"])
        self._send_json(201, sample)

    def h_delete_sample(self, match: "re.Match[str]", user: Any) -> None:
        ok = self.db.delete_sample(int(match.group("id")))
        self._send_json(200 if ok else 404, {"deleted": ok})

    def h_import(self, match: "re.Match[str]", user: Any) -> None:
        filename = self._query().get("filename", ["upload.xlsx"])[0]
        raw = self._read_bytes()
        if not raw:
            raise ValueError("no file uploaded")
        records = parse_file(raw, filename)
        added, skipped = 0, 0
        for rec in records:
            try:
                self.db.create_sample(rec, created_by=user["username"])
                added += 1
            except ValueError:
                skipped += 1
        self._send_json(200, {"added": added, "skipped": skipped, "parsed": len(records)})


def _build_routes() -> list[Route]:
    p = re.compile
    return [
        ("GET", p(r"/"), "h_index", False),
        ("GET", p(r"/static/(?P<name>[\w.\-]+)"), "h_static", False),
        ("GET", p(r"/api/health"), "h_health", False),
        ("POST", p(r"/api/login"), "h_login", False),
        ("POST", p(r"/api/logout"), "h_logout", False),
        ("GET", p(r"/api/me"), "h_me", False),
        ("GET", p(r"/api/options"), "h_options", False),
        ("GET", p(r"/api/users"), "h_users", True),
        ("POST", p(r"/api/users"), "h_create_user", True),
        ("DELETE", p(r"/api/users/(?P<id>\d+)"), "h_delete_user", True),
        ("GET", p(r"/api/samples"), "h_list_samples", False),
        ("POST", p(r"/api/samples"), "h_create_sample", False),
        ("DELETE", p(r"/api/samples/(?P<id>\d+)"), "h_delete_sample", True),
        ("POST", p(r"/api/import"), "h_import", True),
    ]


SEED_USERS = [
    ("admin1", "Administrator 1", "admin"),
    ("admin2", "Administrator 2", "admin"),
    ("user1", "Lab User 1", "staff"),
    ("user2", "Lab User 2", "staff"),
    ("user3", "Lab User 3", "staff"),
    ("user4", "Lab User 4", "staff"),
]


def seed_users(db: Database, password: str) -> bool:
    """Seed the six default accounts if none exist. Returns True if seeded."""
    if db.count_users() > 0:
        return False
    for username, name, role in SEED_USERS:
        db.create_user(username, name, role, password)
    return True


def make_server(
    host: str = "127.0.0.1", port: int = 8000, db_path: Optional[str] = None,
    seed_password: Optional[str] = None,
) -> ThreadingHTTPServer:
    db = Database(db_path or os.environ.get("BIOBANK_DB", "biobank.db"))
    pw = seed_password or os.environ.get("BIOBANK_SEED_PASSWORD") or "ChangeMe@123"
    seeded = seed_users(db, pw)
    handler_cls = type("BoundBiobankHandler", (BiobankHandler,), {"db": db})
    handler_cls.routes = _build_routes()
    server = ThreadingHTTPServer((host, port), handler_cls)
    server.biobank_db = db  # type: ignore[attr-defined]
    server.seeded = seeded  # type: ignore[attr-defined]
    server.seed_password = pw  # type: ignore[attr-defined]
    return server


def main() -> None:
    port = int(os.environ.get("BIOBANK_PORT", "8000"))
    server = make_server(port=port)
    if server.seeded:  # type: ignore[attr-defined]
        print("Seeded default accounts (admin1, admin2, user1-4).")
        print(f"  Password for all seeded accounts: {server.seed_password}")  # type: ignore[attr-defined]
        print("  Set BIOBANK_SEED_PASSWORD before first run to choose your own.")
    print(f"Biobank server listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        server.server_close()
        server.biobank_db.close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
