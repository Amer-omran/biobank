"use strict";

// ---- form field specification ---------------------------------------------
// restricted: true  -> only administrators may fill it (server also enforces)
const FIELD_SPEC = [
  { name: "lab_number",    label: "Lab number",    mono: true,  ph: "264" },
  { name: "sample_number", label: "Sample number", mono: true,  ph: "S-0001" },
  { name: "storage_date",  label: "Storage date",  type: "date", mono: true },
  { name: "storage_method",label: "Storage method",select: ["-20 °C", "-80 °C", "-190 °C"] },
  { name: "freezer_no",    label: "Freezer no.",   mono: true,  ph: "F-03", restricted: true },
  { name: "shelf_no",      label: "Shelf no.",     mono: true,  ph: "R-12", restricted: true },
  { name: "plate_no",      label: "Plate no.",     mono: true,  ph: "P-045", restricted: true },
  { name: "area",          label: "Area",          list: "dl-area",        req: true },
  { name: "animal_type",   label: "Animal type",   list: "dl-animal_type", req: true },
  { name: "sample_type",   label: "Sample type",   list: "dl-sample_type", req: true },
  { name: "quantity_ml",   label: "Quantity (ml)", type: "number", step: "0.1", mono: true, ph: "5.0" },
  { name: "concentration", label: "Concentration", mono: true, ph: "120 ng/µl" },
  { name: "disease",       label: "Disease",       list: "dl-disease" },
  { name: "strain",        label: "Strain",        list: "dl-strain" },
  { name: "department",    label: "Department",    list: "dl-department", req: true },
  { name: "barcode",       label: "Barcode",       mono: true, ph: "BC-000264", restricted: true },
];

const DATALIST_FIELDS = ["area", "animal_type", "sample_type", "disease", "strain", "department"];
const $ = s => document.querySelector(s);
const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));

let me = null;
let deptFilter = "";
let searchTerm = "";
let searchTimer = null;
let lastSamples = [];
let editingId = null;

// ---- API helper ------------------------------------------------------------
async function api(path, { method = "GET", body, raw } = {}) {
  const opts = { method, headers: {} };
  if (raw !== undefined) { opts.body = raw; }
  else if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  const data = res.status === 204 ? {} : await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { status: res.status });
  return data;
}

// Download the auto-filled Word storage form for a sample (shows a message on error).
async function downloadForm(id) {
  const msg = $("#rec-msg");
  try {
    const res = await fetch("/api/samples/" + id + "/form.docx");
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "sample-" + id + "-storage-form.docx"; a.click(); URL.revokeObjectURL(a.href);
  } catch (ex) {
    msg.className = "import-msg bad"; msg.textContent = "Word form: " + ex.message;
  }
}

// ---- build the entry form --------------------------------------------------
function buildForm() {
  $("#fgrid").innerHTML = FIELD_SPEC.map(f => {
    const cls = "f" + (f.req ? " req" : "") + (f.restricted ? " restricted-field" : "");
    let control;
    if (f.select) {
      control = `<select name="${f.name}"><option value="">—</option>` +
        f.select.map(o => `<option>${esc(o)}</option>`).join("") + `</select>`;
    } else if (f.list) {
      control = `<input class="pick" name="${f.name}" list="${f.list}" placeholder="Select or type…" autocomplete="off">`;
    } else {
      control = `<input ${f.mono ? 'class="mono-in" ' : ""}name="${f.name}"` +
        (f.type ? ` type="${f.type}"` : "") + (f.step ? ` step="${f.step}"` : "") +
        (f.ph ? ` placeholder="${esc(f.ph)}"` : "") + ` autocomplete="off">`;
    }
    return `<label class="${cls}"><span>${esc(f.label)}</span>${control}</label>`;
  }).join("");
}

function fillDatalists(options) {
  for (const f of DATALIST_FIELDS) {
    const dl = document.getElementById("dl-" + f);
    if (dl && options[f]) dl.innerHTML = options[f].map(o => `<option value="${esc(o)}">`).join("");
  }
}

// ---- rendering -------------------------------------------------------------
function renderStats(samples) {
  const count = field => {
    const m = {}; for (const s of samples) if (s[field]) m[s[field]] = (m[s[field]] || 0) + 1; return m;
  };
  const bars = map => {
    const entries = Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 3);
    const max = Math.max(1, ...entries.map(e => e[1]));
    return entries.map(([k, v]) => `<div class="bar"><span style="min-width:64px">${esc(k)}</span>
      <span class="track"><span class="fill" style="width:${Math.round(v/max*100)}%"></span></span>
      <span class="n">${v}</span></div>`).join("") || `<div class="bar"><span>—</span></div>`;
  };
  $("#stats").innerHTML = `
    <div class="stat accent"><div class="k">Total records</div><div class="v">${samples.length}</div></div>
    <div class="stat"><div class="k">By department</div><div class="bars">${bars(count("department"))}</div></div>
    <div class="stat"><div class="k">By sample type</div><div class="bars">${bars(count("sample_type"))}</div></div>
    <div class="stat"><div class="k">By animal type</div><div class="bars">${bars(count("animal_type"))}</div></div>`;
}

