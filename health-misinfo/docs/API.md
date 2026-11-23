# API reference

Interactive docs: `http://<api>:8000/docs` (Swagger) and `/redoc`. Machine-readable spec:
[`openapi.json`](openapi.json) (exported from the running code).

**Auth.** `POST /api/v1/auth/login` → `{access_token, user}` and an `HttpOnly; SameSite=Lax` cookie.
Send either `Authorization: Bearer <token>` or the cookie. Cookie-authenticated `POST/PUT/PATCH/DELETE`
must include `X-Requested-With` (CSRF defence). Roles: `admin`, `reviewer`, `researcher`.

**Errors.** `{"detail": ...}`; validation errors are `422 {"detail":"Validation error","errors":[...]}`;
rate limiting returns `429` with `Retry-After`.

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | public | Liveness + DB connectivity (503 if DB down) |
| POST | `/api/v1/auth/login` · `/logout` | public | Session |
| GET | `/api/v1/auth/me` | any | Current user |
| GET | `/api/v1/models` | any | Model slots (`ready`, `not_trained`, `checkpoint_missing`, `runtime_unavailable`, …) + registered versions |
| GET | `/api/v1/models/{id}` | any | Full validation/test metrics, calibration, training run, model card |
| POST | `/api/v1/models/{id}/activate` | admin | Make a registered version active for its language |
| POST | `/api/v1/analyze` | any | `{text, model: auto|ar|en, explain}` → research prediction or explicit `model_not_trained` |
| GET | `/api/v1/history` | any | Own analyses (reviewers/admins: all); filters `language`, `status`, `review_status` |
| GET | `/api/v1/history/{id}` | any | One analysis incl. reviews |
| POST | `/api/v1/history/{id}/request-review` | any | Queue for expert review |
| GET | `/api/v1/datasets` | any | Imports + split versions + progress toward the 3,000/language target |
| GET | `/api/v1/datasets/{id}` · `/samples` | any | Statistics, samples with provenance/eligibility |
| POST | `/api/v1/datasets/preview` | admin, researcher | Columns, head, label values of an upload |
| POST | `/api/v1/datasets/import` | admin, researcher | Multipart import with column + label mapping, license confirmation, synthetic flag |
| POST | `/api/v1/datasets/{id}/refresh` | admin | Re-apply registry mapping, duplicates, reviews, eligibility |
| POST | `/api/v1/datasets/{id}/queue-review` | admin, researcher | Reproducible random sample → review queue |
| POST | `/api/v1/datasets/splits` | admin | Build a verified grouped split (422 + report if refused) |
| GET | `/api/v1/sources` · `/{key}/mapping` | any | Provenance & license registry; full mapping file |
| PATCH | `/api/v1/sources/{key}` | admin | Record a human license review (status + evidence) |
| POST | `/api/v1/reviews` | admin, reviewer | Review or (admin) adjudicate an analysis or sample |
| GET | `/api/v1/reviews/pending` | admin, reviewer | Queue excluding items you reviewed (blind) |
| GET | `/api/v1/reviews?target_type=&target_id=` | any | Reviews of an item (non-admins: own only) |
| GET | `/api/v1/analytics` | any | Dataset distributions, splits, measured model metrics, usage, reviewer agreement (κ) |
| GET | `/api/v1/reports` | any | Catalogue; `?type=summary|analyses|dataset|evaluation|reviews|sources|audit&format=csv|pdf` |
| * | `/api/v1/admin/*` | admin | Users, settings, audit log, training runs, registry reload |

### Analyze response (abridged)

```json
{
  "status": "model_not_trained",          // or completed | model_unavailable | unsupported_language
  "prediction": null,                     // present only when a registered model ran
  "language": {"detected": "ar", "used": "ar", "confidence": 1.0},
  "similar_claims": [{"text": "...", "original_label": "مضلل", "fact_check_url": "https://...", "similarity": 0.91}],
  "review_status": "not_required",
  "disclaimer": {"en": "Research prediction only...", "ar": "..."}
}
```

When a model exists, `prediction` contains `raw_scores` (uncalibrated softmax, explicitly **not** a
confidence), `calibrated_probabilities` and `confidence` (only for temperature-scaled models),
`abstained` and `display_label` (`NEEDS_REVIEW` when abstained).
