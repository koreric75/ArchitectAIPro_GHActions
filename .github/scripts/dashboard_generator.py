#!/usr/bin/env python3
"""
BlueFalconInk LLC — CHAD Advisory Dashboard Generator

Reads audit_report.json and produces a stunning static HTML dashboard
styled after the CHAD (Centralized Hub for Architectural Decision-making)
design system: dark navy theme, Space Grotesk font, status matrices, burn
rate tracking, and actionable cleanup recommendations.

Usage:
    python dashboard_generator.py --input docs/audit_report.json --output docs/dashboard.html
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def status_color(tier: str) -> str:
    """Map tier to CHAD color palette."""
    return {
        "CORE": "#22c55e",       # Green
        "ACTIVE": "#3b82f6",     # Blue
        "DORMANT": "#f59e0b",    # Amber
        "STALE": "#ef4444",      # Red
        "DEAD": "#6b7280",       # Gray
        "LEGACY_FORK": "#8b5cf6", # Purple
        "FORK": "#a78bfa",       # Light purple
        "ARCHIVED": "#374151",   # Dark gray
    }.get(tier, "#6b7280")


def action_badge(action: str) -> str:
    colors = {
        "MAINTAIN": ("#22c55e", "#052e16"),
        "REVIEW": ("#f59e0b", "#451a03"),
        "ARCHIVE": ("#ef4444", "#450a0a"),
        "ARCHIVE_OR_DELETE": ("#dc2626", "#450a0a"),
        "DELETE": ("#b91c1c", "#1f2937"),
        "NONE": ("#6b7280", "#1f2937"),
    }
    fg, bg = colors.get(action, ("#6b7280", "#1f2937"))
    return f'<span class="badge" style="background:{bg};color:{fg};border:1px solid {fg}40">{action}</span>'


def health_indicator(health: str) -> str:
    icons = {
        "HEALTHY": ("✅", "#22c55e"),
        "DEGRADED": ("⚠️", "#f59e0b"),
        "FAILING": ("🔴", "#ef4444"),
        "UNKNOWN": ("➖", "#6b7280"),
    }
    icon, color = icons.get(health, ("➖", "#6b7280"))
    return f'<span style="color:{color}">{icon} {health}</span>'


def bool_icon(val: bool) -> str:
    return "✅" if val else "❌"


def generate_dashboard(report: dict) -> str:
    """Generate the full HTML dashboard."""
    summary = report.get("summary", {})
    repos = report.get("repos", [])
    timestamp = report.get("audit_timestamp", "Unknown")
    owner = report.get("owner", "unknown")

    # --- Stats cards ---
    core = summary.get("core", 0)
    active = summary.get("active", 0)
    stale = summary.get("stale", 0)
    dead = summary.get("dead", 0)
    forks = summary.get("forks", 0)
    total = summary.get("total_repos", 0)
    disk_mb = summary.get("total_disk_mb", 0)
    monthly_burn = summary.get("total_monthly_burn", 0)
    delete_candidates = summary.get("delete_candidates", [])
    archive_candidates = summary.get("archive_candidates", [])
    branding_issues = summary.get("branding_issues", [])

    # --- Repo rows ---
    repo_rows = ""
    for r in repos:
        cls = r.get("classification", {})
        sl = r.get("staleness", {})
        br = r.get("branding", {})
        arch = r.get("architecture", {})
        sec = r.get("secrets", {})
        wf = r.get("workflows", {})
        tier = cls.get("tier", "UNKNOWN")

        visibility = "🔒" if r.get("is_private") else "🌐"
        fork_badge = ' <span class="fork-tag">FORK</span>' if r.get("is_fork") else ""

        repo_rows += f"""
        <tr class="repo-row" data-tier="{tier}">
            <td>
                <a href="{r.get('url', '#')}" target="_blank" class="repo-link">
                    {visibility} {r['name']}
                </a>{fork_badge}
                <div class="repo-desc">{r.get('description', '')[:80]}</div>
            </td>
            <td><span class="tier-dot" style="background:{status_color(tier)}"></span>{tier}</td>
            <td>{action_badge(cls.get('action', 'NONE'))}</td>
            <td>{r.get('language', 'N/A')}</td>
            <td class="num">{cls.get('disk_mb', 0)} MB</td>
            <td class="num">{sl.get('days_since_push', '?')}d</td>
            <td class="num">${cls.get('monthly_burn_estimate', 0)}</td>
            <td>{bool_icon(br.get('compliant', True))}</td>
            <td>{bool_icon(arch.get('fully_configured', False))}</td>
            <td>{bool_icon(sec.get('has_gemini_key', False))}</td>
            <td>{health_indicator(wf.get('health', 'UNKNOWN'))}</td>
        </tr>"""

    # --- Branding issues detail ---
    branding_rows = ""
    for bi in branding_issues:
        for detail in bi.get("details", []):
            branding_rows += f"""
            <tr>
                <td>{bi['repo']}</td>
                <td>{detail.get('file', '')}</td>
                <td class="bad-brand">{detail.get('found', '')}</td>
                <td>{detail.get('fix', '')}</td>
            </tr>"""

    # --- Action items ---
    action_items = ""
    if delete_candidates:
        action_items += '<div class="action-card action-delete"><h3>🗑️ Delete Candidates</h3><ul>'
        for dc in delete_candidates:
            action_items += f"<li>{dc}</li>"
        action_items += "</ul><p>These are stale forks or dead repos consuming storage.</p></div>"

    if archive_candidates:
        action_items += '<div class="action-card action-archive"><h3>📦 Archive Candidates</h3><ul>'
        for ac in archive_candidates:
            action_items += f"<li>{ac}</li>"
        action_items += "</ul><p>Repos with no recent activity. Archive to clean up.</p></div>"

    if branding_issues:
        action_items += '<div class="action-card action-brand"><h3>🏷️ Branding Fixes Needed</h3><ul>'
        for bi in branding_issues:
            action_items += f"<li>{bi['repo']} — {bi['count']} issue(s)</li>"
        action_items += "</ul></div>"

    # Non-configured repos that are active
    missing_arch = [r["name"] for r in repos
                    if r["classification"]["tier"] in ("CORE", "ACTIVE")
                    and not r.get("architecture", {}).get("fully_configured", False)]
    if missing_arch:
        action_items += '<div class="action-card action-arch"><h3>🏗️ Architecture Diagrams Missing</h3><ul>'
        for ma in missing_arch:
            action_items += f"<li>{ma}</li>"
        action_items += "</ul><p>Deploy the architecture workflow to these repos.</p></div>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CHAD — BlueFalconInk Ops Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
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

/* Header */
.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 32px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 32px;
}}
.header h1 {{
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}
.header .subtitle {{
    color: var(--text-secondary);
    font-size: 14px;
    margin-top: 4px;
}}
.header .meta {{
    text-align: right;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
}}
.header .meta .timestamp {{ color: var(--accent-blue); }}

/* Stats Grid */
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}}
.stat-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    transition: transform 0.2s, border-color 0.2s;
}}
.stat-card:hover {{
    transform: translateY(-2px);
    border-color: var(--accent-blue);
}}
.stat-card .label {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }}
.stat-card .value {{ font-size: 32px; font-weight: 700; margin: 8px 0 4px; font-family: var(--font-mono); }}
.stat-card .detail {{ font-size: 12px; color: var(--text-secondary); }}
.stat-green .value {{ color: var(--accent-green); }}
.stat-blue .value {{ color: var(--accent-blue); }}
.stat-amber .value {{ color: var(--accent-amber); }}
.stat-red .value {{ color: var(--accent-red); }}
.stat-purple .value {{ color: var(--accent-purple); }}

/* Sections */
.section {{ margin-bottom: 40px; }}
.section-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
}}
.section-header h2 {{
    font-size: 20px;
    font-weight: 600;
}}
.section-header .filter-btns {{ display: flex; gap: 8px; }}
.filter-btn {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 6px 14px;
    border-radius: 8px;
    cursor: pointer;
    font-family: var(--font-main);
    font-size: 12px;
    transition: all 0.2s;
}}
.filter-btn:hover, .filter-btn.active {{
    background: var(--accent-blue);
    color: white;
    border-color: var(--accent-blue);
}}

/* Table */
.table-wrap {{
    overflow-x: auto;
    border-radius: 12px;
    border: 1px solid var(--border);
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
th {{
    background: var(--bg-secondary);
    padding: 12px 16px;
    text-align: left;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
    position: sticky;
    top: 0;
    z-index: 10;
    border-bottom: 2px solid var(--accent-blue);
}}
td {{
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
}}
tr:hover {{ background: var(--bg-card); }}
.num {{ text-align: right; font-family: var(--font-mono); font-size: 12px; }}
.repo-link {{
    color: var(--accent-blue);
    text-decoration: none;
    font-weight: 500;
    font-size: 14px;
}}
.repo-link:hover {{ text-decoration: underline; }}
.repo-desc {{ color: var(--text-muted); font-size: 11px; margin-top: 2px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.tier-dot {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}}
.badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
.fork-tag {{
    background: var(--accent-purple);
    color: white;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 9px;
    font-weight: 700;
    margin-left: 6px;
    vertical-align: middle;
}}
.bad-brand {{ color: var(--accent-red); font-family: var(--font-mono); font-size: 12px; }}

/* Action Cards */
.actions-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
}}
.action-card {{
    background: var(--bg-card);
    border-radius: 12px;
    padding: 20px;
    border-left: 4px solid;
}}
.action-card h3 {{ font-size: 16px; margin-bottom: 12px; }}
.action-card ul {{ padding-left: 20px; margin-bottom: 8px; }}
.action-card li {{ color: var(--text-secondary); font-size: 13px; margin-bottom: 4px; }}
.action-card p {{ color: var(--text-muted); font-size: 12px; }}
.action-delete {{ border-left-color: var(--accent-red); }}
.action-archive {{ border-left-color: var(--accent-amber); }}
.action-brand {{ border-left-color: var(--accent-purple); }}
.action-arch {{ border-left-color: var(--accent-blue); }}

/* Footer */
.footer {{
    text-align: center;
    padding: 32px 0;
    color: var(--text-muted);
    font-size: 12px;
    border-top: 1px solid var(--border);
    margin-top: 48px;
}}
.footer a {{ color: var(--accent-blue); text-decoration: none; }}

/* Burn Rate Bar */
.burn-bar {{
    background: var(--bg-secondary);
    border-radius: 6px;
    height: 24px;
    display: flex;
    overflow: hidden;
    margin-top: 8px;
}}
.burn-segment {{
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 600;
    color: white;
    min-width: 40px;
    transition: width 0.5s;
}}

/* Responsive */
@media (max-width: 768px) {{
    .container {{ padding: 12px; }}
    .header {{ flex-direction: column; text-align: center; gap: 12px; }}
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .section-header {{ flex-direction: column; gap: 12px; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
    <div>
        <h1>🦅 CHAD — BlueFalconInk Ops</h1>
        <div class="subtitle">Centralized Hub for Architectural Decision-making</div>
    </div>
    <div class="meta">
        <div>Owner: <span class="timestamp">{owner}</span></div>
        <div>Audit: <span class="timestamp">{timestamp[:19]}Z</span></div>
        <div>API calls: {report.get('api_calls_used', '?')}/{MAX_API_CALLS}</div>
    </div>
</div>

<!-- Stats -->
<div class="stats-grid">
    <div class="stat-card stat-blue">
        <div class="label">Total Repos</div>
        <div class="value">{total}</div>
        <div class="detail">{forks} forks</div>
    </div>
    <div class="stat-card stat-green">
        <div class="label">Core Products</div>
        <div class="value">{core}</div>
        <div class="detail">Revenue-generating</div>
    </div>
    <div class="stat-card stat-blue">
        <div class="label">Active</div>
        <div class="value">{active}</div>
        <div class="detail">Updated &lt; 90 days</div>
    </div>
    <div class="stat-card stat-amber">
        <div class="label">Stale / Dormant</div>
        <div class="value">{stale}</div>
        <div class="detail">Archive candidates</div>
    </div>
    <div class="stat-card stat-red">
        <div class="label">Dead / Legacy</div>
        <div class="value">{dead}</div>
        <div class="detail">Delete candidates</div>
    </div>
    <div class="stat-card stat-purple">
        <div class="label">Disk Usage</div>
        <div class="value">{disk_mb:.0f}</div>
        <div class="detail">MB total</div>
    </div>
    <div class="stat-card stat-amber">
        <div class="label">Est. Monthly Burn</div>
        <div class="value">${monthly_burn}</div>
        <div class="detail">GCP + CI/CD</div>
    </div>
    <div class="stat-card stat-red">
        <div class="label">Branding Issues</div>
        <div class="value">{len(branding_issues)}</div>
        <div class="detail">repos need fixes</div>
    </div>
</div>

<!-- Active Infrastructure Matrix -->
<div class="section">
    <div class="section-header">
        <h2>📡 Active Infrastructure Matrix</h2>
        <div class="filter-btns">
            <button class="filter-btn active" onclick="filterRepos('ALL')">All</button>
            <button class="filter-btn" onclick="filterRepos('CORE')">Core</button>
            <button class="filter-btn" onclick="filterRepos('ACTIVE')">Active</button>
            <button class="filter-btn" onclick="filterRepos('STALE')">Stale</button>
            <button class="filter-btn" onclick="filterRepos('DEAD')">Dead</button>
            <button class="filter-btn" onclick="filterRepos('FORK')">Forks</button>
        </div>
    </div>
    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>Repository</th>
                    <th>Tier</th>
                    <th>Action</th>
                    <th>Language</th>
                    <th>Size</th>
                    <th>Last Push</th>
                    <th>Burn/mo</th>
                    <th>Brand</th>
                    <th>Arch</th>
                    <th>Key</th>
                    <th>CI Health</th>
                </tr>
            </thead>
            <tbody id="repoTable">
                {repo_rows}
            </tbody>
        </table>
    </div>
</div>

<!-- Recommended Actions -->
<div class="section">
    <div class="section-header">
        <h2>⚡ Recommended Actions</h2>
    </div>
    <div class="actions-grid">
        {action_items}
    </div>
</div>

<!-- Branding Issues Detail -->
{"" if not branding_issues else f'''
<div class="section">
    <div class="section-header">
        <h2>🏷️ Branding Compliance Report</h2>
    </div>
    <div class="table-wrap">
        <table>
            <thead>
                <tr><th>Repo</th><th>File</th><th>Found (Incorrect)</th><th>Fix</th></tr>
            </thead>
            <tbody>
                {branding_rows}
            </tbody>
        </table>
    </div>
</div>
'''}

<!-- Footer -->
<div class="footer">
    <p>CHAD Dashboard — BlueFalconInk LLC © {datetime.now().year}</p>
    <p>Generated by <a href="https://github.com/{owner}/ArchitectAIPro_GHActions">ArchitectAIPro_GHActions</a> Agent Orchestration</p>
</div>

</div>

<script>
const MAX_API_CALLS = 300;
function filterRepos(tier) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.repo-row').forEach(row => {{
        if (tier === 'ALL') {{
            row.style.display = '';
        }} else if (tier === 'FORK') {{
            row.style.display = (row.dataset.tier === 'LEGACY_FORK' || row.dataset.tier === 'FORK') ? '' : 'none';
        }} else if (tier === 'STALE') {{
            row.style.display = (row.dataset.tier === 'STALE' || row.dataset.tier === 'DORMANT') ? '' : 'none';
        }} else if (tier === 'DEAD') {{
            row.style.display = (row.dataset.tier === 'DEAD' || row.dataset.tier === 'LEGACY_FORK') ? '' : 'none';
        }} else {{
            row.style.display = row.dataset.tier === tier ? '' : 'none';
        }}
    }});
}}
</script>
</body>
</html>"""
    return html


MAX_API_CALLS = 300  # match auditor budget

def main():
    parser = argparse.ArgumentParser(description="CHAD Dashboard Generator")
    parser.add_argument("--input", default="docs/audit_report.json", help="Audit report JSON")
    parser.add_argument("--output", default="docs/dashboard.html", help="Output HTML path")
    args = parser.parse_args()

    report_path = Path(args.input)
    if not report_path.exists():
        print(f"❌ Audit report not found: {args.input}")
        sys.exit(1)

    report = json.loads(report_path.read_text())
    html = generate_dashboard(report)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"📊 Dashboard written to {args.output}")
    print(f"   Open in browser to view the CHAD advisory dashboard.")


if __name__ == "__main__":
    main()
