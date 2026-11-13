# Deployment image for the always-on StockMinds trading service on a persistent-disk server.
# Runs scheduler.py (APScheduler) in the Asia/Kolkata timezone.
# See Plan_v3 §1.4, §Roadmap week 1 day 5.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Kolkata \
    PYTHONPATH=/app/src:/app

WORKDIR /app

# Install system dependencies including timezone data
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy codebase
COPY . .

# Ensure storage and backups persistence directories exist
RUN mkdir -p storage/market storage/ledger backups

# Default entrypoint: persistent APScheduler
CMD ["python", "scheduler.py"]
