"""
BlueFalconInk Architecture Gallery

A FastAPI application that fetches and renders Mermaid.js architecture
diagrams from across all BlueFalconInk GitHub repositories.

Deployed on Google Cloud Run at https://arch.bluefalconink.com
"""

import os
import base64
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(
    title="BlueFalconInk Architecture Gallery",
    description="Centralized architecture diagram viewer for all BlueFalconInk flagships",
    version="1.0.0",
)

# Configuration from Environment Variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ORG = os.getenv("GITHUB_ORG", "bluefalconink")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

templates = Jinja2Templates(directory="templates")

# Simple in-memory cache to avoid GitHub rate limits
_cache: dict = {}
CACHE_TTL = timedelta(minutes=10)


def _get_cached(key: str) -> Optional[dict]:
    """Retrieve a cached value if it hasn't expired."""
    if key in _cache:
        entry = _cache[key]
        if datetime.utcnow() - entry["timestamp"] < CACHE_TTL:
            return entry["data"]
        del _cache[key]
    return None


def _set_cached(key: str, data):
    """Store a value in cache."""
    _cache[key] = {"data": data, "timestamp": datetime.utcnow()}


async def get_repos() -> list:
    """Fetch all repositories for the organization."""
    cached = _get_cached("repos")
    if cached is not None:
        return cached

    url = f"https://api.github.com/orgs/{GITHUB_ORG}/repos"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS, params={"per_page": 100})
        if response.status_code == 200:
            repos = response.json()
            _set_cached("repos", repos)
            return repos
    return []


async def get_file_content(repo_name: str, path: str) -> Optional[str]:
    """Fetch a file's content from a GitHub repository."""
    cache_key = f"{repo_name}/{path}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}/contents/{path}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS)
        if response.status_code == 200:
            content_b64 = response.json().get("content", "")
            content = base64.b64decode(content_b64).decode("utf-8")
            _set_cached(cache_key, content)
            return content
    return None


async def get_last_commit_date(repo_name: str) -> Optional[str]:
    """Get the last commit date for a repository."""
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}/commits"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS, params={"per_page": 1})
        if response.status_code == 200:
            commits = response.json()
            if commits:
                return commits[0]["commit"]["committer"]["date"][:10]
    return "Unknown"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the Architecture Gallery homepage."""
    repos = await get_repos()
    gallery_data = []

    for repo in repos:
        name = repo["name"]
        # Fetch the Mermaid diagram and the config
        diagram = await get_file_content(name, "docs/architecture.md")
        config = await get_file_content(name, "ARCHITECT_CONFIG.json")
        last_updated = await get_last_commit_date(name)

        status = "✅ Synced" if diagram else "❌ Missing"

        gallery_data.append(
            {
                "name": name,
                "description": repo.get("description", "No description provided."),
                "diagram": diagram,
                "config": config,
                "url": repo["html_url"],
                "status": status,
                "last_updated": last_updated,
                "language": repo.get("language", "N/A"),
            }
        )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "repos": gallery_data,
            "org": GITHUB_ORG,
            "total": len(gallery_data),
            "synced": sum(1 for r in gallery_data if r["diagram"]),
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy", "org": GITHUB_ORG, "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/repos")
async def api_repos():
    """JSON API endpoint for repo data."""
    repos = await get_repos()
    return {
        "org": GITHUB_ORG,
        "count": len(repos),
        "repos": [
            {"name": r["name"], "url": r["html_url"], "language": r.get("language")}
            for r in repos
        ],
    }
