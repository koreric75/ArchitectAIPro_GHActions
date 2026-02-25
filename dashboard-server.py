"""
CHAD Dashboard — Hardened Flask server for Cloud Run.

Serves the static dashboard and provides an API endpoint to re-run
the audit and regenerate the dashboard on-demand.

CSIAC Domains:
  - IAM: Secrets accessed only from environment variables (never request body)
  - Forensics: Structured JSON logging for all security-relevant events
  - SoftSec: Input validation, no debug mode in production
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from flask import Flask, send_from_directory, jsonify, request, g

# ---------------------------------------------------------------------------
# Security Logger Setup (CSIAC Forensics)
# ---------------------------------------------------------------------------

# Try to import the shared security logger; fall back to basic logging
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from security_logger import (
        setup_security_logger,
        log_security_event,
        generate_request_id,
        get_client_ip,
        log_request_start,
        log_request_end,
    )
    logger = setup_security_logger("chad-dashboard", service="chad-dashboard")
except ImportError:
    import logging
    logger = logging.getLogger("chad-dashboard")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    def log_security_event(lg, event_type, message, level=logging.INFO, **ctx):
        lg.log(level, f"[{event_type}] {message} {ctx}")

    def generate_request_id():
        import uuid
        return str(uuid.uuid4())

    def get_client_ip(req):
        fwd = req.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() if fwd else req.remote_addr or "unknown"

    def log_request_start(lg, req, rid):
        pass

    def log_request_end(lg, req, resp, rid, dur):
        pass

# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="static")

STATIC_DIR = Path(__file__).parent / "static"

# CSIAC IAM: Input validation regex for GitHub usernames
_VALID_OWNER_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9_-]{0,37}[a-zA-Z0-9])?$")


# ---------------------------------------------------------------------------
# Request Lifecycle Middleware (CSIAC Forensics)
# ---------------------------------------------------------------------------

@app.before_request
def before_request_hook():
    """Log incoming requests and set correlation ID."""
    g.request_id = generate_request_id()
    g.start_time = time.time()
    # Log at DEBUG for health checks to reduce noise
    if request.path == "/health":
        logger.debug(
            f"{request.method} {request.path}",
            extra={
                "event_type": "request_start",
                "source_ip": get_client_ip(request),
                "request_id": g.request_id,
            },
        )
    else:
        log_request_start(logger, request, g.request_id)


@app.after_request
def after_request_hook(response):
    """Log response status and duration."""
    duration_ms = (time.time() - g.get("start_time", time.time())) * 1000
    if request.path != "/health":
        log_request_end(logger, request, response, g.get("request_id", ""), duration_ms)
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the CHAD dashboard."""
    return send_from_directory(STATIC_DIR, "dashboard.html")


@app.route("/audit_report.json")
def audit_report():
    """Serve the latest audit report."""
    return send_from_directory(STATIC_DIR, "audit_report.json")


@app.route("/api/refresh", methods=["POST"])
def refresh():
    """Re-run the audit and regenerate the dashboard.

    CSIAC IAM: Token is sourced ONLY from server-side environment variables.
    Client-submitted tokens are rejected to prevent token-over-wire exposure.
    """
    # CSIAC IAM: Use only server-side token — never accept from request body
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    if not token:
        log_security_event(
            logger, "auth_failure", "No server-side GitHub token configured",
            source_ip=get_client_ip(request),
            request_id=g.get("request_id", ""),
        )
        return jsonify({"error": "No GitHub token configured on server"}), 401

    body = request.get_json(silent=True) or {}

    # Warn if client tried to send a token (policy: server-only)
    if body.get("token"):
        log_security_event(
            logger, "policy_violation",
            "Client attempted to submit token in request body — ignored",
            source_ip=get_client_ip(request),
            request_id=g.get("request_id", ""),
            level=__import__("logging").WARNING,
        )

    # CSIAC SoftSec: Validate owner parameter
    owner = body.get("owner", os.environ.get("GITHUB_OWNER", "koreric75"))
    if not _VALID_OWNER_RE.match(owner):
        log_security_event(
            logger, "input_validation_failure",
            f"Invalid owner parameter rejected: {owner[:50]}",
            source_ip=get_client_ip(request),
            request_id=g.get("request_id", ""),
            level=__import__("logging").WARNING,
        )
        return jsonify({"error": "Invalid owner parameter"}), 400

    log_security_event(
        logger, "audit_trigger",
        f"Audit refresh triggered for owner={owner}",
        source_ip=get_client_ip(request),
        request_id=g.get("request_id", ""),
    )

    try:
        # Set token for subprocess
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = token
        env["GH_TOKEN"] = token

        # Run auditor
        result = subprocess.run(
            [sys.executable, "repo_auditor.py",
             "--owner", owner,
             "--output", str(STATIC_DIR / "audit_report.json")],
            capture_output=True, text=True, timeout=120, env=env,
            cwd=Path(__file__).parent,
        )
        if result.returncode != 0:
            # CSIAC Forensics: Log full error server-side, return generic message
            logger.error(
                f"Audit subprocess failed: {result.stderr[:500]}",
                extra={
                    "event_type": "audit_failure",
                    "request_id": g.get("request_id", ""),
                },
            )
            return jsonify({"error": "Audit process failed"}), 500

        # Regenerate dashboard
        result2 = subprocess.run(
            [sys.executable, "dashboard_generator.py",
             "--input", str(STATIC_DIR / "audit_report.json"),
             "--output", str(STATIC_DIR / "dashboard.html")],
            capture_output=True, text=True, timeout=30,
            cwd=Path(__file__).parent,
        )
        if result2.returncode != 0:
            logger.error(
                f"Dashboard generation failed: {result2.stderr[:500]}",
                extra={
                    "event_type": "dashboard_generation_failure",
                    "request_id": g.get("request_id", ""),
                },
            )
            return jsonify({"error": "Dashboard generation failed"}), 500

        # Load summary
        report = json.loads((STATIC_DIR / "audit_report.json").read_text())

        log_security_event(
            logger, "audit_success",
            f"Audit completed: {report.get('summary', {}).get('total_repos', 0)} repos",
            request_id=g.get("request_id", ""),
        )

        return jsonify({
            "status": "ok",
            "total_repos": report.get("summary", {}).get("total_repos", 0),
            "api_calls": report.get("api_calls_used", 0),
        })
    except subprocess.TimeoutExpired:
        log_security_event(
            logger, "audit_timeout", "Audit subprocess timed out",
            source_ip=get_client_ip(request),
            request_id=g.get("request_id", ""),
            level=__import__("logging").ERROR,
        )
        return jsonify({"error": "Audit timed out"}), 504
    except Exception as e:
        logger.exception(
            "Unexpected error in /api/refresh",
            extra={
                "event_type": "unexpected_error",
                "request_id": g.get("request_id", ""),
            },
        )
        # CSIAC SoftSec: Return generic error — never expose raw exception
        return jsonify({"error": "Internal server error"}), 500


@app.route("/health")
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "healthy", "service": "chad-dashboard"})


if __name__ == "__main__":
    # CSIAC SoftSec: Never default to debug=True in production
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting CHAD Dashboard on port {port} (debug={debug_mode})")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
