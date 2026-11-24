"use client";

import { useState } from "react";

import { useAuth, useLocale } from "@/components/providers";
import { Card, ErrorBox, Field, Loading, Notice, inputCls, useAsync } from "@/components/ui";
import { api, qs } from "@/lib/api";
import type { DictKey } from "@/lib/i18n";

interface Catalog {
  types: Record<string, { formats: string[] }>;
  models: { id: number; version_tag: string; language: string }[];
  datasets: { id: number; name: string; version: string; kind: string; is_synthetic: boolean }[];
}

const linkCls = "inline-flex min-h-10 items-center rounded-lg border border-navy-800 px-4 text-sm font-medium text-navy-900 hover:bg-navy-50";

export default function ReportsPage() {
  const { t } = useLocale();
  const { hasRole } = useAuth();
  const { data, error, loading, reload } = useAsync(() => api<Catalog>("/api/v1/reports"), []);
  const [datasetId, setDatasetId] = useState<string>("");
  const [modelId, setModelId] = useState<string>("");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;

  const row = (type: string, label: DictKey, extra?: Record<string, string>, disabled = false) =>
    data.types[type] && (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 py-3 last:border-0">
      <span className="font-medium text-navy-900">{t(label)}</span>
      <div className="flex gap-2">
        {data.types[type].formats.map((f) =>
          disabled ? (
            <span key={f} className={`${linkCls} cursor-not-allowed opacity-40`} aria-disabled>
              {f.toUpperCase()}
            </span>
          ) : (
            <a key={f} className={linkCls} href={`/api/v1/reports${qs({ type, format: f, ...extra })}`} download>
              {t("common.download")} {f.toUpperCase()}
            </a>
          ),
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-navy-900">{t("rp.title")}</h1>
      <Notice>{t("rp.intro")}</Notice>
      <Card>
        {row("summary", "rp.summary")}
        {row("analyses", "rp.analyses")}
        {row("reviews", "rp.reviews")}
        {row("sources", "rp.sources")}
        {hasRole("admin") && row("audit", "rp.audit")}
      </Card>
      {data.types.dataset && <Card title={t("rp.dataset")}>
        <Field label={t("rp.chooseDataset")} htmlFor="rp-ds">
          <select id="rp-ds" className={inputCls} value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            <option value="">—</option>
            {data.datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}@{d.version} ({d.kind}
                {d.is_synthetic ? ", synthetic" : ""})
              </option>
            ))}
          </select>
        </Field>
        {row("dataset", "rp.dataset", { dataset_id: datasetId }, !datasetId)}
      </Card>}
      <Card title={t("rp.evaluation")}>
        {data.models.length === 0 ? (
          <Notice tone="warn">{t("rp.noModels")}</Notice>
        ) : (
          <>
            <Field label={t("rp.chooseModel")} htmlFor="rp-m">
              <select id="rp-m" className={inputCls} value={modelId} onChange={(e) => setModelId(e.target.value)}>
                <option value="">—</option>
                {data.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.version_tag} ({m.language})
                  </option>
                ))}
              </select>
            </Field>
            {row("evaluation", "rp.evaluation", { model_id: modelId }, !modelId)}
          </>
        )}
      </Card>
    </div>
  );
}
