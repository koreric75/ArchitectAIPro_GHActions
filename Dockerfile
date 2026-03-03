# Dockerfile for ArchitectAIPro GH Actions Dashboard
# M2.1 Standardization: Multi-stage, non-root user, slim base, health check
# Alias for Dockerfile.dashboard - standardized entrypoint for CI/CD

FROM python:3.11-slim AS builder

WORKDIR /app

# Install dependencies in builder
COPY requirements-dashboard.txt ./requirements-dashboard.txt
RUN pip install --no-cache-dir -r requirements-dashboard.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user (UID 1001)
RUN groupadd -g 1001 appuser && \
    useradd -u 1001 -g appuser -m appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy application scripts
COPY .github/scripts/repo_auditor.py /app/repo_auditor.py
COPY .github/scripts/dashboard_generator.py /app/dashboard_generator.py
COPY .github/scripts/ops_page_generator.py /app/ops_page_generator.py
COPY .github/scripts/token_budget.py /app/token_budget.py
COPY .github/scripts/security_logger.py /app/security_logger.py

# Copy architecture docs
RUN mkdir -p /app/docs
COPY docs/architecture.mermaid /app/docs/architecture.mermaid
COPY docs/architecture.md /app/docs/architecture.md

# Copy workflow templates
RUN mkdir -p /app/workflow_templates
COPY .github/workflows/architecture-standalone.yml /app/workflow_templates/architecture-standalone.yml
COPY .github/workflows/security-scan.yml /app/workflow_templates/security-scan.yml

# Create static dir for runtime data
RUN mkdir -p /app/static && \
    echo '{"summary":{"total_repos":0},"repos":[]}' > /app/static/audit_report.json && \
    echo '<html><body><h1>CHAD Dashboard</h1><p>Run POST /api/refresh to generate.</p></body></html>' > /app/static/dashboard.html && \
    echo '<html><body><h1>CHAD Ops Center</h1><p>Run POST /api/refresh to generate.</p></body></html>' > /app/static/ops.html

# Copy server
COPY dashboard-server.py /app/server.py

# Grant write access to static dir
RUN chown -R appuser:appuser /app/static

ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "server:app"]

