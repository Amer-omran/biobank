# Annotation & expert-review guidelines (guidelines-v1)

## Who reviews
Reviewers (`reviewer` role) with health-domain or fact-checking expertise. Each has a pseudonymous
reviewer code (`R-0001`); exports use codes, not names or e-mails.

## Decision procedure for one claim
1. Read the claim exactly as written. Judge **the claim**, not the author's intent or tone.
2. Search reliable evidence: WHO, national health authorities (e.g. Saudi MOH), systematic reviews and
   guidelines, peer-reviewed literature (PubMed). Prefer the most recent authoritative source.
3. Choose one label:
   * **SUPPORTED** — reliable evidence supports the claim as stated.
   * **MISLEADING** — reliable evidence contradicts it, or it is demonstrably misleading (out of context,
     selective, exaggerated causal claim, fabricated attribution).
   * **NEEDS_REVIEW** — evidence is insufficient, conflicting, ambiguous or unverifiable, **including when
     you could not find a source**. Absence of evidence is never grounds for MISLEADING.
4. Paste the evidence URLs you relied on (http/https only) and a short rationale.
5. Do not give medical advice in notes.

## Blind review and disagreement
* You do not see other reviewers' labels before submitting. Each reviewer can review an item once.
* Status flow: `pending → in_review → agreed` once the configured number of reviewers (default 2) agree.
* Any disagreement — between reviewers, or between a reviewer and the source-mapped label of a dataset
  sample — sets `disagreement`; the sample is withheld from training.
* An administrator **adjudicates** with full visibility of all reviews; the adjudication is final and
  recorded separately (`is_adjudication`), so agreement statistics remain unbiased.

## Dataset samples vs. model analyses
* *Samples*: you verify that the fact-checker's original verdict maps correctly to the 3-class scheme.
  The original label and fact-check link are shown as context (not as ground truth).
* *Analyses*: you label the claim; agreement with the model is recorded automatically.

## Label-mapping approval (researchers)
Mapping entries are approved with
`python -m healthmisinfo.cli approve-mapping --source arafacts --approved-by "Name" --entries low-ambiguity`
(or a comma-separated list, optionally `--set-label`). The command writes approver and date into the
version-controlled JSON; commit it and run `refresh-dataset`.
