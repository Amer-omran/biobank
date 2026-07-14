"""HTTP server for the biobank system.

Exposes a small JSON REST API and a single-page web UI, built entirely on
the standard library's http.server. Run with:

    python -m biobank.server            # serves on http://127.0.0.1:8000

Environment:
    BIOBANK_DB    path to the sqlite database (default: biobank.db)
    BIOBANK_PORT  port to listen on (default: 8000)
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

from .db import Database

# (method, compiled-path-regex) -> handler. Handlers take (handler, match, body).
Route = tuple[str, "re.Pattern[str]", Callable[..., Any]]


class BiobankHandler(BaseHTTPRequestHandler):
    db: Database  # injected by make_server
    routes: list[Route] = []

    # ----- helpers --------------------------------------------------------

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html: str) -> None:
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _dispatch(self, method: str) -> None:
        path = urlparse(self.path).path
        for route_method, pattern, handler in self.routes:
            if route_method != method:
                continue
            match = pattern.fullmatch(path)
            if match:
                try:
                    body = self._read_body() if method in ("POST", "PATCH", "PUT") else {}
                    handler(self, match, body)
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

    def log_message(self, *args: Any) -> None:  # keep test output quiet
        if os.environ.get("BIOBANK_VERBOSE"):
            super().log_message(*args)

    # ----- route handlers -------------------------------------------------

    def h_index(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        self._send_html(200, INDEX_HTML)

    def h_health(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        self._send_json(200, {"status": "ok"})

    def h_stats(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        self._send_json(200, self.db.stats())

    def h_list_donors(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        self._send_json(200, {"donors": self.db.list_donors()})

    def h_create_donor(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        donor = self.db.create_donor(
            code=body.get("code", ""),
            full_name=body.get("full_name", ""),
            birth_year=body.get("birth_year"),
            sex=body.get("sex"),
        )
        self._send_json(201, donor)

    def h_get_donor(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        donor = self.db.get_donor(int(match.group("id")))
        if donor is None:
            self._send_json(404, {"error": "donor not found"})
        else:
            self._send_json(200, donor)

    def h_delete_donor(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        ok = self.db.delete_donor(int(match.group("id")))
        self._send_json(200 if ok else 404, {"deleted": ok})

    def h_list_samples(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        params = parse_qs(urlparse(self.path).query)
        donor_id = params.get("donor_id", [None])[0]
        status = params.get("status", [None])[0]
        samples = self.db.list_samples(
            donor_id=int(donor_id) if donor_id else None,
            status=status,
        )
        self._send_json(200, {"samples": samples})

    def h_create_sample(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        if "donor_id" not in body:
            raise ValueError("'donor_id' is required")
        sample = self.db.create_sample(
            donor_id=int(body["donor_id"]),
            sample_type=body.get("sample_type", ""),
            volume_ml=body.get("volume_ml"),
            storage_temp=body.get("storage_temp"),
            location=body.get("location"),
            collected_at=body.get("collected_at"),
        )
        self._send_json(201, sample)

    def h_update_sample(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        if "status" not in body:
            raise ValueError("'status' is required")
        sample = self.db.update_sample_status(int(match.group("id")), body["status"])
        if sample is None:
            self._send_json(404, {"error": "sample not found"})
        else:
            self._send_json(200, sample)

    def h_delete_sample(self, match: "re.Match[str]", body: dict[str, Any]) -> None:
        ok = self.db.delete_sample(int(match.group("id")))
        self._send_json(200 if ok else 404, {"deleted": ok})


def _build_routes() -> list[Route]:
    p = re.compile
    H = BiobankHandler
    return [
        ("GET", p(r"/"), H.h_index),
        ("GET", p(r"/api/health"), H.h_health),
        ("GET", p(r"/api/stats"), H.h_stats),
        ("GET", p(r"/api/donors"), H.h_list_donors),
        ("POST", p(r"/api/donors"), H.h_create_donor),
        ("GET", p(r"/api/donors/(?P<id>\d+)"), H.h_get_donor),
        ("DELETE", p(r"/api/donors/(?P<id>\d+)"), H.h_delete_donor),
        ("GET", p(r"/api/samples"), H.h_list_samples),
        ("POST", p(r"/api/samples"), H.h_create_sample),
        ("PATCH", p(r"/api/samples/(?P<id>\d+)"), H.h_update_sample),
        ("DELETE", p(r"/api/samples/(?P<id>\d+)"), H.h_delete_sample),
    ]


def make_server(
    host: str = "127.0.0.1", port: int = 8000, db_path: Optional[str] = None
) -> ThreadingHTTPServer:
    db = Database(db_path or os.environ.get("BIOBANK_DB", "biobank.db"))
    handler_cls = type("BoundBiobankHandler", (BiobankHandler,), {"db": db})
    handler_cls.routes = _build_routes()
    # Rebind the unbound handler methods onto the subclass' route table.
    handler_cls.routes = [
        (m, pat, getattr(handler_cls, fn.__name__)) for (m, pat, fn) in handler_cls.routes
    ]
    server = ThreadingHTTPServer((host, port), handler_cls)
    server.biobank_db = db  # type: ignore[attr-defined]
    return server


def main() -> None:
    port = int(os.environ.get("BIOBANK_PORT", "8000"))
    server = make_server(port=port)
    print(f"Biobank server listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        server.server_close()
        server.biobank_db.close()  # type: ignore[attr-defined]


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Biobank</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --acc:#38bdf8; --txt:#e2e8f0; --mut:#94a3b8; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,sans-serif; background:var(--bg); color:var(--txt); }
  header { padding:1.2rem 2rem; background:var(--card); border-bottom:1px solid #334155; }
  header h1 { margin:0; font-size:1.3rem; } header span { color:var(--mut); font-size:.85rem; }
  main { max-width:1000px; margin:0 auto; padding:1.5rem 2rem; display:grid; gap:1.5rem; }
  .stats { display:flex; gap:1rem; flex-wrap:wrap; }
  .stat { background:var(--card); border-radius:10px; padding:1rem 1.4rem; flex:1; min-width:120px; }
  .stat b { font-size:1.8rem; color:var(--acc); display:block; }
  .stat small { color:var(--mut); }
  section { background:var(--card); border-radius:10px; padding:1.2rem 1.4rem; }
  h2 { margin:0 0 .8rem; font-size:1rem; }
  form { display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom:1rem; }
  input,select,button { padding:.5rem .6rem; border-radius:7px; border:1px solid #334155;
    background:#0f172a; color:var(--txt); font-size:.85rem; }
  button { background:var(--acc); color:#04222f; border:none; cursor:pointer; font-weight:600; }
  button.ghost { background:transparent; color:var(--mut); border:1px solid #334155; }
  table { width:100%; border-collapse:collapse; font-size:.85rem; }
  th,td { text-align:left; padding:.5rem .4rem; border-bottom:1px solid #334155; }
  th { color:var(--mut); font-weight:500; }
  .tag { padding:.1rem .5rem; border-radius:20px; font-size:.72rem; background:#334155; }
  .tag.stored{background:#14532d;color:#86efac;} .tag.in_use{background:#78350f;color:#fcd34d;}
  .tag.depleted{background:#450a0a;color:#fca5a5;} .tag.discarded{background:#334155;color:#94a3b8;}
</style>
</head>
<body>
<header><h1>🧬 Biobank <span>sample &amp; donor management</span></h1></header>
<main>
  <div class="stats" id="stats"></div>
  <section>
    <h2>Register donor</h2>
    <form id="donor-form">
      <input name="code" placeholder="Code (e.g. D-001)" required>
      <input name="full_name" placeholder="Full name" required>
      <input name="birth_year" type="number" placeholder="Birth year" style="width:110px">
      <select name="sex"><option value="">Sex</option><option>M</option><option>F</option><option>O</option></select>
      <button>Add donor</button>
    </form>
    <table><thead><tr><th>ID</th><th>Code</th><th>Name</th><th>Year</th><th>Sex</th><th></th></tr></thead>
    <tbody id="donors"></tbody></table>
  </section>
  <section>
    <h2>Collect sample</h2>
    <form id="sample-form">
      <select name="donor_id" id="sample-donor" required></select>
      <input name="sample_type" placeholder="Type (blood, DNA…)" required>
      <input name="volume_ml" type="number" step="0.1" placeholder="Vol (ml)" style="width:100px">
      <input name="storage_temp" type="number" placeholder="°C" style="width:80px">
      <input name="location" placeholder="Freezer / location">
      <button>Add sample</button>
    </form>
    <table><thead><tr><th>ID</th><th>Donor</th><th>Type</th><th>Vol</th><th>Temp</th><th>Location</th><th>Status</th><th></th></tr></thead>
    <tbody id="samples"></tbody></table>
  </section>
</main>
<script>
const api = (u,o) => fetch(u,o).then(r => r.json());
const el = id => document.getElementById(id);

async function refresh() {
  const [stats, donors, samples] = await Promise.all([
    api('/api/stats'), api('/api/donors'), api('/api/samples')
  ]);
  el('stats').innerHTML = `
    <div class="stat"><b>${stats.donors}</b><small>donors</small></div>
    <div class="stat"><b>${stats.samples}</b><small>samples</small></div>
    <div class="stat"><b>${stats.samples_by_status.stored||0}</b><small>stored</small></div>
    <div class="stat"><b>${stats.samples_by_status.in_use||0}</b><small>in use</small></div>`;
  el('donors').innerHTML = donors.donors.map(d => `<tr>
    <td>${d.id}</td><td>${d.code}</td><td>${d.full_name}</td>
    <td>${d.birth_year||'—'}</td><td>${d.sex||'—'}</td>
    <td><button class="ghost" onclick="delDonor(${d.id})">✕</button></td></tr>`).join('');
  el('sample-donor').innerHTML = '<option value="">Donor…</option>' +
    donors.donors.map(d => `<option value="${d.id}">${d.code} — ${d.full_name}</option>`).join('');
  const byId = Object.fromEntries(donors.donors.map(d => [d.id, d.code]));
  el('samples').innerHTML = samples.samples.map(s => `<tr>
    <td>${s.id}</td><td>${byId[s.donor_id]||s.donor_id}</td><td>${s.sample_type}</td>
    <td>${s.volume_ml??'—'}</td><td>${s.storage_temp??'—'}</td><td>${s.location||'—'}</td>
    <td><select class="tag ${s.status}" onchange="setStatus(${s.id}, this.value)">
      ${['stored','in_use','depleted','discarded'].map(st =>
        `<option ${st===s.status?'selected':''}>${st}</option>`).join('')}
    </select></td>
    <td><button class="ghost" onclick="delSample(${s.id})">✕</button></td></tr>`).join('');
}
function formData(f){const o={};new FormData(f).forEach((v,k)=>{if(v!=='')o[k]=v;});return o;}
el('donor-form').onsubmit = async e => { e.preventDefault();
  const d = formData(e.target); if(d.birth_year)d.birth_year=+d.birth_year;
  await api('/api/donors',{method:'POST',body:JSON.stringify(d)}); e.target.reset(); refresh(); };
el('sample-form').onsubmit = async e => { e.preventDefault();
  const d = formData(e.target); d.donor_id=+d.donor_id;
  if(d.volume_ml)d.volume_ml=+d.volume_ml; if(d.storage_temp)d.storage_temp=+d.storage_temp;
  await api('/api/samples',{method:'POST',body:JSON.stringify(d)}); e.target.reset(); refresh(); };
async function delDonor(id){ await fetch('/api/donors/'+id,{method:'DELETE'}); refresh(); }
async function delSample(id){ await fetch('/api/samples/'+id,{method:'DELETE'}); refresh(); }
async function setStatus(id,status){
  await api('/api/samples/'+id,{method:'PATCH',body:JSON.stringify({status})}); refresh(); }
refresh();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
