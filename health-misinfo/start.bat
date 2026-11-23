@echo off
REM One-command local start (Windows). Needs Python 3.11+ ("py") and Node.js 20+. Opens http://localhost:3000
setlocal
cd /d "%~dp0"
where py >nul 2>nul || (echo Please install Python 3.11+ from python.org & exit /b 1)
where npm >nul 2>nul || (echo Please install Node.js 20+ from nodejs.org & exit /b 1)

if not exist backend\.venv (
  echo == Installing backend (first run only)
  py -3 -m venv backend\.venv
  backend\.venv\Scripts\python -m pip install -q --upgrade pip
  backend\.venv\Scripts\pip install -q -r backend\requirements.txt
)
if exist models\ar\ (
  backend\.venv\Scripts\python -c "import torch, transformers" 2>nul || backend\.venv\Scripts\pip install -q torch==2.15.0 transformers==5.24.0 safetensors==0.8.0
)
if not exist frontend\.next (
  echo == Building website (first run only)
  pushd frontend
  call npm ci --no-audit --no-fund --silent
  set BACKEND_URL=http://127.0.0.1:8000
  call npm run build --silent
  popd
)
if not exist data\raw\arafacts (
  where git >nul 2>nul && (
    echo == Downloading AraFacts
    git clone --quiet https://gitlab.com/bigirqu/AraFacts.git data\raw\arafacts
    git -C data\raw\arafacts checkout --quiet 69d48d39afaec609d7040c446c2e2691b85fa86b
  )
)
set HMD_ENVIRONMENT=development
if not exist backend\healthmisinfo_dev.db (
  set /p HMD_ADMIN_EMAIL=Admin e-mail: 
  set /p HMD_ADMIN_PASSWORD=Admin password (min 10 chars, mix letters/digits/symbols): 
)
pushd backend
.venv\Scripts\python -m healthmisinfo.cli bootstrap
popd
set HMD_ADMIN_PASSWORD=
start "API" /d backend .venv\Scripts\uvicorn healthmisinfo.main:app --host 127.0.0.1 --port 8000
start "Web" /d frontend cmd /c "npx next start -p 3000 -H 127.0.0.1"
timeout /t 5 >nul
start http://localhost:3000
echo Open http://localhost:3000  (close the "API" and "Web" windows to stop)
