#!/usr/bin/env bash
# One-command local start (macOS / Linux). Needs Python 3.11+ and Node.js 20+. No Docker, no PostgreSQL.
#   ./start.sh          -> http://localhost:3000
# First run asks for an admin e-mail and password. Data is stored in backend/healthmisinfo_dev.db (SQLite).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
command -v python3 >/dev/null || { echo "Please install Python 3.11+"; exit 1; }
command -v npm >/dev/null || { echo "Please install Node.js 20+"; exit 1; }

if [ ! -d backend/.venv ]; then
  echo "== Installing backend (first run only)"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q --upgrade pip
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
# Trained models need PyTorch + transformers; install them only when a model folder exists.
if ls models/*/*/evaluation.json >/dev/null 2>&1 && ! backend/.venv/bin/python -c "import torch, transformers" 2>/dev/null; then
  echo "== Installing PyTorch + transformers (a trained model was found)"
  backend/.venv/bin/pip install -q torch==2.15.0 transformers==5.24.0 safetensors==0.8.0
fi
if [ ! -d frontend/.next ]; then
  echo "== Building website (first run only)"
  (cd frontend && npm ci --no-audit --no-fund --silent && BACKEND_URL=http://127.0.0.1:8000 npm run build --silent)
fi
if [ ! -d data/raw/arafacts ] && command -v git >/dev/null; then
  echo "== Downloading AraFacts (public, for similar fact-checked claims)"
  ./scripts/fetch_datasets.sh || echo "   (download failed - the site still works without it)"
fi

export HMD_ENVIRONMENT=development
if [ ! -f backend/healthmisinfo_dev.db ]; then
  read -r -p "Admin e-mail: " HMD_ADMIN_EMAIL
  read -r -s -p "Admin password (min 10 chars, mix letters/digits/symbols): " HMD_ADMIN_PASSWORD; echo
  export HMD_ADMIN_EMAIL HMD_ADMIN_PASSWORD
fi
(cd backend && .venv/bin/python -m healthmisinfo.cli bootstrap)
unset HMD_ADMIN_PASSWORD

(cd backend && .venv/bin/uvicorn healthmisinfo.main:app --host 127.0.0.1 --port 8000) &
API=$!
(cd frontend && npx next start -p 3000 -H 127.0.0.1) &
WEB=$!
trap 'kill $API $WEB 2>/dev/null' EXIT INT TERM
sleep 4
echo ""
echo "  Open http://localhost:3000   (Ctrl+C to stop)"
(command -v open >/dev/null && open http://localhost:3000) || (command -v xdg-open >/dev/null && xdg-open http://localhost:3000) || true
wait
