// In-browser re-implementation of the study's hybrid TF-IDF + logistic regression triage scorer.
// Mirrors scikit-learn TfidfVectorizer (sublinear tf, idf, l2 per block) exactly; parity-tested in Python.
function normalizeClaim(t) {
  t = String(t).normalize("NFKC");
  t = t.replace(/(?:https?:\/\/|www\.)\S+/gi, " ").replace(/@\w+/g, " ");
  t = t.replace(/[\p{Mn}\p{Cf}]/gu, "");
  t = t.replace(/[أإآٱ]/g, "ا").replace(/ى/g, "ي").replace(/ـ/g, "");
  t = t.replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x660)).replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x6f0));
  return t.replace(/\s+/g, " ").trim().toLowerCase();
}
function block(counts, vocab) {
  const feats = [];
  let ss = 0;
  for (const [g, c] of counts) {
    const v = vocab[g];
    if (!v) continue;
    const w = (1 + Math.log(c)) * v[0];
    feats.push([g, w, v[1]]);
    ss += w * w;
  }
  const n = Math.sqrt(ss) || 1;
  return feats.map(([g, w, coef]) => ({ g, x: w / n, contrib: (w / n) * coef }));
}
function scoreClaim(model, raw) {
  const t = normalizeClaim(raw);
  const toks = t.match(/[\p{L}\p{N}_]+/gu) || [];
  const wc = new Map();
  toks.forEach((tok, i) => {
    wc.set(tok, (wc.get(tok) || 0) + 1);
    if (i + 1 < toks.length) { const bg = tok + " " + toks[i + 1]; wc.set(bg, (wc.get(bg) || 0) + 1); }
  });
  const chars = Array.from(t.replace(/\s\s+/g, " "));
  const cc = new Map();
  for (let n = 3; n <= 5; n++) for (let i = 0; i + n <= chars.length; i++) { const g = chars.slice(i, i + n).join(""); cc.set(g, (cc.get(g) || 0) + 1); }
  const feats = [...block(wc, model.word).map((f) => ({ ...f, kind: "word" })), ...block(cc, model.char).map((f) => ({ ...f, kind: "char" }))];
  const z = model.intercept + feats.reduce((a, f) => a + f.contrib, 0);
  return { normalized: t, score: 1 / (1 + Math.exp(-z)), feats, knownWords: feats.filter((f) => f.kind === "word").length, knownChars: feats.filter((f) => f.kind === "char").length };
}
if (typeof module !== "undefined") module.exports = { normalizeClaim, scoreClaim };