function renderRows(samples) {
  $("#rec-count").textContent = `${samples.length} record${samples.length === 1 ? "" : "s"}`;
  const isAdmin = me && me.role === "admin";
  const cell = v => v == null || v === "" ? '<td class="muted">—</td>' : `<td>${esc(v)}</td>`;
  const num = v => `<td class="num">${v == null || v === "" ? "—" : esc(v)}</td>`;
  $("#rows").innerHTML = samples.length ? samples.map(s => `<tr>
    <td class="num">${s.id}</td>${num(s.lab_number)}
    <td class="key">${s.sample_number ? esc(s.sample_number) : "—"}</td>
    ${num(s.storage_date)}${num(s.storage_method)}${num(s.freezer_no)}${num(s.shelf_no)}${num(s.plate_no)}
    ${cell(s.area)}${cell(s.animal_type)}${cell(s.sample_type)}
    ${num(s.quantity_ml)}${cell(s.concentration)}${cell(s.disease)}${cell(s.strain)}
    <td>${s.department ? `<span class="dept ${esc(s.department)}">${esc(s.department)}</span>` : "—"}</td>
    ${cell(s.barcode)}<td class="muted">${s.created_by ? esc(s.created_by) : "—"}</td>
    <td style="text-align:right; white-space:nowrap">
      <button class="x" data-receipt="${s.id}" title="Reception form (PDF)">📄</button>
      <button class="x" data-form="${s.id}" title="Storage request form (Word)">📝</button>
      <button class="x" data-edit="${s.id}" title="Edit">✎</button>
      ${isAdmin ? `<button class="x" data-del="${s.id}" title="Delete">✕</button>` : ""}</td>
  </tr>`).join("") : `<tr><td colspan="19" class="empty">No records${
    searchTerm || deptFilter ? " match your filters" : " yet"}.</td></tr>`;
}

async function refresh() {
  const q = new URLSearchParams();
  if (deptFilter) q.set("department", deptFilter);
  if (searchTerm) q.set("search", searchTerm);
  const { samples } = await api("/api/samples?" + q.toString());
  lastSamples = samples;
  renderStats(samples);
  renderRows(samples);
}

// ---- session ---------------------------------------------------------------
function applyAuthUI() {
  const root = document.documentElement;
  root.classList.toggle("authed", !!me);
  root.classList.toggle("role-admin", !!me && me.role === "admin");
  root.classList.toggle("role-staff", !!me && me.role === "staff");
  if (me) {
    $("#userchip").innerHTML = `<span class="who">${esc(me.name)}</span>
      <span class="role-badge ${me.role}">${me.role === "admin" ? "Full access" : "Data entry"}</span>`;
  }
}

async function enterApp() {
  const { options } = await api("/api/options");
  fillDatalists(options);
  await refresh();
  if (me && me.role === "admin") { await loadUsers(); await loadAudit(); }
}

// refresh the sample list, and the audit log too when signed in as admin
async function reloadData() {
  await refresh();
  if (me && me.role === "admin") await loadAudit();
}

// ---- audit log (admin only) -----------------------------------------------
async function loadAudit() {
  const { audit } = await api("/api/audit");
  $("#audit-rows").innerHTML = audit.length ? audit.map(a => `<tr>
    <td class="num">${a.ts ? esc(a.ts.replace("T", " ").slice(0, 19)) : "—"}</td>
    <td class="key">${a.username ? esc(a.username) : "—"}</td>
    <td>${esc(a.action)}</td>
    <td class="num">${a.sample_id != null ? "#" + a.sample_id : "—"}</td>
    <td class="muted">${a.summary ? esc(a.summary) : "—"}</td>
  </tr>`).join("") : `<tr><td colspan="5" class="empty">No activity yet.</td></tr>`;
}

