# One image runs both the scheduler (default) and the API (command override in docker-compose.yml).
# Runtime state (storage/, backups/) is bind-mounted from the host disk; nothing stateful is baked in.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Kolkata \
    PYTHONPATH=/app/src:/app \
    HF_HOME=/app/storage/hf_cache \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends tzdata curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU-only torch (FinBERT runs on CPU): ~200MB instead of multi-GB CUDA wheels.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

COPY . .
RUN mkdir -p storage/market storage/ledger backups \
    && useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

CMD ["python", "scheduler.py"]
