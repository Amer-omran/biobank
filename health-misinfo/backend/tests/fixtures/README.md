# ⚠️ SYNTHETIC TEST FIXTURES — NOT RESEARCH DATA

Every file in this directory is **synthetic**, template-generated for software tests
(`make_synthetic_fixtures.py`). Each text starts with `[SYNTHETIC]` and every row has
`is_synthetic=true`.

Safeguards enforced in code:

* The import API refuses a file whose rows declare `is_synthetic=true` unless the dataset itself is
  imported as synthetic.
* Synthetic samples are always `excluded` with reason `synthetic_fixture` and never reach a split.
* `ml/train.py` refuses synthetic splits unless `--smoke-test-tiny-random --allow-synthetic` is used,
  and such runs are flagged `smoke_test`/`synthetic_data` and **cannot be registered** as models.
* Synthetic datasets never appear in similar-claim retrieval or dataset-progress counts.

`arafacts_sample_schema.csv` reproduces the **column layout** of AraFacts with invented
`[SYNTHETIC]` rows so the adapter can be tested without redistributing the real data.
