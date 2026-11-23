"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useAuth, useLocale } from "@/components/providers";
import { Loading, cx } from "@/components/ui";
import type { DictKey } from "@/lib/i18n";
import type { Role } from "@/lib/types";

const NAV: { href: string; key: DictKey; roles?: Role[] }[] = [
  { href: "/", key: "nav.dashboard" },
  { href: "/analyze", key: "nav.analyze" },
  { href: "/history", key: "nav.history" },
  { href: "/datasets", key: "nav.datasets" },
  { href: "/reviews", key: "nav.reviews", roles: ["admin", "reviewer"] },
  { href: "/analytics", key: "nav.analytics" },
  { href: "/reports", key: "nav.reports" },
  { href: "/admin", key: "nav.admin", roles: ["admin"] },
];

export function LanguageSwitcher({ className }: { className?: string }) {
  const { t, locale, setLocale } = useLocale();
  return (
    <button
      type="button"
      onClick={() => setLocale(locale === "ar" ? "en" : "ar")}
      aria-label={t("lang.switchLabel")}
      lang={locale === "ar" ? "en" : "ar"}
      className={cx("min-h-10 rounded-lg border border-white/30 px-3 py-1.5 text-sm font-medium hover:bg-white/10", className)}
    >
      {t("lang.switch")}
    </button>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, td } = useLocale();
  const { user, loading, logout, hasRole } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  if (pathname === "/login") return <>{children}</>;
  if (loading || !user) return <Loading />;

  const items = NAV.filter((n) => !n.roles || hasRole(...n.roles));
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="min-h-screen md:flex">
      <a href="#main" className="skip-link">
        {t("app.skip")}
      </a>
      <aside className={cx("bg-navy-900 text-white md:sticky md:top-0 md:flex md:h-screen md:w-64 md:flex-col", open ? "block" : "hidden md:flex")} aria-label={t("nav.menu")}>
        <div className="hidden px-5 py-6 md:block">
          <p className="text-lg font-bold">{t("app.short")}</p>
          <p className="mt-1 text-xs text-navy-100/80">{t("app.subtitle")}</p>
        </div>
        <nav className="flex-1 px-3 pb-4">
          <ul className="space-y-1">
            {items.map((n) => (
              <li key={n.href}>
                <Link
                  href={n.href}
                  onClick={() => setOpen(false)}
                  aria-current={isActive(n.href) ? "page" : undefined}
                  className={cx(
                    "block rounded-lg px-3 py-2 text-sm",
                    isActive(n.href) ? "bg-teal-700 font-semibold text-white" : "text-navy-100 hover:bg-navy-800 hover:text-white",
                  )}
                >
                  {t(n.key)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="border-t border-navy-800 px-5 py-4 text-xs text-navy-100">
          <p className="font-medium text-white">{user.display_name}</p>
          <p>
            {td(`role.${user.role}`, user.role)} · {user.reviewer_code}
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 bg-navy-900 px-4 py-3 text-white md:bg-white md:text-navy-900 md:shadow-sm">
          <div className="flex items-center gap-2">
            <button type="button" className="min-h-10 rounded-lg border border-white/30 px-3 md:hidden" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
              {t("nav.menu")}
            </button>
            <span className="text-sm font-semibold md:text-base">{t("app.title")}</span>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSwitcher className="md:border-navy-800 md:hover:bg-navy-50" />
            <button type="button" onClick={() => void logout()} className="min-h-10 rounded-lg px-3 text-sm hover:bg-white/10 md:hover:bg-navy-50">
              {t("nav.logout")}
            </button>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-7xl flex-1 p-4 md:p-8">
          {children}
        </main>
        <footer className="border-t border-slate-200 bg-white px-4 py-3 text-xs text-slate-600 md:px-8">{t("attribution.arafacts")}</footer>
      </div>
    </div>
  );
}
