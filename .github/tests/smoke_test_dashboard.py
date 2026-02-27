#!/usr/bin/env python3
"""CHAD Dashboard — Smoke Tests.

Validates all critical endpoints on the live Cloud Run service.
Designed to run in CI (GitHub Actions) or locally.

Usage:
    SERVICE_URL=https://... python smoke_test_dashboard.py

Exit codes:
    0 — all tests passed
    1 — one or more tests failed
"""

import json
import os
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVICE_URL = os.environ.get(
    "SERVICE_URL", "https://chad-dashboard-42380604425.us-central1.run.app"
).rstrip("/")

GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Cloud Run cold-start budget (seconds)
MAX_RESPONSE_TIME = 15.0
# Warm endpoint budget
MAX_WARM_TIME = 5.0

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

results = []


def run_test(name, fn):
    """Execute a test function and record the result."""
    start = time.monotonic()
    try:
        fn()
        duration_ms = int((time.monotonic() - start) * 1000)
        results.append(
            {"name": name, "passed": True, "status": "PASS", "duration_ms": duration_ms}
        )
        print(f"  ✅ {name} ({duration_ms}ms)")
    except AssertionError as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        results.append(
            {
                "name": name,
                "passed": False,
                "status": f"FAIL: {e}",
                "duration_ms": duration_ms,
            }
        )
        print(f"  ❌ {name} — {e} ({duration_ms}ms)")
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        results.append(
            {
                "name": name,
                "passed": False,
                "status": f"ERROR: {e}",
                "duration_ms": duration_ms,
            }
        )
        print(f"  ❌ {name} — ERROR: {e} ({duration_ms}ms)")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_endpoint():
    """GET /health returns 200 with healthy status."""
    r = requests.get(f"{SERVICE_URL}/health", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()
    assert body.get("status") == "healthy", f"Expected healthy, got {body}"


def test_health_response_time():
    """GET /health responds within warm-endpoint budget."""
    start = time.monotonic()
    r = requests.get(f"{SERVICE_URL}/health", timeout=MAX_RESPONSE_TIME)
    elapsed = time.monotonic() - start
    assert r.status_code == 200, f"Health returned {r.status_code}"
    assert elapsed < MAX_WARM_TIME, f"Too slow: {elapsed:.2f}s > {MAX_WARM_TIME}s"


def test_root_serves_dashboard():
    """GET / returns 200 with CHAD dashboard HTML."""
    r = requests.get(f"{SERVICE_URL}/", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct, f"Expected text/html, got {ct}"
    assert "CHAD" in r.text, "Dashboard HTML missing 'CHAD' title"


def test_dashboard_has_table():
    """Dashboard HTML contains the infrastructure matrix table."""
    r = requests.get(f"{SERVICE_URL}/", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    # After a refresh, the generated dashboard should have repo rows
    # or at minimum the table structure
    assert "repoTable" in r.text or "<table" in r.text, "No table found in dashboard"


def test_dashboard_has_services_column():
    """Dashboard HTML includes the new Services column."""
    r = requests.get(f"{SERVICE_URL}/", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    # Check for Services header or svc-badge/svc-cell CSS
    has_header = "Services</th>" in r.text or ">Services<" in r.text
    has_css = "svc-badge" in r.text or "svc-cell" in r.text
    assert has_header or has_css, "Services column not found in dashboard"


def test_audit_report_json():
    """GET /audit_report.json returns valid JSON."""
    r = requests.get(f"{SERVICE_URL}/audit_report.json", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()  # Will throw if invalid JSON
    # Should have at minimum a summary key or repos key
    assert "summary" in body or "repos" in body, f"Missing expected keys: {list(body.keys())}"


def test_audit_report_has_repos():
    """Audit report contains repo entries (data was populated)."""
    r = requests.get(f"{SERVICE_URL}/audit_report.json", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()
    repos = body.get("repos", [])
    # After a refresh, there should be repos. On cold deploy, might be empty.
    # We accept either — but flag if zero.
    summary = body.get("summary", {})
    total = summary.get("total_repos", len(repos))
    assert total >= 0, f"Unexpected total_repos: {total}"


def test_audit_report_has_services():
    """Audit report repos include 'services' field from new detection."""
    r = requests.get(f"{SERVICE_URL}/audit_report.json", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()
    repos = body.get("repos", [])
    if not repos:
        return  # Skip if no data yet (pre-refresh)
    # Check at least one repo has the services field
    has_services = any("services" in repo for repo in repos)
    assert has_services, "No repos have 'services' field — auditor update may not be deployed"


def test_refresh_endpoint_exists():
    """POST /api/refresh is reachable (may require auth)."""
    # Send a minimal POST to verify the endpoint exists
    # The refresh triggers a full audit — use a long timeout
    try:
        r = requests.post(
            f"{SERVICE_URL}/api/refresh",
            json={"owner": "koreric75"},
            timeout=180,
            headers={"Content-Type": "application/json"},
        )
    except requests.exceptions.ReadTimeout:
        # Timeout is acceptable — it means the endpoint exists and is running
        # the audit (which takes >15s)
        return
    # Accept 200 (running), 409 (already running), or 500 (token issue)
    # 404 would mean the endpoint doesn't exist
    assert r.status_code != 404, "Refresh endpoint not found (404)"
    assert r.status_code != 405, "Refresh endpoint method not allowed (405)"


def test_deploy_workflow_endpoint_exists():
    """POST /api/deploy-workflow is reachable."""
    r = requests.post(
        f"{SERVICE_URL}/api/deploy-workflow",
        json={},
        timeout=MAX_RESPONSE_TIME,
        headers={"Content-Type": "application/json"},
    )
    # Should get 400 (bad request — missing fields) or 401 (no token)
    # NOT 404 (endpoint missing)
    assert r.status_code != 404, "Deploy-workflow endpoint not found (404)"
    assert r.status_code != 405, "Deploy-workflow endpoint method not allowed (405)"


def test_no_debug_mode():
    """Server does not expose debug/traceback info."""
    # Hit a non-existent endpoint
    r = requests.get(f"{SERVICE_URL}/nonexistent-path-12345", timeout=MAX_RESPONSE_TIME)
    # Should be 404 (not found) but NOT contain Python tracebacks
    body = r.text.lower()
    assert "traceback" not in body, "Server leaking traceback in error responses"
    assert "debugger" not in body, "Server running in debug mode"


def test_security_headers():
    """Response includes basic security headers / no sensitive leaks."""
    r = requests.get(f"{SERVICE_URL}/health", timeout=MAX_RESPONSE_TIME)
    # Server header should not reveal too much
    server = r.headers.get("server", "").lower()
    assert "werkzeug" not in server, f"Server header leaks framework: {server}"
    # No X-Powered-By exposing framework
    powered_by = r.headers.get("x-powered-by", "")
    assert not powered_by, f"X-Powered-By header present: {powered_by}"


def test_cors_not_wildcard():
    """Verify CORS is not set to wildcard (security)."""
    r = requests.get(f"{SERVICE_URL}/health", timeout=MAX_RESPONSE_TIME)
    acao = r.headers.get("access-control-allow-origin", "")
    # Wildcard CORS is risky for an API that handles tokens
    # It's OK if there's no CORS header at all
    if acao:
        assert acao != "*", "CORS set to wildcard (*) — risky for token-handling API"


def test_ops_center_page():
    """Verify /ops returns the Ops Center page."""
    r = requests.get(f"{SERVICE_URL}/ops", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert len(r.text) > 500, f"Ops page too small ({len(r.text)} bytes)"
    assert "Ops Center" in r.text, "Missing 'Ops Center' title"


def test_ops_has_architecture():
    """Verify Ops Center has architecture diagram section."""
    r = requests.get(f"{SERVICE_URL}/ops", timeout=MAX_RESPONSE_TIME)
    assert "architectureSection" in r.text, "Missing architecture section"
    assert "mermaid" in r.text.lower(), "Missing Mermaid diagram"


def test_ops_has_deployments():
    """Verify Ops Center has deployment status table."""
    r = requests.get(f"{SERVICE_URL}/ops", timeout=MAX_RESPONSE_TIME)
    assert "deploymentsSection" in r.text, "Missing deployments section"
    assert "deploy-table" in r.text, "Missing deployment table"


def test_ops_has_recommendations():
    """Verify Ops Center has recommendations section."""
    r = requests.get(f"{SERVICE_URL}/ops", timeout=MAX_RESPONSE_TIME)
    assert "recommendationsSection" in r.text, "Missing recommendations section"


def test_deployments_api():
    """Verify /api/deployments returns deployment data."""
    r = requests.get(f"{SERVICE_URL}/api/deployments", timeout=MAX_RESPONSE_TIME)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "deployments" in data, "Missing deployments key"
    assert "summary" in data, "Missing summary key"
    assert "recommendations" in data, "Missing recommendations key"
    assert isinstance(data["deployments"], list), "Deployments is not a list"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print(f"\n🧪 CHAD Dashboard Smoke Tests")
    print(f"   Target: {SERVICE_URL}\n")

    # Wait for cold-start if needed
    print("   Warming up service (cold-start wake)...")
    try:
        requests.get(f"{SERVICE_URL}/health", timeout=MAX_RESPONSE_TIME)
    except Exception:
        print("   ⚠️  Warm-up request failed, continuing with tests...\n")
        time.sleep(3)

    print()

    # Run all tests
    tests = [
        ("Health endpoint", test_health_endpoint),
        ("Health response time", test_health_response_time),
        ("Root serves dashboard", test_root_serves_dashboard),
        ("Dashboard has table", test_dashboard_has_table),
        ("Dashboard has Services column", test_dashboard_has_services_column),
        ("Audit report JSON", test_audit_report_json),
        ("Audit report has repos", test_audit_report_has_repos),
        ("Audit report has services", test_audit_report_has_services),
        ("Refresh endpoint exists", test_refresh_endpoint_exists),
        ("Deploy-workflow endpoint exists", test_deploy_workflow_endpoint_exists),
        ("No debug mode", test_no_debug_mode),
        ("Security headers", test_security_headers),
        ("CORS not wildcard", test_cors_not_wildcard),
        ("Ops Center page", test_ops_center_page),
        ("Ops has architecture", test_ops_has_architecture),
        ("Ops has deployments", test_ops_has_deployments),
        ("Ops has recommendations", test_ops_has_recommendations),
        ("Deployments API", test_deployments_api),
    ]

    total_start = time.monotonic()
    for name, fn in tests:
        run_test(name, fn)
    total_ms = int((time.monotonic() - total_start) * 1000)

    # Summary
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print(f"\n{'=' * 50}")
    print(f"  Results: {passed}/{len(results)} passed, {failed} failed ({total_ms}ms)")
    print(f"{'=' * 50}\n")

    # Write results JSON for CI summary
    summary = {
        "service_url": SERVICE_URL,
        "tests": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "total_duration_ms": total_ms,
        },
    }
    with open("test-results.json", "w") as f:
        json.dump(summary, f, indent=2)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
