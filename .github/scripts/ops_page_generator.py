#!/usr/bin/env python3
"""CHAD Ops Center — Architecture & Deployment Status Page Generator.

Generates a feature-rich ops page showing:
  1. BlueFalconInk LLC full architecture (Mermaid diagram, rendered client-side)
  2. Deployment / CI pipeline status for every repo
  3. AI-recommended actions for failing or unhealthy repos

Usage:
    python ops_page_generator.py --input docs/audit_report.json --output static/ops.html
"""

import argparse
import json
import sys
from pathlib import Path


def _health_color(health: str) -> str:
    return {
        "HEALTHY": "#22c55e",
        "DEGRADED": "#f59e0b",
        "FAILING": "#ef4444",
    }.get(health, "#64748b")


def _health_icon(health: str) -> str:
    return {
        "HEALTHY": "✅",
        "DEGRADED": "⚠️",
        "FAILING": "🔴",
    }.get(health, "❔")


def _severity_color(sev: str) -> str:
    return {
        "critical": "#ef4444",
        "warning": "#f59e0b",
        "info": "#3b82f6",
    }.get(sev, "#64748b")


def _severity_bg(sev: str) -> str:
    return {
        "critical": "rgba(239,68,68,0.08)",
        "warning": "rgba(245,158,11,0.08)",
        "info": "rgba(59,130,246,0.08)",
    }.get(sev, "rgba(100,116,139,0.08)")


def generate_ops_page(report: dict, mermaid_src: str = "") -> str:
    """Generate the full Ops Center HTML page."""
    repos = report.get("repos", [])
    owner = report.get("owner", "unknown")
    timestamp = report.get("audit_timestamp", "Unknown")
    summary = report.get("summary", {})

    # ── Deployment status table rows ──
    health_order = {"FAILING": 0, "DEGRADED": 1, "HEALTHY": 2, "UNKNOWN": 3}
    sorted_repos = sorted(repos, key=lambda r: (
        health_order.get(r.get("workflows", {}).get("health", "UNKNOWN"), 9),
        r.get("owner", owner),
        r["name"],
    ))

    deploy_rows = ""
    total_healthy = 0
    total_degraded = 0
    total_failing = 0
    total_no_ci = 0

    for r in sorted_repos:
        if r.get("is_archived", False):
            continue

        repo_owner = r.get("owner", owner)
        name = r["name"]
        full_name = f"{repo_owner}/{name}"
        url = r.get("url", f"https://github.com/{full_name}")
        tier = r.get("classification", {}).get("tier", "UNKNOWN")
        wf = r.get("workflows", {})
        health = wf.get("health", "UNKNOWN")
        recent_runs = wf.get("recent_runs", [])
        has_ci = len(recent_runs) > 0 or r.get("architecture", {}).get("has_workflow", False)
        days = r.get("staleness", {}).get("days_since_push", "?")

        if health == "HEALTHY":
            total_healthy += 1
        elif health == "DEGRADED":
            total_degraded += 1
        elif health == "FAILING":
            total_failing += 1
        if not has_ci:
            total_no_ci += 1

        # Build run indicators (dots)
        run_dots = ""
        for run in recent_runs[:5]:
            conclusion = run.get("conclusion", "")
            run_name = run.get("name", "workflow")
            if conclusion == "success":
                dot_color = "#22c55e"
                dot_title = f"{run_name}: success"
            elif conclusion == "failure":
                dot_color = "#ef4444"
                dot_title = f"{run_name}: failure"
            elif conclusion == "cancelled":
                dot_color = "#64748b"
                dot_title = f"{run_name}: cancelled"
            else:
                dot_color = "#f59e0b"
                dot_title = f"{run_name}: {run.get('status', 'unknown')}"
            run_dots += f'<span class="run-dot" style="background:{dot_color}" title="{dot_title}"></span>'

        if not run_dots:
            run_dots = '<span style="color:var(--text-muted);font-size:11px">No runs</span>'

        health_badge = f'<span class="health-badge" style="background:{_health_color(health)}20;color:{_health_color(health)};border:1px solid {_health_color(health)}40">{_health_icon(health)} {health}</span>'

        ci_badge = ""
        if not has_ci:
            ci_badge = '<span class="ci-badge no-ci">NO CI</span>'

        deploy_rows += f"""
        <tr class="deploy-row" data-health="{health}" data-tier="{tier}">
            <td>
                <a href="{url}" target="_blank" class="repo-link">{full_name}</a>
                <div class="repo-tier">{tier}</div>
            </td>
            <td>{health_badge} {ci_badge}</td>
            <td class="runs-cell">{run_dots}</td>
            <td class="num">{days}d</td>
            <td>
                <a href="{url}/actions" target="_blank" class="action-link">View Runs →</a>
            </td>
        </tr>"""

    total_active = total_healthy + total_degraded + total_failing

    # ── Recommendations ──
    recommendations = _build_recommendations(sorted_repos, report, owner)
    rec_cards = ""
    for rec in recommendations:
        sev = rec["severity"]
        repo_list = ""
        for rname in rec.get("repos", [])[:8]:
            repo_list += f'<div class="rec-repo">{rname}</div>'
        if len(rec.get("repos", [])) > 8:
            repo_list += f'<div class="rec-repo-more">+{len(rec["repos"]) - 8} more</div>'

        rec_cards += f"""
        <div class="rec-card" style="border-left:3px solid {_severity_color(sev)};background:{_severity_bg(sev)}">
            <div class="rec-header">
                <span class="rec-icon">{rec['icon']}</span>
                <span class="rec-title">{rec['title']}</span>
                <span class="rec-severity" style="color:{_severity_color(sev)}">{sev.upper()}</span>
            </div>
            <div class="rec-desc">{rec['description']}</div>
            <div class="rec-repos">{repo_list}</div>
            <div class="rec-action">💡 {rec['action']}</div>
        </div>"""

    if not rec_cards:
        rec_cards = '<div class="rec-card" style="border-left:3px solid #22c55e;background:rgba(34,197,94,0.08)"><div class="rec-header"><span class="rec-icon">🎉</span><span class="rec-title">All systems healthy!</span></div><div class="rec-desc">No critical issues detected across your infrastructure.</div></div>'

    # ── Mermaid diagram ──
    # Escape for embedding in JS string
    mermaid_escaped = mermaid_src.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CHAD Ops Center — BlueFalconInk LLC</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
