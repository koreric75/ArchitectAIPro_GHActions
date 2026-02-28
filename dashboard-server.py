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
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip() or None

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

        # Generate Ops Center page
        app_dir = Path(__file__).parent
        mermaid_path = app_dir / "docs" / "architecture.mermaid"
        ops_cmd = [
            sys.executable, "ops_page_generator.py",
            "--input", str(STATIC_DIR / "audit_report.json"),
            "--mermaid", str(mermaid_path),
            "--output", str(STATIC_DIR / "ops.html"),
        ]
        result3 = subprocess.run(
            ops_cmd, capture_output=True, text=True, timeout=30,
            cwd=app_dir,
        )
        if result3.returncode != 0:
            logger.warning(f"Ops page generation failed (non-fatal): {result3.stderr[:300]}")

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


@app.route("/api/status", methods=["GET"])
def api_status():
    """Return CHAD refresh status — useful for debugging staleness."""
    import datetime
    report_path = STATIC_DIR / "audit_report.json"
    report_age = None
    total_repos = 0
    if report_path.exists():
        stat = report_path.stat()
        report_age = time.time() - stat.st_mtime
        try:
            rpt = json.loads(report_path.read_text())
            total_repos = rpt.get("summary", {}).get("total_repos", 0)
        except Exception:
            pass

    last_dt = (
        datetime.datetime.fromtimestamp(_last_refresh_time, tz=datetime.timezone.utc).isoformat()
        if _last_refresh_time > 0 else None
    )
    return jsonify({
        "last_refresh_utc": last_dt,
        "refresh_interval_hours": REFRESH_INTERVAL / 3600,
        "report_age_seconds": round(report_age) if report_age is not None else None,
        "total_repos": total_repos,
        "dashboard_exists": (STATIC_DIR / "dashboard.html").exists(),
        "ops_exists": (STATIC_DIR / "ops.html").exists(),
    })


# ---------------------------------------------------------------------------
# Ops Center Page + API  (Architecture, Deployments, Recommendations)
# ---------------------------------------------------------------------------

@app.route("/ops")
def ops_page():
    """Serve the CHAD Ops Center page."""
    ops_html = STATIC_DIR / "ops.html"
    if ops_html.exists():
        return send_from_directory(STATIC_DIR, "ops.html")
    return "<html><body><h1>CHAD Ops Center</h1><p>Run POST /api/refresh to generate.</p></body></html>", 200


@app.route("/api/architecture", methods=["GET"])
def get_architecture():
    """Return the BlueFalconInk LLC architecture diagram (Mermaid source)."""
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    owner = os.environ.get("GITHUB_OWNER", "koreric75")
    repo = "ArchitectAIPro_GHActions"

    mermaid_src = ""
    arch_md = ""

    # Try fetching live from GitHub first, fall back to local file
    if token:
        headers = _github_headers(token)
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/docs/architecture.mermaid"
            resp = http_requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                import base64 as b64
                mermaid_src = b64.b64decode(resp.json()["content"]).decode("utf-8")
        except Exception:
            pass
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/docs/architecture.md"
            resp = http_requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                import base64 as b64
                arch_md = b64.b64decode(resp.json()["content"]).decode("utf-8")
        except Exception:
            pass

    # Fall back to local files in the container
    if not mermaid_src:
        local = Path(__file__).parent / "docs" / "architecture.mermaid"
        if local.exists():
            mermaid_src = local.read_text(encoding="utf-8")
    if not arch_md:
        local = Path(__file__).parent / "docs" / "architecture.md"
        if local.exists():
            arch_md = local.read_text(encoding="utf-8")

    return jsonify({
        "mermaid": mermaid_src,
        "markdown": arch_md,
    })


