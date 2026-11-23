"use client";

import { useParams } from "next/navigation";

import { AnalysisResult } from "@/components/analysis-result";
import { useLocale } from "@/components/providers";
import { Card, Disclaimer, ErrorBox, LabelBadge, Loading, Table, Td, useAsync } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/i18n";
import type { Analysis } from "@/lib/types";

export default function HistoryDetail() {
  const { id } = useParams<{ id: string }>();
  const { t, locale } = useLocale();
  const { data, error, loading, reload, setData } = useAsync(() => api<Analysis>(`/api/v1/history/${encodeURIComponent(id)}`), [id]);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-navy-900">
        {t("history.title")} #{data.id}
      </h1>
      <Disclaimer />
      {data.text && (
        <Card title={t("common.text")}>
          <p dir="auto" className="whitespace-pre-wrap text-slate-900">
            {data.text}
          </p>
        </Card>
      )}
      <AnalysisResult analysis={data} onChange={setData} />
      <Card title={t("history.reviews")}>
        {!data.reviews || data.reviews.length === 0 ? (
          <p className="text-sm text-slate-600">{t("history.noReviews")}</p>
        ) : (
          <Table head={[t("ad.reviewerCode"), t("rv.label"), t("rv.evidence"), t("rv.notes"), t("common.date")]}>
            {data.reviews.map((r) => (
              <tr key={r.id}>
                <Td>
                  {r.reviewer_code}
                  {r.is_adjudication && <span className="ms-1 text-xs text-teal-700">({t("rv.adjudicate")})</span>}
                </Td>
                <Td>
                  <LabelBadge label={r.label_name} />
                </Td>
                <Td>
                  <ul className="space-y-1">
                    {r.evidence_urls.map((u) => (
                      <li key={u}>
                        <a href={u} target="_blank" rel="noopener noreferrer nofollow" className="break-all text-teal-700 underline" dir="ltr">
                          {u}
                        </a>
                      </li>
                    ))}
                  </ul>
                </Td>
                <Td className="max-w-xs whitespace-pre-wrap">{r.notes ?? "—"}</Td>
                <Td className="whitespace-nowrap">{formatDate(locale, r.created_at)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
