"use client";

import { useState } from "react";

import { BarList, LABEL_COLOR } from "@/components/charts";
import { useLocale } from "@/components/providers";
import { Badge, Button, Card, ErrorBox, LabelBadge, Notice, ReviewStatusBadge, Table, Td } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/i18n";
import type { Analysis, LabelName } from "@/lib/types";

export function AnalysisResult({ analysis, onChange }: { analysis: Analysis; onChange?: (a: Analysis) => void }) {
  const { t, td, locale } = useLocale();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const a = analysis;
  const p = a.prediction;

  async function requestReview() {
    setBusy(true);
    setErr(null);
    try {
      onChange?.(await api<Analysis>(`/api/v1/history/${a.id}/request-review`, { method: "POST" }));
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  const statusTone = a.status === "completed" ? "teal" : "amber";
  return (
    <div className="space-y-4" aria-live="polite">
      <Card
        title={t("analyze.result")}
        actions={
          <span className="text-xs text-slate-500">
            #{a.id} · {formatDate(locale, a.created_at)}
          </span>
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={statusTone}>{td(`analyze.status.${a.status}`, a.status)}</Badge>
          <Badge tone="navy">
            {t("analyze.detected")}: {a.language.detected} ({formatNumber(locale, a.language.confidence * 100, 0)}%)
          </Badge>
          {a.health_topic && (
            <Badge>
              {t("analyze.topic")}: {a.health_topic}
            </Badge>
          )}
          {a.model && (
            <Badge tone="gray">
              <span dir="ltr" className="font-mono">
                {a.model.version_tag}
              </span>
            </Badge>
          )}
        </div>

        {a.warnings.length > 0 && (
          <ul className="mt-3 list-inside list-disc text-sm text-amber-800">
            {a.warnings.map((w) => (
              <li key={w}>{td(`analyze.warning.${w}`, w)}</li>
            ))}
          </ul>
        )}
        {Object.keys(a.redactions).length > 0 && <p className="mt-2 text-xs text-slate-600">{t("analyze.redacted")}</p>}

        {!p ? (
          <div className="mt-4 space-y-2">
            <Notice tone="warn" title={td(`analyze.status.${a.status}`, a.status)}>
              <p>{t("analyze.noPrediction")}</p>
              {a.status === "model_not_trained" && <p className="mt-1">{t("model.notTrainedHelp")}</p>}
              {a.status === "unsupported_language" && <p className="mt-1">{t("analyze.unsupportedHelp")}</p>}
            </Notice>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-slate-600">{t("analyze.prediction")}:</span>
              <LabelBadge label={p.display_label} />
              <span className="text-sm text-slate-600">{t(`labeldesc.${p.display_label}`)}</span>
            </div>
            {p.abstained && <Notice tone="warn">{t("analyze.abstained")}</Notice>}
            <p className="text-sm">
              <span className="font-medium">{t("analyze.confidence")}: </span>
              {p.confidence !== null ? `${formatNumber(locale, p.confidence * 100, 1)}%` : <span className="text-slate-600">{t("analyze.confidenceNA")}</span>}
            </p>
            <div className="grid gap-6 md:grid-cols-2">
              {p.calibrated_probabilities && (
                <BarList
                  title={t("analyze.calibrated")}
                  max={1}
                  colorFor={(k) => LABEL_COLOR[k]}
                  data={(Object.keys(p.calibrated_probabilities) as LabelName[]).map((l) => ({ key: l, label: t(`label.${l}`), value: p.calibrated_probabilities![l] }))}
                />
              )}
              <BarList title={t("analyze.raw")} max={1} colorFor={() => "bg-slate-400"} data={(Object.keys(p.raw_scores) as LabelName[]).map((l) => ({ key: l, label: t(`label.${l}`), value: p.raw_scores[l] }))} />
            </div>
          </div>
        )}
      </Card>

      {p && a.explanation.tokens && a.explanation.tokens.length > 0 && (
        <Card title={t("analyze.explanation")}>
          <p className="mb-3 text-xs text-slate-600">{t("analyze.explanationNote")}</p>
          <ul className="flex flex-wrap gap-2">
            {a.explanation.tokens.map((tok, i) => (
              <li
                key={i}
                className={`rounded border px-2 py-1 text-sm ${tok.importance >= 0 ? "border-teal-600 bg-teal-50" : "border-slate-300 bg-slate-50"}`}
                title={String(tok.importance)}
              >
                {tok.token} <span className="font-mono text-xs text-slate-600">{tok.importance >= 0 ? "+" : ""}{formatNumber(locale, tok.importance, 3)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title={t("analyze.similar")}>
        <p className="mb-3 text-xs text-slate-600">{t("analyze.similarNote")}</p>
        <p className="mb-3 text-xs text-slate-600">{t("attribution.arafacts")}</p>
        {a.similar_claims.length === 0 ? (
          <p className="text-sm text-slate-700">{t("analyze.similarNone")}</p>
        ) : (
          <Table head={[t("common.text"), t("analyze.originalVerdict"), t("analyze.similarity"), t("analyze.factCheck")]}>
            {a.similar_claims.map((s) => (
              <tr key={s.sample_id}>
                <Td className="max-w-md min-w-48">{s.text}</Td>
                <Td>
                  <Badge>{s.original_label ?? "—"}</Badge>
                  <div className="mt-1 text-xs text-slate-500">{s.source_key}</div>
                </Td>
                <Td className="tabular-nums">{formatNumber(locale, s.similarity, 2)}</Td>
                <Td>
                  {s.fact_check_url ? (
                    <a href={s.fact_check_url} target="_blank" rel="noopener noreferrer nofollow" className="text-teal-700 underline">
                      {t("common.view")}
                    </a>
                  ) : (
                    "—"
                  )}
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title={t("analyze.verify")}>
          <ul className="space-y-1 text-sm">
            {a.verification_resources.map((r) => (
              <li key={r.url}>
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-teal-700 underline">
                  {r.name[locale]}
                </a>
              </li>
            ))}
          </ul>
        </Card>
        <Card title={t("analyze.review")}>
          <div className="flex flex-wrap items-center gap-3">
            <ReviewStatusBadge status={a.review_status} />
            {a.final_label_name && (
              <span className="text-sm">
                {t("history.final")}: <LabelBadge label={a.final_label_name} />
              </span>
            )}
            {a.review_status === "not_required" ? (
              <Button variant="secondary" busy={busy} onClick={requestReview}>
                {t("analyze.requestReview")}
              </Button>
            ) : (
              a.review_status === "pending" && <span className="text-sm text-slate-600">{t("analyze.reviewRequested")}</span>
            )}
          </div>
          {err !== null && (
            <div className="mt-3">
              <ErrorBox error={err} />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
