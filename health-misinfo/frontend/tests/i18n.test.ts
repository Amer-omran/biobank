import { describe, expect, it } from "vitest";

import { DICTS, dirOf, formatNumber, translate, translateDynamic } from "@/lib/i18n";

describe("i18n dictionaries", () => {
  it("have identical key sets and no empty strings", () => {
    const en = Object.keys(DICTS.en).sort();
    const ar = Object.keys(DICTS.ar).sort();
    expect(ar).toEqual(en);
    for (const [k, v] of Object.entries(DICTS.ar)) expect(v.trim(), k).not.toBe("");
    for (const [k, v] of Object.entries(DICTS.en)) expect(v.trim(), k).not.toBe("");
  });

  it("use the same placeholders in both languages", () => {
    const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const k of Object.keys(DICTS.en) as (keyof typeof DICTS.en)[]) expect(ph(DICTS.ar[k]), k).toEqual(ph(DICTS.en[k]));
  });

  it("translates with variables and falls back for dynamic keys", () => {
    expect(translate("en", "common.page", { page: 2, pages: 5 })).toBe("Page 2 of 5");
    expect(translate("ar", "label.MISLEADING")).toBe("مضلل");
    expect(translateDynamic("en", "review.status.unknown_x", "raw")).toBe("raw");
  });

  it("sets direction per locale and uses Latin digits for Arabic numbers", () => {
    expect(dirOf("ar")).toBe("rtl");
    expect(dirOf("en")).toBe("ltr");
    expect(formatNumber("ar", 3000)).toBe("3,000");
    expect(formatNumber("en", null)).toBe("—");
  });
});
