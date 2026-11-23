"use client";

import { useState } from "react";

import { useAuth, useLocale } from "@/components/providers";
import { Badge, Button, Card, EmptyState, ErrorBox, Field, LabelBadge, Loading, Notice, Pagination, RequireRole, ReviewStatusBadge, inputCls, useAsync } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { formatNumber } from "@/lib/i18n";
import { LABELS, type LabelName, type PageOf } from "@/lib/types";

interface PendingItem {
  target_type: "analysis" | "sample";
  target_id: number;
  text: string | null;
  language: string;
  review_status: string;
  review_count: number;
  already_reviewed_by_me: boolean;
  reviews: { reviewer_code: string; label_name: LabelName; is_adjudication: boolean; notes: string | null }[] | null;
  predicted_label_name?: LabelName | null;
  abstained?: boolean;
  confidence?: number | null;
  status?: string;
  dataset?: string;
  is_synthetic?: boolean;
  original_label?: string | null;
  mapped_label_name?: LabelName | null;
  fact_check_url?: string | null;
  evidence_urls?: string[];
  exclusion_reason?: string | null;
}

function ReviewForm({ item, onDone }: { item: PendingItem; onDone: (msg: string) => void }) {
  const { t, td } = useLocale();
  const { hasRole } = useAuth();
  const [label, setLabel] = useState<LabelName | "">("");
  const [evidence, setEvidence] = useState("");
  const [notes, setNotes] = useState("");
  const [adjudicate, setAdjudicate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const canReview = !item.already_reviewed_by_me || adjudicate;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ target_review_status: string }>("/api/v1/reviews", {
        body: {
          target_type: item.target_type,
          target_id: item.target_id,
          label,
          evidence_urls: evidence.split(/\s+/).filter(Boolean),
          notes: notes || null,
          is_adjudication: adjudicate,
        },
      });
      onDone(t("rv.submitted", { status: td(`review.status.${r.target_review_status}`, r.target_review_status) }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const fid = `${item.target_type}-${item.target_id}`;
  return (
    <form onSubmit={submit} className="mt-4 grid gap-3 border-t border-slate-100 pt-4 md:grid-cols-2">
      <fieldset className="md:col-span-2">
        <legend className="mb-2 text-sm font-medium">{t("rv.label")}</legend>
        <div className="flex flex-wrap gap-3">
          {LABELS.map((l) => (
            <label key={l} className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 px-3 text-sm has-[:checked]:border-teal-700 has-[:checked]:bg-teal-50">
              <input type="radio" name={`label-${fid}`} value={l} checked={label === l} onChange={() => setLabel(l)} className="accent-teal-700" required />
              {t(`label.${l}`)}
            </label>
          ))}
        </div>
      </fieldset>
      <Field label={t("rv.evidence")} htmlFor={`ev-${fid}`}>
        <textarea id={`ev-${fid}`} rows={3} dir="ltr" className={inputCls} value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="https://" />
      </Field>
      <Field label={t("rv.notes")} htmlFor={`nt-${fid}`}>
        <textarea id={`nt-${fid}`} rows={3} dir="auto" className={inputCls} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <div className="flex flex-wrap items-center gap-4 md:col-span-2">
        {hasRole("admin") && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-teal-700" checked={adjudicate} onChange={(e) => setAdjudicate(e.target.checked)} />
            {t("rv.adjudicate")}
          </label>
        )}
        <Button type="submit" busy={busy} disabled={!label || !canReview}>
          {t("common.submit")}
        </Button>
      </div>
      {error !== null && (
        <div className="md:col-span-2">
          <ErrorBox error={error} />
        </div>
      )}
    </form>
  );
}

function Queue({ type }: { type: "analysis" | "sample" }) {
  const { t, locale } = useLocale();
  const [page, setPage] = useState(1);
  const [msg, setMsg] = useState<string | null>(null);
  const { data, error, loading, reload } = useAsync(() => api<PageOf<PendingItem>>(`/api/v1/reviews/pending${qs({ target_type: type, page, page_size: 10 })}`), [type, page]);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="space-y-4">
      {msg && <Notice tone="success">{msg}</Notice>}
      {data.items.length === 0 ? (
        <EmptyState>{t("rv.empty")}</EmptyState>
      ) : (
        data.items.map((it) => (
          <Card key={`${it.target_type}-${it.target_id}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-slate-500">
                {it.target_type} #{it.target_id}
              </span>
              <ReviewStatusBadge status={it.review_status} />
              <Badge>{t("rv.reviewCount", { n: it.review_count })}</Badge>
              <Badge tone="navy">{it.language}</Badge>
              {it.is_synthetic && <Badge tone="red">{t("ds.syntheticBadge")}</Badge>}
              {it.exclusion_reason && <Badge tone="amber">{it.exclusion_reason}</Badge>}
            </div>
            <p dir="auto" className="mt-3 text-slate-900">
              {it.text ?? "—"}
            </p>
            <dl className="mt-3 grid gap-2 text-sm md:grid-cols-[14rem_1fr]">
              {it.target_type === "analysis" ? (
                <>
                  <dt className="text-slate-600">{t("rv.modelSays")}</dt>
                  <dd className="flex items-center gap-2">
                    <LabelBadge label={it.abstained ? "NEEDS_REVIEW" : it.predicted_label_name} />
                    {it.confidence != null && <span className="text-xs">{formatNumber(locale, it.confidence * 100, 1)}%</span>}
                    {it.status !== "completed" && <span className="text-xs text-slate-500">{it.status}</span>}
                  </dd>
                </>
              ) : (
                <>
                  <dt className="text-slate-600">{t("rv.sourceSays")}</dt>
                  <dd>
                    <Badge>{it.original_label ?? "—"}</Badge>
                    {it.fact_check_url && (
                      <a href={it.fact_check_url} target="_blank" rel="noopener noreferrer nofollow" className="ms-2 text-teal-700 underline">
                        {t("analyze.factCheck")}
                      </a>
                    )}
                  </dd>
                  <dt className="text-slate-600">{t("rv.proposedMapping")}</dt>
                  <dd>
                    <LabelBadge label={it.mapped_label_name} />
                  </dd>
                  <dt className="text-slate-600">{t("rv.evidence")}</dt>
                  <dd>
                    <ul dir="ltr" className="text-start">
                      {(it.evidence_urls ?? []).slice(0, 5).map((u) => (
                        <li key={u}>
                          <a href={u} target="_blank" rel="noopener noreferrer nofollow" className="break-all text-xs text-teal-700 underline">
                            {u}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </dd>
                </>
              )}
            </dl>
            {it.reviews ? (
              <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
                <p className="mb-1 font-medium">{t("rv.otherReviews")}</p>
                <ul className="space-y-1">
                  {it.reviews.map((r, i) => (
                    <li key={i} className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs">{r.reviewer_code}</span> <LabelBadge label={r.label_name} />
                      {r.notes && <span className="text-xs text-slate-600">— {r.notes}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-500">{t("rv.blind")}</p>
            )}
            <ReviewForm
              item={it}
              onDone={(m) => {
                setMsg(m);
                void reload();
              }}
            />
          </Card>
        ))
      )}
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
    </div>
  );
}

export default function ReviewsPage() {
  const { t } = useLocale();
  const [tab, setTab] = useState<"analysis" | "sample">("analysis");
  return (
    <RequireRole roles={["admin", "reviewer"]}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-navy-900">{t("rv.title")}</h1>
        <Notice>{t("rv.guidelines")}</Notice>
        <div role="tablist" className="flex gap-2">
          {(["analysis", "sample"] as const).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={tab === k}
              onClick={() => setTab(k)}
              className={`min-h-10 rounded-lg px-4 text-sm font-medium ${tab === k ? "bg-navy-900 text-white" : "bg-white text-navy-900 border border-slate-300"}`}
            >
              {k === "analysis" ? t("rv.analyses") : t("rv.samples")}
            </button>
          ))}
        </div>
        <div role="tabpanel">
          <Queue key={tab} type={tab} />
        </div>
      </div>
    </RequireRole>
  );
}
