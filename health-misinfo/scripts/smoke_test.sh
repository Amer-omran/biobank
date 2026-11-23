#!/usr/bin/env bash
# Smoke test: starts the API on a throw-away SQLite database, exercises the main endpoints over
# real HTTP, then (optionally) runs the browser e2e against a running frontend.
#   scripts/smoke_test.sh                 # API only
#   E2E_BASE_URL=http://localhost:3000 scripts/smoke_test.sh   # + Playwright e2e (frontend must proxy to $API_PORT)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/backend/.venv/bin/python}"
API_PORT="${API_PORT:-8000}"
TMP="$(mktemp -d)"
API="http://127.0.0.1:$API_PORT"
PASS="Smoke-$(openssl rand -hex 8)!"
cleanup() { [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true; rm -rf "$TMP"; }
trap cleanup EXIT

export HMD_ENVIRONMENT=development HMD_DATABASE_URL="sqlite:///$TMP/smoke.db" HMD_DATA_DIR="$TMP/data" HMD_MODELS_DIR="$TMP/models"
cd "$ROOT/backend"
"$PY" -m healthmisinfo.cli init-db >/dev/null
HMD_NEW_USER_PASSWORD="$PASS" "$PY" -m healthmisinfo.cli create-user --email smoke-admin@research-uni.org --name "Smoke Admin" --role admin >/dev/null
"$PY" -m uvicorn healthmisinfo.main:app --host 127.0.0.1 --port "$API_PORT" >"$TMP/api.log" 2>&1 &
API_PID=$!
for _ in $(seq 1 40); do curl -sf "$API/health" >/dev/null && break; sleep 0.25; done

ok=0; fail=0
check() { # name expected-substring command...
  local name="$1" want="$2"; shift 2
  local out; out="$("$@" 2>&1 || true)"
  if grep -q -- "$want" <<<"$out"; then echo "PASS  $name"; ok=$((ok+1)); else echo "FAIL  $name -> ${out:0:300}"; fail=$((fail+1)); fi
}
J=(-H "Content-Type: application/json" -H "X-Requested-With: smoke")

check "health" '"database":true' curl -s "$API/health"
check "auth required" '401' curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/models"
TOKEN="$(curl -s "${J[@]}" -d "{\"email\":\"smoke-admin@research-uni.org\",\"password\":\"$PASS\"}" "$API/api/v1/auth/login" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
A=(-H "Authorization: Bearer $TOKEN")
check "models report not_trained" '"state":"not_trained"' curl -s "${A[@]}" "$API/api/v1/models"
check "analyze -> explicit model_not_trained, no prediction" '"prediction":null' curl -s "${A[@]}" "${J[@]}" -d '{"text":"الثوم يعالج الإنفلونزا خلال يوم واحد"}' "$API/api/v1/analyze"
check "text length validation" '422' curl -s -o /dev/null -w "%{http_code}" "${A[@]}" "${J[@]}" -d '{"text":"short"}' "$API/api/v1/analyze"
check "history" '"total":1' curl -s "${A[@]}" "$API/api/v1/history"
check "source registry" '"key":"arafacts"' curl -s "${A[@]}" "$API/api/v1/sources"
check "synthetic import guarded" 'synthetic' curl -s "${A[@]}" -H "X-Requested-With: smoke" -F "file=@$ROOT/backend/tests/fixtures/synthetic_claims_en.csv" -F name=smoke -F version=1 -F language=en "$API/api/v1/datasets/import"
check "synthetic import as synthetic" '"is_synthetic":true' curl -s "${A[@]}" -H "X-Requested-With: smoke" -F "file=@$ROOT/backend/tests/fixtures/synthetic_claims_en.csv" -F name=smoke -F version=1 -F language=en -F is_synthetic=true "$API/api/v1/datasets/import"
check "split refused without eligible data" '"status":"invalid"' curl -s "${A[@]}" "${J[@]}" -d '{"language":"en","version":"smoke"}' "$API/api/v1/datasets/splits"
check "analytics: no measured results" '"measured_results_available":false' curl -s "${A[@]}" "$API/api/v1/analytics"
check "reviews pending" '"items"' curl -s "${A[@]}" "$API/api/v1/reviews/pending"
pdf_head() { curl -s "${A[@]}" "$API/api/v1/reports?type=summary&format=pdf" | head -c 4; }
check "summary PDF" '%PDF' pdf_head
check "OpenAPI docs" '"/api/v1/analyze"' curl -s "$API/openapi.json"

if [ -n "${E2E_BASE_URL:-}" ]; then
  (cd "$ROOT/frontend" && E2E_EMAIL=smoke-admin@research-uni.org E2E_PASSWORD="$PASS" node tests/e2e/smoke.e2e.mjs) && ok=$((ok+1)) || fail=$((fail+1))
fi

echo "smoke: $ok passed, $fail failed"
[ "$fail" -eq 0 ]
