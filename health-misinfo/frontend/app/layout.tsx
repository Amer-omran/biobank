import type { Metadata } from "next";
import { cookies } from "next/headers";

import { AppShell } from "@/components/app-shell";
import { AuthProvider, LocaleProvider } from "@/components/providers";
import { LOCALE_COOKIE, type Locale, dirOf } from "@/lib/i18n";

import "./globals.css";

export const metadata: Metadata = {
  title: "Health Misinformation Research Platform | منصة أبحاث المعلومات الصحية المضللة",
  description: "Bilingual research platform for detecting health rumors and misinformation (research predictions, not medical advice).",
  robots: { index: false, follow: false },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const c = (await cookies()).get(LOCALE_COOKIE)?.value;
  const locale: Locale = c === "en" ? "en" : "ar";
  return (
    <html lang={locale} dir={dirOf(locale)}>
      <body className="font-sans antialiased">
        <LocaleProvider initial={locale}>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
