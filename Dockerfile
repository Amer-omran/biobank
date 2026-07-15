# Biobank — dependency-free Python app, so a slim base is all we need.
FROM python:3.12-slim

WORKDIR /app
COPY biobank ./biobank

ENV BIOBANK_HOST=0.0.0.0 \
    BIOBANK_PORT=8000 \
    BIOBANK_DB=/data/biobank.db \
    PYTHONUNBUFFERED=1

# Persist the SQLite database outside the image.
VOLUME ["/data"]
EXPOSE 8000

# Provide BIOBANK_SEED_PASSWORD at runtime for the first launch.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

CMD ["python", "-m", "biobank.server"]
