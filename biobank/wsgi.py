"""WSGI entry point for the biobank system.

Lets the app run on WSGI hosts (e.g. the free tier of PythonAnywhere) without
any third-party packages. It reuses all business logic — the database layer,
importer, exporter and options — and re-implements only the thin request
routing against the WSGI interface. Access control matches server.py exactly.

PythonAnywhere usage: point your web app's WSGI file at `application` below,
for example:

    import os
    os.environ["BIOBANK_DB"] = "/home/USERNAME/biobank/biobank.db"
    os.environ["BIOBANK_SEED_PASSWORD"] = "a-strong-first-run-password"
    os.environ["BIOBANK_SECURE_COOKIE"] = "1"
    from biobank.wsgi import application
"""

from __future__ import annotations

import json
import os
import re
from http import cookies as http_cookies
from typing import Any, Callable, Optional
from urllib.parse import parse_qs

from .db import Database
from .docx_form import build_form_docx
from .exporter import build_xlsx
from .importer import parse_file
from .options import FIELD_LABELS, OPTIONS, RESTRICTED_FIELDS, SAMPLE_FIELDS
from .pdf import build_receipt_pdf
from .server import COOKIE_NAME, STATIC_DIR, seed_users, validate_pdf

_STATUS = {
    200: "200 OK", 201: "201 Created", 400: "400 Bad Request",
    401: "401 Unauthorized", 403: "403 Forbidden", 404: "404 Not Found",
    500: "500 Internal Server Error",
}
_CTYPES = {"js": "application/javascript", "css": "text/css", "html": "text/html"}


