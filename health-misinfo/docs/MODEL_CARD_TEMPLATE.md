# Model card template

Model cards are **generated automatically** from real run artefacts by
`backend/healthmisinfo/ml/model_card.py` at the end of `python -m healthmisinfo.ml.train`, and saved as
`models/<lang>/<run_tag>/model_card.md`. They are never written by hand, so every number in them traces to
`evaluation.json` / `calibration.json` / `run_config.json` of the same run.

Sections (after Mitchell et al., 2019):

1. **Model details** — task, language, base model, hyper-parameters, seed, best validation macro-F1, git commit, environment.
2. **Intended use** — research on health misinformation; predictions require evidence verification and expert review.
3. **Out-of-scope use** — diagnosis/treatment, automated moderation, definitive verdicts, other languages.
4. **Training data** — split version and SHA-256, sizes, class distributions, grouping method, shortfall vs. target.
5. **Evaluation** — validation vs. held-out test: accuracy, macro P/R/F1; per-class table; confusion matrix.
6. **Calibration & abstention** — temperature, ECE before/after on test, threshold and whether the validation target was met, test coverage/selective accuracy.
7. **Subgroup evaluation** — by heuristic health topic and by source, with small-sample warnings.
8. **Limitations** and 9. **Ethical considerations**.

Smoke-test runs (tiny random network, synthetic data) produce a card headed
"PIPELINE SMOKE TEST — NOT A RESEARCH RESULT" and cannot be registered.

**Current status:** no real model card exists, because no model has been fine-tuned (see `DATA_STATUS.md`).
