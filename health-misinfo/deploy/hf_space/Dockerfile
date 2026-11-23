# Single-container demo for Hugging Face Spaces (Docker SDK). Build context = staged folder created by
# scripts/deploy_hf_space.py (backend/, frontend/, data/registry/, scripts/, models/).
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1 BACKEND_URL=http://127.0.0.1:8000
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git fonts-dejavu-core libstdc++6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=web /usr/local/bin/node /usr/local/bin/node
RUN useradd -m -u 1000 user
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 \
    && pip install transformers==5.24.0 safetensors==0.8.0
COPY --chown=user backend/ backend/
COPY --chown=user data/registry/ data/registry/
COPY --chown=user scripts/ scripts/
COPY --chown=user models/ models/
COPY --chown=user start.sh start.sh
COPY --from=web --chown=user /web/.next/standalone web/
COPY --from=web --chown=user /web/.next/static web/.next/static
# Public AraFacts data (CC BY-NC 4.0) at the audited revision, SHA-256 verified; used for similar-claim retrieval.
RUN mkdir -p data/raw data/processed data/manual runtime && ./scripts/fetch_datasets.sh && chown -R user /app
USER user
ENV HMD_ENVIRONMENT=production HMD_COOKIE_SECURE=true HMD_DATA_DIR=/app/data HMD_MODELS_DIR=/app/models \
    HMD_REGISTRY_DIR=/app/data/registry HMD_PDF_FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
EXPOSE 7860
CMD ["./start.sh"]
