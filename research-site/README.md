# Health Claims Triage — research website

Static, bilingual (Arabic/English) website for the Gulf Colleges graduation project
*Automated Detection of Health Rumors and Medical Misinformation Using NLP: An Applied Study in the Digital Health Sector*.

* `site/index.html` + `site/model.json` — the whole website. No server: the triage preview model runs in the visitor's browser and nothing typed is sent or stored.
* Results shown on the site are quoted from the study's tables. The preview model is an independent
  re-implementation of the documented method (hybrid word 1–2-gram + character 3–5-gram TF-IDF, weighted
  logistic regression, C = 1.0, threshold 0.50) trained on the 186 pre-2021 claims; it reproduces the
  study's temporal test exactly (macro-F1 0.643; 77/82 false, 3/9 true).

## Rebuild the model

```bash
python build/prep.py "<path>/AraFacts 2.csv"   # 18,598 -> 756 -> 488 -> 277 claims (248 false, 29 true)
python build/export.py                          # writes build/model.json (+ temporal check)
cp build/model.json site/model.json
```

`build/scorer.js` is the browser scorer; it matches scikit-learn on all 277 claims (max difference 4e-7).
`build/cv.py` runs the five-fold comparison; it comes close to, but does not exactly reproduce, Table 11
(an exact match needs the study's own experiment script).

## Publish free on GitHub Pages

1. Repository **Settings → Pages → Source: GitHub Actions**.
2. Push to the branch (or run the workflow *Deploy research site* manually from the **Actions** tab).
3. The site appears at `https://<owner>.github.io/<repo>/`.

Data: AraFacts (Sheikh Ali et al., 2021), CC BY-NC 4.0 — non-commercial use with attribution.
