"use client";

import Link from "next/link";
import { useState } from "react";

import { useLocale } from "@/components/providers";
import { Badge, Card, EmptyState, ErrorBox, Field, LabelBadge, Loading, Pagination, ReviewStatusBadge, Table, Td, inputCls, useAsync } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/i18n";
import type { AnalysisSummary, PageOf } from "@/lib/types";

const STATUSES = ["completed", "model_not_trained", "model_unavailable", "unsupported_language"];
const REVIEW = ["not_required", "pending", "in_review", "agreed", "disagreement", "adjudicated"];

export default function HistoryPage() {
  const { t, td, locale } = useLocale();
  const [page, setPage] = useState(1);
  const [language, setLanguage] = useState("");
  const [status, setStatus] = useState("");
  const [review, setReview] = useState("");
  const { data, error, loading, reload } = useAsync(
    () => api<PageOf<AnalysisSummary>>(`/api/v1/history${qs({ page, page_size: 20, language, status, review_status: review })}`),
    [page, language, status, review],
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-navy-900">{t("history.title")}</h1>
      <Card>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Field label={t("common.language")} htmlFor="f-lang">
            <select id="f-lang" className={inputCls} value={language} onChange={(e) => (setLanguage(e.target.value), setPage(1))}>
              <option value="">{t("common.all")}</option>
              <option value="ar">العربية</option>
              <option value="en">English</option>
            </select>
          </Field>
          <Field label={t("common.status")} htmlFor="f-status">
            <select id="f-status" className={inputCls} value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))}>
              <option value="">{t("common.all")}</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {td(`analyze.status.${s}`, s)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("history.review")} htmlFor="f-review">
            <select id="f-review" className={inputCls} value={review} onChange={(e) => (setReview(e.target.value), setPage(1))}>
              <option value="">{t("common.all")}</option>
              {REVIEW.map((s) => (
                <option key={s} value={s}>
                  {td(`review.status.${s}`, s)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {loading ? (
          <Loading />
        ) : error || !data ? (
          <ErrorBox error={error} onRetry={reload} />
        ) : data.items.length === 0 ? (
          <EmptyState>{t("history.empty")}</EmptyState>
        ) : (
          <>
            <Table head={["#", t("common.date"), t("common.text"), t("common.status"), t("history.prediction"), t("history.review"), ""]}>
              {data.items.map((a) => (
                <tr key={a.id}>
                  <Td className="tabular-nums">{a.id}</Td>
                  <Td className="whitespace-nowrap">{formatDate(locale, a.created_at)}</Td>
                  <Td className="max-w-xs">
                    <span dir="auto" className="line-clamp-2">
                      {a.text_preview ?? "—"}
                    </span>
                  </Td>
                  <Td>
                    <Badge tone={a.status === "completed" ? "teal" : "amber"}>{td(`analyze.status.${a.status}`, a.status)}</Badge>
                  </Td>
                  <Td>
                    <LabelBadge label={a.abstained ? "NEEDS_REVIEW" : a.predicted_label_name} />
                    {a.confidence !== null && <div className="mt-1 text-xs text-slate-500">{formatNumber(locale, a.confidence * 100, 1)}%</div>}
                  </Td>
                  <Td>
                    <ReviewStatusBadge status={a.review_status} />
                  </Td>
                  <Td>
                    <Link href={`/history/${a.id}`} className="text-teal-700 underline">
                      {t("common.details")}
                    </Link>
                  </Td>
                </tr>
              ))}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
