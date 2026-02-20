"""
CHAD Dashboard — Lightweight Flask server for Cloud Run.

Serves the static dashboard and provides an API endpoint to re-run
the audit and regenerate the dashboard on-demand.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, send_from_directory, jsonify, request

app = Flask(__name__, static_folder="static")

STATIC_DIR = Path(__file__).parent / "static"


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
    
    Requires GITHUB_TOKEN env var or token in request body.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    body = request.get_json(silent=True) or {}
    if body.get("token"):
        token = body["token"]

    if not token:
        return jsonify({"error": "No GitHub token available"}), 401

    owner = body.get("owner", os.environ.get("GITHUB_OWNER", "koreric75"))

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
            return jsonify({"error": "Audit failed", "stderr": result.stderr}), 500

        # Regenerate dashboard
        result2 = subprocess.run(
            [sys.executable, "dashboard_generator.py",
             "--input", str(STATIC_DIR / "audit_report.json"),
             "--output", str(STATIC_DIR / "dashboard.html")],
            capture_output=True, text=True, timeout=30,
            cwd=Path(__file__).parent,
        )
        if result2.returncode != 0:
            return jsonify({"error": "Dashboard generation failed", "stderr": result2.stderr}), 500

        # Load summary
        report = json.loads((STATIC_DIR / "audit_report.json").read_text())
        return jsonify({
            "status": "ok",
            "total_repos": report.get("summary", {}).get("total_repos", 0),
            "api_calls": report.get("api_calls_used", 0),
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Audit timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "chad-dashboard"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
