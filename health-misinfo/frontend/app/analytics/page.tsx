"use client";

import { BarList, ConfusionMatrix, LABEL_COLOR } from "@/components/charts";
import { useLocale } from "@/components/providers";
import { Badge, Card, ErrorBox, Loading, Notice, Table, Td, useAsync } from "@/components/ui";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/i18n";
import { LABELS } from "@/lib/types";

type Dist = Record<string, Record<string, number>>;
interface ModelMetrics {
  id: number;
  version_tag: string;
  language: string;
  base_model: string;
  status: string;
  test: Record<string, number | null>;
  per_class: Record<string, { precision: number; recall: number; f1: number; support: number }> | null;
  confusion_matrix: { labels: string[]; matrix: number[][] } | null;
  calibration: { ece_raw?: number; ece_calibrated?: number } | null;
}
interface Analytics {
  measured_results_available: boolean;
  datasets: {
    eligibility_by_language: Dist;
    eligible_label_distribution: Dist;
    exclusion_reasons_by_language: Dist;
    by_source: Dist;
  };
  splits: { id: number; language: string; version: string; split_sizes: Record<string, number> | null; label_distribution: Dist | null }[];
  models: ModelMetrics[];
  analyses: { total: number; by_status: Record<string, number>; by_language: Record<string, number>; by_predicted_label: Record<string, number> };
  reviews: { total: number; agreement: { items_with_2plus_reviews: number; percent_agreement: number | null; cohen_kappa: number | null } };
}

const bars = (o: Record<string, number> | undefined) =>
  Object.entries(o ?? {})
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({ key: k, label: k, value: v }));

export default function AnalyticsPage() {
  const { t, td, locale } = useLocale();
  const { data, error, loading, reload } = useAsync(() => api<Analytics>("/api/v1/analytics"), []);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;
  const pct = (v: number | null | undefined) => (v == null ? "—" : `${formatNumber(locale, v * 100, 2)}%`);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-navy-900">{t("an.title")}</h1>

      <Card title={t("an.models")} actions={data.measured_results_available && <Badge tone="teal">{t("an.measuredBadge")}</Badge>}>
        {!data.measured_results_available ? (
          <Notice tone="warn" title={t("an.noMeasured")}>
            {t("an.noMeasuredBody")}
          </Notice>
        ) : (
          <div className="space-y-6">
            <Table head={["Model", t("common.language"), "n", t("an.accuracy"), t("an.macroP"), t("an.macroR"), t("an.macroF1"), "ECE"]}>
              {data.models.map((m) => (
                <tr key={m.id}>
                  <Td>
                    <span dir="ltr" className="font-mono text-xs">
                      {m.version_tag}
                    </span>
                    <div className="text-xs text-slate-500">{m.status}</div>
                  </Td>
                  <Td>{m.language}</Td>
                  <Td className="tabular-nums">{m.test.n ?? "—"}</Td>
                  <Td className="tabular-nums">{pct(m.test.accuracy)}</Td>
                  <Td className="tabular-nums">{pct(m.test.macro_precision)}</Td>
                  <Td className="tabular-nums">{pct(m.test.macro_recall)}</Td>
                  <Td className="tabular-nums font-semibold">{pct(m.test.macro_f1)}</Td>
                  <Td className="tabular-nums text-xs">
                    {m.calibration?.ece_raw != null ? `${formatNumber(locale, m.calibration.ece_raw, 3)} → ${formatNumber(locale, m.calibration.ece_calibrated ?? 0, 3)}` : "—"}
                  </Td>
                </tr>
              ))}
            </Table>
            <div className="grid gap-6 lg:grid-cols-2">
              {data.models.map((m) => (
                <div key={m.id} className="rounded-lg border border-slate-200 p-4">
                  <p className="mb-1 text-sm font-semibold">{t("an.confusion", { model: m.version_tag })}</p>
                  <p className="mb-3 text-xs text-slate-500">{t("an.rowsTrue")}</p>
                  {m.confusion_matrix && <ConfusionMatrix matrix={m.confusion_matrix.matrix} labels={m.confusion_matrix.labels.map((l) => td(`label.${l}`, l))} />}
                  {m.per_class && (
                    <div className="mt-4">
                      <Table head={["", t("an.precision"), t("an.recall"), t("an.f1"), t("an.support")]} caption={t("an.perClass")}>
                        {Object.entries(m.per_class).map(([c, v]) => (
                          <tr key={c}>
                            <Td>{td(`label.${c}`, c)}</Td>
                            <Td className="tabular-nums">{pct(v.precision)}</Td>
                            <Td className="tabular-nums">{pct(v.recall)}</Td>
                            <Td className="tabular-nums">{pct(v.f1)}</Td>
                            <Td className="tabular-nums">{v.support}</Td>
                          </tr>
                        ))}
                      </Table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {(["ar", "en"] as const).map((lang) => (
          <Card key={lang} title={`${t("an.datasetDist")} — ${lang}`}>
            <div className="space-y-6">
              <BarList
                title={t("ds.labelDist")}
                colorFor={(k) => LABEL_COLOR[k]}
                data={LABELS.map((l) => ({ key: l, label: t(`label.${l}`), value: data.datasets.eligible_label_distribution[lang]?.[l] ?? 0 }))}
              />
              <BarList title={t("an.eligibility")} data={bars(data.datasets.eligibility_by_language[lang])} />
              <BarList title={t("an.exclusions")} colorFor={() => "bg-navy-700"} data={bars(data.datasets.exclusion_reasons_by_language[lang])} />
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={t("an.sources")}>
          <Table head={[t("ds.source"), "eligible", "pending", "excluded"]}>
            {Object.entries(data.datasets.by_source).map(([src, v]) => (
              <tr key={src}>
                <Td>{src}</Td>
                <Td className="tabular-nums">{formatNumber(locale, v.eligible ?? 0)}</Td>
                <Td className="tabular-nums">{formatNumber(locale, v.pending ?? 0)}</Td>
                <Td className="tabular-nums">{formatNumber(locale, v.excluded ?? 0)}</Td>
              </tr>
            ))}
          </Table>
        </Card>
        <Card title={t("an.splits")}>
          {data.splits.length === 0 ? (
            <p className="text-sm text-slate-600">{t("common.none")}</p>
          ) : (
            <Table head={[t("ds.version"), t("common.language"), "train / val / test"]}>
              {data.splits.map((s) => (
                <tr key={s.id}>
                  <Td>
                    <span dir="ltr">{s.version}</span>
                  </Td>
                  <Td>{s.language}</Td>
                  <Td className="tabular-nums">{s.split_sizes ? `${s.split_sizes.train} / ${s.split_sizes.validation} / ${s.split_sizes.test}` : "—"}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={t("an.analyses")}>
          <BarList title={t("common.status")} data={bars(data.analyses.by_status).map((b) => ({ ...b, label: td(`analyze.status.${b.key}`, b.key) }))} />
        </Card>
        <Card title={t("an.reviews")}>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-slate-600">{t("an.doubly")}</dt>
            <dd className="tabular-nums">{data.reviews.agreement.items_with_2plus_reviews}</dd>
            <dt className="text-slate-600">{t("an.agreement")}</dt>
            <dd className="tabular-nums">{pct(data.reviews.agreement.percent_agreement)}</dd>
            <dt className="text-slate-600">{t("an.kappa")}</dt>
            <dd className="tabular-nums">{data.reviews.agreement.cohen_kappa == null ? "—" : formatNumber(locale, data.reviews.agreement.cohen_kappa, 3)}</dd>
          </dl>
        </Card>
      </div>
    </div>
  );
}