// ---- user management (admin only) -----------------------------------------
async function loadUsers() {
  const { users } = await api("/api/users");
  $("#user-rows").innerHTML = users.map(u => `<tr>
    <td class="num">${u.id}</td>
    <td class="key">${esc(u.username)}</td>
    <td>${esc(u.name)}</td>
    <td><span class="role-badge ${u.role}">${esc(u.role)}</span></td>
    <td class="num">${u.created_at ? esc(u.created_at.slice(0, 10)) : "—"}</td>
    <td style="text-align:right">${
      me && u.username === me.username ? '<span class="muted" style="font-size:11px">you</span>'
        : `<button class="x" data-del-user="${u.id}" title="Delete user">✕</button>`}</td>
  </tr>`).join("");
}
$("#user-form").addEventListener("submit", async e => {
  e.preventDefault();
  const err = $("#user-err"); err.textContent = "";
  const body = {};
  new FormData(e.target).forEach((v, k) => { body[k] = String(v); });
  try { await api("/api/users", { method: "POST", body }); e.target.reset(); await loadUsers(); }
  catch (ex) { err.textContent = ex.message; }
});
$("#user-rows").addEventListener("click", async e => {
  const b = e.target.closest("[data-del-user]"); if (!b) return;
  try { await api("/api/users/" + b.dataset.delUser, { method: "DELETE" }); await loadUsers(); }
  catch (ex) { $("#user-err").textContent = ex.message; }
});

// ---- events ----------------------------------------------------------------
$("#login-form").addEventListener("submit", async e => {
  e.preventDefault();
  const err = $("#login-err"); err.textContent = "";
  try {
    const data = await api("/api/login", { method: "POST", body: {
      username: $("#lg-user").value.trim(), password: $("#lg-pass").value,
    }});
    me = data.user; $("#login-form").reset(); applyAuthUI(); await enterApp();
  } catch (ex) { err.textContent = ex.status === 401 ? "Wrong username or password." : ex.message; }
});
$("#logout").addEventListener("click", async () => {
  try { await api("/api/logout", { method: "POST" }); } catch {}
  me = null; applyAuthUI(); $("#lg-user").focus();
});
$(".demo-accts").addEventListener("click", e => {
  const c = e.target.closest("[data-fill]"); if (!c) return;
  $("#lg-user").value = c.dataset.fill; $("#lg-pass").focus();
});

function startEdit(s) {
  editingId = s.id;
  const form = $("#rec-form");
  FIELD_SPEC.forEach(f => {
    const el = form.elements[f.name];
    if (el) el.value = s[f.name] == null ? "" : s[f.name];
  });
  $("#form-title").textContent = "Edit record #" + s.id;
  $("#save-btn").textContent = "Update record";
  $("#cancel-edit").hidden = false;
  $("#rec-err").textContent = "";
  form.scrollIntoView({ behavior: "smooth", block: "center" });
}
function cancelEdit() {
  editingId = null;
  $("#rec-form").reset();
  $("#form-title").textContent = "New sample record";
  $("#save-btn").textContent = "Save record";
  $("#cancel-edit").hidden = true;
  $("#rec-err").textContent = "";
}
$("#cancel-edit").addEventListener("click", cancelEdit);
$("#rec-msg").addEventListener("click", e => {
  const a = e.target.closest("[data-form-link]");
  if (a) { e.preventDefault(); downloadForm(a.dataset.formLink); }
});

$("#rec-form").addEventListener("submit", async e => {
  e.preventDefault();
  const err = $("#rec-err"); err.textContent = "";
  $("#rec-msg").innerHTML = "";
  const body = {};
  new FormData(e.target).forEach((v, k) => {
    const val = String(v).trim();
    // when editing, send empties too so a cleared optional field is saved
    if (editingId || val !== "") body[k] = val;
  });
  try {
    if (editingId) {
      await api("/api/samples/" + editingId, { method: "PATCH", body });
      cancelEdit();
    } else {
      const created = await api("/api/samples", { method: "POST", body });
      e.target.reset();
      const lk = "color:var(--accent);font-weight:600;text-decoration:none";
      $("#rec-msg").className = "import-msg";
      $("#rec-msg").innerHTML = `Saved ✓ &nbsp;` +
        `<a href="/api/samples/${created.id}/receipt.pdf" target="_blank" style="${lk}">📄 PDF</a>` +
        ` &nbsp;·&nbsp; <a href="#" data-form-link="${created.id}" style="${lk}">📝 Storage form (Word)</a>`;
    }
    await reloadData();
  } catch (ex) { err.textContent = ex.message; }
});
$("#rows").addEventListener("click", async e => {
  const receipt = e.target.closest("[data-receipt]");
  if (receipt) { window.open("/api/samples/" + receipt.dataset.receipt + "/receipt.pdf", "_blank"); return; }
  const formBtn = e.target.closest("[data-form]");
  if (formBtn) { downloadForm(formBtn.dataset.form); return; }
  const edit = e.target.closest("[data-edit]");
  if (edit) {
    const s = lastSamples.find(x => String(x.id) === edit.dataset.edit);
    if (s) startEdit(s);
    return;
  }
  const b = e.target.closest("[data-del]"); if (!b) return;
  if (String(editingId) === b.dataset.del) cancelEdit();
  try { await api("/api/samples/" + b.dataset.del, { method: "DELETE" }); await reloadData(); }
  catch (ex) { $("#rec-err").textContent = ex.message; }
});
$("#search").addEventListener("input", e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { searchTerm = e.target.value.trim(); refresh(); }, 200);
});
$(".filters").addEventListener("click", e => {
  const chip = e.target.closest(".chip"); if (!chip) return;
  deptFilter = chip.dataset.dept;
  document.querySelectorAll(".filters .chip").forEach(c =>
    c.setAttribute("aria-pressed", c === chip ? "true" : "false"));
  refresh();
});
$("#theme").addEventListener("click", () => {
  const root = document.documentElement;
  const cur = root.getAttribute("data-theme")
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  root.setAttribute("data-theme", cur === "dark" ? "light" : "dark");
});

