"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth, useLocale } from "@/components/providers";
import { errorMessage } from "@/lib/api";
import type { LabelName } from "@/lib/types";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ title, actions, children, className }: { title?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-xl border border-slate-200 bg-white p-5 shadow-sm", className)}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold text-navy-900">{title}</h2>}
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; busy?: boolean };

export function Button({ variant = "primary", busy, className, children, disabled, ...rest }: BtnProps) {
  const styles = {
    primary: "bg-teal-700 text-white hover:bg-teal-800 disabled:bg-slate-300",
    secondary: "border border-navy-800 text-navy-900 bg-white hover:bg-navy-50 disabled:text-slate-400 disabled:border-slate-300",
    ghost: "text-navy-800 hover:bg-navy-50",
    danger: "bg-red-700 text-white hover:bg-red-800 disabled:bg-slate-300",
  }[variant];
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cx("inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed", styles, className)}
    >
      {busy && <Spinner small />}
      {children}
    </button>
  );
}

export function Spinner({ small }: { small?: boolean }) {
  return <span aria-hidden className={cx("inline-block animate-spin rounded-full border-2 border-current border-t-transparent", small ? "h-4 w-4" : "h-6 w-6")} />;
}

export function Loading() {
  const { t } = useLocale();
  return (
    <div role="status" className="flex items-center gap-3 p-6 text-slate-600">
      <Spinner /> {t("common.loading")}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useLocale();
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <span>
        <strong>{t("common.error")}:</strong> {errorMessage(error)}
      </span>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      )}
    </div>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: "info" | "warn" | "success"; title?: React.ReactNode; children: React.ReactNode }) {
  const styles = {
    info: "border-navy-100 bg-navy-50 text-navy-900",
    warn: "border-amber-300 bg-amber-50 text-amber-900",
    success: "border-teal-100 bg-teal-50 text-teal-800",
  }[tone];
  const icon = { info: "ℹ", warn: "⚠", success: "✓" }[tone];
  return (
    <div role={tone === "success" ? "status" : "note"} className={cx("rounded-lg border p-4 text-sm", styles)}>
      {title && (
        <p className="mb-1 font-semibold">
          <span aria-hidden>{icon} </span>
          {title}
        </p>
      )}
      <div>{children}</div>
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-600">{children}</div>;
}

export function Badge({ children, tone = "gray" }: { children: React.ReactNode; tone?: "gray" | "navy" | "teal" | "amber" | "red" }) {
  const styles = {
    gray: "bg-slate-100 text-slate-700",
    navy: "bg-navy-100 text-navy-900",
    teal: "bg-teal-100 text-teal-800",
    amber: "bg-amber-100 text-amber-900",
    red: "bg-red-100 text-red-800",
  }[tone];
  return <span className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap", styles)}>{children}</span>;
}

const LABEL_SWATCH: Record<LabelName, string> = { SUPPORTED: "bg-series-1", MISLEADING: "bg-series-2", NEEDS_REVIEW: "bg-series-3" };

export function LabelBadge({ label }: { label: LabelName | null | undefined }) {
  const { t } = useLocale();
  if (!label) return <span className="text-slate-400">—</span>;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-xs font-semibold text-slate-800 whitespace-nowrap">
      <span aria-hidden className={cx("h-2.5 w-2.5 rounded-full", LABEL_SWATCH[label])} />
      {t(`label.${label}`)}
    </span>
  );
}

export function ReviewStatusBadge({ status }: { status: string }) {
  const { td } = useLocale();
  const tone = status === "disagreement" ? "red" : status === "pending" || status === "in_review" ? "amber" : status === "agreed" || status === "adjudicated" ? "teal" : "gray";
  return <Badge tone={tone}>{td(`review.status.${status}`, status)}</Badge>;
}

export function Disclaimer() {
  const { t } = useLocale();
  return (
    <Notice tone="warn" title={t("disclaimer.title")}>
      {t("disclaimer.body")}
    </Notice>
  );
}

export function Field({ label, htmlFor, hint, children }: { label: React.ReactNode; htmlFor: string; hint?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-sm font-medium text-slate-800">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-slate-600">{hint}</p>}
    </div>
  );
}

export const inputCls =
  "min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-500 focus:border-teal-600 focus:outline-none";

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const { t } = useLocale();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav aria-label="pagination" className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-700">
      <span>
        {t("common.page", { page, pages })} · {t("common.total", { n: total })}
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          {t("common.prev")}
        </Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          {t("common.next")}
        </Button>
      </div>
    </nav>
  );
}

export function Table({ head, children, caption }: { head: React.ReactNode[]; children: React.ReactNode; caption?: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-slate-50">
          <tr>
            {head.map((h, i) => (
              <th key={i} scope="col" className="px-3 py-2 text-start font-semibold whitespace-nowrap text-slate-700">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">{children}</tbody>
      </table>
    </div>
  );
}

export function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cx("px-3 py-2 align-top text-slate-800", className)}>{children}</td>;
}

/** Load data from the API with loading / error / reload state. */
export function useAsync<T>(fn: () => Promise<T>, deps: React.DependencyList) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fnRef.current());
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void reload();
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, loading, reload, setData };
}

export function RequireRole({ roles, children }: { roles: ("admin" | "reviewer" | "researcher")[]; children: React.ReactNode }) {
  const { t } = useLocale();
  const { hasRole } = useAuth();
  if (!hasRole(...roles)) return <Notice tone="warn">{t("common.forbidden")}</Notice>;
  return <>{children}</>;
}
