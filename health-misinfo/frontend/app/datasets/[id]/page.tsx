"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { BarList, LABEL_COLOR } from "@/components/charts";
import { useAuth, useLocale } from "@/components/providers";
import { Badge, Button, Card, ErrorBox, Field, LabelBadge, Loading, Notice, Pagination, ReviewStatusBadge, Table, Td, inputCls, useAsync } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { formatNumber } from "@/lib/i18n";
import type { DatasetRow, LabelName, PageOf } from "@/lib/types";

interface DatasetDetail extends DatasetRow {
  params: Record<string, unknown>;
  stats: Record<string, unknown>;
}
interface Sample {
  id: number;
  row_number: number;
  external_id: string | null;
  text: string | null;
  text_available: boolean;
  original_label: string | null;
  mapping_status: string;
  final_label_name: LabelName | null;
  final_label_source: string | null;
  eligibility: string;
  exclusion_reason: string | null;
  review_status: string;
  health_topic: string | null;
  source_url: string | null;
}

const LABEL_BY_ID: LabelName[] = ["SUPPORTED", "MISLEADING", "NEEDS_REVIEW"];

function toBars(obj: unknown, labelOf: (k: string) => string = (k) => k) {
  return Object.entries((obj as Record<string, number>) ?? {})
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({ key: k, label: labelOf(k), value: v }));
}

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t, locale } = useLocale();
  const { hasRole } = useAuth();
  const [page, setPage] = useState(1);
  const [eligibility, setEligibility] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [count, setCount] = useState(50);
  const [msg, setMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const ds = useAsync(() => api<DatasetDetail>(`/api/v1/datasets/${encodeURIComponent(id)}`), [id]);
  const samples = useAsync(
    () => api<PageOf<Sample>>(`/api/v1/datasets/${encodeURIComponent(id)}/samples${qs({ page, page_size: 25, eligibility, q: query })}`),
    [id, page, eligibility, query],
  );

  async function act(fn: () => Promise<string>) {
    setBusy(true);
    setActionErr(null);
    setMsg(null);
    try {
      setMsg(await fn());
      await Promise.all([ds.reload(), samples.reload()]);
    } catch (e) {
      setActionErr(e);
    } finally {
      setBusy(false);
    }
  }

  if (ds.loading) return <Loading />;
  if (ds.error || !ds.data) return <ErrorBox error={ds.error} onRetry={ds.reload} />;
  const d = ds.data;
  const st = d.stats;
  const isImport = d.kind === "import";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-navy-900" dir="ltr">
        {d.name} @ {d.version}
      </h1>
      {d.is_synthetic && <Notice tone="warn">{t("ds.syntheticBadge")}</Notice>}
      <Card
        title={t("ds.stats")}
        actions={
          <>
            <a className="text-sm text-teal-700 underline" href={`/api/v1/reports?type=dataset&format=csv&dataset_id=${d.id}`}>
              CSV
            </a>
            <a className="text-sm text-teal-700 underline" href={`/api/v1/reports?type=dataset&format=pdf&dataset_id=${d.id}`}>
              PDF
            </a>
          </>
        }
      >
        <dl className="mb-6 grid gap-2 text-sm md:grid-cols-4">
          <dt className="text-slate-600">{t("ds.source")}</dt>
          <dd>{d.source_name ?? t("ds.userUpload")}</dd>
          <dt className="text-slate-600">{t("ds.rows")}</dt>
          <dd className="tabular-nums">{formatNumber(locale, d.imported_count)}</dd>
          <dt className="text-slate-600">{t("ds.eligible")}</dt>
          <dd className="tabular-nums font-semibold">{formatNumber(locale, d.eligible ?? 0)}</dd>
          <dt className="text-slate-600">{t("ds.mapping")}</dt>
          <dd dir="ltr" className="text-start font-mono text-xs">
            {d.label_mapping_version ?? "—"}
          </dd>
          <dt className="text-slate-600">SHA-256</dt>
          <dd dir="ltr" className="break-all text-start font-mono text-xs md:col-span-3">
            {d.file_sha256 ?? "—"}
          </dd>
        </dl>
        {isImport ? (
          <div className="grid gap-6 md:grid-cols-2">
            <BarList title={t("ds.eligibility")} data={toBars(st.eligibility)} />
            <BarList title={t("ds.exclusions")} data={toBars(st.exclusion_reasons)} colorFor={() => "bg-navy-700"} />
            <BarList
              title={t("ds.labelDist")}
              data={toBars(st.eligible_label_distribution, (k) => t(`label.${LABEL_BY_ID[Number(k)]}`)).map((b) => ({ ...b, key: LABEL_BY_ID[Number(b.key)] }))}
              colorFor={(k) => LABEL_COLOR[k]}
            />
            <BarList title={t("ds.mappingStatusTitle")} data={toBars(st.mapping_status)} colorFor={() => "bg-navy-700"} />
            <BarList title={t("ds.topics")} data={toBars(st.health_topics)} />
            <BarList title={t("ds.originalLabel")} data={toBars(st.original_labels)} colorFor={() => "bg-slate-500"} />
          </div>
        ) : (
          <pre dir="ltr" className="max-h-96 overflow-auto rounded bg-slate-50 p-3 text-start text-xs">
            {JSON.stringify(st, null, 2)}
          </pre>
        )}
      </Card>

      {isImport && (
        <Card title={t("ds.samples")}>
          <div className="mb-4 flex flex-wrap items-end gap-3">
            <Field label={t("ds.eligibility")} htmlFor="s-elig">
              <select id="s-elig" className={inputCls} value={eligibility} onChange={(e) => (setEligibility(e.target.value), setPage(1))}>
                <option value="">{t("common.all")}</option>
                <option value="eligible">eligible</option>
                <option value="pending">pending</option>
                <option value="excluded">excluded</option>
              </select>
            </Field>
            <form
              className="flex items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                setPage(1);
                setQuery(q);
              }}
            >
              <Field label={t("ds.search")} htmlFor="s-q">
                <input id="s-q" className={inputCls} value={q} onChange={(e) => setQ(e.target.value)} dir="auto" />
              </Field>
              <Button type="submit" variant="secondary">
                {t("common.view")}
              </Button>
            </form>
          </div>
          {samples.loading ? (
            <Loading />
          ) : samples.error || !samples.data ? (
            <ErrorBox error={samples.error} onRetry={samples.reload} />
          ) : (
            <>
              <Table head={["#", t("common.text"), t("ds.originalLabel"), t("ds.finalLabel"), t("ds.eligibility"), t("history.review")]}>
                {samples.data.items.map((s) => (
                  <tr key={s.id}>
                    <Td className="tabular-nums">{s.row_number}</Td>
                    <Td className="max-w-md">
                      <span dir="auto">{s.text ?? <em className="text-slate-500">({t("common.notAvailable")})</em>}</span>
                      {s.source_url && (
                        <a href={s.source_url} target="_blank" rel="noopener noreferrer nofollow" className="ms-2 text-xs text-teal-700 underline">
                          ↗
                        </a>
                      )}
                    </Td>
                    <Td>
                      <Badge>{s.original_label ?? "—"}</Badge>
                      <div className="mt-1 font-mono text-[11px] text-slate-500">{s.mapping_status}</div>
                    </Td>
                    <Td>
                      <LabelBadge label={s.final_label_name} />
                      {s.final_label_source && <div className="mt-1 text-[11px] text-slate-500">{s.final_label_source}</div>}
                    </Td>
                    <Td>
                      <Badge tone={s.eligibility === "eligible" ? "teal" : s.eligibility === "pending" ? "amber" : "gray"}>{s.eligibility}</Badge>
                      {s.exclusion_reason && <div className="mt-1 font-mono text-[11px] text-slate-500">{s.exclusion_reason}</div>}
                    </Td>
                    <Td>
                      <ReviewStatusBadge status={s.review_status} />
                    </Td>
                  </tr>
                ))}
              </Table>
              <Pagination page={samples.data.page} pageSize={samples.data.page_size} total={samples.data.total} onPage={setPage} />
            </>
          )}
        </Card>
      )}

      {isImport && hasRole("admin", "researcher") && (
        <Card title={t("common.details")}>
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("ds.count")} htmlFor="q-count">
              <input id="q-count" type="number" min={1} max={2000} className={`${inputCls} w-32`} value={count} onChange={(e) => setCount(Number(e.target.value))} />
            </Field>
            <Button
              variant="secondary"
              busy={busy}
              onClick={() =>
                act(async () => {
                  const r = await api<{ queued: number }>(`/api/v1/datasets/${d.id}/queue-review`, { body: { count, seed: 42, only_eligible: true } });
                  return t("ds.queued", { n: r.queued });
                })
              }
            >
              {t("ds.queueReview")}
            </Button>
            {hasRole("admin") && (
              <Button
                variant="secondary"
                busy={busy}
                onClick={() =>
                  act(async () => {
                    const r = await api<{ stats: { eligible: number } }>(`/api/v1/datasets/${d.id}/refresh`, { method: "POST" });
                    return `${t("ds.eligible")}: ${r.stats.eligible}`;
                  })
                }
              >
                {t("ds.refresh")}
              </Button>
            )}
          </div>
          {msg && (
            <div className="mt-3">
              <Notice tone="success">{msg}</Notice>
            </div>
          )}
          {actionErr !== null && (
            <div className="mt-3">
              <ErrorBox error={actionErr} />
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
