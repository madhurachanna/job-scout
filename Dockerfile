# ── Job Scout — Dockerfile ────────────────────────────────────
# Python 3.12 slim for a small image footprint
FROM python:3.12-slim

# Keeps Python from generating .pyc files, and ensures logs flush immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps needed by some scraping libraries (e.g. lxml)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libxml2-dev \
        libxslt-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its system dependencies (chromium only to save space)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium \
    && rm -rf /ms-playwright/firefox-* /ms-playwright/webkit-* /ms-playwright/ffmpeg-* \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# Copy the rest of the project (venv, data, output, .env excluded via .dockerignore)
COPY . .

# Ensure persistent data & output directories exist inside the image
RUN mkdir -p data output

# Expose the server port
EXPOSE 8080

# Health check — polls /api/status
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

CMD ["python", "server.py", "--port", "8080", "--host", "0.0.0.0"]
