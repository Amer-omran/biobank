"use client";

import Link from "next/link";

import { ProgressBar } from "@/components/charts";
import { DatasetImport } from "@/components/dataset-import";
import { useAuth, useLocale } from "@/components/providers";
import { SourceRegistry } from "@/components/source-registry";
import { Badge, Card, EmptyState, ErrorBox, Loading, Notice, Table, Td, useAsync } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/i18n";
import type { DatasetsResponse, Source } from "@/lib/types";

export default function DatasetsPage() {
  const { t, td, locale } = useLocale();
  const { hasRole } = useAuth();
  const { data, error, loading, reload } = useAsync(
    () => Promise.all([api<DatasetsResponse>("/api/v1/datasets"), api<{ items: Source[] }>("/api/v1/sources")]),
    [],
  );
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;
  const [ds, sources] = data;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-navy-900">{t("ds.title")}</h1>

      <Card title={t("ds.progress")}>
        <div className="grid gap-6 md:grid-cols-2">
          {(["ar", "en"] as const).map((lang) => (
            <div key={lang} className="space-y-2">
              <p className="font-medium">{lang === "ar" ? "العربية / Arabic" : "English / الإنجليزية"}</p>
              <ProgressBar label={t("dash.eligible")} value={ds.progress[lang].eligible} target={ds.progress[lang].target} />
              <ProgressBar label={t("dash.reviewed")} value={ds.progress[lang].eligible_human_reviewed} target={ds.progress[lang].target} />
            </div>
          ))}
        </div>
        <div className="mt-4">
          <Notice>{t("dash.targetNote")}</Notice>
        </div>
      </Card>

      <Card title={t("ds.list")}>
        {ds.items.length === 0 ? (
          <EmptyState>{t("ds.empty")}</EmptyState>
        ) : (
          <Table head={[t("ds.name"), t("ds.version"), t("common.language"), t("ds.kind"), t("ds.source"), t("ds.license"), t("ds.rows"), t("ds.eligible"), t("common.date")]}>
            {ds.items.map((d) => (
              <tr key={d.id}>
                <Td>
                  <Link href={`/datasets/${d.id}`} className="font-medium text-teal-700 underline" dir="ltr">
                    {d.name}
                  </Link>
                  {d.is_synthetic && (
                    <div className="mt-1">
                      <Badge tone="red">{t("ds.syntheticBadge")}</Badge>
                    </div>
                  )}
                </Td>
                <Td>
                  <span dir="ltr">{d.version}</span>
                </Td>
                <Td>{d.language}</Td>
                <Td>{d.kind}</Td>
                <Td>{d.source_name ?? t("ds.userUpload")}</Td>
                <Td>
                  <Badge tone={d.license_status === "verified" || d.license_status === "uploader_confirmed" ? "teal" : "amber"}>
                    {td(`ds.licenseStatus.${d.license_status}`, d.license_status)}
                  </Badge>
                </Td>
                <Td className="tabular-nums">{formatNumber(locale, d.imported_count)}</Td>
                <Td className="tabular-nums font-semibold">{formatNumber(locale, d.eligible ?? 0)}</Td>
                <Td className="whitespace-nowrap">{formatDate(locale, d.created_at)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {hasRole("admin", "researcher") && <DatasetImport sources={sources.items} onImported={reload} />}
      <SourceRegistry sources={sources.items} onChange={reload} />
    </div>
  );
}
