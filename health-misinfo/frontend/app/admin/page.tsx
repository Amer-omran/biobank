"use client";

import { useState } from "react";

import { useAuth, useLocale } from "@/components/providers";
import { Badge, Button, Card, ErrorBox, Field, Loading, Notice, Pagination, RequireRole, Table, Td, inputCls, useAsync } from "@/components/ui";
import { ApiError, api, qs } from "@/lib/api";
import { formatDate } from "@/lib/i18n";
import type { ModelsResponse, PageOf, Role, User } from "@/lib/types";

function Users() {
  const { t, td, locale } = useLocale();
  const { user: me } = useAuth();
  const { data, error, loading, reload } = useAsync(() => api<User[]>("/api/v1/admin/users"), []);
  const [form, setForm] = useState({ email: "", display_name: "", password: "", role: "reviewer" as Role });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={t("ad.users")}>
      {loading ? (
        <Loading />
      ) : error || !data ? (
        <ErrorBox error={error} onRetry={reload} />
      ) : (
        <Table head={[t("ad.reviewerCode"), t("login.email"), t("ad.displayName"), t("ad.role"), t("ad.active"), t("common.date"), ""]}>
          {data.map((u) => (
            <tr key={u.id}>
              <Td className="font-mono">{u.reviewer_code}</Td>
              <Td>
                <span dir="ltr">{u.email}</span>
              </Td>
              <Td>{u.display_name}</Td>
              <Td>
                <select
                  aria-label={t("ad.role")}
                  className={`${inputCls} w-40`}
                  value={u.role}
                  disabled={u.id === me?.id || busy}
                  onChange={(e) => run(() => api(`/api/v1/admin/users/${u.id}`, { method: "PATCH", body: { role: e.target.value } }))}
                >
                  {(["admin", "reviewer", "researcher"] as const).map((r) => (
                    <option key={r} value={r}>
                      {td(`role.${r}`, r)}
                    </option>
                  ))}
                </select>
              </Td>
              <Td>{u.is_active ? <Badge tone="teal">{t("common.yes")}</Badge> : <Badge>{t("common.no")}</Badge>}</Td>
              <Td className="whitespace-nowrap">{formatDate(locale, u.created_at)}</Td>
              <Td>
                {u.id !== me?.id && (
                  <Button variant="ghost" disabled={busy} onClick={() => run(() => api(`/api/v1/admin/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }))}>
                    {u.is_active ? t("ad.deactivate") : t("ad.activate")}
                  </Button>
                )}
              </Td>
            </tr>
          ))}
        </Table>
      )}
      <form
        className="mt-6 grid gap-3 md:grid-cols-5 md:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            await api("/api/v1/admin/users", { body: form });
            setForm({ email: "", display_name: "", password: "", role: "reviewer" });
          });
        }}
      >
        <Field label={t("login.email")} htmlFor="nu-email">
          <input id="nu-email" type="email" required dir="ltr" className={inputCls} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label={t("ad.displayName")} htmlFor="nu-name">
          <input id="nu-name" required className={inputCls} value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
        </Field>
        <Field label={t("login.password")} htmlFor="nu-pw">
          <input id="nu-pw" type="password" required minLength={10} autoComplete="new-password" dir="ltr" className={inputCls} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </Field>
        <Field label={t("ad.role")} htmlFor="nu-role">
          <select id="nu-role" className={inputCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            {(["admin", "reviewer", "researcher"] as const).map((r) => (
              <option key={r} value={r}>
                {td(`role.${r}`, r)}
              </option>
            ))}
          </select>
        </Field>
        <Button type="submit" busy={busy}>
          {t("ad.createUser")}
        </Button>
      </form>
      {err !== null && (
        <div className="mt-3">
          <ErrorBox error={err} />
        </div>
      )}
    </Card>
  );
}

type AppSettings = { reviews_required: number; store_analysis_text: boolean; auto_queue_abstained: boolean; auto_queue_needs_review: boolean };

function Settings() {
  const { t } = useLocale();
  const { data, error, loading, reload, setData } = useAsync(() => api<AppSettings>("/api/v1/admin/settings"), []);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;
  const toggle = (k: keyof AppSettings, label: string) => (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" className="h-4 w-4 accent-teal-700" checked={Boolean(data[k])} onChange={(e) => setData({ ...data, [k]: e.target.checked })} />
      {label}
    </label>
  );
  return (
    <Card title={t("ad.settings")}>
      <form
        className="space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setErr(null);
          setSaved(false);
          try {
            setData(await api<AppSettings>("/api/v1/admin/settings", { method: "PUT", body: data }));
            setSaved(true);
          } catch (x) {
            setErr(x);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label={t("ad.reviewsRequired")} htmlFor="st-rr">
          <input id="st-rr" type="number" min={1} max={5} className={`${inputCls} w-24`} value={data.reviews_required} onChange={(e) => setData({ ...data, reviews_required: Number(e.target.value) })} />
        </Field>
        {toggle("store_analysis_text", t("ad.storeText"))}
        {toggle("auto_queue_abstained", t("ad.autoAbstained"))}
        {toggle("auto_queue_needs_review", t("ad.autoNeedsReview"))}
        <Button type="submit" busy={busy}>
          {t("common.save")}
        </Button>
        {saved && <Notice tone="success">✓</Notice>}
        {err !== null && <ErrorBox error={err} />}
      </form>
    </Card>
  );
}

function SplitBuilder() {
  const { t } = useLocale();
  const [f, setF] = useState({ language: "ar", version: "v1", seed: 42, require_human_review: false });
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<Record<string, unknown> | null>(null);
  const [refused, setRefused] = useState<{ message: string; report: Record<string, unknown> } | null>(null);
  const [err, setErr] = useState<unknown>(null);
  return (
    <Card title={t("ad.splits")}>
      <p className="mb-3 text-sm text-slate-700">{t("ad.splitHelp")}</p>
      <form
        className="grid gap-3 md:grid-cols-5 md:items-end"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setOk(null);
          setRefused(null);
          setErr(null);
          try {
            const r = await api<{ report: Record<string, unknown> }>("/api/v1/datasets/splits", { body: f });
            setOk(r.report);
          } catch (x) {
            if (x instanceof ApiError && x.status === 422 && typeof x.detail === "object" && x.detail && "report" in x.detail) setRefused(x.detail as never);
            else setErr(x);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label={t("common.language")} htmlFor="sp-lang">
          <select id="sp-lang" className={inputCls} value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}>
            <option value="ar">العربية</option>
            <option value="en">English</option>
          </select>
        </Field>
        <Field label={t("ds.version")} htmlFor="sp-v">
          <input id="sp-v" required pattern="[A-Za-z0-9._\-]{1,64}" dir="ltr" className={inputCls} value={f.version} onChange={(e) => setF({ ...f, version: e.target.value })} />
        </Field>
        <Field label={t("ad.seed")} htmlFor="sp-seed">
          <input id="sp-seed" type="number" className={inputCls} value={f.seed} onChange={(e) => setF({ ...f, seed: Number(e.target.value) })} />
        </Field>
        <label className="flex min-h-10 items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-teal-700" checked={f.require_human_review} onChange={(e) => setF({ ...f, require_human_review: e.target.checked })} />
          {t("ad.requireHuman")}
        </label>
        <Button type="submit" busy={busy}>
          {t("ad.build")}
        </Button>
      </form>
      {ok && (
        <div className="mt-4 space-y-2">
          <Notice tone="success">{t("ad.splitOk", { version: f.version })}</Notice>
          <pre dir="ltr" className="max-h-80 overflow-auto rounded bg-slate-50 p-3 text-start text-xs">
            {JSON.stringify({ split_sizes: ok.split_sizes, label_distribution: ok.label_distribution, grouping: ok.grouping, shortfall_vs_target: ok.shortfall_vs_target }, null, 2)}
          </pre>
        </div>
      )}
      {refused && (
        <div className="mt-4 space-y-2">
          <Notice tone="warn" title={t("ad.splitRefused")}>
            {refused.message}
          </Notice>
          <pre dir="ltr" className="max-h-80 overflow-auto rounded bg-slate-50 p-3 text-start text-xs">
            {JSON.stringify(refused.report, null, 2)}
          </pre>
        </div>
      )}
      {err !== null && (
        <div className="mt-3">
          <ErrorBox error={err} />
        </div>
      )}
    </Card>
  );
}

function Models() {
  const { t } = useLocale();
  const { data, error, loading, reload } = useAsync(
    () => Promise.all([api<ModelsResponse>("/api/v1/models"), api<{ items: { id: number; run_tag: string; language: string; status: string; seed: number; test_macro_f1: number | null; data_sha256: string | null }[] }>("/api/v1/admin/training-runs")]),
    [],
  );
  const [err, setErr] = useState<unknown>(null);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;
  const [models, runs] = data;
  return (
    <Card title={t("ad.models")}>
      {models.versions.length === 0 ? (
        <Notice tone="warn">{t("ad.noModels")}</Notice>
      ) : (
        <Table head={["Tag", t("common.language"), t("common.status"), "Macro-F1", ""]}>
          {models.versions.map((m) => (
            <tr key={m.id}>
              <Td>
                <span dir="ltr" className="font-mono text-xs">
                  {m.version_tag}
                </span>
              </Td>
              <Td>{m.language}</Td>
              <Td>
                <Badge tone={m.status === "active" ? "teal" : "gray"}>{m.status}</Badge>
              </Td>
              <Td className="tabular-nums">{m.test_metrics.macro_f1 ?? "—"}</Td>
              <Td>
                {m.status !== "active" && (
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      setErr(null);
                      try {
                        await api(`/api/v1/models/${m.id}/activate`, { method: "POST" });
                        await reload();
                      } catch (x) {
                        setErr(x);
                      }
                    }}
                  >
                    {t("ad.activateModel")}
                  </Button>
                )}
              </Td>
            </tr>
          ))}
        </Table>
      )}
      <h3 className="mt-6 mb-2 text-sm font-semibold text-navy-900">{t("ad.runs")}</h3>
      {runs.items.length === 0 ? (
        <p className="text-sm text-slate-600">{t("common.none")}</p>
      ) : (
        <Table head={["Run", t("common.language"), t("common.status"), t("ad.seed"), "Macro-F1", "data sha256"]}>
          {runs.items.map((r) => (
            <tr key={r.id}>
              <Td className="font-mono text-xs">{r.run_tag}</Td>
              <Td>{r.language}</Td>
              <Td>{r.status}</Td>
              <Td>{r.seed}</Td>
              <Td className="tabular-nums">{r.test_macro_f1 ?? "—"}</Td>
              <Td className="font-mono text-[11px]">{r.data_sha256?.slice(0, 16) ?? "—"}</Td>
            </tr>
          ))}
        </Table>
      )}
      {err !== null && (
        <div className="mt-3">
          <ErrorBox error={err} />
        </div>
      )}
    </Card>
  );
}

interface AuditRow {
  id: number;
  created_at: string;
  actor: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown>;
}

function Audit() {
  const { t, locale } = useLocale();
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useAsync(() => api<PageOf<AuditRow>>(`/api/v1/admin/audit-logs${qs({ page, page_size: 20 })}`), [page]);
  const [seedErr, setSeedErr] = useState<unknown>(null);
  return (
    <Card
      title={t("ad.audit")}
      actions={
        <Button
          variant="ghost"
          onClick={async () => {
            setSeedErr(null);
            try {
              await api("/api/v1/admin/seed-registry", { method: "POST" });
              await reload();
            } catch (x) {
              setSeedErr(x);
            }
          }}
        >
          {t("ad.seedRegistry")}
        </Button>
      }
    >
      {seedErr !== null && <ErrorBox error={seedErr} />}
      {loading ? (
        <Loading />
      ) : error || !data ? (
        <ErrorBox error={error} onRetry={reload} />
      ) : (
        <>
          <Table head={[t("common.date"), t("ad.actor"), t("ad.action"), t("ad.entity"), t("common.details")]}>
            {data.items.map((r) => (
              <tr key={r.id}>
                <Td className="whitespace-nowrap">{formatDate(locale, r.created_at)}</Td>
                <Td className="font-mono text-xs">{r.actor ?? "—"}</Td>
                <Td className="font-mono text-xs">{r.action}</Td>
                <Td className="font-mono text-xs">
                  {r.entity_type}:{r.entity_id ?? ""}
                </Td>
                <Td>
                  <code dir="ltr" className="line-clamp-2 block max-w-md text-start text-[11px] break-all text-slate-600">
                    {JSON.stringify(r.details)}
                  </code>
                </Td>
              </tr>
            ))}
          </Table>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </Card>
  );
}

export default function AdminPage() {
  const { t } = useLocale();
  return (
    <RequireRole roles={["admin"]}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-navy-900">{t("ad.title")}</h1>
        <Users />
        <div className="grid gap-6 lg:grid-cols-2">
          <Settings />
          <Models />
        </div>
        <SplitBuilder />
        <Audit />
      </div>
    </RequireRole>
  );
}
