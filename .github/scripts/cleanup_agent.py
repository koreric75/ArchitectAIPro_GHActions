#!/usr/bin/env python3
"""
BlueFalconInk LLC — CHAD Cleanup Agent

Executes automated cleanup actions on GitHub repos:
- Archive stale/dead repos
- Delete old forks (with confirmation)
- Fix branding across repos (BlueFalconInk LLC)
- Standardize ARCHITECT_CONFIG.json
- Deploy architecture workflow to unconfigured repos

Usage:
    python cleanup_agent.py --owner koreric75 --report docs/audit_report.json [--dry-run] [--action archive|brand|deploy]

Environment:
    GITHUB_TOKEN  — GitHub personal access token with repo/workflow/delete scope
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

GITHUB_API = "https://api.github.com"

# Standard branding
BRAND_MAP = {
    "Blue Falcon RC & Media": "BlueFalconInk LLC",
    "Blue Falcon RC and Media": "BlueFalconInk LLC",
    "BlueFalcon RC & Media": "BlueFalconInk LLC",
    "@BlueFalconRCandMedia": "BlueFalconInk LLC",
}

# Standard ARCHITECT_CONFIG
STANDARD_CONFIG = {
    "org_name": "BlueFalconInk LLC",
    "preferred_cloud": "GCP",
    "container_orchestration": "Cloud Run",
    "ci_cd": "GitHub Actions",
    "iac_tool": "Terraform",
    "database_defaults": {
        "relational": "Cloud SQL (PostgreSQL)",
        "document": "Firestore",
        "cache": "Cloud Memorystore"
    },
    "monitoring": "Cloud Monitoring + Cloud Logging",
    "secrets_management": "GitHub Secrets + Secret Manager",
    "ai_provider": "Google Gemini API"
}


class CleanupAgent:
    def __init__(self, owner: str, token: str, dry_run: bool = True):
        self.owner = owner
        self.token = token
        self.dry_run = dry_run
        self.actions_taken = []
        self.errors = []

    def _headers(self, raw=False):
        h = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        if raw:
            h["Accept"] = "application/vnd.github.v3.raw"
        return h

    def log(self, msg: str):
        prefix = "[DRY-RUN] " if self.dry_run else "[EXEC] "
        print(f"{prefix}{msg}")
        self.actions_taken.append({"action": msg, "dry_run": self.dry_run, "time": datetime.now(timezone.utc).isoformat()})

    def archive_repo(self, repo_name: str) -> bool:
        """Archive a repository."""
        self.log(f"📦 Archive: {repo_name}")
        if self.dry_run:
            return True
        resp = requests.patch(
            f"{GITHUB_API}/repos/{self.owner}/{repo_name}",
            headers=self._headers(),
            json={"archived": True},
            timeout=30,
        )
        if resp.status_code == 200:
            self.log(f"  ✅ Archived {repo_name}")
            return True
        else:
            self.errors.append(f"Archive {repo_name}: {resp.status_code}")
            self.log(f"  ❌ Failed: {resp.status_code}")
            return False

    def fix_branding_in_file(self, repo_name: str, file_path: str, branch: str) -> bool:
        """Fix branding in a specific file."""
        # Get current content
        url = f"{GITHUB_API}/repos/{self.owner}/{repo_name}/contents/{file_path}?ref={branch}"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        if resp.status_code != 200:
            return False

        file_data = resp.json()
        content = base64.b64decode(file_data["content"]).decode("utf-8", errors="replace")
        original = content

        # Apply all branding fixes
        for old, new in BRAND_MAP.items():
            content = content.replace(old, new)

        if content == original:
            return False  # No changes needed

        self.log(f"🏷️  Fix branding: {repo_name}/{file_path}")
        if self.dry_run:
            return True

        # Update file
        resp = requests.put(
            f"{GITHUB_API}/repos/{self.owner}/{repo_name}/contents/{file_path}",
            headers=self._headers(),
            json={
                "message": f"fix: Update branding to BlueFalconInk LLC in {file_path}",
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "sha": file_data["sha"],
                "branch": branch,
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            self.log(f"  ✅ Updated {file_path}")
            return True
        else:
            self.errors.append(f"Brand fix {repo_name}/{file_path}: {resp.status_code}")
            return False

    def fix_branding(self, repo_name: str, branch: str) -> int:
        """Fix branding across all key files in a repo."""
        files = ["README.md", "package.json", "pyproject.toml", "LICENSE",
                 "ARCHITECT_CONFIG.json", "src/index.html", "index.html"]
        fixed = 0
        for f in files:
            if self.fix_branding_in_file(repo_name, f, branch):
                fixed += 1
        return fixed

    def deploy_config(self, repo_name: str, branch: str, description: str = "") -> bool:
        """Deploy or update ARCHITECT_CONFIG.json to a repo."""
        config = STANDARD_CONFIG.copy()
        config["repo_name"] = repo_name
        config["description"] = description

        content_str = json.dumps(config, indent=2)
        encoded = base64.b64encode(content_str.encode("utf-8")).decode("ascii")

        self.log(f"⚙️  Deploy config: {repo_name}/ARCHITECT_CONFIG.json")
        if self.dry_run:
            return True

        # Check if file exists
        url = f"{GITHUB_API}/repos/{self.owner}/{repo_name}/contents/ARCHITECT_CONFIG.json?ref={branch}"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        sha = None
        if resp.status_code == 200:
            sha = resp.json()["sha"]

        payload = {
            "message": "chore: Standardize ARCHITECT_CONFIG.json",
            "content": encoded,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        resp = requests.put(
            f"{GITHUB_API}/repos/{self.owner}/{repo_name}/contents/ARCHITECT_CONFIG.json",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            self.log(f"  ✅ Config deployed")
            return True
        else:
            self.errors.append(f"Config {repo_name}: {resp.status_code}")
            return False

    def run_from_report(self, report: dict, actions: list[str]) -> dict:
        """Execute cleanup based on audit report."""
        repos = report.get("repos", [])
        summary = {"archived": 0, "branding_fixed": 0, "configs_deployed": 0, "errors": 0}

        for repo in repos:
            name = repo["name"]
            branch = repo.get("default_branch", "main")
            tier = repo["classification"]["tier"]
            action = repo["classification"]["action"]

            # Archive stale repos
            if "archive" in actions and action in ("ARCHIVE", "ARCHIVE_OR_DELETE"):
                if not repo.get("is_archived", False):
                    if self.archive_repo(name):
                        summary["archived"] += 1

            # Fix branding
            if "brand" in actions:
                if not repo.get("branding", {}).get("compliant", True):
                    fixed = self.fix_branding(name, branch)
                    summary["branding_fixed"] += fixed

            # Deploy configs
            if "deploy" in actions:
                if tier in ("CORE", "ACTIVE") and not repo.get("architecture", {}).get("files", {}).get("ARCHITECT_CONFIG.json", False):
                    if self.deploy_config(name, branch, repo.get("description", "")):
                        summary["configs_deployed"] += 1

        summary["errors"] = len(self.errors)
        summary["total_actions"] = len(self.actions_taken)
        return summary


def main():
    parser = argparse.ArgumentParser(description="CHAD Cleanup Agent")
    parser.add_argument("--owner", required=True, help="GitHub username")
    parser.add_argument("--report", required=True, help="Path to audit_report.json")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default)")
    parser.add_argument("--execute", action="store_true", help="Actually execute changes")
    parser.add_argument("--action", nargs="+", choices=["archive", "brand", "deploy", "all"],
                        default=["all"], help="Actions to perform")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN not set")
        sys.exit(1)

    report = json.loads(Path(args.report).read_text())
    dry_run = not args.execute

    if dry_run:
        print("🔍 DRY-RUN MODE — no changes will be made")
    else:
        print("⚡ EXECUTE MODE — changes will be applied!")

    actions = args.action
    if "all" in actions:
        actions = ["archive", "brand", "deploy"]

    agent = CleanupAgent(args.owner, token, dry_run=dry_run)
    summary = agent.run_from_report(report, actions)

    print(f"\n{'='*50}")
    print(f"📊 Cleanup Summary:")
    print(f"   Repos archived: {summary['archived']}")
    print(f"   Files brand-fixed: {summary['branding_fixed']}")
    print(f"   Configs deployed: {summary['configs_deployed']}")
    print(f"   Errors: {summary['errors']}")
    print(f"   Total actions: {summary['total_actions']}")

    if agent.errors:
        print(f"\n⚠️  Errors encountered:")
        for e in agent.errors:
            print(f"   - {e}")

    # Write action log
    log_path = Path("docs/cleanup_log.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "summary": summary,
        "actions": agent.actions_taken,
        "errors": agent.errors,
    }, indent=2))
    print(f"\n📄 Action log: {log_path}")


if __name__ == "__main__":
    main()
