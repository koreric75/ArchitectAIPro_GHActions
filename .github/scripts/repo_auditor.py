#!/usr/bin/env python3
"""
BlueFalconInk LLC -- CHAD Repo Auditor Agent

Scans all repos under a GitHub org/user (and optional extra orgs) and produces
a structured audit report. Evaluates: branding compliance, staleness,
architecture status, secrets health, disk usage, branch hygiene, and generates
archive/delete recommendations.

Usage:
    python repo_auditor.py --owner koreric75 --extra-orgs bluefalconink --output docs/audit_report.json

Environment:
    GITHUB_TOKEN  -- GitHub personal access token or GH Actions token
    GEMINI_API_KEY -- (optional) for AI-assisted analysis
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
    "videogamedev", "Afterword", "BlueFalconInk",
}

# Branding strings to check for
BRAND_CORRECT = ["BlueFalconInk LLC", "BlueFalconInk", "bluefalconink"]
BRAND_INCORRECT = [
    "Blue Falcon RC & Media", "Blue Falcon RC and Media",
    "BlueFalcon RC & Media", "bluefalcon rc",
    "@BlueFalconRCandMedia",
]

# Staleness thresholds
STALE_DAYS = 180      # 6 months -> candidate for archive
DEAD_DAYS = 365 * 2   # 2 years -> candidate for deletion

# Token budget per audit run (prevents runaway API calls)
MAX_API_CALLS = 300
api_call_count = 0

# ---------------------------------------------------------------------------
# 3rd-Party Service Cost Map (monthly estimates per service)
# ---------------------------------------------------------------------------
# These represent typical free-tier or starter-plan costs.  The auditor
# detects service usage by scanning dependency files, Docker configs,
# and Terraform manifests for each repo.

THIRD_PARTY_SERVICE_COSTS = {
    # Backend / Database
    "supabase":      {"cost": 25, "label": "Supabase",      "category": "BaaS"},
    "firebase":      {"cost": 25, "label": "Firebase",       "category": "BaaS"},
    "planetscale":   {"cost": 29, "label": "PlanetScale",    "category": "Database"},
    "neon":          {"cost": 19, "label": "Neon Postgres",   "category": "Database"},
    "upstash":       {"cost":  5, "label": "Upstash Redis",   "category": "Cache"},
    "redis":         {"cost":  5, "label": "Redis Cloud",     "category": "Cache"},

    # Hosting / Edge
    "vercel":        {"cost": 20, "label": "Vercel",          "category": "Hosting"},
    "netlify":       {"cost": 19, "label": "Netlify",         "category": "Hosting"},
    "cloudflare":    {"cost":  5, "label": "Cloudflare",      "category": "CDN"},

    # Media / Video
    "mux":           {"cost": 20, "label": "Mux Video",       "category": "Media"},
    "cloudinary":    {"cost": 10, "label": "Cloudinary",      "category": "Media"},
    "imgix":         {"cost": 10, "label": "imgix",           "category": "Media"},

    # Payments / Commerce
    "stripe":        {"cost":  0, "label": "Stripe",          "category": "Payments"},

    # Auth
    "auth0":         {"cost":  0, "label": "Auth0",           "category": "Auth"},
    "clerk":         {"cost": 25, "label": "Clerk",           "category": "Auth"},

    # AI / ML
    "openai":        {"cost": 20, "label": "OpenAI API",      "category": "AI"},
    "anthropic":     {"cost": 20, "label": "Anthropic API",   "category": "AI"},
    "gemini":        {"cost":  0, "label": "Gemini API",      "category": "AI"},
    "replicate":     {"cost": 10, "label": "Replicate",       "category": "AI"},
    "huggingface":   {"cost": 10, "label": "Hugging Face",    "category": "AI"},

    # Monitoring / Observability
    "sentry":        {"cost":  0, "label": "Sentry",          "category": "Observability"},
    "datadog":       {"cost": 15, "label": "Datadog",         "category": "Observability"},

    # CI / CD
    "circleci":      {"cost": 15, "label": "CircleCI",        "category": "CI/CD"},

    # Email / Notifications
    "sendgrid":      {"cost":  0, "label": "SendGrid",        "category": "Email"},
    "resend":        {"cost":  0, "label": "Resend",          "category": "Email"},
    "twilio":        {"cost": 10, "label": "Twilio",          "category": "Communications"},

    # Music / Audio
    "suno":          {"cost": 10, "label": "Suno API",        "category": "Audio"},
}

# Patterns that indicate a service (case-insensitive substring matches)
# Searched across: package.json, requirements.txt, pyproject.toml,
#   docker-compose*.yml, Dockerfile, terraform/*.tf, .env.example
SERVICE_DETECTION_PATTERNS = {
    "supabase":    ["@supabase/", "supabase-py", "supabase-js", "supabase.co"],
    "firebase":    ["firebase-admin", "@firebase/", "firebaseConfig", "google-cloud-firestore"],
    "planetscale": ["@planetscale/", "planetscale"],
    "neon":        ["@neondatabase/", "neon.tech"],
    "upstash":     ["@upstash/", "upstash-redis"],
    "redis":       ["redis", "ioredis", "aioredis", "redis-py"],
    "vercel":      ["@vercel/", "vercel.json", "VERCEL_", "vercel.app"],
    "netlify":     ["netlify.toml", "netlify-cli", "NETLIFY_"],
    "cloudflare":  ["cloudflare", "wrangler", "CLOUDFLARE_"],
    "mux":         ["@mux/", "mux-python", "mux.com", "MUX_TOKEN"],
    "cloudinary":  ["cloudinary", "CLOUDINARY_"],
    "imgix":       ["imgix"],
    "stripe":      ["stripe", "@stripe/", "STRIPE_"],
    "auth0":       ["@auth0/", "auth0-python", "AUTH0_"],
    "clerk":       ["@clerk/", "CLERK_"],
    "openai":      ["openai", "OPENAI_API_KEY"],
    "anthropic":   ["anthropic", "ANTHROPIC_API_KEY"],
    "gemini":      ["gemini", "GEMINI_API_KEY", "google-generativeai", "@google/generative-ai"],
    "replicate":   ["replicate", "REPLICATE_"],
    "huggingface": ["huggingface", "transformers", "huggingface_hub"],
    "sentry":      ["@sentry/", "sentry-sdk", "SENTRY_DSN"],
    "datadog":     ["datadog", "ddtrace"],
    "circleci":    [".circleci"],
    "sendgrid":    ["sendgrid", "@sendgrid/", "SENDGRID_"],
    "resend":      ["resend"],
    "twilio":      ["twilio", "TWILIO_"],
    "suno":        ["suno"],
}

# Cloud Run scale-to-zero base cost (per repo with active Cloud Run service)
CLOUD_RUN_IDLE_BASE = 0      # $0/mo when scaled to zero
CLOUD_RUN_ACTIVE_BASE = 3    # ~$3/mo for occasional cold starts / minimum activity
GH_ACTIONS_CI_BASE = 0       # Free tier for public repos, ~$0 for private (2000 min/mo)


def _check(val):
    """Return a check/cross label for boolean values."""
    return "[OK]" if val else "[X]"


def api_get(url: str, token: str, params: dict = None) -> Optional[dict]:
    """Make an authenticated GitHub API GET request with budget tracking."""
    global api_call_count
    api_call_count += 1
    if api_call_count > MAX_API_CALLS:
        print(f"[WARN] API budget exhausted ({MAX_API_CALLS} calls). Stopping.")
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
            print(f"  [WARN] API {resp.status_code} for {url}")
            return None
    except Exception as e:
        print(f"  [WARN] API error: {e}")
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


def detect_third_party_services(owner: str, repo_name: str, token: str,
                                  default_branch: str) -> dict:
    """Detect 3rd-party services by scanning dependency/config files.

    Returns a dict with:
      - services: list of detected service keys
      - service_details: list of {service, label, cost, category}
      - third_party_cost: total estimated monthly 3rd-party cost
    """
    scan_files = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Dockerfile",
        ".env.example",
        ".env.sample",
        "vercel.json",
        "netlify.toml",
        "wrangler.toml",
    ]
    # Also scan terraform directory
    tf_files = []
    tf_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/contents/terraform?ref={default_branch}"
    tf_listing = api_get(tf_url, token)
    if tf_listing and isinstance(tf_listing, list):
        for f in tf_listing:
            if f.get("name", "").endswith(".tf"):
                tf_files.append(f"terraform/{f['name']}")

    all_files = scan_files + tf_files

    # Collect all file content into a single search corpus
    corpus = ""
    for fpath in all_files:
        url = f"{GITHUB_API}/repos/{owner}/{repo_name}/contents/{fpath}?ref={default_branch}"
        content = api_get_text(url, token)
        if content:
            corpus += "\n" + content

    if not corpus:
        return {"services": [], "service_details": [], "third_party_cost": 0}

    corpus_lower = corpus.lower()
    detected = {}  # service_key -> True

    for svc_key, patterns in SERVICE_DETECTION_PATTERNS.items():
        for pat in patterns:
            if pat.lower() in corpus_lower:
                detected[svc_key] = True
                break

    # Build detailed breakdown
    details = []
    total_cost = 0
    for svc_key in sorted(detected.keys()):
        info = THIRD_PARTY_SERVICE_COSTS.get(svc_key, {})
        cost = info.get("cost", 0)
        details.append({
            "service": svc_key,
            "label": info.get("label", svc_key),
            "cost": cost,
            "category": info.get("category", "Other"),
        })
        total_cost += cost

    return {
        "services": sorted(detected.keys()),
        "service_details": details,
        "third_party_cost": total_cost,
    }


def classify_repo(repo: dict, staleness: dict, services: dict = None) -> dict:
    """Generate classification, action recommendation, and burn rate.

    Burn rate model:
      - Cloud Run scale-to-zero: $0–$3/mo base (idle vs. occasional activity)
      - GH Actions CI: $0 (free tier)
      - 3rd-party services: detected dynamically from dependency files
      - Storage: negligible for repo-level Git storage
    """
    name = repo["name"]
    is_fork = repo.get("fork", repo.get("isFork", False))
    is_archived = repo.get("archived", repo.get("isArchived", False))
    disk_kb = repo.get("size", repo.get("diskUsage", 0))
    services = services or {}

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

    # ------------------------------------------------------------------
    # Burn-rate estimation  (Cloud Run scale-to-zero aware)
    # ------------------------------------------------------------------
    burn_breakdown = {}

    if tier in ("CORE", "ACTIVE", "DORMANT"):
        # Cloud Run: scale-to-zero means essentially free for idle services.
        # ACTIVE/CORE repos with recent pushes get a small baseline for
        # cold-start invocations and artifact registry storage.
        if staleness["days_since_push"] < 30:
            burn_breakdown["Cloud Run"] = CLOUD_RUN_ACTIVE_BASE
        else:
            burn_breakdown["Cloud Run"] = CLOUD_RUN_IDLE_BASE

        # CI minutes (GitHub Actions free tier covers most usage)
        burn_breakdown["CI/CD"] = GH_ACTIONS_CI_BASE

        # 3rd-party services — actual detected costs
        third_party = services.get("third_party_cost", 0)
        svc_details = services.get("service_details", [])
        for svc in svc_details:
            if svc["cost"] > 0:
                burn_breakdown[svc["label"]] = svc["cost"]
            # $0 services tracked but not added to burn
    else:
        # Archived / Dead / Stale / Forks incur $0
        pass

    monthly_burn = sum(burn_breakdown.values())

    return {
        "tier": tier,
        "action": action,
        "monthly_burn_estimate": monthly_burn,
        "burn_breakdown": burn_breakdown,
        "disk_mb": round(disk_kb / 1024, 1),
    }


# ---------------------------------------------------------------------------
# Main Auditor
# ---------------------------------------------------------------------------

def run_audit(owner: str, token: str, extra_orgs: list = None) -> dict:
    """Run full audit across all repos (primary owner + extra orgs)."""
    owners_scanned = [owner] + (extra_orgs or [])
    print(f"[SCAN] CHAD Repo Auditor -- scanning {', '.join(owners_scanned)}...")
    print(f"   Budget: {MAX_API_CALLS} API calls max")

    # Fetch all repos from multiple endpoints and merge (dedup by owner/name).
    seen = {}  # key: "owner/name" to handle cross-org repos

    # 1) Authenticated endpoint -- private + owned repos for primary owner
    page = 1
    while True:
        url = f"{GITHUB_API}/user/repos"
        params = {"per_page": 100, "page": page, "affiliation": "owner", "sort": "pushed"}
        batch = api_get(url, token, params)
        if not batch:
            break
        for r in batch:
            repo_login = r.get("owner", {}).get("login", "")
            if repo_login.lower() == owner.lower():
                key = f"{repo_login}/{r['name']}"
                seen[key] = r
        if len(batch) < 100:
            break
        page += 1

    # 2) Public endpoint for primary owner -- catches forks and public repos
    page = 1
    while True:
        url = f"{GITHUB_API}/users/{owner}/repos"
        params = {"per_page": 100, "page": page, "type": "all"}
        batch = api_get(url, token, params)
        if not batch:
            break
        for r in batch:
            repo_login = r.get("owner", {}).get("login", owner)
            key = f"{repo_login}/{r['name']}"
            if key not in seen:
                seen[key] = r
        if len(batch) < 100:
            break
        page += 1

    # 3) Extra orgs -- scan via /orgs/{org}/repos endpoint
    for org in (extra_orgs or []):
        print(f"\n[ORG] Scanning org: {org}")
        page = 1
        while True:
            url = f"{GITHUB_API}/orgs/{org}/repos"
            params = {"per_page": 100, "page": page, "type": "all"}
            batch = api_get(url, token, params)
            if not batch:
                break
            for r in batch:
                repo_login = r.get("owner", {}).get("login", org)
                key = f"{repo_login}/{r['name']}"
                if key not in seen:
                    seen[key] = r
            if len(batch) < 100:
                break
            page += 1

    repos = list(seen.values())

    print(f"   Found {len(repos)} repos across {', '.join(owners_scanned)}")

    audit_results = []
    summary = {
        "total_repos": len(repos),
        "owners_scanned": owners_scanned,
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
        repo_owner = repo.get("owner", {}).get("login", owner)
        default_branch = repo.get("default_branch", "main")
        pushed_at = repo.get("pushed_at", "2000-01-01T00:00:00Z")
        print(f"\n[REPO] Auditing: {repo_owner}/{name}")

        # Staleness
        staleness = audit_staleness(pushed_at)
        print(f"   [DATE] {staleness['status']} ({staleness['days_since_push']}d)")

        # Deep audit for active/core repos only (budget conservation)
        branding = {"compliant": True, "issues": [], "files_checked": 0}
        architecture = {"fully_configured": False, "has_workflow": False, "files": {}}
        secrets = {"has_gemini_key": False}
        workflows = {"health": "UNKNOWN", "recent_runs": []}
        services = {"services": [], "service_details": [], "third_party_cost": 0}

        # Preliminary classification (without services) to decide scan depth
        pre_class = classify_repo(repo, staleness)

        if pre_class["tier"] in ("CORE", "ACTIVE", "DORMANT"):
            branding = audit_branding(repo_owner, name, token, default_branch)
            if branding["issues"]:
                print(f"   [WARN] Branding issues: {len(branding['issues'])}")

            architecture = audit_architecture(repo_owner, name, token, default_branch)
            secrets = audit_secrets(repo_owner, name, token)
            workflows = audit_workflows(repo_owner, name, token)

            # Detect 3rd-party service dependencies for burn rate
            services = detect_third_party_services(repo_owner, name, token, default_branch)
            if services["services"]:
                print(f"   [SVC] 3rd-party: {', '.join(services['services'])} (${services['third_party_cost']}/mo)")

            arch_icon = _check(architecture["fully_configured"])
            key_icon = _check(secrets["has_gemini_key"])
            print(f"   [ARCH] Architecture: {arch_icon}")
            print(f"   [KEY] GEMINI_API_KEY: {key_icon}")
            print(f"   [FLOW] Workflows: {workflows.get('health', 'N/A')}")

        # Final classification with service cost data
        classification = classify_repo(repo, staleness, services)
        print(f"   [TAG] {classification['tier']} -> {classification['action']} (${classification['monthly_burn_estimate']}/mo)")

        result = {
            "name": name,
            "owner": repo_owner,
            "full_name": f"{repo_owner}/{name}",
            "description": repo.get("description", "") or "",
            "url": repo.get("html_url", f"https://github.com/{repo_owner}/{name}"),
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
            "services": services,
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
            summary["delete_candidates"].append(f"{repo_owner}/{name}")
        elif classification["action"] in ("ARCHIVE", "ARCHIVE_OR_DELETE"):
            summary["archive_candidates"].append(f"{repo_owner}/{name}")

        if branding["issues"]:
            summary["branding_issues"].append({
                "repo": f"{repo_owner}/{name}",
                "count": len(branding["issues"]),
                "details": branding["issues"],
            })

        summary["total_disk_mb"] += classification["disk_mb"]
        summary["total_monthly_burn"] += classification["monthly_burn_estimate"]

    report = {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "owner": owner,
        "owners": owners_scanned,
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
    print(f"[STATS] CHAD Audit Complete -- {', '.join(owners_scanned)}")
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
    parser.add_argument("--extra-orgs", default="", help="Comma-separated list of additional GitHub orgs to scan")
    parser.add_argument("--output", default="docs/audit_report.json", help="Output JSON path")
    args = parser.parse_args()

    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        print("[ERROR] GITHUB_TOKEN not set")
        sys.exit(1)

    extra_orgs = [o.strip() for o in args.extra_orgs.split(",") if o.strip()] if args.extra_orgs else []
    report = run_audit(args.owner, token, extra_orgs=extra_orgs)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n[FILE] Report written to {args.output}")


if __name__ == "__main__":
    main()