@app.route("/api/deployments", methods=["GET"])
def get_deployments():
    """Fetch recent workflow runs across all audited repos.

    Returns deployment status for every repo that has GitHub Actions configured.
    Uses the cached audit_report.json to know which repos to scan.
    """
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        return jsonify({"error": "No GitHub token configured"}), 401

    headers = _github_headers(token)

    # Load latest audit report for repo list
    report_path = STATIC_DIR / "audit_report.json"
    if not report_path.exists():
        return jsonify({"error": "No audit report available. Run /api/refresh first."}), 404

    report = json.loads(report_path.read_text())
    repos = report.get("repos", [])

    deployments = []
    for repo_data in repos:
        repo_name = repo_data["name"]
        repo_owner = repo_data.get("owner", report.get("owner", "koreric75"))
        full_name = f"{repo_owner}/{repo_name}"

        # Use cached workflow data from audit
        wf_data = repo_data.get("workflows", {})
        cached_runs = wf_data.get("recent_runs", [])
        health = wf_data.get("health", "UNKNOWN")

        # Also pull repo metadata
        tier = repo_data.get("classification", {}).get("tier", "UNKNOWN")
        is_archived = repo_data.get("is_archived", False)
        url = repo_data.get("url", f"https://github.com/{full_name}")
        has_workflow = repo_data.get("architecture", {}).get("has_workflow", False)
        staleness = repo_data.get("staleness", {})
        days_since_push = staleness.get("days_since_push", "?")

        entry = {
            "repo": repo_name,
            "owner": repo_owner,
            "full_name": full_name,
            "url": url,
            "tier": tier,
            "is_archived": is_archived,
            "has_ci": len(cached_runs) > 0 or has_workflow,
            "health": health,
            "days_since_push": days_since_push,
            "recent_runs": cached_runs[:5],
        }
        deployments.append(entry)

    # Sort: failing first, then degraded, then healthy, then unknown
    health_order = {"FAILING": 0, "DEGRADED": 1, "HEALTHY": 2, "UNKNOWN": 3}
    deployments.sort(key=lambda d: (health_order.get(d["health"], 9), d["full_name"]))

    # Summary stats
    total = len(deployments)
    healthy = sum(1 for d in deployments if d["health"] == "HEALTHY")
    degraded = sum(1 for d in deployments if d["health"] == "DEGRADED")
    failing = sum(1 for d in deployments if d["health"] == "FAILING")
    no_ci = sum(1 for d in deployments if not d["has_ci"])

    # Build recommendations
    recommendations = _build_recommendations(deployments, repos, report)

    return jsonify({
        "deployments": deployments,
        "summary": {
            "total": total,
            "healthy": healthy,
            "degraded": degraded,
            "failing": failing,
            "no_ci": no_ci,
        },
        "recommendations": recommendations,
    })


def _build_recommendations(deployments, repos, report):
    """Generate actionable recommendations based on deployment health + audit data."""
    recs = []

    # 1. Repos with failing CI
    failing_repos = [d for d in deployments if d["health"] == "FAILING"]
    if failing_repos:
        recs.append({
            "severity": "critical",
            "icon": "🔴",
            "title": f"{len(failing_repos)} repo(s) have failing CI pipelines",
            "description": "These repositories have 3+ recent workflow failures. Investigate and fix build/test issues.",
            "repos": [d["full_name"] for d in failing_repos],
            "action": "Inspect workflow logs and fix root causes immediately.",
        })

    # 2. Repos with degraded CI
    degraded_repos = [d for d in deployments if d["health"] == "DEGRADED"]
    if degraded_repos:
        recs.append({
            "severity": "warning",
            "icon": "🟡",
            "title": f"{len(degraded_repos)} repo(s) have degraded CI health",
            "description": "Occasional failures detected. May indicate flaky tests or intermittent issues.",
            "repos": [d["full_name"] for d in degraded_repos],
            "action": "Review recent failure logs to identify patterns (flaky tests, timeouts, dependency issues).",
        })

    # 3. Active repos with no CI
    no_ci_active = [d for d in deployments if not d["has_ci"] and d["tier"] in ("CORE", "ACTIVE") and not d["is_archived"]]
    if no_ci_active:
        recs.append({
            "severity": "warning",
            "icon": "⚠️",
            "title": f"{len(no_ci_active)} active repo(s) have no CI/CD pipeline",
            "description": "Core/Active repos without continuous integration are at risk of undetected regressions.",
            "repos": [d["full_name"] for d in no_ci_active],
            "action": "Deploy an architecture or security-scan workflow from the CHAD dashboard.",
        })

    # 4. Repos missing architecture workflow
    no_arch = [r for r in repos if not r.get("architecture", {}).get("has_workflow", False)
               and not r.get("is_archived", False)
               and r.get("classification", {}).get("tier") in ("CORE", "ACTIVE")]
    if no_arch:
        recs.append({
            "severity": "info",
            "icon": "🏗️",
            "title": f"{len(no_arch)} repo(s) missing architecture diagrams workflow",
            "description": "Architecture diagrams keep documentation in sync. Deploy the workflow to auto-generate them.",
            "repos": [f"{r.get('owner', 'unknown')}/{r['name']}" for r in no_arch],
            "action": "Use the Deploy Workflow feature on the main dashboard.",
        })

    # 5. Stale repos that should be archived
    stale_active = [r for r in repos if r.get("classification", {}).get("tier") in ("STALE", "DEAD", "DORMANT")
                    and not r.get("is_archived", False)]
    if stale_active:
        recs.append({
            "severity": "info",
            "icon": "📦",
            "title": f"{len(stale_active)} stale/dead repo(s) should be archived",
            "description": "These repos haven't had activity in a long time. Archiving reduces security surface area.",
            "repos": [f"{r.get('owner', 'unknown')}/{r['name']}" for r in stale_active],
            "action": "Select these repos on the main dashboard and use Archive.",
        })

    # 6. Branding compliance
    branding_issues = report.get("summary", {}).get("branding_issues", [])
    if branding_issues:
        recs.append({
            "severity": "info",
            "icon": "🎨",
            "title": f"{len(branding_issues)} repo(s) have branding compliance issues",
            "description": "Missing or incorrect LICENSE, README, or .github templates.",
            "repos": [b["repo"] for b in branding_issues],
            "action": "Review branding requirements and add missing files.",
        })

    return recs


