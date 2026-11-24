"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { type DictKey, type Locale, LOCALE_COOKIE, dirOf, translate, translateDynamic } from "@/lib/i18n";
import type { User } from "@/lib/types";

interface LocaleCtx {
  locale: Locale;
  dir: "rtl" | "ltr";
  t: (key: DictKey, vars?: Record<string, string | number>) => string;
  td: (key: string, fallback: string) => string;
  setLocale: (l: Locale) => void;
}

const LocaleContext = createContext<LocaleCtx | null>(null);

export function LocaleProvider({ initial, children }: { initial: Locale; children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initial);
  const setLocale = useCallback((l: Locale) => {
    document.cookie = `${LOCALE_COOKIE}=${l}; path=/; max-age=31536000; samesite=lax`;
    document.documentElement.lang = l;
    document.documentElement.dir = dirOf(l);
    setLocaleState(l);
  }, []);
  const value = useMemo<LocaleCtx>(
    () => ({
      locale,
      dir: dirOf(locale),
      t: (k, v) => translate(locale, k, v),
      td: (k, f) => translateDynamic(locale, k, f),
      setLocale,
    }),
    [locale, setLocale],
  );
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleCtx {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used inside LocaleProvider");
  return ctx;
}

interface AuthCtx {
  user: User | null;
  loading: boolean;
  /** Public mode: anonymous visitors may use the public pages without signing in. */
  publicMode: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: User["role"][]) => boolean;
}

const AuthContext = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [publicMode, setPublicMode] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    try {
      const cfg = await api<{ public_mode: boolean }>("/api/v1/auth/public-config").catch(() => ({ public_mode: false }));
      setPublicMode(cfg.public_mode);
    } catch {
      setPublicMode(false);
    }
    try {
      setUser(await api<User>("/api/v1/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!loading && !user && !publicMode && pathname !== "/login") router.replace("/login");
  }, [loading, user, publicMode, pathname, router]);

  const logout = useCallback(async () => {
    await api("/api/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    setUser(null);
    router.replace(publicMode ? "/" : "/login");
  }, [router, publicMode]);

  const value = useMemo<AuthCtx>(
    () => ({ user, loading, publicMode, refresh, logout, hasRole: (...roles) => !!user && roles.includes(user.role) }),
    [user, loading, publicMode, refresh, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
