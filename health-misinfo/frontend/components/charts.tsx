"use client";

import { useState } from "react";

import { useLocale } from "@/components/providers";
import { Table, Td, cx } from "@/components/ui";
import { formatNumber } from "@/lib/i18n";

/** Horizontal bar list: direct labels + values (identity never by color alone), per-bar hover
 * tooltip, logical (RTL-safe) layout, and a table-view toggle. */
export function BarList({
  data,
  title,
  colorFor,
  max,
}: {
  data: { key: string; label: string; value: number }[];
  title: string;
  colorFor?: (key: string) => string;
  max?: number;
}) {
  const { t, locale } = useLocale();
  const [asTable, setAsTable] = useState(false);
  const top = max ?? Math.max(1, ...data.map((d) => d.value));
  const total = data.reduce((a, d) => a + d.value, 0);
  return (
    <figure className="w-full">
      <div className="mb-2 flex items-center justify-between gap-2">
        <figcaption className="text-sm font-medium text-slate-700">{title}</figcaption>
        <button type="button" onClick={() => setAsTable((v) => !v)} className="text-xs text-teal-700 underline underline-offset-2" aria-pressed={asTable}>
          {t("common.tableView")}
        </button>
      </div>
      {asTable ? (
        <Table head={["", t("common.count")]} caption={title}>
          {data.map((d) => (
            <tr key={d.key}>
              <Td>{d.label}</Td>
              <Td>{formatNumber(locale, d.value)}</Td>
            </tr>
          ))}
        </Table>
      ) : data.length === 0 ? (
        <p className="text-sm text-slate-500">{t("common.none")}</p>
      ) : (
        <ul className="space-y-2">
          {data.map((d) => {
            const pct = total ? (100 * d.value) / total : 0;
            return (
              <li key={d.key} className="group" title={`${d.label}: ${formatNumber(locale, d.value)} (${formatNumber(locale, pct, 1)}%)`}>
                <div className="mb-0.5 flex justify-between gap-2 text-xs text-slate-700">
                  <span className="truncate">{d.label}</span>
                  <span className="tabular-nums text-slate-900">
                    {formatNumber(locale, d.value)} <span className="text-slate-500">({formatNumber(locale, pct, 1)}%)</span>
                  </span>
                </div>
                <div className="h-3 w-full rounded-e bg-slate-100">
                  <div
                    className={cx("h-3 rounded-e transition-[filter] group-hover:brightness-90", colorFor ? colorFor(d.key) : "bg-teal-600")}
                    style={{ width: `${Math.max(d.value > 0 ? 1.5 : 0, (100 * d.value) / top)}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </figure>
  );
}

/** Progress toward a target. */
export function ProgressBar({ value, target, label }: { value: number; target: number; label: string }) {
  const { locale } = useLocale();
  const pct = target ? Math.min(100, (100 * value) / target) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-slate-700">{label}</span>
        <span dir="ltr" className="tabular-nums font-medium text-navy-900">
          {formatNumber(locale, value)} / {formatNumber(locale, target)}
        </span>
      </div>
      <div className="h-3 w-full rounded bg-slate-100" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={target} aria-valuenow={value}>
        <div className="h-3 rounded bg-teal-600" style={{ width: `${Math.max(value > 0 ? 1 : 0, pct)}%` }} />
      </div>
    </div>
  );
}

/** Confusion matrix as an accessible table with a single-hue (teal) sequential fill. */
export function ConfusionMatrix({ matrix, labels }: { matrix: number[][]; labels: string[] }) {
  const max = Math.max(1, ...matrix.flat());
  return (
    <div className="overflow-x-auto">
      <table className="text-sm">
        <thead>
          <tr>
            <th scope="col" />
            {labels.map((l) => (
              <th key={l} scope="col" className="px-2 py-1 text-center text-xs font-semibold text-slate-700">
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <th scope="row" className="pe-2 text-end text-xs font-semibold text-slate-700">
                {labels[i]}
              </th>
              {row.map((v, j) => {
                const a = v / max;
                return (
                  <td
                    key={j}
                    title={`${labels[i]} → ${labels[j]}: ${v}`}
                    className={cx("h-14 w-20 border-2 border-white text-center font-semibold tabular-nums", a > 0.55 ? "text-white" : "text-slate-900")}
                    style={{ backgroundColor: `rgba(15, 118, 110, ${0.08 + 0.92 * a})` }}
                  >
                    {v}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const LABEL_COLOR: Record<string, string> = { SUPPORTED: "bg-series-1", MISLEADING: "bg-series-2", NEEDS_REVIEW: "bg-series-3" };