# ---------------------------------------------------------------------------
# Workflow Deployment API  (CSIAC IAM + SoftSec)
# ---------------------------------------------------------------------------

# Valid GitHub repo name pattern
_VALID_REPO_RE = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")

# Deployable workflow templates — id → { file, target, label, description }
_WORKFLOW_TEMPLATES_DIR = Path(__file__).parent / "workflow_templates"
_WORKFLOW_TEMPLATES = {
    "architecture": {
        "file": "architecture-standalone.yml",
        "target": ".github/workflows/architecture.yml",
        "label": "🏗️ Architecture Diagrams",
        "description": "Auto-generate architecture diagrams on push",
    },
    "security-scan": {
        "file": "security-scan.yml",
        "target": ".github/workflows/security-scan.yml",
        "label": "🔒 Security Scan",
        "description": "SAST, dependency scanning, and container scanning",
    },
}

# Legacy fallback path (used if workflow_templates dir doesn't exist)
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


def _resolve_workflow_template(workflow_id: str):
    """Resolve a workflow template file by ID. Returns (content, target_path, label) or raises."""
    tmpl = _WORKFLOW_TEMPLATES.get(workflow_id)
    if not tmpl:
        return None, None, None

    # Check workflow_templates dir first, then legacy path
    tmpl_path = _WORKFLOW_TEMPLATES_DIR / tmpl["file"]
    if not tmpl_path.exists():
        # Legacy: try .github/workflows/
        tmpl_path = Path(__file__).parent / ".github" / "workflows" / tmpl["file"]

    if not tmpl_path.exists():
        return None, None, None

    content = tmpl_path.read_text(encoding="utf-8")
    return content, tmpl["target"], tmpl["label"]


@app.route("/api/workflows", methods=["GET"])
def list_workflows():
    """List available workflow templates that can be deployed."""
    workflows = []
    for wf_id, tmpl in _WORKFLOW_TEMPLATES.items():
        tmpl_path = _WORKFLOW_TEMPLATES_DIR / tmpl["file"]
        if not tmpl_path.exists():
            tmpl_path = Path(__file__).parent / ".github" / "workflows" / tmpl["file"]
        workflows.append({
            "id": wf_id,
            "label": tmpl["label"],
            "description": tmpl["description"],
            "target": tmpl["target"],
            "available": tmpl_path.exists(),
        })
    return jsonify({"workflows": workflows})