:root {{
    --bg-primary: #020617;
    --bg-secondary: #0f172a;
    --bg-card: #1e293b;
    --bg-card-hover: #334155;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-blue: #3b82f6;
    --accent-green: #22c55e;
    --accent-amber: #f59e0b;
    --accent-red: #ef4444;
    --accent-purple: #8b5cf6;
    --border: #1e293b;
    --font-main: 'Space Grotesk', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', 'Cascadia Code', monospace;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-main);
    line-height: 1.6;
    min-height: 100vh;
}}
.container {{ max-width: 1600px; margin: 0 auto; padding: 24px; }}

/* Navigation */
.nav-bar {{
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 16px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
}}
.nav-brand {{
    font-size: 20px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-decoration: none;
}}
.nav-links {{ display: flex; gap: 4px; }}
.nav-link {{
    padding: 8px 16px;
    border-radius: 8px;
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s;
}}
.nav-link:hover {{ background: var(--bg-card); color: var(--text-primary); }}
.nav-link.active {{
    background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(139,92,246,0.15));
    color: var(--accent-blue);
    border: 1px solid rgba(59,130,246,0.2);
}}
.nav-right {{
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 12px;
}}
.nav-timestamp {{ font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }}

/* Page Header */
.page-header {{
    margin-bottom: 32px;
}}
.page-header h1 {{
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 8px;
}}
.page-header .subtitle {{
    color: var(--text-secondary);
    font-size: 14px;
}}

