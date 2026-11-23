#!/usr/bin/env bash
# Starts FastAPI (internal, 127.0.0.1:8000) and the Next.js server (public, $PORT, default 7860).
set -euo pipefail
APP="${APP_DIR:-/app}"
# Secrets come from the Space settings. Without HMD_SECRET_KEY a random one is generated (sessions reset on restart).
export HMD_SECRET_KEY="${HMD_SECRET_KEY:-$(python -c 'import secrets; print(secrets.token_urlsafe(48))')}"
# Default storage is the container disk (reset when the Space restarts). Set HMD_DATABASE_URL to a
# PostgreSQL URL (e.g. a free Neon database) for persistent history and reviews.
export HMD_DATABASE_URL="${HMD_DATABASE_URL:-sqlite:///$APP/runtime/hmd.db}"
cd "$APP/backend"
python -m healthmisinfo.cli bootstrap
python -m uvicorn healthmisinfo.main:app --host 127.0.0.1 --port 8000 --workers 1 &
API_PID=$!
for _ in $(seq 1 60); do python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" 2>/dev/null && break; sleep 1; done
cd "$APP/web"
PORT="${PORT:-7860}" HOSTNAME=0.0.0.0 node server.js &
WEB_PID=$!
wait -n "$API_PID" "$WEB_PID"
exit 1
