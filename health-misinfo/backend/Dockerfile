# FastAPI backend. Build arg INSTALL_ML=1 adds torch/transformers (CPU) for serving trained models.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-ml.txt ./
ARG INSTALL_ML=0
RUN pip install -r requirements.txt \
    && if [ "$INSTALL_ML" = "1" ]; then \
         pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 \
         && pip install transformers==5.24.0 accelerate==1.16.0 safetensors==0.8.0 matplotlib==3.11.2; \
       fi
COPY backend/ ./
COPY data/registry /app/data/registry
RUN mkdir -p /app/data/processed /app/data/raw /app/models && chown -R app:app /app
USER app
ENV HMD_ENVIRONMENT=production HMD_PDF_FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"
# Migrate, seed the source registry, then serve.
CMD ["sh", "-c", "python -m healthmisinfo.cli init-db && exec uvicorn healthmisinfo.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --workers 1"]
