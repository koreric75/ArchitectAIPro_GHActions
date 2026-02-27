"""CHAD Dashboard — Hardened Flask server for Cloud Run.

Serves the static dashboard and provides an API endpoint to re-run
the audit and regenerate the dashboard on-demand.

CSIAC Domains:
  - IAM: Secrets accessed only from environment variables (never request body)
  - Forensics: Structured JSON logging for all security-relevant events
  - SoftSec: Input validation, no debug mode in production
"""

import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests as http_requests
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

# Extra orgs to scan (comma-separated)
EXTRA_ORGS = os.environ.get("EXTRA_ORGS", "bluefalconink")


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
        f"Audit refresh triggered for owner={owner} extra_orgs={EXTRA_ORGS}",
        source_ip=get_client_ip(request),
        request_id=g.get("request_id", ""),
    )

    try:
        # Set token for subprocess
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = token
        env["GH_TOKEN"] = token

        # Build auditor command with extra orgs support
        cmd = [
            sys.executable, "repo_auditor.py",
            "--owner", owner,
            "--output", str(STATIC_DIR / "audit_report.json"),
        ]
        if EXTRA_ORGS:
            cmd.extend(["--extra-orgs", EXTRA_ORGS])

        # Run auditor
        result = subprocess.run(
            cmd,
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


# ---------------------------------------------------------------------------
# Workflow Deployment API  (CSIAC IAM + SoftSec)
# ---------------------------------------------------------------------------

# Valid GitHub repo name pattern
_VALID_REPO_RE = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")

# Path to the architecture-standalone workflow template
_WORKFLOW_TEMPLATE_PATH = (
    Path(__file__).parent / ".github" / "workflows" / "architecture-standalone.yml"
)


def _resolve_deploy_token():
    """Resolve a GitHub token for workflow deployment.

    Priority:
      1. Bearer token in Authorization header  (client-initiated)
      2. Server-side GITHUB_TOKEN / GH_TOKEN   (headless / CI)

    Returns (token, source) or (None, None).
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token, "bearer_header"

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token, "server_env"

    return None, None


def _github_headers(token):
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@app.route("/api/deploy-workflow", methods=["POST"])
def deploy_workflow():
    """Deploy the architecture-standalone workflow to one or more repos.

    Expects JSON body:
      { "owner": "<github-user>", "repos": ["repo1", "repo2"] }

    Authentication:
      - Bearer token in Authorization header, OR
      - Server-side GITHUB_TOKEN environment variable

    CSIAC Domains:
      - IAM:     Token resolved from header or env, never from request body
      - SoftSec: Input validation on owner + repo names
      - Forensics: Structured logging for every deploy attempt
    """
    token, token_source = _resolve_deploy_token()

    if not token:
        log_security_event(
            logger, "auth_failure",
            "No GitHub token available for deploy-workflow",
            source_ip=get_client_ip(request),
            request_id=g.get("request_id", ""),
        )
        return jsonify({"error": "Authentication required. Provide a Bearer token or configure GITHUB_TOKEN on the server."}), 401

    body = request.get_json(silent=True) or {}

    # Validate owner
    owner = body.get("owner", os.environ.get("GITHUB_OWNER", "koreric75"))
    if not _VALID_OWNER_RE.match(owner):
        log_security_event(
            logger, "input_validation_failure",
            f"Invalid owner for deploy-workflow: {str(owner)[:50]}",
            source_ip=get_client_ip(request),
            request_id=g.get("request_id", ""),
            level=__import__("logging").WARNING,
        )
        return jsonify({"error": "Invalid owner parameter"}), 400

    # Validate repos list
    repos = body.get("repos", [])
    if not isinstance(repos, list) or len(repos) == 0:
        return jsonify({"error": "repos must be a non-empty list"}), 400
    if len(repos) > 20:
        return jsonify({"error": "Maximum 20 repos per request"}), 400

    for repo in repos:
        if not isinstance(repo, str) or not _VALID_REPO_RE.match(repo):
            return jsonify({"error": f"Invalid repo name: {str(repo)[:100]}"}), 400

    # Load workflow template
    if not _WORKFLOW_TEMPLATE_PATH.exists():
        logger.error("Workflow template not found at %s", _WORKFLOW_TEMPLATE_PATH)
        return jsonify({"error": "Workflow template not found on server"}), 500

    workflow_content = _WORKFLOW_TEMPLATE_PATH.read_text(encoding="utf-8")
    workflow_b64 = base64.b64encode(workflow_content.encode("utf-8")).decode("ascii")

    log_security_event(
        logger, "deploy_workflow_start",
        f"Deploying architecture workflow to {len(repos)} repo(s) for owner={owner}",
        source_ip=get_client_ip(request),
        request_id=g.get("request_id", ""),
        token_source=token_source,
        repos=repos,
    )

    headers = _github_headers(token)
    target_path = ".github/workflows/architecture.yml"
    results = []

    for repo in repos:
        entry = {"repo": repo, "status": "pending"}
        try:
            # Check if file already exists (to get the sha for update)
            check_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{target_path}"
            check_resp = http_requests.get(check_url, headers=headers, timeout=15)

            sha = None
            if check_resp.status_code == 200:
                sha = check_resp.json().get("sha")

            # Create or update the file
            put_payload = {
                "message": "ci: deploy architecture workflow via CHAD dashboard [skip ci]",
                "content": workflow_b64,
                "committer": {
                    "name": "CHAD Dashboard",
                    "email": "chad-bot@bluefalconink.com",
                },
            }
            if sha:
                put_payload["sha"] = sha

            put_resp = http_requests.put(check_url, headers=headers, json=put_payload, timeout=30)

            if put_resp.status_code in (200, 201):
                entry["status"] = "ok"
                entry["action"] = "updated" if sha else "created"
                log_security_event(
                    logger, "deploy_workflow_success",
                    f"Workflow deployed to {owner}/{repo}",
                    request_id=g.get("request_id", ""),
                    repo=repo,
                    action=entry["action"],
                )
            else:
                entry["status"] = "error"
                err_body = put_resp.json() if put_resp.headers.get("content-type", "").startswith("application/json") else {}
                entry["message"] = err_body.get("message", f"HTTP {put_resp.status_code}")
                log_security_event(
                    logger, "deploy_workflow_failure",
                    f"Failed to deploy to {owner}/{repo}: {entry['message']}",
                    request_id=g.get("request_id", ""),
                    repo=repo,
                    http_status=put_resp.status_code,
                    level=__import__("logging").WARNING,
                )
        except http_requests.Timeout:
            entry["status"] = "error"
            entry["message"] = "Request timed out"
        except Exception as exc:
            entry["status"] = "error"
            entry["message"] = str(exc)[:200]
            logger.exception(
                "Unexpected error deploying workflow to %s/%s", owner, repo,
                extra={"request_id": g.get("request_id", "")},
            )

        results.append(entry)

    success_count = sum(1 for r in results if r["status"] == "ok")
    log_security_event(
        logger, "deploy_workflow_complete",
        f"Deploy complete: {success_count}/{len(repos)} succeeded",
        request_id=g.get("request_id", ""),
    )

    return jsonify({
        "status": "ok" if success_count == len(repos) else "partial" if success_count > 0 else "failed",
        "deployed": success_count,
        "total": len(repos),
        "results": results,
    }), 200 if success_count > 0 else 500


# ---------------------------------------------------------------------------
# Auto-refresh on Startup
# ---------------------------------------------------------------------------

def _auto_refresh():
    """Run audit + dashboard generation in a background thread on startup.

    This ensures the dashboard is populated immediately after deployment
    instead of showing the placeholder page. Only runs when a GITHUB_TOKEN
    is available on the server.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        logger.info("No GITHUB_TOKEN configured — skipping auto-refresh")
        return

    owner = os.environ.get("GITHUB_OWNER", "koreric75")
    logger.info(f"Auto-refresh: starting audit for owner={owner}")

    try:
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = token
        env["GH_TOKEN"] = token
        app_dir = Path(__file__).parent

        # Run auditor
        result = subprocess.run(
            [sys.executable, "repo_auditor.py",
             "--owner", owner,
             "--output", str(STATIC_DIR / "audit_report.json")],
            capture_output=True, text=True, timeout=120, env=env,
            cwd=app_dir,
        )
        if result.returncode != 0:
            logger.error(f"Auto-refresh audit failed: {result.stderr[:500]}")
            return

        # Generate dashboard
        result2 = subprocess.run(
            [sys.executable, "dashboard_generator.py",
             "--input", str(STATIC_DIR / "audit_report.json"),
             "--output", str(STATIC_DIR / "dashboard.html")],
            capture_output=True, text=True, timeout=30,
            cwd=app_dir,
        )
        if result2.returncode != 0:
            logger.error(f"Auto-refresh dashboard generation failed: {result2.stderr[:500]}")
            return

        report = json.loads((STATIC_DIR / "audit_report.json").read_text())
        total = report.get("summary", {}).get("total_repos", 0)
        logger.info(f"Auto-refresh complete: {total} repos audited")
    except subprocess.TimeoutExpired:
        logger.error("Auto-refresh timed out")
    except Exception:
        logger.exception("Auto-refresh failed with unexpected error")


def _start_auto_refresh():
    """Launch auto-refresh in a daemon thread so it doesn't block startup."""
    t = threading.Thread(target=_auto_refresh, daemon=True, name="auto-refresh")
    t.start()


# Trigger auto-refresh once when the module is first loaded by gunicorn
_start_auto_refresh()


if __name__ == "__main__":
    # CSIAC SoftSec: Never default to debug=True in production
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting CHAD Dashboard on port {port} (debug={debug_mode})")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