@app.route("/api/deploy-workflow", methods=["POST"])
def deploy_workflow():
    """Deploy a workflow to one or more repos.

    Expects JSON body:
      { "owner": "<github-user>", "repos": ["repo1", "repo2"], "workflow": "architecture" }

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

    # Resolve workflow template by ID (default: architecture for backward compat)
    workflow_id = body.get("workflow", "architecture")
    if not isinstance(workflow_id, str) or not re.match(r"^[a-zA-Z0-9_-]{1,50}$", workflow_id):
        return jsonify({"error": "Invalid workflow parameter"}), 400

    workflow_content, target_path, workflow_label = _resolve_workflow_template(workflow_id)
    if not workflow_content:
        logger.error("Workflow template not found for id=%s", workflow_id)
        return jsonify({"error": f"Workflow template '{workflow_id}' not found on server"}), 500

    workflow_b64 = base64.b64encode(workflow_content.encode("utf-8")).decode("ascii")

    log_security_event(
        logger, "deploy_workflow_start",
        f"Deploying {workflow_id} workflow to {len(repos)} repo(s) for owner={owner}",
        source_ip=get_client_ip(request),
        request_id=g.get("request_id", ""),
        token_source=token_source,
        repos=repos,
    )

    headers = _github_headers(token)
    results = []

    for repo in repos:
        entry = {"repo": repo, "status": "pending", "workflow": workflow_id}
        try:
            # Check if file already exists (to get the sha for update)
            check_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{target_path}"
            check_resp = http_requests.get(check_url, headers=headers, timeout=15)

            sha = None
            if check_resp.status_code == 200:
                sha = check_resp.json().get("sha")

            # Create or update the file
            put_payload = {
                "message": f"ci: deploy {workflow_id} workflow via CHAD dashboard [skip ci]",
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

# ---------------------------------------------------------------------------
# Periodic auto-refresh interval in seconds (default: 4 hours).
# Override with CHAD_REFRESH_INTERVAL env var.
# ---------------------------------------------------------------------------
REFRESH_INTERVAL = int(os.environ.get("CHAD_REFRESH_INTERVAL", 4 * 3600))
_last_refresh_time: float = 0.0
_refresh_lock = threading.Lock()


def _run_refresh_cycle():
    """Execute one audit + dashboard + ops page generation cycle.

    Returns True on success, False on failure.
    """
    global _last_refresh_time
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        logger.info("No GITHUB_TOKEN configured — skipping auto-refresh")
        return False

    owner = os.environ.get("GITHUB_OWNER", "koreric75")
    logger.info(f"Auto-refresh: starting audit for owner={owner}")

    try:
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = token
        env["GH_TOKEN"] = token
        app_dir = Path(__file__).parent

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
            capture_output=True, text=True, timeout=180, env=env,
            cwd=app_dir,
        )
        if result.returncode != 0:
            logger.error(f"Auto-refresh audit failed: {result.stderr[:500]}")
            return False

        # Generate dashboard
        result2 = subprocess.run(
            [sys.executable, "dashboard_generator.py",
             "--input", str(STATIC_DIR / "audit_report.json"),
             "--output", str(STATIC_DIR / "dashboard.html")],
            capture_output=True, text=True, timeout=60,
            cwd=app_dir,
        )
        if result2.returncode != 0:
            logger.error(f"Auto-refresh dashboard generation failed: {result2.stderr[:500]}")
            return False

        # Generate Ops Center page
        mermaid_path = app_dir / "docs" / "architecture.mermaid"
        result3 = subprocess.run(
            [sys.executable, "ops_page_generator.py",
             "--input", str(STATIC_DIR / "audit_report.json"),
             "--mermaid", str(mermaid_path),
             "--output", str(STATIC_DIR / "ops.html")],
            capture_output=True, text=True, timeout=60,
            cwd=app_dir,
        )
        if result3.returncode != 0:
            logger.warning(f"Auto-refresh ops page generation failed (non-fatal): {result3.stderr[:300]}")

        report = json.loads((STATIC_DIR / "audit_report.json").read_text())
        total = report.get("summary", {}).get("total_repos", 0)
        _last_refresh_time = time.time()
        logger.info(f"Auto-refresh complete: {total} repos audited")
        return True
    except subprocess.TimeoutExpired:
        logger.error("Auto-refresh timed out")
        return False
    except Exception:
        logger.exception("Auto-refresh failed with unexpected error")
        return False


def _auto_refresh_loop():
    """Run refresh immediately on startup, then repeat every REFRESH_INTERVAL.

    This ensures:
      1. Dashboard is populated right after a cold-start.
      2. Data stays fresh even if the container stays alive for days.
    """
    # Initial refresh — retry up to 3 times on failure (token may not be
    # available instantly on Cloud Run cold-start).
    for attempt in range(1, 4):
        with _refresh_lock:
            ok = _run_refresh_cycle()
        if ok:
            break
        wait = 15 * attempt
        logger.warning(f"Auto-refresh attempt {attempt}/3 failed, retrying in {wait}s")
        time.sleep(wait)

    # Periodic loop
    logger.info(f"Scheduled periodic refresh every {REFRESH_INTERVAL}s ({REFRESH_INTERVAL / 3600:.1f}h)")
    while True:
        time.sleep(REFRESH_INTERVAL)
        logger.info("Periodic auto-refresh triggered")
        with _refresh_lock:
            _run_refresh_cycle()


def _start_auto_refresh():
    """Launch the auto-refresh loop in a daemon thread so it doesn't block startup."""
    t = threading.Thread(target=_auto_refresh_loop, daemon=True, name="auto-refresh")
    t.start()


# Trigger auto-refresh loop when the module is first loaded by gunicorn
_start_auto_refresh()


if __name__ == "__main__":
    # CSIAC SoftSec: Never default to debug=True in production
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting CHAD Dashboard on port {port} (debug={debug_mode})")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