class HttpError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def make_app(
    db_path: Optional[str] = None, seed_password: Optional[str] = None,
    secure_cookies: Optional[bool] = None,
) -> Callable:
    db = Database(db_path or os.environ.get("BIOBANK_DB", "biobank.db"))
    seed_users(db, seed_password or os.environ.get("BIOBANK_SEED_PASSWORD") or "ChangeMe@123")
    secure = secure_cookies if secure_cookies is not None else _flag("BIOBANK_SECURE_COOKIE")

    def session_cookie(token: str, max_age: int) -> str:
        parts = [f"{COOKIE_NAME}={token}", "HttpOnly", "Path=/", "SameSite=Lax", f"Max-Age={max_age}"]
        if secure:
            parts.append("Secure")
        return "; ".join(parts)

    # ----- response builders (return (status, headers, body_bytes)) --------

    def json_resp(code: int, payload: Any, cookie: Optional[str] = None):
        body = json.dumps(payload, indent=2).encode()
        headers = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))]
        if cookie is not None:
            headers.append(("Set-Cookie", cookie))
        return _STATUS[code], headers, body

    def file_resp(name: str, ctype: str):
        try:
            with open(os.path.join(STATIC_DIR, name), "rb") as fh:
                body = fh.read()
        except OSError:
            return json_resp(404, {"error": "not found"})
        return _STATUS[200], [("Content-Type", ctype), ("Content-Length", str(len(body)))], body

    def bytes_resp(data: bytes, ctype: str, filename: str, disposition: str = "attachment"):
        headers = [
            ("Content-Type", ctype),
            ("Content-Disposition", f'{disposition}; filename="{filename}"'),
            ("Content-Length", str(len(data))),
        ]
        return _STATUS[200], headers, data

    # ----- request context -------------------------------------------------

    def read_json(raw: bytes) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def cookie_token(environ) -> Optional[str]:
        header = environ.get("HTTP_COOKIE")
        if not header:
            return None
        jar = http_cookies.SimpleCookie()
        try:
            jar.load(header)
        except http_cookies.CookieError:
            return None
        morsel = jar.get(COOKIE_NAME)
        return morsel.value if morsel else None

    # ----- handlers --------------------------------------------------------

    def h_index(m, user, ctx):
        return file_resp("index.html", "text/html; charset=utf-8")

    def h_static(m, user, ctx):
        name = m.group("name")
        if "/" in name or ".." in name:
            return json_resp(404, {"error": "not found"})
        ext = name.rsplit(".", 1)[-1].lower()
        return file_resp(name, _CTYPES.get(ext, "application/octet-stream") + "; charset=utf-8")

    def h_health(m, user, ctx):
        return json_resp(200, {"status": "ok"})

    def h_login(m, user, ctx):
        body = read_json(ctx["raw"])
        account = db.verify_credentials(str(body.get("username", "")).strip(), str(body.get("password", "")))
        if account is None:
            return json_resp(401, {"error": "wrong username or password"})
        token = db.create_session(account["id"])
        pub = {"username": account["username"], "name": account["name"], "role": account["role"]}
        return json_resp(200, {"user": pub}, cookie=session_cookie(token, 8 * 60 * 60))

    def h_logout(m, user, ctx):
        db.delete_session(ctx["token"])
        return json_resp(200, {"ok": True}, cookie=session_cookie("", 0))

    def h_me(m, user, ctx):
        return json_resp(200, {"user": {"username": user["username"], "name": user["name"], "role": user["role"]}})

    def h_options(m, user, ctx):
        return json_resp(200, {"options": OPTIONS, "fields": SAMPLE_FIELDS, "restricted": RESTRICTED_FIELDS})

    def h_list_samples(m, user, ctx):
        q = ctx["query"]
        samples = db.list_samples(
            department=q.get("department", [None])[0], search=q.get("search", [None])[0]
        )
        return json_resp(200, {"samples": samples})

    def h_create_sample(m, user, ctx):
        data = {k: v for k, v in read_json(ctx["raw"]).items() if k in SAMPLE_FIELDS}
        if user["role"] != "admin":
            for f in RESTRICTED_FIELDS:
                data.pop(f, None)
        sample = db.create_sample(data, created_by=user["username"])
        db.add_audit(user["username"], "create", sample["id"],
                     f"created sample ({sample.get('sample_type') or '?'} · {sample.get('area') or '?'})")
        return json_resp(201, sample)

    def h_update_sample(m, user, ctx):
        sid = int(m.group("id"))
        data = {k: v for k, v in read_json(ctx["raw"]).items() if k in SAMPLE_FIELDS}
        if user["role"] != "admin":
            for f in RESTRICTED_FIELDS:
                data.pop(f, None)
        before = db.get_sample(sid)
        sample = db.update_sample(sid, data)
        if sample is None:
            return json_resp(404, {"error": "sample not found"})
        changes = {f: [before.get(f), sample.get(f)] for f in SAMPLE_FIELDS
                   if before and before.get(f) != sample.get(f)}
        if changes:
            db.add_audit(user["username"], "update", sid, "updated " + ", ".join(changes.keys()),
                         json.dumps(changes, ensure_ascii=False))
        return json_resp(200, sample)

    def h_delete_sample(m, user, ctx):
        sid = int(m.group("id"))
        before = db.get_sample(sid)
        ok = db.delete_sample(sid)
        if ok:
            db.add_audit(user["username"], "delete", sid, f"deleted sample #{sid}"
                         + (f" ({before.get('sample_type') or '?'} · {before.get('area') or '?'})" if before else ""))
        return json_resp(200 if ok else 404, {"deleted": ok})

    def h_change_password(m, user, ctx):
        body = read_json(ctx["raw"])
        new = str(body.get("new_password", ""))
        if len(new) < 6:
            raise HttpError(400, "new password must be at least 6 characters")
        if db.verify_credentials(user["username"], str(body.get("current_password", ""))) is None:
            return json_resp(400, {"error": "current password is incorrect"})
        db.update_password(user["id"], new)
        return json_resp(200, {"ok": True})

    def h_import(m, user, ctx):
        filename = ctx["query"].get("filename", ["upload.xlsx"])[0]
        if not ctx["raw"]:
            raise HttpError(400, "no file uploaded")
        records = parse_file(ctx["raw"], filename)
        added, skipped = 0, 0
        for rec in records:
            try:
                db.create_sample(rec, created_by=user["username"])
                added += 1
            except ValueError:
                skipped += 1
        db.add_audit(user["username"], "import", None,
                     f"imported {added} record(s) from {filename}" + (f", {skipped} skipped" if skipped else ""))
        return json_resp(200, {"added": added, "skipped": skipped, "parsed": len(records)})

    def h_receipt(m, user, ctx):
        sample = db.get_sample(int(m.group("id")))
        if sample is None:
            return json_resp(404, {"error": "sample not found"})
        return bytes_resp(build_receipt_pdf(sample), "application/pdf",
                          f"sample-{sample['id']}-receipt.pdf", disposition="inline")

    def h_form(m, user, ctx):
        sample = db.get_sample(int(m.group("id")))
        if sample is None:
            return json_resp(404, {"error": "sample not found"})
        try:
            data = build_form_docx(sample)
        except FileNotFoundError:
            return json_resp(503, {"error": "the Word form template is not configured on the server"})
        return bytes_resp(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            f"sample-{sample['id']}-storage-form.docx",
        )

    def h_list_attachments(m, user, ctx):
        sid = int(m.group("id"))
        if db.get_sample(sid) is None:
            return json_resp(404, {"error": "sample not found"})
        return json_resp(200, {"attachments": db.list_attachments(sid)})

    def h_upload_attachment(m, user, ctx):
        sid = int(m.group("id"))
        if db.get_sample(sid) is None:
            return json_resp(404, {"error": "sample not found"})
        filename = os.path.basename(ctx["query"].get("filename", ["file.pdf"])[0])
        data = ctx["raw"]
        validate_pdf(filename, data)
        att = db.add_attachment(sid, filename, data, user["username"])
        db.add_audit(user["username"], "attach", sid, f"attached {filename}")
        return json_resp(201, att)

    def h_download_attachment(m, user, ctx):
        att = db.get_attachment(int(m.group("id")))
        if att is None:
            return json_resp(404, {"error": "attachment not found"})
        return bytes_resp(att["data"], att["content_type"], att["filename"], disposition="inline")

    def h_delete_attachment(m, user, ctx):
        att = db.get_attachment_meta(int(m.group("id")))
        ok = db.delete_attachment(int(m.group("id")))
        if ok and att:
            db.add_audit(user["username"], "detach", att["sample_id"], f"removed {att['filename']}")
        return json_resp(200 if ok else 404, {"deleted": ok})

    def h_audit(m, user, ctx):
        return json_resp(200, {"audit": db.list_audit()})

    def h_export_xlsx(m, user, ctx):
        q = ctx["query"]
        samples = db.list_samples(department=q.get("department", [None])[0], search=q.get("search", [None])[0])
        headers = ["NO"] + [FIELD_LABELS[f] for f in SAMPLE_FIELDS] + ["Created by", "Created at"]
        rows = [[s["id"]] + [s.get(f) for f in SAMPLE_FIELDS] + [s.get("created_by"), s.get("created_at")]
                for s in samples]
        db.add_audit(user["username"], "export", None, f"exported {len(samples)} records to Excel")
        return bytes_resp(build_xlsx(headers, rows),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          "biobank-export.xlsx")

    def h_users(m, user, ctx):
        return json_resp(200, {"users": db.list_users()})

    def h_create_user(m, user, ctx):
        body = read_json(ctx["raw"])
        username = str(body.get("username", "")).strip()
        name = str(body.get("name", "")).strip()
        role = str(body.get("role", "")).strip()
        password = str(body.get("password", ""))
        if not username:
            raise HttpError(400, "username is required")
        if not name:
            raise HttpError(400, "name is required")
        if role not in ("admin", "staff"):
            raise HttpError(400, "role must be 'admin' or 'staff'")
        if len(password) < 6:
            raise HttpError(400, "password must be at least 6 characters")
        return json_resp(201, db.create_user(username, name, role, password))

    def h_delete_user(m, user, ctx):
        target = db.get_user(int(m.group("id")))
        if target is None:
            return json_resp(404, {"error": "user not found"})
        if target["id"] == user["id"]:
            raise HttpError(400, "you cannot delete your own account")
        if target["role"] == "admin" and db.count_admins() <= 1:
            raise HttpError(400, "cannot delete the last administrator")
        return json_resp(200, {"deleted": db.delete_user(target["id"])})

    # method, pattern, handler, needs_auth, admin_only
    routes = [
        ("GET", re.compile(r"/"), h_index, False, False),
        ("GET", re.compile(r"/static/(?P<name>[\w.\-]+)"), h_static, False, False),
        ("GET", re.compile(r"/api/health"), h_health, False, False),
        ("POST", re.compile(r"/api/login"), h_login, False, False),
        ("POST", re.compile(r"/api/logout"), h_logout, True, False),
        ("GET", re.compile(r"/api/me"), h_me, True, False),
        ("GET", re.compile(r"/api/options"), h_options, True, False),
        ("GET", re.compile(r"/api/samples"), h_list_samples, True, False),
        ("POST", re.compile(r"/api/samples"), h_create_sample, True, False),
        ("GET", re.compile(r"/api/samples/(?P<id>\d+)/receipt\.pdf"), h_receipt, True, False),
        ("GET", re.compile(r"/api/samples/(?P<id>\d+)/form\.docx"), h_form, True, False),
        ("GET", re.compile(r"/api/samples/(?P<id>\d+)/attachments"), h_list_attachments, True, False),
        ("POST", re.compile(r"/api/samples/(?P<id>\d+)/attachments"), h_upload_attachment, True, False),
        ("GET", re.compile(r"/api/attachments/(?P<id>\d+)"), h_download_attachment, True, False),
        ("DELETE", re.compile(r"/api/attachments/(?P<id>\d+)"), h_delete_attachment, True, True),
        ("PATCH", re.compile(r"/api/samples/(?P<id>\d+)"), h_update_sample, True, False),
        ("DELETE", re.compile(r"/api/samples/(?P<id>\d+)"), h_delete_sample, True, True),
        ("POST", re.compile(r"/api/change-password"), h_change_password, True, False),
        ("POST", re.compile(r"/api/import"), h_import, True, True),
        ("GET", re.compile(r"/api/audit"), h_audit, True, True),
        ("GET", re.compile(r"/api/export\.xlsx"), h_export_xlsx, True, True),
        ("GET", re.compile(r"/api/users"), h_users, True, True),
        ("POST", re.compile(r"/api/users"), h_create_user, True, True),
        ("DELETE", re.compile(r"/api/users/(?P<id>\d+)"), h_delete_user, True, True),
    ]

    def application(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "") or "/"
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        raw = environ["wsgi.input"].read(length) if length else b""
        ctx = {
            "query": parse_qs(environ.get("QUERY_STRING", "")),
            "raw": raw,
            "token": cookie_token(environ),
        }
        status, headers, body = _route(method, path, ctx)
        start_response(status, headers)
        return [body]

    def _route(method: str, path: str, ctx: dict):
        for r_method, pattern, handler, needs_auth, admin_only in routes:
            if r_method != method:
                continue
            match = pattern.fullmatch(path)
            if not match:
                continue
            try:
                user = None
                if needs_auth:
                    user = db.get_session_user(ctx["token"])
                    if user is None:
                        return json_resp(401, {"error": "authentication required"})
                    if admin_only and user["role"] != "admin":
                        return json_resp(403, {"error": "administrator access required"})
                return handler(match, user, ctx)
            except HttpError as exc:
                return json_resp(exc.status, {"error": str(exc)})
            except ValueError as exc:
                return json_resp(400, {"error": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                return json_resp(500, {"error": str(exc)})
        return json_resp(404, {"error": "not found"})

    return application


# Module-level callable for WSGI servers that import `application` directly.
# Built lazily on the first request so merely importing the module has no
# side effects (no database file is created until the app actually serves).
_app: Optional[Callable] = None


def application(environ, start_response):
    global _app
    if _app is None:
        _app = make_app()
    return _app(environ, start_response)
