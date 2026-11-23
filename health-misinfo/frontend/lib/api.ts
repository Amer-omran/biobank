/** Same-origin API client. Next.js rewrites /api/* to FastAPI, so the HttpOnly session cookie is
 * first-party. Unsafe methods send X-Requested-With, which the backend requires for cookie auth
 * (CSRF defence). */

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail as { message?: string; errors?: { loc?: unknown[]; msg?: string }[] } | string;
    if (typeof d === "string") return d;
    if (d && typeof d === "object") {
      if (d.message) return d.message;
      if (Array.isArray(d.errors) && d.errors.length)
        return d.errors.map((x) => `${(x.loc ?? []).slice(1).join(".")}: ${x.msg}`).join("; ");
    }
    return `HTTP ${e.status}`;
  }
  return e instanceof Error ? e.message : String(e);
}

type Opts = { method?: string; body?: unknown; form?: FormData; signal?: AbortSignal };

export async function api<T>(path: string, opts: Opts = {}): Promise<T> {
  const method = opts.method ?? (opts.body !== undefined || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["X-Requested-With"] = "fetch";
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, { method, headers, body, credentials: "same-origin", signal: opts.signal, cache: "no-store" });
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : data;
    const errs = data && typeof data === "object" && "errors" in data ? (data as { errors: unknown }).errors : undefined;
    throw new ApiError(res.status, errs ? { message: undefined, errors: errs } : detail);
  }
  return data as T;
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}
