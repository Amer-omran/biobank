import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, errorMessage, qs } from "@/lib/api";
import { detectScript } from "@/lib/lang";

afterEach(() => vi.restoreAllMocks());

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify(body), { status }));
}

describe("api client", () => {
  it("sends JSON with the CSRF header on unsafe methods only", async () => {
    const f = mockFetch(200, { ok: true });
    await api("/api/v1/analyze", { body: { text: "x" } });
    const [, init] = f.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>)["X-Requested-With"]).toBe("fetch");
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    await api("/api/v1/models");
    expect((f.mock.calls[1][1]?.headers as Record<string, string>)["X-Requested-With"]).toBeUndefined();
  });

  it("raises ApiError with the server detail", async () => {
    mockFetch(422, { detail: "Text must be at least 10 characters" });
    await expect(api("/api/v1/analyze", { body: {} })).rejects.toMatchObject({ status: 422 });
    mockFetch(422, { detail: "Validation error", errors: [{ loc: ["body", "text"], msg: "Field required" }] });
    const e = await api("/x", { body: {} }).catch((x) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(errorMessage(e)).toBe("text: Field required");
  });

  it("builds query strings without empty values", () => {
    expect(qs({ a: 1, b: "", c: undefined, d: "x y" })).toBe("?a=1&d=x+y");
    expect(qs({})).toBe("");
  });

  it("previews language like the backend", () => {
    expect(detectScript("الثوم يعالج كورونا")).toBe("ar");
    expect(detectScript("Garlic cures flu")).toBe("en");
    expect(detectScript("5G يسبب كورونا covid-19 virus")).toBe("mixed");
    expect(detectScript("!!")).toBe("unknown");
  });
});
