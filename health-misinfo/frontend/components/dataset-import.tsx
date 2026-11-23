"use client";

import { useState } from "react";

import { useLocale } from "@/components/providers";
import { Button, Card, ErrorBox, Field, Notice, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import { LABELS, type Source } from "@/lib/types";

interface Preview {
  file_name: string;
  rows: number;
  columns: string[];
  head: Record<string, string>[];
  declares_synthetic: boolean;
  label_values?: Record<string, number>;
}

export function DatasetImport({ sources, onImported }: { sources: Source[]; onImported: () => void }) {
  const { t } = useLocale();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [cols, setCols] = useState({ text: "", label: "", id: "", group: "", url: "", evidence: "" });
  const [meta, setMeta] = useState({ name: "", version: "v1", language: "ar", source_key: "user_upload", license_note: "", notes: "" });
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [useRegistry, setUseRegistry] = useState(false);
  const [synthetic, setSynthetic] = useState(false);
  const [licenseOk, setLicenseOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);

  async function doPreview(labelColumn?: string) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (labelColumn) fd.append("label_column", labelColumn);
      const p = await api<Preview>("/api/v1/datasets/preview", { form: fd });
      setPreview(p);
      if (!labelColumn) {
        const guess = (names: string[]) => p.columns.find((c) => names.includes(c.toLowerCase())) ?? "";
        const label = guess(["label", "source_label", "verdict"]);
        setCols({ text: guess(["text", "claim", "content"]) || p.columns[0], label, id: guess(["id", "claimid", "claim_id"]), group: guess(["group_key"]), url: guess(["source_url", "url"]), evidence: guess(["evidence_urls", "sources"]) });
        setSynthetic(p.declares_synthetic);
        if (label) await doPreview(label);
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      Object.entries(meta).forEach(([k, v]) => v && fd.append(k, v));
      fd.append("text_column", cols.text);
      if (cols.label) fd.append("label_column", cols.label);
      else fd.append("label_column", "");
      if (cols.id) fd.append("id_column", cols.id);
      if (cols.group) fd.append("group_key_column", cols.group);
      if (cols.url) fd.append("source_url_column", cols.url);
      if (cols.evidence) fd.append("evidence_urls_column", cols.evidence);
      const chosen = Object.fromEntries(Object.entries(mapping).filter(([, v]) => v));
      if (useRegistry) fd.append("use_registry_mapping", "true");
      else if (Object.keys(chosen).length) fd.append("label_mapping", JSON.stringify(chosen));
      fd.append("is_synthetic", String(synthetic));
      fd.append("license_confirmed", String(licenseOk));
      const res = await api<{ imported_count: number; stats: { eligible: number } }>("/api/v1/datasets/import", { form: fd });
      setDone(t("ds.imported", { n: res.imported_count, e: res.stats.eligible }));
      onImported();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const colSelect = (key: keyof typeof cols, label: string, optional = true) => (
    <Field label={label} htmlFor={`col-${key}`}>
      <select
        id={`col-${key}`}
        className={inputCls}
        value={cols[key]}
        onChange={(e) => {
          setCols({ ...cols, [key]: e.target.value });
          if (key === "label") {
            setMapping({});
            void doPreview(e.target.value || undefined);
          }
        }}
      >
        {optional && <option value="">—</option>}
        {preview?.columns.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </Field>
  );

  return (
    <Card title={t("ds.import")}>
      <form onSubmit={submit} className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label={t("ds.file")} htmlFor="ds-file">
            <input
              id="ds-file"
              type="file"
              accept=".csv,.tsv,.json,.jsonl"
              className="text-sm"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setPreview(null);
                setDone(null);
              }}
            />
          </Field>
          <Button type="button" variant="secondary" disabled={!file} busy={busy && !preview} onClick={() => void doPreview()}>
            {t("ds.preview")}
          </Button>
        </div>

        {preview && (
          <>
            <p className="text-sm text-slate-700">
              {preview.file_name} · {preview.rows} {t("ds.rows")} · {t("ds.columns")}: <span dir="ltr">{preview.columns.join(", ")}</span>
            </p>
            {preview.declares_synthetic && <Notice tone="warn">{t("ds.declaresSynthetic")}</Notice>}
            <div className="grid gap-3 md:grid-cols-3">
              <Field label={t("ds.name")} htmlFor="ds-name">
                <input id="ds-name" required pattern="[A-Za-z0-9._\-]{1,120}" dir="ltr" className={inputCls} value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} />
              </Field>
              <Field label={t("ds.version")} htmlFor="ds-version">
                <input id="ds-version" required pattern="[A-Za-z0-9._\-]{1,64}" dir="ltr" className={inputCls} value={meta.version} onChange={(e) => setMeta({ ...meta, version: e.target.value })} />
              </Field>
              <Field label={t("common.language")} htmlFor="ds-lang">
                <select id="ds-lang" className={inputCls} value={meta.language} onChange={(e) => setMeta({ ...meta, language: e.target.value })}>
                  <option value="ar">العربية</option>
                  <option value="en">English</option>
                </select>
              </Field>
              {colSelect("text", t("ds.textColumn"), false)}
              {colSelect("label", t("ds.labelColumn"))}
              {colSelect("id", t("ds.idColumn"))}
              {colSelect("group", t("ds.groupColumn"))}
              {colSelect("url", t("ds.urlColumn"))}
              {colSelect("evidence", t("ds.evidenceColumn"))}
              <Field label={t("ds.sourceKey")} htmlFor="ds-source">
                <select id="ds-source" className={inputCls} value={meta.source_key} onChange={(e) => setMeta({ ...meta, source_key: e.target.value })}>
                  <option value="user_upload">{t("ds.userUpload")}</option>
                  {sources
                    .filter((s) => s.license_status !== "not_a_dataset")
                    .map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.name}
                      </option>
                    ))}
                </select>
              </Field>
            </div>

            {cols.label && preview.label_values && (
              <fieldset className="rounded-lg border border-slate-200 p-4">
                <legend className="px-1 text-sm font-semibold text-navy-900">{t("ds.mapping")}</legend>
                <p className="mb-3 text-xs text-slate-600">{t("ds.mappingHelp")}</p>
                {meta.source_key !== "user_upload" && sources.find((s) => s.key === meta.source_key)?.label_mapping && (
                  <label className="mb-3 flex items-center gap-2 text-sm">
                    <input type="checkbox" className="h-4 w-4 accent-teal-700" checked={useRegistry} onChange={(e) => setUseRegistry(e.target.checked)} />
                    {t("ds.useRegistryMapping")}
                  </label>
                )}
                {!useRegistry && (
                  <div className="grid gap-2 md:grid-cols-2">
                    {Object.entries(preview.label_values).map(([value, n]) => (
                      <label key={value} className="flex items-center justify-between gap-2 text-sm">
                        <span dir="auto">
                          {value} <span className="text-xs text-slate-500">({n})</span>
                        </span>
                        <select className={`${inputCls} max-w-48`} value={mapping[value] ?? ""} onChange={(e) => setMapping({ ...mapping, [value]: e.target.value })} aria-label={value}>
                          <option value="">{t("ds.mappingNone")}</option>
                          {LABELS.map((l) => (
                            <option key={l} value={l}>
                              {t(`label.${l}`)}
                            </option>
                          ))}
                          <option value="EXCLUDE">EXCLUDE</option>
                        </select>
                      </label>
                    ))}
                  </div>
                )}
              </fieldset>
            )}

            <div className="grid gap-3 md:grid-cols-2">
              <Field label={t("ds.licenseNote")} htmlFor="ds-lic">
                <input id="ds-lic" className={inputCls} value={meta.license_note} onChange={(e) => setMeta({ ...meta, license_note: e.target.value })} />
              </Field>
              <Field label={t("ds.notes")} htmlFor="ds-notes">
                <input id="ds-notes" className={inputCls} value={meta.notes} onChange={(e) => setMeta({ ...meta, notes: e.target.value })} />
              </Field>
            </div>
            <div className="flex flex-col gap-2 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" className="h-4 w-4 accent-teal-700" checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} />
                {t("ds.isSynthetic")}
              </label>
              {meta.source_key === "user_upload" && (
                <label className="flex items-center gap-2">
                  <input type="checkbox" className="h-4 w-4 accent-teal-700" checked={licenseOk} onChange={(e) => setLicenseOk(e.target.checked)} />
                  {t("ds.licenseConfirmed")}
                </label>
              )}
            </div>
            <Button type="submit" busy={busy} disabled={!meta.name || !cols.text}>
              {t("ds.importSubmit")}
            </Button>
          </>
        )}
        {error !== null && <ErrorBox error={error} />}
        {done && <Notice tone="success">{done}</Notice>}
      </form>
    </Card>
  );
}
