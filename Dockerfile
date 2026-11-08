# HisabSetu AI — one container: FastAPI + ffmpeg + SQLite.
# Build:  docker build -t hisabsetu .
# Run:    docker run --rm -p 8000:8000 --env-file .env -v hisabsetu-data:/data hisabsetu

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VOICE_KHATA_DB_URL=sqlite:////data/khata.db \
    PORT=8000

# ffmpeg converts browser WebM/MP4 recordings to 16 kHz mono WAV before STT;
# curl is used by the container healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data \
 && useradd --create-home --uid 10001 app \
 && chown -R app:app /app /data
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

# Platforms inject $PORT; it falls back to 8000 for a plain `docker run`.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
