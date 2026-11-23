# Research methodology

## 1. Task definition

Three-class classification of a single health claim (Arabic or English):

| id | Label | Definition |
| --- | --- | --- |
| 0 | SUPPORTED | Supported by reliable evidence. |
| 1 | MISLEADING | Contradicted by reliable evidence or demonstrably misleading. |
| 2 | NEEDS_REVIEW | Insufficient, conflicting, ambiguous, or unverified evidence. |

**Label schemes.** `three_class` trains all three labels. `binary` (used for the prototype because
NEEDS_REVIEW has only 3 eligible Arabic samples) trains SUPPORTED vs MISLEADING and produces NEEDS_REVIEW
exclusively by calibrated abstention (§6); samples whose final label is NEEDS_REVIEW are excluded from a
binary split and counted in its manifest (`excluded_by_label_scheme`).

The classifier sees only the claim text. It is a **research prediction** model, not a fact-checker:
it does not retrieve evidence, and a missing supporting source is never treated as evidence of falsity.

## 2. Data provenance and licensing

Every source is recorded in `data/registry/sources.json` (seeded into `source_registry`) with the official
URL, audited revision, file SHA-256, license and the evidence for it, redistribution and commercial terms,
text availability, citation and training-use status. A research paper's license is never assumed to be the
dataset's license. Sources with `license_status != verified` cannot contribute training samples until an
administrator records a license review (who, when, evidence) — see `docs/DATA_STATUS.md` for current status.

Raw third-party data is never committed; `scripts/fetch_datasets.sh` re-downloads pinned revisions and
verifies hashes.

## 3. Import pipeline (per dataset, independent adapters)

1. **Adapter** reads the official schema and fails loudly on missing columns. Original text and *all*
   original labels are preserved verbatim (`original_text`, `original_label`, `original_labels`).
2. **Normalization** (`norm-v1`, stored with every dataset): NFKC, removal of invisible/bidi controls,
   Arabic tatweel and diacritics, URL/e-mail/@mention placeholders, whitespace collapse. Identical at
   training and inference.
3. **Label mapping**: version-controlled JSON per source with per-entry `proposed | approved | rejected`
   status, ambiguity rating and rationale. Only `approved` entries (with a named approver) are applied.
   AraFacts is mapped from the fact-checker's original label, not the authors' normalized label.
4. **Duplicates**: an aggressive match key (lower-case, punctuation removed, Arabic letter unification)
   identifies exact duplicates across all datasets of a language; the earliest sample is canonical.
   Duplicates whose labels disagree are withheld as `label_conflict` pending human review.
5. **Eligibility** is computed (never by deletion) with a machine-readable reason:
   `synthetic_fixture, text_unavailable, text_too_short, exact_duplicate, review_disagreement,
   pending_mapping_approval, excluded_by_mapping, no_approved_label, label_conflict, license_review_required`.
6. **Audit**: every import, refresh, review, license decision and split attempt (including failed ones) is
   written to `audit_logs`.

## 4. Leakage control and splitting

Leakage groups are recomputed across all candidate datasets of a language by union-find over: exact match
keys; near-duplicates (character 3–5-gram TF-IDF cosine ≥ 0.85, `dedup-v1`); the same fact-check article
URL; and researcher-supplied `group_key` values (to link known translations/paraphrases). Each group stays
in one split.

Splits use scikit-learn `StratifiedGroupKFold`: ≈15% test (1 of 7 folds), then ≈15% validation from the
remainder; seeds are recorded. **Verification** requires zero group overlap and all three classes in every
split; classes with < 3 independent groups are refused up front. An invalid split raises an error with a
full report and is never written. Valid splits are written to
`data/processed/<lang>/<version>/{train,validation,test}.csv` with a `manifest.json` (SHA-256 per file,
sizes, class distributions, grouping statistics, shortfall vs. target), and membership is stored in
`split_assignments`.

The PUBHEALTH original train/dev/test split is recorded per sample but re-split group-aware, so that both
languages follow one procedure; this choice should be reported.

What-if analysis used in `DATA_STATUS.md` (reads real files, modifies and approves nothing):

```bash
cd backend && python -m healthmisinfo.data.whatif --source arafacts --file "../data/raw/arafacts/Dataset/AraFacts 2/AraFacts 2.csv"
```

## 5. Models and training

* Arabic: `aubmindlab/bert-base-arabertv02`; English: `FacebookAI/xlm-roberta-base` (trained independently).
* Hugging Face `Trainer`, class-weighted cross-entropy (`balanced`), AdamW, linear warm-up (6%), weight
  decay 0.01, lr 2e-5, batch 16, max length 128, ≤ 4 epochs, early stopping (patience 2) on **validation
  macro-F1**, best checkpoint restored. Seed controls data order, init of the classification head and
  shuffling (`transformers.set_seed`, `data_seed`).
* Before training, every split CSV's SHA-256 is checked against the manifest.
* Recorded per run (`run_config.json`): all hyper-parameters, seed, split version and data hash, library
  versions, device, git commit, class weights, best epoch metric.

## 6. Calibration and abstention (validation split only)

* **Temperature scaling** (single scalar T minimising validation NLL). ECE (15 bins), NLL and Brier are
  reported before/after. Raw softmax is always labelled *uncalibrated* and never shown as confidence.
* **Abstention**: the smallest threshold on calibrated max-probability whose validation selective accuracy
  reaches 0.90 with coverage ≥ 0.30. If none qualifies, the best feasible threshold is used and
  `target_met = false` is reported. Abstained predictions are displayed as NEEDS_REVIEW and queued for experts.

## 7. Evaluation

The test split is touched once, after model selection and calibration are frozen. Reported: accuracy,
macro precision/recall/F1, weighted F1, per-class precision/recall/F1/support, confusion matrix,
true/predicted class distributions, ECE raw vs calibrated, selective accuracy and coverage at the chosen
threshold, and subgroup metrics by heuristic health topic and by source (with a warning below n = 30).
Outputs: `evaluation.json`, `predictions_test.csv`, `confusion_matrix_test.png`, `model_card.md`.

A model can be registered (and served) only if its run directory contains weights, tokenizer, evaluation,
calibration and model card, and it is neither a smoke test nor trained on synthetic data.

## 8. Human review

See `ANNOTATION_GUIDELINES.md`. Inter-reviewer agreement (percent agreement and Cohen's κ over the first two
reviewers of each doubly-reviewed item) is computed from real reviews in `/api/v1/analytics`.

## 9. Limitations (to report in the thesis)

* Class imbalance: fact-checkers mostly publish debunks (AraFacts health: 28 true-like vs 709 false-like
  under the proposed mapping), so SUPPORTED and NEEDS_REVIEW are scarce.
* Topic concentration: 53% of AraFacts health claims concern COVID-19; temporal drift is likely.
* Many AraFacts claims refer to images/videos (`claim_type`); text alone may not determine the verdict.
* Health topics come from a keyword heuristic (`topics-v1`), not expert coding.
* Near-duplicate detection is lexical; paraphrases with different wording and cross-lingual translations
  are only grouped if a researcher links them.
* Language identification is script-based plus English function words; mixed-language text uses the
  dominant script.
* Leave-one-word-out explanations describe model behaviour, not evidence.
