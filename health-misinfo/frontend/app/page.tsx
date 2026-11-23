"use client";

import Link from "next/link";

import { ProgressBar } from "@/components/charts";
import { useLocale } from "@/components/providers";
import { Badge, Card, Disclaimer, ErrorBox, Loading, Notice } from "@/components/ui";
import { useAsync } from "@/components/ui";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/i18n";
import type { DatasetsResponse, ModelsResponse } from "@/lib/types";

interface AnalyticsLite {
  measured_results_available: boolean;
  models: unknown[];
  analyses: { total: number };
  reviews: { open_analyses: number; open_samples: number };
}

export default function Dashboard() {
  const { t, td, locale } = useLocale();
  const { data, error, loading, reload } = useAsync(
    () =>
      Promise.all([
        api<ModelsResponse>("/api/v1/models"),
        api<DatasetsResponse>("/api/v1/datasets"),
        api<AnalyticsLite>("/api/v1/analytics"),
      ]),
    [],
  );
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;
  const [models, datasets, analytics] = data;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-navy-900">{t("dash.title")}</h1>
      <Disclaimer />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-sm text-slate-600">{t("dash.analyses")}</p>
          <p className="mt-1 text-3xl font-bold text-navy-900 tabular-nums">{formatNumber(locale, analytics.analyses.total)}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-600">{t("dash.openReviews")}</p>
          <p className="mt-1 text-3xl font-bold text-navy-900 tabular-nums">{formatNumber(locale, analytics.reviews.open_analyses + analytics.reviews.open_samples)}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-600">{t("dash.measured")}</p>
          <p className="mt-1 text-base font-semibold text-navy-900">
            {analytics.measured_results_available ? t("dash.measuredSome", { n: analytics.models.length }) : t("dash.measuredNone")}
          </p>
        </Card>
      </div>

      <Card title={t("dash.models")}>
        <div className="grid gap-4 md:grid-cols-2">
          {models.slots.map((s) => (
            <div key={s.language} className="rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-navy-900">{s.display_name[locale]}</p>
                <Badge tone={s.state === "ready" ? "teal" : "amber"}>{td(`model.state.${s.state}`, s.state)}</Badge>
              </div>
              <p className="mt-1 font-mono text-xs text-slate-600" dir="ltr">
                {s.base_model}
              </p>
              {s.active_version ? (
                <p className="mt-2 text-sm text-slate-700">
                  {t("model.activeVersion")}: <span className="font-mono">{s.active_version.version_tag}</span> ·{" "}
                  {s.active_version.is_calibrated ? t("model.calibrated") : t("model.uncalibrated")}
                </p>
              ) : (
                <p className="mt-2 text-sm text-slate-700">{t("model.notTrainedHelp")}</p>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Card
        title={t("dash.datasetProgress")}
        actions={
          <Link href="/datasets" className="text-sm text-teal-700 underline underline-offset-2">
            {t("nav.datasets")}
          </Link>
        }
      >
        <div className="grid gap-6 md:grid-cols-2">
          {(["ar", "en"] as const).map((lang) => {
            const p = datasets.progress[lang];
            return (
              <div key={lang} className="space-y-3">
                <p className="font-semibold text-navy-900">{lang === "ar" ? "العربية / Arabic" : "English / الإنجليزية"}</p>
                <ProgressBar label={t("dash.eligible")} value={p.eligible} target={p.target} />
                <ProgressBar label={t("dash.reviewed")} value={p.eligible_human_reviewed} target={p.target} />
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <dt className="text-slate-600">{t("dash.imported")}</dt>
                  <dd className="tabular-nums">{formatNumber(locale, p.imported)}</dd>
                  <dt className="text-slate-600">{t("dash.shortfall")}</dt>
                  <dd className="tabular-nums font-semibold text-amber-800">{formatNumber(locale, p.shortfall)}</dd>
                </dl>
              </div>
            );
          })}
        </div>
        <div className="mt-4">
          <Notice>{t("dash.targetNote")}</Notice>
        </div>
      </Card>
    </div>
  );
}
