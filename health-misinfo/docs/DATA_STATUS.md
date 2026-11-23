# Data status — measured on 2026-11-23

All numbers below were produced by this repository's pipeline from the real files at the pinned
revisions in `data/registry/sources.json` (SHA-256 verified by `scripts/fetch_datasets.sh`).
Nothing here is estimated or invented.

## Target vs. reality

| | Target | Imported (text available) | Eligible for training now | Shortfall |
| --- | --- | --- | --- | --- |
| Arabic | 3,000 | 755 (AraFacts health) + 0 (AraCOVID19-MFH has no text) | **0** | **3,000** |
| English | 3,000 | 0 (PUBHEALTH not downloadable here) | **0** | **3,000** |

No model has been trained. No accuracy, F1 or any other result exists for this platform yet.

## Why nothing is eligible yet

| Dataset | Rows | Status | Blocking reason(s) |
| --- | --- | --- | --- |
| AraFacts v2, `normalized_category == Health` | 756 | 755 `pending_mapping_approval`, 1 `text_too_short` | Label mapping entries are *proposed*, not approved by a named researcher |
| AraCOVID19-MFH V1.0 | 10,828 | all `text_unavailable` | Tweet IDs only; no license file; no approved label mapping |
| PUBHEALTH | – | not imported | Official host (Google Drive) blocked from the build environment; license of the data (vs. code) unclear |

## What-if analysis: AraFacts health subset if *every* proposed mapping were approved

(Computed without changing any file; reproducible with `python -m healthmisinfo.data.whatif --source arafacts --file ...`.)

| Proposed target | Count | of which low / medium / high ambiguity |
| --- | --- | --- |
| MISLEADING | 709 | 593 / 76 / 40 |
| SUPPORTED | 28 | 28 / 0 / 0 |
| NEEDS_REVIEW | 3 | 0 / 3 / 0 |
| EXCLUDE (satire, opinion) | 15 | 15 / 0 / 0 |

* Leakage grouping found **no** exact or near-duplicate pairs (threshold 0.85) inside this subset
  (740 groups for 740 samples).
* **A valid 3-class grouped split is NOT possible**: the pipeline refuses it because the validation
  split would contain no NEEDS_REVIEW sample. With only low-ambiguity entries approved, the subset is
  593 MISLEADING vs. 28 SUPPORTED and has no NEEDS_REVIEW class at all.
* 402 of 756 claims (53%) are COVID-19 related (heuristic topic tagger), so topic diversity is low.

## Consequences for the study (decisions needed from the research team)

1. **Approve or amend the AraFacts mapping** (`python -m healthmisinfo.cli approve-mapping ...`).
   High-ambiguity entries (`انتقائي`, `مجتزأ`, `إثارة`, `انحياز`, `صحيح جزئياً`, …) need an explicit decision.
2. **Source additional SUPPORTED and NEEDS_REVIEW Arabic claims.** Fact-checking sites mostly publish
   debunks, so the class balance cannot come from AraFacts alone. Options: expert-written claims based
   on MOH/WHO guidance (recorded with author, evidence URL and review), human annotation of AraFacts'
   5,366 `UNCATEGORIZED` claims for health relevance, or another licensed corpus.
3. **AraCOVID19-MFH** requires author permission/license clarification, lawful tweet hydration, and a
   designed mapping before use; otherwise it can only serve descriptive statistics.
4. **PUBHEALTH** must be downloaded from the official link and its data license confirmed; the
   `mixture` label mapping (proposed: NEEDS_REVIEW) needs a decision.
5. Consider whether a 3-class formulation is supportable for Arabic, or whether NEEDS_REVIEW should be
   produced only by abstention (calibrated threshold) — a methodological choice for the thesis.
