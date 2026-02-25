FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for git interactions
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# CSIAC NetSec: Create non-root user and group
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# CSIAC NetSec: Switch to non-root user
USER appuser

# Cloud Run listens on port 8080 by default
EXPOSE 8080

# CSIAC NetSec: Container health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
