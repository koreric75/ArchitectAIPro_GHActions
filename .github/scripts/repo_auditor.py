#!/usr/bin/env python3
"""
BlueFalconInk LLC — CHAD Repo Auditor Agent

Scans all repos under a GitHub org/user and produces a structured audit report.
Evaluates: branding compliance, staleness, architecture status, secrets health,
disk usage, branch hygiene, and generates archive/delete recommendations.

Usage:
    python repo_auditor.py --owner koreric75 --output docs/audit_report.json

Environment:
    GITHUB_TOKEN  — GitHub personal access token or GH Actions token
    GEMINI_API_KEY — (optional) for AI-assisted analysis
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
ORG_NAME = "BlueFalconInk LLC"

# Repos that are core to BlueFalconInk LLC operations
CORE_REPOS = {
    "ArchitectAIPro", "ArchitectAIPro_GHActions", "clipstream",
    "ProposalBuddyAI", "polymath-hub", "BlueFalconInkLanding",
    "videogamedev", "Afterword",
}

# Branding strings to check for
BRAND_CORRECT = ["BlueFalconInk LLC", "BlueFalconInk", "bluefalconink"]
BRAND_INCORRECT = [
    "Blue Falcon RC & Media", "Blue Falcon RC and Media",
    "BlueFalcon RC & Media", "bluefalcon rc",
    "@BlueFalconRCandMedia",
]

# Staleness thresholds
STALE_DAYS = 180      # 6 months → candidate for archive
DEAD_DAYS = 365 * 2   # 2 years → candidate for deletion

# Token budget per audit run (prevents runaway API calls)
MAX_API_CALLS = 300
api_call_count = 0


def api_get(url: str, token: str, params: dict = None) -> Optional[dict]:
    """Make an authenticated GitHub API GET request with budget tracking."""
    global api_call_count
    api_call_count += 1
    if api_call_count > MAX_API_CALLS:
        print(f"⚠️  API budget exhausted ({MAX_API_CALLS} calls). Stopping.")
        return None

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return None
        else:
            print(f"  ⚠️  API {resp.status_code} for {url}")
            return None
    except Exception as e:
        print(f"  ⚠️  API error: {e}")
        return None


def api_get_text(url: str, token: str) -> Optional[str]:
    """Fetch raw file content from GitHub."""
    global api_call_count
    api_call_count += 1
    if api_call_count > MAX_API_CALLS:
        return None

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.raw",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Audit Functions
# ---------------------------------------------------------------------------

def audit_staleness(pushed_at: str) -> dict:
    """Evaluate how stale a repo is."""
    last_push = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    days_since = (now - last_push).days

    if days_since > DEAD_DAYS:
        status = "DEAD"
        recommendation = "DELETE or ARCHIVE"
    elif days_since > STALE_DAYS:
        status = "STALE"
        recommendation = "ARCHIVE"
    elif days_since > 90:
        status = "DORMANT"
        recommendation = "REVIEW"
    else:
        status = "ACTIVE"
        recommendation = "KEEP"

    return {
        "last_push": pushed_at,
        "days_since_push": days_since,
        "status": status,
        "recommendation": recommendation,
    }


def audit_branding(owner: str, repo_name: str, token: str, default_branch: str) -> dict:
    """Check key files for branding compliance."""
    files_to_check = ["README.md", "package.json", "pyproject.toml", "LICENSE",
                      "ARCHITECT_CONFIG.json"]
    issues = []
    files_checked = 0

    for fname in files_to_check:
        url = f"{GITHUB_API}/repos/{owner}/{repo_name}/contents/{fname}?ref={default_branch}"
        content = api_get_text(url, token)
        if content is None:
            continue

        files_checked += 1
        for bad in BRAND_INCORRECT:
            if bad.lower() in content.lower():
                issues.append({
                    "file": fname,
                    "found": bad,
                    "fix": f"Replace '{bad}' with 'BlueFalconInk LLC'",
                })

    has_branding = any(
        b.lower() in (content or "").lower()
        for b in BRAND_CORRECT
    ) if files_checked > 0 else False

    return {
        "files_checked": files_checked,
        "issues": issues,
        "compliant": len(issues) == 0,
        "has_branding": has_branding,
    }


def audit_architecture(owner: str, repo_name: str, token: str, default_branch: str) -> dict:
    """Check if architecture diagram files exist."""
    arch_files = {
        "docs/architecture.md": False,
        "docs/architecture.mermaid": False,
        "docs/architecture.png": False,
        "docs/architecture.drawio": False,
        "ARCHITECT_CONFIG.json": False,
    }

    for fpath in arch_files:
        url = f"{GITHUB_API}/repos/{owner}/{repo_name}/contents/{fpath}?ref={default_branch}"
        result = api_get(url, token)
        if result:
            arch_files[fpath] = True

    has_workflow = False
    url = f"{GITHUB_API}/repos/{owner}/{repo_name}/contents/.github/workflows?ref={default_branch}"
    workflows = api_get(url, token)
    if workflows and isinstance(workflows, list):
        for wf in workflows:
            if "architecture" in wf.get("name", "").lower():
                has_workflow = True
                break

    return {
        "files": arch_files,
        "has_workflow": has_workflow,
        "fully_configured": all(arch_files.values()) and has_workflow,
    }


def audit_secrets(owner: str, repo_name: str, token: str) -> dict:
    """Check if required secrets are configured."""
    url = f"{GITHUB_API}/repos/{owner}/{repo_name}/actions/secrets"
    result = api_get(url, token)

    secret_names = []
    if result and "secrets" in result:
        secret_names = [s["name"] for s in result["secrets"]]

    return {
        "secrets": secret_names,
        "has_gemini_key": "GEMINI_API_KEY" in secret_names,
        "has_gcp_creds": any("GCP" in s or "GOOGLE" in s for s in secret_names),
    }


def audit_workflows(owner: str, repo_name: str, token: str) -> dict:
    """Check recent workflow run status."""
    url = f"{GITHUB_API}/repos/{owner}/{repo_name}/actions/runs"
    result = api_get(url, token, params={"per_page": 5})

    if not result or "workflow_runs" not in result:
        return {"total_runs": 0, "recent_runs": []}

    runs = []
    for run in result["workflow_runs"][:5]:
        runs.append({
            "name": run.get("name", ""),
            "status": run.get("status", ""),
            "conclusion": run.get("conclusion", ""),
            "created_at": run.get("created_at", ""),
        })

    failing = sum(1 for r in runs if r["conclusion"] == "failure")

    return {
        "total_runs": result.get("total_count", 0),
        "recent_runs": runs,
        "recent_failures": failing,
        "health": "HEALTHY" if failing == 0 else "DEGRADED" if failing < 3 else "FAILING",
    }


def classify_repo(repo: dict, staleness: dict) -> dict:
    """Generate classification and action recommendation."""
    name = repo["name"]
    is_fork = repo.get("isFork", False)
    is_archived = repo.get("isArchived", False)
    disk_kb = repo.get("diskUsage", 0)

    # Priority classification
    if is_archived:
        tier = "ARCHIVED"
        action = "NONE"
    elif name in CORE_REPOS:
        tier = "CORE"
        action = "MAINTAIN"
    elif is_fork and staleness["status"] in ("DEAD", "STALE"):
        tier = "LEGACY_FORK"
        action = "DELETE"
    elif is_fork:
        tier = "FORK"
        action = "REVIEW"
    elif staleness["status"] == "DEAD":
        tier = "DEAD"
        action = "ARCHIVE_OR_DELETE"
    elif staleness["status"] == "STALE":
        tier = "STALE"
        action = "ARCHIVE"
    elif staleness["status"] == "DORMANT":
        tier = "DORMANT"
        action = "REVIEW"
    else:
        tier = "ACTIVE"
        action = "MAINTAIN"

    # Cost estimation (simplified GCP-aware)
    monthly_burn = 0
    if tier in ("CORE", "ACTIVE"):
        if disk_kb > 10000:
            monthly_burn = 45  # Storage-heavy
        elif disk_kb > 1000:
            monthly_burn = 25
        else:
            monthly_burn = 10
        # Core products get higher burn estimates (CI, hosting, API calls)
        if name in ("ArchitectAIPro", "clipstream", "ProposalBuddyAI", "polymath-hub"):
            monthly_burn += 85

    return {
        "tier": tier,
        "action": action,
        "monthly_burn_estimate": monthly_burn,
        "disk_mb": round(disk_kb / 1024, 1),
    }


# ---------------------------------------------------------------------------
# Main Auditor
# ---------------------------------------------------------------------------

def run_audit(owner: str, token: str) -> dict:
    """Run full audit across all repos."""
    print(f"🔍 CHAD Repo Auditor — scanning {owner}...")
    print(f"   Budget: {MAX_API_CALLS} API calls max")

    # Fetch all repos (use /user/repos for authenticated access to private repos,
    # fall back to /users/{owner}/repos for public-only)
    repos = []
    page = 1
    while True:
        # Try authenticated endpoint first (includes private repos)
        url = f"{GITHUB_API}/user/repos"
        params = {"per_page": 100, "page": page, "affiliation": "owner", "sort": "pushed"}
        batch = api_get(url, token, params)
        if not batch:
            # Fallback to public endpoint
            url = f"{GITHUB_API}/users/{owner}/repos"
            params = {"per_page": 100, "page": page, "type": "all"}
            batch = api_get(url, token, params)
        if not batch:
            break
        # Filter to only repos owned by the target owner
        batch = [r for r in batch if r.get("owner", {}).get("login", "").lower() == owner.lower()]
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    print(f"   Found {len(repos)} repos")

    audit_results = []
    summary = {
        "total_repos": len(repos),
        "core": 0, "active": 0, "stale": 0, "dead": 0,
        "forks": 0, "archived": 0,
        "delete_candidates": [],
        "archive_candidates": [],
        "branding_issues": [],
        "total_disk_mb": 0,
        "total_monthly_burn": 0,
    }

    for repo in repos:
        name = repo["name"]
        default_branch = repo.get("default_branch", "main")
        pushed_at = repo.get("pushed_at", "2000-01-01T00:00:00Z")
        print(f"\n📦 Auditing: {name}")

        # Staleness
        staleness = audit_staleness(pushed_at)
        print(f"   📅 {staleness['status']} ({staleness['days_since_push']}d)")

        # Classification
        classification = classify_repo(repo, staleness)
        print(f"   🏷️  {classification['tier']} → {classification['action']}")

        # Deep audit for active/core repos only (budget conservation)
        branding = {"compliant": True, "issues": [], "files_checked": 0}
        architecture = {"fully_configured": False, "has_workflow": False, "files": {}}
        secrets = {"has_gemini_key": False}
        workflows = {"health": "UNKNOWN", "recent_runs": []}

        if classification["tier"] in ("CORE", "ACTIVE", "DORMANT"):
            branding = audit_branding(owner, name, token, default_branch)
            if branding["issues"]:
                print(f"   ⚠️  Branding issues: {len(branding['issues'])}")

            architecture = audit_architecture(owner, name, token, default_branch)
            secrets = audit_secrets(owner, name, token)
            workflows = audit_workflows(owner, name, token)
            print(f"   🏗️  Architecture: {'✅' if architecture['fully_configured'] else '❌'}")
            print(f"   🔑 GEMINI_API_KEY: {'✅' if secrets['has_gemini_key'] else '❌'}")
            print(f"   🔄 Workflows: {workflows.get('health', 'N/A')}")

        result = {
            "name": name,
            "description": repo.get("description", "") or "",
            "url": repo.get("html_url", f"https://github.com/{owner}/{name}"),
            "is_private": repo.get("private", False),
            "is_fork": repo.get("fork", False),
            "is_archived": repo.get("archived", False),
            "language": (repo.get("language") or "None"),
            "default_branch": default_branch,
            "disk_usage_kb": repo.get("diskUsage", repo.get("size", 0)),
            "staleness": staleness,
            "classification": classification,
            "branding": branding,
            "architecture": architecture,
            "secrets": secrets,
            "workflows": workflows,
        }

        audit_results.append(result)

        # Update summary
        tier = classification["tier"]
        if tier == "CORE":
            summary["core"] += 1
        elif tier == "ACTIVE":
            summary["active"] += 1
        elif tier in ("STALE", "DORMANT"):
            summary["stale"] += 1
        elif tier in ("DEAD", "LEGACY_FORK"):
            summary["dead"] += 1

        if repo.get("fork", False):
            summary["forks"] += 1
        if repo.get("archived", False):
            summary["archived"] += 1

        if classification["action"] == "DELETE":
            summary["delete_candidates"].append(name)
        elif classification["action"] in ("ARCHIVE", "ARCHIVE_OR_DELETE"):
            summary["archive_candidates"].append(name)

        if branding["issues"]:
            summary["branding_issues"].append({
                "repo": name,
                "count": len(branding["issues"]),
                "details": branding["issues"],
            })

        summary["total_disk_mb"] += classification["disk_mb"]
        summary["total_monthly_burn"] += classification["monthly_burn_estimate"]

    report = {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "owner": owner,
        "org_name": ORG_NAME,
        "api_calls_used": api_call_count,
        "summary": summary,
        "repos": sorted(audit_results, key=lambda r: (
            {"CORE": 0, "ACTIVE": 1, "DORMANT": 2, "STALE": 3, "DEAD": 4,
             "LEGACY_FORK": 5, "FORK": 6, "ARCHIVED": 7}.get(r["classification"]["tier"], 9),
            r["name"],
        )),
    }

    print(f"\n{'='*60}")
    print(f"📊 CHAD Audit Complete")
    print(f"   Repos: {summary['total_repos']}")
    print(f"   Core: {summary['core']} | Active: {summary['active']} | Stale: {summary['stale']} | Dead: {summary['dead']}")
    print(f"   Forks: {summary['forks']} | Archived: {summary['archived']}")
    print(f"   Delete candidates: {summary['delete_candidates']}")
    print(f"   Archive candidates: {summary['archive_candidates']}")
    print(f"   Branding issues: {len(summary['branding_issues'])} repos")
    print(f"   Total disk: {summary['total_disk_mb']:.1f} MB")
    print(f"   Est. monthly burn: ${summary['total_monthly_burn']}")
    print(f"   API calls used: {api_call_count}/{MAX_API_CALLS}")

    return report


def main():
    parser = argparse.ArgumentParser(description="CHAD Repo Auditor")
    parser.add_argument("--owner", required=True, help="GitHub username or org")
    parser.add_argument("--output", default="docs/audit_report.json", help="Output JSON path")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN not set")
        sys.exit(1)

    report = run_audit(args.owner, token)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n📄 Report written to {args.output}")


if __name__ == "__main__":
    main()
