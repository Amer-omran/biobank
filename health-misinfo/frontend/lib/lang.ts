/** Client-side preview of the language (script) of the input. The server's detector is
 * authoritative; this only shows the user what is likely to happen. Mirrors the backend rules. */
export function detectScript(text: string): "ar" | "en" | "mixed" | "unknown" {
  const ar = (text.match(/[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]/g) ?? []).length;
  const lat = (text.match(/[A-Za-zÀ-ɏ]/g) ?? []).length;
  const total = ar + lat;
  if (total < 3) return "unknown";
  const r = ar / total;
  if (r >= 0.8) return "ar";
  if (r <= 0.2) return "en";
  return "mixed";
}
