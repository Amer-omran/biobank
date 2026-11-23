# Privacy, security and ethics

## Ethics
* Outputs are research predictions; every screen, API response and report carries the disclaimer.
* No diagnosis or treatment recommendation is produced anywhere.
* No placeholder predictions: without an evaluated, registered model the API returns `model_not_trained`.
* Measured results come only from stored evaluation files; illustrative examples are labelled as such.

## Data minimisation
| Data | Handling |
| --- | --- |
| Analysed claim text | E-mails, phone numbers, 10-digit IDs and @handles redacted before storage; storage can be switched off (`store_analysis_text`); SHA-256 kept for de-duplication |
| Client IP | Never stored raw; salted SHA-256 in audit logs only |
| Dataset social-media links (`claim_urls`) | Not stored (only a count) — they identify individuals |
| Tweet text (AraCOVID19-MFH) | Not distributed by the source; never hydrated by this project |
| Reviewer identity | Pseudonymous reviewer codes in exports |
| Raw third-party datasets | Not committed to git; fetched by script, `data/raw` is gitignored |

No personal health information is collected; users submit public claims, not patient data.

## Application security controls
* Passwords: scrypt (n=2^14, r=8, p=1, 16-byte salt); minimum 10 chars mixing 3 character classes; login
  runs a constant scrypt check for unknown e-mails (no account enumeration by timing).
* Sessions: HS256 JWT (8 h) in an `HttpOnly; SameSite=Lax` cookie (`Secure` via `HMD_COOKIE_SECURE`) or
  Bearer header; cookie-authenticated unsafe requests require `X-Requested-With` (CSRF).
* Role-based access enforced server-side (admin / reviewer / researcher); blind review for non-admins.
* Production refuses to start without `HMD_SECRET_KEY` ≥ 32 chars or with a wildcard CORS origin.
* CORS: explicit allow-list; the browser normally talks same-origin through the Next.js proxy.
* Rate limiting: login and analyze (per user) sliding windows → `429` + `Retry-After`. In-process; use a
  shared store if running several API replicas.
* Input limits: claim 10–2,000 chars; uploads ≤ 50 MB; strict name/version patterns; Pydantic validation.
* Only `http(s)` URLs are accepted from datasets and reviews (blocks `javascript:` links).
* CSV exports neutralise spreadsheet formulas (`=`, `+`, `-`, `@` prefixed with `'`).
* `ast.literal_eval` only (no `eval`) when parsing dataset URL lists.
* Security headers (`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, API CSP
  `default-src 'none'`), `Cache-Control: no-store` on API responses; generic 500 messages.
* Containers run as non-root; the API port is not published by docker-compose.
* Secrets only via environment (`.env`, never committed; `.env.example` documents them).

## Verification performed (2026-11-23)
* 56 backend tests incl. auth, CSRF, roles, rate limit, formula injection, URL scheme filtering.
* `pip-audit` on `requirements.txt`: no known vulnerabilities. `npm audit --omit=dev`: 0 vulnerabilities.
* `ruff` with bandit (`S`) rules: clean.
