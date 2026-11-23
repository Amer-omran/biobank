# Architecture & Implementation Plan

**Project:** AI-Powered Detection of Health Rumors and Misinformation Using NLP — an applied study in the digital health sector.

> All model outputs are **research predictions**, not medical advice and not definitive fact-checks.

## 1. Repository inspection (Phase 1 finding)

The repository previously contained only an unrelated, working *biobank* sample-management app
(`/biobank`, stdlib Python). It is left untouched. The research platform lives in
`/health-misinfo` so the two never share code, dependencies or databases.

## 2. Environment constraints found during inspection (affect what can be *executed* here)

| Resource | Status in the build environment | Consequence |
| --- | --- | --- |
| PyPI, npm | reachable | backend + frontend build and test here |
| `huggingface.co` | **blocked by network policy** | AraBERT / XLM-R weights cannot be downloaded here → **no model is trained here**; the platform shows *model-not-trained* |
| Google Drive (official PUBHEALTH host) | **blocked** | PUBHEALTH must be placed manually in `data/manual/pubhealth/` |
| gitlab.com / github.com | reachable | AraFacts and AraCOVID19-MFH were downloaded and audited |
| MOH / WHO / PubMed | blocked | registered as evidence references only, licenses marked unverified |
| GPU | none (4 CPU, 15 GB RAM) | training scripts target GPU/CPU machines elsewhere |
| Docker daemon | not running | compose files are written and config-validated, not run here |
| PostgreSQL 16 | installed locally | migrations + integration tests run against real PostgreSQL |

## 3. Components

```
                 ┌─────────────────────────────────────────────┐
  Browser ──────▶│ Next.js (App Router, TS, Tailwind)          │
  (ar RTL/en LTR)│  /api/* rewritten → backend (same-origin)   │
                 └───────────────┬─────────────────────────────┘
                                 │ JSON / multipart
                 ┌───────────────▼─────────────────────────────┐
                 │ FastAPI  (healthmisinfo.api)                │
                 │  auth (JWT cookie/Bearer, roles)            │
                 │  rate limiting, CORS allow-list, validation │
                 │  /health  /api/v1/{models,analyze,history,  │
                 │   datasets,datasets/import,analytics,       │
                 │   reviews,reviews/pending,reports,...}      │
                 ├─────────────────────────────────────────────┤
                 │ services                                    │
                 │  inference  (lazy torch; per-language slot) │
                 │  similar-claim retrieval (TF-IDF, sklearn)  │
                 │  dataset import / dedup / grouping / split  │
                 │  reviews + adjudication + audit log         │
                 │  analytics + CSV/PDF reports                │
                 └───────┬───────────────────────┬─────────────┘
                         │ SQLAlchemy 2          │ filesystem
                 ┌───────▼────────┐     ┌────────▼───────────────────┐
                 │ PostgreSQL 16  │     │ data/raw (gitignored)      │
                 │ (SQLite dev)   │     │ data/processed/<version>/  │
                 │ Alembic        │     │ models/<lang>/<version>/   │
                 └────────────────┘     │  checkpoint + eval + card  │
                                        └────────────────────────────┘
  Offline CLI (python -m healthmisinfo.cli …): seed-registry, import-*, build-splits,
  train, evaluate, register-model, create-user.
```

### Key design decisions

1. **One Python package (`healthmisinfo`)** for API, data pipeline and training, so text
   normalization, label definitions and language detection are *identical* at training and
   inference time.
2. **Torch is optional at runtime.** The API imports it lazily. Without a registered, evaluated
   checkpoint the analysis endpoint returns `status="model_not_trained"` with **no label and no
   probabilities** — never a placeholder prediction.
3. **A model can be registered only if** its checkpoint directory exists, its
   `evaluation.json` (held-out test metrics) exists, and it was not trained on synthetic data.
   This is enforced in code (`healthmisinfo/ml/registry.py`).
4. **Calibration is explicit.** Raw softmax is returned as `raw_scores` and labelled
   *uncalibrated*. `confidence` is populated only from a temperature-scaled model whose
   temperature and abstention threshold were fitted on the validation split.
5. **Label mappings are version-controlled JSON with per-entry approval** (`data/registry/label_mappings`).
   Unapproved entries leave samples `pending_mapping_approval` and out of training.
6. **Provenance everywhere:** original text, original label, source key, source URL, file
   SHA-256, mapping version and every exclusion reason are persisted.
7. **Leakage control:** exact duplicates (hash of an aggressive matching key) and near
   duplicates (char n-gram TF-IDF cosine ≥ threshold) and shared fact-check URLs are unioned into
   `group_id`s; splits are made with `StratifiedGroupKFold`, never by row.
8. **Same-origin cookie auth:** the frontend proxies `/api/*`, so the JWT lives in an
   `HttpOnly; SameSite=Lax` cookie; unsafe methods additionally require the `X-Requested-With`
   header (CSRF defence). Bearer tokens are accepted for scripts.
9. **Privacy:** analysis text is redacted for e-mail/phone/URL user handles before storage, IPs are
   stored only as salted hashes in audit logs, social-media `claim_urls` from datasets are not
   stored (only their count).

## 4. Data model (tables)

`users, analyses, datasets, dataset_samples, source_registry, annotations, expert_reviews,
model_versions, training_runs, audit_logs, app_settings` — see `backend/healthmisinfo/db/models.py`
and the Alembic migration in `backend/alembic/versions/`.

## 5. Phased plan & checklist

Legend: ✅ done & tested · 🟡 implemented, needs external resource to run fully · ⬜ pending

### Phase 1 — inspection & plan
- ✅ Inspect repository, toolchain and network reachability
- ✅ Download & audit AraFacts, AraCOVID19-MFH, PUBHEALTH repo (schemas, licenses, counts)
- ✅ Source registry (`data/registry/sources.json`) and proposed label mappings

### Phase 2 — backend
- ✅ Settings, DB layer, ORM models, Alembic migration, indexes
- ✅ Auth (users, roles, JWT), rate limiting, CORS, error handling, audit log
- ✅ All required endpoints + admin endpoints, OpenAPI
- ✅ Tests: 56 backend tests pass on SQLite and on PostgreSQL 16; `alembic check` shows no drift

### Phase 3 — frontend
- ✅ Bilingual (ar RTL / en LTR) Next.js app, all pages wired to real endpoints
- ✅ Vitest (11 tests: i18n parity, API client, result component) + Playwright e2e (14 steps, live stack)

### Phase 4 — data pipeline
- ✅ Adapters: AraFacts, AraCOVID19-MFH (IDs only), PUBHEALTH (manual files), generic CSV/JSON
- ✅ Conservative normalization, dedup, near-dup grouping, grouped split with verification
- 🟡 Label mappings **await human approval** → 0 eligible samples (see `DATA_STATUS.md`)
- ❌ Even with all proposals approved, AraFacts health alone cannot form a valid 3-class split (3 NEEDS_REVIEW)

### Phase 5/6 — training & inference
- ✅ Trainer pipeline, metrics, confusion matrix, temperature scaling, abstention, model card
- ✅ Pipeline smoke-tested with a tiny *randomly initialised* model on synthetic fixtures (not a result)
- 🟡 Real fine-tuning requires Hugging Face access (+ ideally a GPU) and approved mappings

### Phase 7 — deployment & docs
- ✅ Dockerfiles, docker-compose (validated with `docker compose config`), `.env.example`, bilingual README, methodology, privacy, API docs
- ✅ Smoke test (14 API checks), pip-audit and npm audit clean, ruff (incl. bandit rules) clean
- 🟡 `docker compose up` not executed here (no Docker daemon)
