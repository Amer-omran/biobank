"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { LanguageSwitcher } from "@/components/app-shell";
import { useAuth, useLocale } from "@/components/providers";
import { Button, Disclaimer, Field, inputCls } from "@/components/ui";
import { ApiError, api } from "@/lib/api";

export default function LoginPage() {
  const { t } = useLocale();
  const { refresh } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/v1/auth/login", { body: { email, password } });
      await refresh();
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t("login.failed") : String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-navy-900">
      <div className="flex justify-end p-4 text-white">
        <LanguageSwitcher />
      </div>
      <main id="main" className="flex flex-1 items-center justify-center p-4">
        <div className="w-full max-w-md space-y-4">
          <div className="text-center text-white">
            <h1 className="text-2xl font-bold">{t("app.title")}</h1>
            <p className="mt-2 text-sm text-navy-100">{t("app.subtitle")}</p>
          </div>
          <form onSubmit={submit} className="space-y-4 rounded-xl bg-white p-6 shadow-lg" noValidate>
            <h2 className="text-lg font-semibold text-navy-900">{t("login.title")}</h2>
            <Field label={t("login.email")} htmlFor="email">
              <input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} dir="ltr" />
            </Field>
            <Field label={t("login.password")} htmlFor="password">
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputCls}
                dir="ltr"
              />
            </Field>
            {error && (
              <p role="alert" className="text-sm text-red-700">
                {error}
              </p>
            )}
            <Button type="submit" busy={busy} className="w-full" disabled={!email || !password}>
              {t("login.submit")}
            </Button>
            <p className="text-xs text-slate-600">{t("login.note")}</p>
          </form>
          <Disclaimer />
        </div>
      </main>
    </div>
  );
}
