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
from .docx_form import build_form_docx
from .exporter import build_xlsx
from .importer import parse_file
from .options import FIELD_LABELS, OPTIONS, RESTRICTED_FIELDS, SAMPLE_FIELDS
from .pdf import build_receipt_pdf

COOKIE_NAME = "bb_session"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB per file


def validate_pdf(filename: str, data: bytes) -> None:
    """Raise ValueError unless `data` is a non-empty PDF within the size limit."""
    if not data:
        raise ValueError("no file uploaded")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValueError("file too large (max 10 MB)")
    if not filename.lower().endswith(".pdf") or data.lstrip()[:4] != b"%PDF":
        raise ValueError("only PDF files are allowed")

Route = tuple[str, "re.Pattern[str]", str, bool]  # method, pattern, handler-name, admin_only


class AuthError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class BiobankHandler(BaseHTTPRequestHandler):
    db: Database
    routes: list[Route] = []
    secure_cookies: bool = False  # add the Secure flag when served behind HTTPS

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

    def _send_bytes(self, data: bytes, content_type: str, filename: str,
                    disposition: str = "attachment") -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'{disposition}; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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

    def _session_cookie(self, token: str, max_age: int) -> str:
        parts = [f"{COOKIE_NAME}={token}", "HttpOnly", "Path=/", "SameSite=Lax", f"Max-Age={max_age}"]
        if self.secure_cookies:
            parts.append("Secure")
        return "; ".join(parts)

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

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

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
        cookie = self._session_cookie(token, 8 * 60 * 60)
        self._send_json(200, {"user": self._public_user(account)}, cookie=cookie)

    def h_logout(self, match: "re.Match[str]", user: Any) -> None:
        self.db.delete_session(self._cookie_token())
        self._send_json(200, {"ok": True}, cookie=self._session_cookie("", 0))

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
        self.db.add_audit(
            user["username"], "create", sample["id"],
            f"created sample ({sample.get('sample_type') or '?'} · {sample.get('area') or '?'})",
        )
        self._send_json(201, sample)

    def h_update_sample(self, match: "re.Match[str]", user: Any) -> None:
        sample_id = int(match.group("id"))
        data = {k: v for k, v in self._read_json().items() if k in SAMPLE_FIELDS}
        if user["role"] != "admin":
            for field in RESTRICTED_FIELDS:  # staff cannot change these; leave them intact
                data.pop(field, None)
        before = self.db.get_sample(sample_id)
        sample = self.db.update_sample(sample_id, data)
        if sample is None:
            self._send_json(404, {"error": "sample not found"})
            return
        changes = {
            f: [before.get(f), sample.get(f)]
            for f in SAMPLE_FIELDS
            if before and before.get(f) != sample.get(f)
        }
        if changes:
            self.db.add_audit(
                user["username"], "update", sample_id,
                "updated " + ", ".join(changes.keys()),
                json.dumps(changes, ensure_ascii=False),
            )
        self._send_json(200, sample)

    def h_delete_sample(self, match: "re.Match[str]", user: Any) -> None:
        sample_id = int(match.group("id"))
        before = self.db.get_sample(sample_id)
        ok = self.db.delete_sample(sample_id)
        if ok:
            self.db.add_audit(
                user["username"], "delete", sample_id,
                f"deleted sample #{sample_id}"
                + (f" ({before.get('sample_type') or '?'} · {before.get('area') or '?'})" if before else ""),
            )
        self._send_json(200 if ok else 404, {"deleted": ok})

    def h_receipt(self, match: "re.Match[str]", user: Any) -> None:
        sample = self.db.get_sample(int(match.group("id")))
        if sample is None:
            self._send_json(404, {"error": "sample not found"})
            return
        self._send_bytes(build_receipt_pdf(sample), "application/pdf",
                         f"sample-{sample['id']}-receipt.pdf", disposition="inline")

    def h_form(self, match: "re.Match[str]", user: Any) -> None:
        sample = self.db.get_sample(int(match.group("id")))
        if sample is None:
            self._send_json(404, {"error": "sample not found"})
            return
        try:
            data = build_form_docx(sample)
        except FileNotFoundError:
            self._send_json(503, {"error": "the Word form template is not configured on the server"})
            return
        self._send_bytes(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            f"sample-{sample['id']}-storage-form.docx",
        )

    def h_list_attachments(self, match: "re.Match[str]", user: Any) -> None:
        sid = int(match.group("id"))
        if self.db.get_sample(sid) is None:
            self._send_json(404, {"error": "sample not found"})
            return
        self._send_json(200, {"attachments": self.db.list_attachments(sid)})

    def h_upload_attachment(self, match: "re.Match[str]", user: Any) -> None:
        sid = int(match.group("id"))
        if self.db.get_sample(sid) is None:
            self._send_json(404, {"error": "sample not found"})
            return
        filename = os.path.basename(self._query().get("filename", ["file.pdf"])[0])
        data = self._read_bytes()
        validate_pdf(filename, data)
        att = self.db.add_attachment(sid, filename, data, user["username"])
        self.db.add_audit(user["username"], "attach", sid, f"attached {filename}")
        self._send_json(201, att)

    def h_download_attachment(self, match: "re.Match[str]", user: Any) -> None:
        att = self.db.get_attachment(int(match.group("id")))
        if att is None:
            self._send_json(404, {"error": "attachment not found"})
            return
        self._send_bytes(att["data"], att["content_type"], att["filename"], disposition="inline")

    def h_delete_attachment(self, match: "re.Match[str]", user: Any) -> None:
        att = self.db.get_attachment_meta(int(match.group("id")))
        ok = self.db.delete_attachment(int(match.group("id")))
        if ok and att:
            self.db.add_audit(user["username"], "detach", att["sample_id"], f"removed {att['filename']}")
        self._send_json(200 if ok else 404, {"deleted": ok})

    def h_list_barcodes(self, match: "re.Match[str]", user: Any) -> None:
        sid = int(match.group("id"))
        if self.db.get_sample(sid) is None:
            self._send_json(404, {"error": "sample not found"})
            return
        self._send_json(200, {"barcodes": self.db.list_barcodes(sid)})

    def h_add_barcode(self, match: "re.Match[str]", user: Any) -> None:
        sid = int(match.group("id"))
        if self.db.get_sample(sid) is None:
            self._send_json(404, {"error": "sample not found"})
            return
        barcode = str(self._read_json().get("barcode", "")).strip()
        if not barcode:
            raise ValueError("barcode is required")
        bc = self.db.add_barcode(sid, barcode, user["username"])
        self.db.add_audit(user["username"], "barcode-add", sid, f"added barcode {barcode}")
        self._send_json(201, bc)

    def h_delete_barcode(self, match: "re.Match[str]", user: Any) -> None:
        bc = self.db.get_barcode(int(match.group("id")))
        ok = self.db.delete_barcode(int(match.group("id")))
        if ok and bc:
            self.db.add_audit(user["username"], "barcode-remove", bc["sample_id"], f"removed barcode {bc['barcode']}")
        self._send_json(200 if ok else 404, {"deleted": ok})

    def h_list_sample_numbers(self, match: "re.Match[str]", user: Any) -> None:
        sid = int(match.group("id"))
        if self.db.get_sample(sid) is None:
            self._send_json(404, {"error": "sample not found"})
            return
        self._send_json(200, {"sample_numbers": self.db.list_sample_numbers(sid)})

    def h_add_sample_number(self, match: "re.Match[str]", user: Any) -> None:
        sid = int(match.group("id"))
        if self.db.get_sample(sid) is None:
            self._send_json(404, {"error": "sample not found"})
            return
        value = str(self._read_json().get("sample_number", "")).strip()
        if not value:
            raise ValueError("sample number is required")
        sn = self.db.add_sample_number(sid, value, user["username"])
        self.db.add_audit(user["username"], "sample-number-add", sid, f"added sample number {value}")
        self._send_json(201, sn)

    def h_delete_sample_number(self, match: "re.Match[str]", user: Any) -> None:
        sn = self.db.get_sample_number(int(match.group("id")))
        ok = self.db.delete_sample_number(int(match.group("id")))
        if ok and sn:
            self.db.add_audit(user["username"], "sample-number-remove", sn["sample_id"],
                              f"removed sample number {sn['sample_number']}")
        self._send_json(200 if ok else 404, {"deleted": ok})

    def h_audit(self, match: "re.Match[str]", user: Any) -> None:
        self._send_json(200, {"audit": self.db.list_audit()})

    def h_export_xlsx(self, match: "re.Match[str]", user: Any) -> None:
        q = self._query()
        samples = self.db.list_samples(
            department=q.get("department", [None])[0],
            search=q.get("search", [None])[0],
        )
        headers = ["NO"] + [FIELD_LABELS[f] for f in SAMPLE_FIELDS] + ["Created by", "Created at"]
        rows = [
            [s["id"]] + [s.get(f) for f in SAMPLE_FIELDS] + [s.get("created_by"), s.get("created_at")]
            for s in samples
        ]
        data = build_xlsx(headers, rows)
        self.db.add_audit(user["username"], "export", None, f"exported {len(samples)} records to Excel")
        self._send_bytes(
            data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "biobank-export.xlsx",
        )

    def h_change_password(self, match: "re.Match[str]", user: Any) -> None:
        body = self._read_json()
        current = str(body.get("current_password", ""))
        new = str(body.get("new_password", ""))
        if len(new) < 6:
            raise ValueError("new password must be at least 6 characters")
        if self.db.verify_credentials(user["username"], current) is None:
            self._send_json(400, {"error": "current password is incorrect"})
            return
        self.db.update_password(user["id"], new)
        self._send_json(200, {"ok": True})

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
        self.db.add_audit(
            user["username"], "import", None,
            f"imported {added} record(s) from {filename}" + (f", {skipped} skipped" if skipped else ""),
        )
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
        ("GET", p(r"/api/samples/(?P<id>\d+)/receipt\.pdf"), "h_receipt", False),
        ("GET", p(r"/api/samples/(?P<id>\d+)/form\.docx"), "h_form", False),
        ("GET", p(r"/api/samples/(?P<id>\d+)/attachments"), "h_list_attachments", False),
        ("POST", p(r"/api/samples/(?P<id>\d+)/attachments"), "h_upload_attachment", False),
        ("GET", p(r"/api/attachments/(?P<id>\d+)"), "h_download_attachment", False),
        ("DELETE", p(r"/api/attachments/(?P<id>\d+)"), "h_delete_attachment", True),
        ("GET", p(r"/api/samples/(?P<id>\d+)/barcodes"), "h_list_barcodes", False),
        ("POST", p(r"/api/samples/(?P<id>\d+)/barcodes"), "h_add_barcode", True),
        ("DELETE", p(r"/api/barcodes/(?P<id>\d+)"), "h_delete_barcode", True),
        ("GET", p(r"/api/samples/(?P<id>\d+)/sample-numbers"), "h_list_sample_numbers", False),
        ("POST", p(r"/api/samples/(?P<id>\d+)/sample-numbers"), "h_add_sample_number", False),
        ("DELETE", p(r"/api/sample-numbers/(?P<id>\d+)"), "h_delete_sample_number", True),
        ("PATCH", p(r"/api/samples/(?P<id>\d+)"), "h_update_sample", False),
        ("DELETE", p(r"/api/samples/(?P<id>\d+)"), "h_delete_sample", True),
        ("POST", p(r"/api/change-password"), "h_change_password", False),
        ("POST", p(r"/api/import"), "h_import", True),
        ("GET", p(r"/api/audit"), "h_audit", True),
        ("GET", p(r"/api/export\.xlsx"), "h_export_xlsx", True),
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


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def make_server(
    host: str = "127.0.0.1", port: int = 8000, db_path: Optional[str] = None,
    seed_password: Optional[str] = None, secure_cookies: Optional[bool] = None,
) -> ThreadingHTTPServer:
    db = Database(db_path or os.environ.get("BIOBANK_DB", "biobank.db"))
    pw = seed_password or os.environ.get("BIOBANK_SEED_PASSWORD") or "ChangeMe@123"
    seeded = seed_users(db, pw)
    secure = secure_cookies if secure_cookies is not None else _env_flag("BIOBANK_SECURE_COOKIE")
    handler_cls = type(
        "BoundBiobankHandler", (BiobankHandler,), {"db": db, "secure_cookies": secure}
    )
    handler_cls.routes = _build_routes()
    server = ThreadingHTTPServer((host, port), handler_cls)
    server.biobank_db = db  # type: ignore[attr-defined]
    server.seeded = seeded  # type: ignore[attr-defined]
    server.seed_password = pw  # type: ignore[attr-defined]
    return server


def main() -> None:
    host = os.environ.get("BIOBANK_HOST", "127.0.0.1")
    port = int(os.environ.get("BIOBANK_PORT", "8000"))
    server = make_server(host=host, port=port)
    if server.seeded:  # type: ignore[attr-defined]
        print("Seeded default accounts (admin1, admin2, user1-4).")
        print(f"  Password for all seeded accounts: {server.seed_password}")  # type: ignore[attr-defined]
        print("  Set BIOBANK_SEED_PASSWORD before first run to choose your own.")
    print(f"Biobank server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        server.server_close()
        server.biobank_db.close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