// ---- import ----------------------------------------------------------------
const TMPL_COLS = ["Lab number","Sample number","Sample storage date","Storage method","Freezer number",
  "Shelf number","Plate number","area","animal type","Sample type","Sample quantity (ML)",
  "Sample concentration","Name of the disease","strain","department","barcode number"];
$("#tmpl-btn").addEventListener("click", () => {
  const rows = [ TMPL_COLS.join(","),
    "264,S-0001,2025-02-11,-80 °C,F-03,R-12,P-045,Riyadh,Cattle,blood,5,120 ng/µl,FMD,SAT2,virology,BC-000264",
    "397,S-0002,2025-03-12,-20 °C,F-01,R-04,P-008,Jeddah,Sheep,Serum,3,,PPR,,virology,BC-000397" ].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + rows], { type: "text/csv;charset=utf-8" }));
  a.download = "biobank-import-template.csv"; a.click(); URL.revokeObjectURL(a.href);
});
// ---- export ----------------------------------------------------------------
$("#export-btn").addEventListener("click", () => {
  if (!lastSamples.length) { $("#import-msg").className = "import-msg"; $("#import-msg").textContent = "Nothing to export."; return; }
  const q = v => { v = v == null ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  const cols = ["id", ...FIELD_SPEC.map(f => f.name), "created_by", "created_at"];
  const head = ["NO", ...FIELD_SPEC.map(f => f.label), "Created by", "Created at"];
  const lines = [head.join(",")].concat(lastSamples.map(s => cols.map(c => q(s[c])).join(",")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  a.download = "biobank-export.csv"; a.click(); URL.revokeObjectURL(a.href);
});

// ---- change password -------------------------------------------------------
$("#pw-form").addEventListener("submit", async e => {
  e.preventDefault();
  const msg = $("#pw-msg"); msg.style.color = ""; msg.textContent = "";
  const f = new FormData(e.target);
  if (f.get("new_password") !== f.get("confirm")) { msg.textContent = "New passwords do not match."; return; }
  try {
    await api("/api/change-password", { method: "POST", body: {
      current_password: f.get("current_password"), new_password: f.get("new_password"),
    }});
    e.target.reset(); msg.style.color = "var(--accent)"; msg.textContent = "Password updated.";
  } catch (ex) { msg.textContent = ex.message; }
});

$("#import-btn").addEventListener("click", () => $("#file").click());
$("#file").addEventListener("change", async e => {
  const file = e.target.files[0]; if (!file) return;
  const msg = $("#import-msg"); msg.className = "import-msg"; msg.textContent = "Uploading…";
  try {
    const buf = await file.arrayBuffer();
    const res = await api("/api/import?filename=" + encodeURIComponent(file.name), { method: "POST", raw: buf });
    msg.className = "import-msg ok";
    msg.textContent = `Imported ${res.added} record(s)` + (res.skipped ? ` · ${res.skipped} skipped` : "") + ".";
    await reloadData();
  } catch (ex) { msg.className = "import-msg bad"; msg.textContent = "Import failed: " + ex.message; }
  e.target.value = "";
});

// ---- Excel export (admin only) --------------------------------------------
$("#export-xlsx-btn").addEventListener("click", async () => {
  const msg = $("#import-msg"); msg.className = "import-msg"; msg.textContent = "Preparing Excel…";
  try {
    const q = new URLSearchParams();
    if (deptFilter) q.set("department", deptFilter);
    if (searchTerm) q.set("search", searchTerm);
    const res = await fetch("/api/export.xlsx?" + q.toString());
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "biobank-export.xlsx"; a.click();
    URL.revokeObjectURL(a.href);
    msg.className = "import-msg ok"; msg.textContent = "Excel exported.";
    if (me && me.role === "admin") await loadAudit();
  } catch (ex) { msg.className = "import-msg bad"; msg.textContent = "Export failed: " + ex.message; }
});

// ---- boot ------------------------------------------------------------------
buildForm();
(async () => {
  try { const data = await api("/api/me"); me = data.user; applyAuthUI(); await enterApp(); }
  catch { applyAuthUI(); $("#lg-user").focus(); }
})();