/* Status Cards */
.status-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}}
.status-card {{
    background: var(--bg-card);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--border);
    text-align: center;
}}
.status-card .stat-number {{
    font-size: 36px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1;
    margin-bottom: 4px;
}}
.status-card .stat-label {{
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* Sections */
.section {{
    margin-bottom: 40px;
}}
.section-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}}
.section-title {{
    font-size: 20px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.section-subtitle {{
    font-size: 13px;
    color: var(--text-muted);
}}

/* Architecture Diagram */
.arch-container {{
    background: var(--bg-card);
    border-radius: 12px;
    border: 1px solid var(--border);
    padding: 24px;
    overflow-x: auto;
    position: relative;
}}
.arch-container .mermaid {{
    display: flex;
    justify-content: center;
}}
.arch-container .mermaid svg {{
    max-width: 100%;
    height: auto;
}}
.arch-controls {{
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
}}
.arch-btn {{
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 12px;
    font-family: var(--font-main);
    transition: all 0.2s;
}}
.arch-btn:hover {{ background: var(--bg-card-hover); color: var(--text-primary); }}
.arch-btn.active {{ background: var(--accent-blue); color: white; border-color: var(--accent-blue); }}
.arch-placeholder {{
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 300px;
    color: var(--text-muted);
    font-size: 14px;
}}

/* Deployments Table */
.deploy-table-wrap {{
    background: var(--bg-card);
    border-radius: 12px;
    border: 1px solid var(--border);
    overflow: hidden;
}}
.deploy-filters {{
    display: flex;
    gap: 6px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
}}
.filter-btn {{
    padding: 5px 12px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 12px;
    font-family: var(--font-main);
    transition: all 0.2s;
}}
.filter-btn:hover {{ background: var(--bg-card-hover); }}
.filter-btn.active {{
    background: var(--accent-blue);
    color: white;
    border-color: var(--accent-blue);
}}
.deploy-table {{
    width: 100%;
    border-collapse: collapse;
}}
.deploy-table th {{
    text-align: left;
    padding: 12px 16px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
}}
.deploy-table td {{
    padding: 12px 16px;
    font-size: 13px;
    border-bottom: 1px solid rgba(30,41,59,0.5);
    vertical-align: middle;
}}
.deploy-row:hover {{ background: var(--bg-card-hover); }}
.repo-link {{
    color: var(--accent-blue);
    text-decoration: none;
    font-weight: 500;
}}
.repo-link:hover {{ text-decoration: underline; }}
.repo-tier {{
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
}}
.health-badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
}}
.ci-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    margin-left: 6px;
}}
.ci-badge.no-ci {{
    background: rgba(100,116,139,0.2);
    color: var(--text-muted);
    border: 1px solid rgba(100,116,139,0.3);
}}
.run-dot {{
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 3px;
    vertical-align: middle;
}}
.runs-cell {{ white-space: nowrap; }}
.num {{ text-align: right; font-family: var(--font-mono); }}
.action-link {{
    color: var(--text-muted);
    text-decoration: none;
    font-size: 12px;
    transition: color 0.2s;
}}
.action-link:hover {{ color: var(--accent-blue); }}

/* Recommendations */
.rec-grid {{
    display: grid;
    gap: 16px;
}}
.rec-card {{
    border-radius: 12px;
    padding: 20px;
}}
.rec-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}}
.rec-icon {{ font-size: 18px; }}
.rec-title {{ font-weight: 600; font-size: 15px; flex: 1; }}
.rec-severity {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(0,0,0,0.2);
}}
.rec-desc {{
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 10px;
    line-height: 1.5;
}}
.rec-repos {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}}
.rec-repo {{
    font-family: var(--font-mono);
    font-size: 11px;
    background: rgba(0,0,0,0.2);
    padding: 3px 8px;
    border-radius: 6px;
    color: var(--text-secondary);
}}
.rec-repo-more {{
    font-size: 11px;
    color: var(--text-muted);
    padding: 3px 8px;
}}
.rec-action {{
    font-size: 12px;
    color: var(--accent-blue);
    font-weight: 500;
}}

/* Live status ring */
.status-ring {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}}
.ring-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
}}
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.4; }}
}}

