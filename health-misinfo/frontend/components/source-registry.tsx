"use client";

import { useState } from "react";

import { useAuth, useLocale } from "@/components/providers";
import { Badge, Button, Card, ErrorBox, Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { Source } from "@/lib/types";

function LicenseForm({ source, onSaved }: { source: Source; onSaved: () => void }) {
  const { t, td } = useLocale();
  const [status, setStatus] = useState(source.license_status);
  const [evidence, setEvidence] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/api/v1/sources/${source.key}`, { method: "PATCH", body: { license_status: status, license_evidence: evidence } });
      setEvidence("");
      onSaved();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save} className="mt-3 grid gap-2 rounded-lg bg-slate-50 p-3 md:grid-cols-[12rem_1fr_auto] md:items-end">
      <Field label={t("ds.license")} htmlFor={`ls-${source.key}`}>
        <select id={`ls-${source.key}`} className={inputCls} value={status} onChange={(e) => setStatus(e.target.value)}>
          {["verified", "unclear_needs_review", "unknown", "not_a_dataset"].map((s) => (
            <option key={s} value={s}>
              {td(`ds.licenseStatus.${s}`, s)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("ds.evidence")} htmlFor={`le-${source.key}`}>
        <input id={`le-${source.key}`} required minLength={10} className={inputCls} value={evidence} onChange={(e) => setEvidence(e.target.value)} />
      </Field>
      <Button type="submit" busy={busy} disabled={evidence.length < 10}>
        {t("ds.reviewLicense")}
      </Button>
      {error !== null && (
        <div className="md:col-span-3">
          <ErrorBox error={error} />
        </div>
      )}
    </form>
  );
}

export function SourceRegistry({ sources, onChange }: { sources: Source[]; onChange: () => void }) {
  const { t, td } = useLocale();
  const { hasRole } = useAuth();
  return (
    <Card title={t("ds.registry")}>
      <div className="space-y-4">
        {sources.map((s) => (
          <details key={s.key} className="rounded-lg border border-slate-200 p-4">
            <summary className="flex cursor-pointer flex-wrap items-center gap-2">
              <span className="font-semibold text-navy-900">{s.name}</span>
              <Badge tone={s.license_status === "verified" ? "teal" : s.license_status === "not_a_dataset" ? "gray" : "amber"}>
                {td(`ds.licenseStatus.${s.license_status}`, s.license_status)}
              </Badge>
              <Badge tone={s.text_available ? "navy" : "red"}>
                {t("ds.textAvailable")}: {s.text_available ? t("common.yes") : t("common.no")}
              </Badge>
              <span className="font-mono text-xs text-slate-500">{s.training_use_status}</span>
            </summary>
            <dl className="mt-3 grid gap-x-4 gap-y-2 text-sm md:grid-cols-[12rem_1fr]">
              <dt className="text-slate-600">{t("ds.license")}</dt>
              <dd>
                {s.license_name ?? "—"}
                {s.license_url && (
                  <a href={s.license_url} target="_blank" rel="noopener noreferrer" className="ms-2 text-teal-700 underline">
                    ↗
                  </a>
                )}
              </dd>
              <dt className="text-slate-600">{t("ds.evidence")}</dt>
              <dd className="whitespace-pre-wrap text-slate-800">{s.license_evidence ?? "—"}</dd>
              <dt className="text-slate-600">{t("ds.source")}</dt>
              <dd dir="ltr" className="break-all text-start">
                {s.official_url ? (
                  <a href={s.official_url} target="_blank" rel="noopener noreferrer" className="text-teal-700 underline">
                    {s.official_url}
                  </a>
                ) : (
                  "—"
                )}
              </dd>
              <dt className="text-slate-600">{t("ds.mappingStatus")}</dt>
              <dd dir="ltr" className="text-start font-mono text-xs">
                {s.label_mapping ? `${s.label_mapping.mapping_version ?? ""} ${JSON.stringify(s.label_mapping.entry_status_counts ?? s.label_mapping.error ?? {})}` : "—"}
              </dd>
              <dt className="text-slate-600">{t("ds.citation")}</dt>
              <dd dir="ltr" className="break-all text-start font-mono text-xs">
                {s.citation ?? "—"}
              </dd>
              <dt className="text-slate-600">{t("ds.notesTitle")}</dt>
              <dd>
                <ul className="list-inside list-disc space-y-1" dir="ltr">
                  {s.notes.map((n, i) => (
                    <li key={i} className="text-start">
                      {n}
                    </li>
                  ))}
                </ul>
              </dd>
            </dl>
            {hasRole("admin") && <LicenseForm source={s} onSaved={onChange} />}
          </details>
        ))}
      </div>
    </Card>
  );
}
