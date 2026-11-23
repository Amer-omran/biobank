"use client";

import { useMemo, useState } from "react";

import { AnalysisResult } from "@/components/analysis-result";
import { useLocale } from "@/components/providers";
import { Button, Card, Disclaimer, ErrorBox, Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import { detectScript } from "@/lib/lang";
import type { Analysis } from "@/lib/types";

const MIN = 10;
const MAX = 2000;

export default function AnalyzePage() {
  const { t } = useLocale();
  const [text, setText] = useState("");
  const [model, setModel] = useState<"auto" | "ar" | "en">("auto");
  const [explain, setExplain] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<Analysis | null>(null);
  const hint = useMemo(() => detectScript(text), [text]);
  const len = text.trim().length;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await api<Analysis>("/api/v1/analyze", { body: { text, model, explain } }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-navy-900">{t("analyze.title")}</h1>
      <Disclaimer />
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <Field
            label={t("analyze.input")}
            htmlFor="claim"
            hint={
              <span className="flex flex-wrap justify-between gap-2">
                <span>{t("analyze.chars", { n: len, max: MAX })}</span>
                {len > 0 && (
                  <span>
                    {t("analyze.detected")}: <strong>{hint}</strong>
                  </span>
                )}
              </span>
            }
          >
            <textarea
              id="claim"
              rows={6}
              maxLength={MAX}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t("analyze.placeholder")}
              dir="auto"
              className={inputCls}
            />
          </Field>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label={t("analyze.model")} htmlFor="model">
              <select id="model" value={model} onChange={(e) => setModel(e.target.value as typeof model)} className={inputCls}>
                <option value="auto">{t("analyze.model.auto")}</option>
                <option value="ar">{t("analyze.model.ar")}</option>
                <option value="en">{t("analyze.model.en")}</option>
              </select>
            </Field>
            <label className="flex items-center gap-2 self-end text-sm text-slate-800">
              <input type="checkbox" checked={explain} onChange={(e) => setExplain(e.target.checked)} className="h-4 w-4 accent-teal-700" />
              {t("analyze.explain")}
            </label>
          </div>
          {len > 0 && len < MIN && <p className="text-sm text-amber-800">{t("analyze.tooShort", { min: MIN })}</p>}
          <Button type="submit" busy={busy} disabled={len < MIN}>
            {busy ? t("analyze.running") : t("analyze.submit")}
          </Button>
        </form>
      </Card>
      {error !== null && <ErrorBox error={error} />}
      {result && <AnalysisResult analysis={result} onChange={setResult} />}
    </div>
  );
}