/* Refresh button */
.refresh-btn {{
    padding: 8px 16px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 12px;
    font-family: var(--font-main);
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.refresh-btn:hover {{ background: var(--bg-card-hover); color: var(--text-primary); }}
.refresh-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.refresh-btn .spinner {{
    display: none;
    width: 14px;
    height: 14px;
    border: 2px solid var(--text-muted);
    border-top-color: var(--accent-blue);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}

/* Footer */
.footer {{
    text-align: center;
    padding: 32px 0;
    color: var(--text-muted);
    font-size: 12px;
    border-top: 1px solid var(--border);
    margin-top: 40px;
}}
.footer a {{ color: var(--accent-blue); text-decoration: none; }}
</style>
</head>
<body>
<div class="container">
    <!-- Navigation -->
    <nav class="nav-bar">
        <a href="/" class="nav-brand">⚡ CHAD</a>
        <div class="nav-links">
            <a href="/" class="nav-link">📊 Dashboard</a>
            <a href="/ops" class="nav-link active">🛰️ Ops Center</a>
        </div>
        <div class="nav-right">
            <div class="status-ring" id="statusRing" style="background:rgba(34,197,94,0.1);color:#22c55e;border:1px solid rgba(34,197,94,0.2)">
                <span class="ring-dot" style="background:#22c55e"></span>
                <span id="statusText">Systems Operational</span>
            </div>
            <span class="nav-timestamp">{timestamp}</span>
        </div>
    </nav>

    <!-- Header -->
    <div class="page-header">
        <h1>🛰️ Ops Center</h1>
        <div class="subtitle">BlueFalconInk LLC — Architecture, Deployments & Recommendations</div>
    </div>

    <!-- Status Summary -->
    <div class="status-grid">
        <div class="status-card">
            <div class="stat-number" style="color:var(--text-primary)">{summary.get('total_repos', 0)}</div>
            <div class="stat-label">Total Repos</div>
        </div>
        <div class="status-card">
            <div class="stat-number" style="color:var(--accent-green)">{total_healthy}</div>
            <div class="stat-label">Healthy CI</div>
        </div>
        <div class="status-card">
            <div class="stat-number" style="color:var(--accent-amber)">{total_degraded}</div>
            <div class="stat-label">Degraded</div>
        </div>
        <div class="status-card">
            <div class="stat-number" style="color:var(--accent-red)">{total_failing}</div>
            <div class="stat-label">Failing</div>
        </div>
        <div class="status-card">
            <div class="stat-number" style="color:var(--text-muted)">{total_no_ci}</div>
            <div class="stat-label">No CI</div>
        </div>
    </div>

    <!-- Section 1: Architecture Diagram -->
    <div class="section" id="architectureSection">
        <div class="section-header">
            <div>
                <div class="section-title">🏗️ Infrastructure Architecture</div>
                <div class="section-subtitle">Live Mermaid diagram of the BlueFalconInk LLC platform</div>
            </div>
            <div class="arch-controls">
                <button class="arch-btn active" onclick="setArchView('diagram')">Diagram</button>
                <button class="arch-btn" onclick="setArchView('source')">Source</button>
                <button class="arch-btn" onclick="toggleFullscreen()">⛶ Fullscreen</button>
            </div>
        </div>
        <div class="arch-container" id="archContainer">
            <div id="archDiagram" class="mermaid">{mermaid_escaped if mermaid_src else ''}</div>
            <pre id="archSource" style="display:none;color:var(--text-secondary);font-family:var(--font-mono);font-size:12px;white-space:pre-wrap;max-height:600px;overflow-y:auto"></pre>
            <div id="archPlaceholder" class="arch-placeholder" style="{'display:none' if mermaid_src else ''}">
                No architecture diagram available. Ensure docs/architecture.mermaid exists in the repo.
            </div>
        </div>
    </div>

    <!-- Section 2: Deployment Status -->
    <div class="section" id="deploymentsSection">
        <div class="section-header">
            <div>
                <div class="section-title">🚀 Deployment & CI Status</div>
                <div class="section-subtitle">Workflow health across all BlueFalconInk repos</div>
            </div>
            <button class="refresh-btn" id="refreshBtn" onclick="refreshDeployments()">
                <span class="spinner" id="refreshSpinner"></span>
                🔄 Refresh Data
            </button>
        </div>
        <div class="deploy-table-wrap">
            <div class="deploy-filters">
                <button class="filter-btn active" onclick="filterDeploy('ALL', this)">All</button>
                <button class="filter-btn" onclick="filterDeploy('FAILING', this)">🔴 Failing</button>
                <button class="filter-btn" onclick="filterDeploy('DEGRADED', this)">⚠️ Degraded</button>
                <button class="filter-btn" onclick="filterDeploy('HEALTHY', this)">✅ Healthy</button>
                <button class="filter-btn" onclick="filterDeploy('UNKNOWN', this)">❔ Unknown</button>
            </div>
            <table class="deploy-table">
                <thead>
                    <tr>
                        <th>Repository</th>
                        <th>Health</th>
                        <th>Recent Runs</th>
                        <th style="text-align:right">Last Push</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="deployBody">
                    {deploy_rows}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Section 3: Recommendations -->
    <div class="section" id="recommendationsSection">
        <div class="section-header">
            <div>
                <div class="section-title">💡 Recommended Actions</div>
                <div class="section-subtitle">AI-generated suggestions to improve infrastructure health</div>
            </div>
        </div>
        <div class="rec-grid">
            {rec_cards}
        </div>
    </div>

    <!-- Footer -->
    <div class="footer">
        <p>CHAD Ops Center — <a href="https://github.com/{owner}/ArchitectAIPro_GHActions">ArchitectAIPro_GHActions</a> | BlueFalconInk LLC</p>
    </div>
</div>

<script>
// ── Mermaid Init ──
mermaid.initialize({{
    startOnLoad: true,
    theme: 'dark',
    themeVariables: {{
        primaryColor: '#1e293b',
        primaryTextColor: '#f8fafc',
        primaryBorderColor: '#3b82f6',
        lineColor: '#64748b',
        secondaryColor: '#0f172a',
        tertiaryColor: '#020617',
        fontFamily: 'Space Grotesk, system-ui, sans-serif',
    }},
    flowchart: {{
        curve: 'basis',
        useMaxWidth: true,
    }},
    securityLevel: 'strict',
}});

const MERMAID_SRC = `{mermaid_escaped}`;

// Store source for toggle
document.getElementById('archSource').textContent = MERMAID_SRC;

// ── Architecture View Toggle ──
function setArchView(view) {{
    const diagram = document.getElementById('archDiagram');
    const source = document.getElementById('archSource');
    const placeholder = document.getElementById('archPlaceholder');
    document.querySelectorAll('.arch-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');

    if (view === 'diagram') {{
        diagram.style.display = '';
        source.style.display = 'none';
    }} else {{
        diagram.style.display = 'none';
        source.style.display = '';
    }}
}}

function toggleFullscreen() {{
    const container = document.getElementById('archContainer');
    if (!document.fullscreenElement) {{
        container.requestFullscreen().catch(() => {{}});
        container.style.background = 'var(--bg-primary)';
    }} else {{
        document.exitFullscreen();
        container.style.background = '';
    }}
}}

// ── Deploy Filters ──
function filterDeploy(health, btn) {{
    document.querySelectorAll('.deploy-filters .filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.deploy-row').forEach(row => {{
        if (health === 'ALL') {{
            row.style.display = '';
        }} else {{
            row.style.display = row.dataset.health === health ? '' : 'none';
        }}
    }});
}}

// ── Refresh ──
async function refreshDeployments() {{
    const btn = document.getElementById('refreshBtn');
    const spinner = document.getElementById('refreshSpinner');
    btn.disabled = true;
    spinner.style.display = 'inline-block';

    try {{
        // Trigger a full refresh of the audit data
        const resp = await fetch('/api/refresh', {{ method: 'POST' }});
        if (resp.ok) {{
            // Reload the page to show updated data
            setTimeout(() => window.location.reload(), 1000);
        }} else {{
            alert('Refresh failed: ' + (await resp.json()).error);
        }}
    }} catch (e) {{
        alert('Refresh error: ' + e.message);
    }} finally {{
        btn.disabled = false;
        spinner.style.display = 'none';
    }}
}}

// ── Status Ring ──
(function updateStatusRing() {{
    const failing = {total_failing};
    const degraded = {total_degraded};
    const ring = document.getElementById('statusRing');
    const text = document.getElementById('statusText');
    const dot = ring.querySelector('.ring-dot');

    if (failing > 0) {{
        ring.style.background = 'rgba(239,68,68,0.1)';
        ring.style.color = '#ef4444';
        ring.style.border = '1px solid rgba(239,68,68,0.2)';
        dot.style.background = '#ef4444';
        text.textContent = failing + ' System(s) Failing';
    }} else if (degraded > 0) {{
        ring.style.background = 'rgba(245,158,11,0.1)';
        ring.style.color = '#f59e0b';
        ring.style.border = '1px solid rgba(245,158,11,0.2)';
        dot.style.background = '#f59e0b';
        text.textContent = degraded + ' Degraded';
    }} else {{
        text.textContent = 'All Systems Operational';
    }}
}})();
</script>
</body>
</html>"""
    return html


def _build_recommendations(repos, report, owner):
    """Generate actionable recommendations from audit data."""
    recs = []

    # 1. Failing CI
    failing = [r for r in repos if r.get("workflows", {}).get("health") == "FAILING" and not r.get("is_archived")]
    if failing:
        recs.append({
            "severity": "critical",
            "icon": "🔴",
            "title": f"{len(failing)} repo(s) have failing CI pipelines",
            "description": "These repos have 3+ recent workflow failures. Investigate build/test issues immediately.",
            "repos": [f"{r.get('owner', owner)}/{r['name']}" for r in failing],
            "action": "Click \"View Runs\" to inspect workflow logs and fix root causes.",
        })

    # 2. Degraded CI
    degraded = [r for r in repos if r.get("workflows", {}).get("health") == "DEGRADED" and not r.get("is_archived")]
    if degraded:
        recs.append({
            "severity": "warning",
            "icon": "⚠️",
            "title": f"{len(degraded)} repo(s) have degraded CI health",
            "description": "Occasional failures detected — possible flaky tests or intermittent issues.",
            "repos": [f"{r.get('owner', owner)}/{r['name']}" for r in degraded],
            "action": "Review recent failure logs to identify patterns.",
        })

    # 3. Active repos with no CI
    no_ci = [r for r in repos
             if not r.get("workflows", {}).get("recent_runs")
             and not r.get("architecture", {}).get("has_workflow", False)
             and r.get("classification", {}).get("tier") in ("CORE", "ACTIVE")
             and not r.get("is_archived")]
    if no_ci:
        recs.append({
            "severity": "warning",
            "icon": "⚙️",
            "title": f"{len(no_ci)} active repo(s) have no CI/CD pipeline",
            "description": "Core/Active repos without CI risk undetected regressions and security issues.",
            "repos": [f"{r.get('owner', owner)}/{r['name']}" for r in no_ci],
            "action": "Go to Dashboard → select repos → Deploy Workflow to add CI.",
        })

    # 4. Missing architecture workflow
    no_arch = [r for r in repos
               if not r.get("architecture", {}).get("has_workflow", False)
               and not r.get("is_archived")
               and r.get("classification", {}).get("tier") in ("CORE", "ACTIVE")]
    if no_arch:
        recs.append({
            "severity": "info",
            "icon": "🏗️",
            "title": f"{len(no_arch)} repo(s) missing architecture diagrams",
            "description": "Auto-generated architecture diagrams keep documentation in sync with code changes.",
            "repos": [f"{r.get('owner', owner)}/{r['name']}" for r in no_arch],
            "action": "Use Dashboard → Deploy Workflow → Architecture Diagrams.",
        })

    # 5. Stale repos → archive
    stale = [r for r in repos
             if r.get("classification", {}).get("tier") in ("STALE", "DEAD", "DORMANT")
             and not r.get("is_archived")]
    if stale:
        recs.append({
            "severity": "info",
            "icon": "📦",
            "title": f"{len(stale)} stale/dead repo(s) should be archived",
            "description": "Inactive repos increase security surface area. Archiving makes them read-only.",
            "repos": [f"{r.get('owner', owner)}/{r['name']}" for r in stale],
            "action": "Go to Dashboard → select repos → Archive.",
        })

    # 6. Branding compliance
    branding = report.get("summary", {}).get("branding_issues", [])
    if branding:
        recs.append({
            "severity": "info",
            "icon": "🎨",
            "title": f"{len(branding)} repo(s) have branding compliance gaps",
            "description": "Missing LICENSE, README, or org templates reduce professional consistency.",
            "repos": [b["repo"] for b in branding],
            "action": "Add required branding files per BlueFalconInk LLC standards.",
        })

    return recs


def main():
    parser = argparse.ArgumentParser(description="CHAD Ops Center Page Generator")
    parser.add_argument("--input", default="docs/audit_report.json", help="Audit report JSON")
    parser.add_argument("--mermaid", default="docs/architecture.mermaid", help="Mermaid diagram source")
    parser.add_argument("--output", default="static/ops.html", help="Output HTML path")
    args = parser.parse_args()

    report_path = Path(args.input)
    if not report_path.exists():
        print(f"❌ Audit report not found: {args.input}")
        sys.exit(1)

    report = json.loads(report_path.read_text())

    mermaid_src = ""
    mermaid_path = Path(args.mermaid)
    if mermaid_path.exists():
        mermaid_src = mermaid_path.read_text(encoding="utf-8")
    else:
        print(f"⚠️  Mermaid file not found: {args.mermaid} — diagram section will be empty")

    html = generate_ops_page(report, mermaid_src)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"🛰️  Ops Center page written to {args.output}")


if __name__ == "__main__":
    main()
