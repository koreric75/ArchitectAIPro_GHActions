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
        svc = r.get("services", {})
        tier = cls.get("tier", "UNKNOWN")

        visibility = "🔒" if r.get("is_private") else "🌐"
        fork_badge = ' <span class="fork-tag">FORK</span>' if r.get("is_fork") else ""

        # Burn breakdown tooltip
        burn_total = cls.get("monthly_burn_estimate", 0)
        burn_bd = cls.get("burn_breakdown", {})
        if burn_bd:
            tooltip_lines = [f"{k}: ${v}" for k, v in burn_bd.items() if v > 0]
            burn_tooltip = "&#10;".join(tooltip_lines) if tooltip_lines else "Scaled to zero"
        else:
            burn_tooltip = "No active services"

        # Service badges
        detected_svcs = svc.get("service_details", [])
        svc_html = ""
        if detected_svcs:
            badges = []
            for s in detected_svcs:
                cat_color = {
                    "BaaS": "#22c55e", "Database": "#22c55e", "Cache": "#06b6d4",
                    "Hosting": "#8b5cf6", "CDN": "#f59e0b", "Media": "#ec4899",
                    "Payments": "#f59e0b", "Auth": "#3b82f6", "AI": "#a78bfa",
                    "Observability": "#6b7280", "CI/CD": "#6b7280",
                    "Email": "#64748b", "Communications": "#64748b",
                    "Audio": "#ec4899",
                }.get(s.get("category", ""), "#6b7280")
                cost_tag = f" ${s['cost']}" if s.get("cost", 0) > 0 else ""
                badges.append(
                    f'<span class="svc-badge" style="border-color:{cat_color};color:{cat_color}">'
                    f'{s["label"]}{cost_tag}</span>'
                )
            svc_html = " ".join(badges)
        else:
            svc_html = '<span style="color:var(--text-muted);font-size:11px">—</span>'

        repo_owner = r.get('owner', owner)
        repo_rows += f"""
        <tr class="repo-row" data-tier="{tier}" data-repo="{r['name']}" data-owner="{repo_owner}" data-archived="{str(r.get('is_archived', False)).lower()}">
            <td class="cb-cell"><input type="checkbox" class="repo-cb" data-repo="{r['name']}" /></td>
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
            <td class="num burn-cell" title="{burn_tooltip}">${burn_total}</td>
            <td class="svc-cell">{svc_html}</td>
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
    missing_arch_json = json.dumps(missing_arch) if missing_arch else "[]"
    if missing_arch:
        action_items += f'<div class="action-card action-arch" id="deployCard" data-repos=\'{missing_arch_json}\'>'
        action_items += '<h3>🏗️ Architecture Diagrams Missing</h3><ul>'
        for ma in missing_arch:
            action_items += f"<li>{ma}</li>"
        action_items += '</ul><p>Deploy the architecture workflow to these repos.</p>'
        action_items += '<button class="btn-deploy-sm" onclick="selectAndDeploy(\'architecture\')">🚀 Select &amp; Deploy</button>'
        action_items += '</div>'

    # Build JSON map of all non-archived repo names → owner for the deploy UI
    all_repo_names = json.dumps([r["name"] for r in repos if not r.get("is_archived")])

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

/* Service Badges */
.svc-badge {{
    display: inline-block;
    padding: 1px 7px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    border: 1px solid;
    margin: 1px 2px;
    white-space: nowrap;
    background: transparent;
}}
.svc-cell {{ max-width: 220px; }}
.burn-cell {{
    cursor: help;
    border-bottom: 1px dashed var(--text-muted);
}}

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

/* Deploy Button */
/* Deploy Button (toolbar) */
.btn-deploy {{
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
    color: #fff;
    border: none;
    padding: 8px 18px;
    border-radius: 8px;
    cursor: pointer;
    font-family: var(--font-main);
    font-weight: 600;
    font-size: 12px;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}}
.btn-deploy:hover {{ filter: brightness(1.15); transform: translateY(-1px); }}
.btn-deploy:disabled {{ opacity: 0.5; cursor: not-allowed; filter: none; transform: none; }}
.btn-deploy .spinner {{
    display: none;
    width: 14px; height: 14px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
}}
.btn-deploy.loading .spinner {{ display: inline-block; }}
.btn-deploy.loading .btn-label {{ display: none; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}

/* Small action-card deploy button */
.btn-deploy-sm {{
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
    color: #fff;
    border: none;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-family: var(--font-main);
    font-weight: 600;
    font-size: 12px;
    margin-top: 10px;
    transition: all 0.2s;
}}
.btn-deploy-sm:hover {{ filter: brightness(1.15); }}

/* Deploy modal workflow selector */
.wf-selector {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 12px 0;
}}
.wf-option {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid var(--border);
    cursor: pointer;
    transition: all 0.15s;
    background: var(--card-bg);
}}
.wf-option:hover {{ border-color: var(--accent-blue); }}
.wf-option.selected {{ border-color: var(--accent-blue); background: rgba(59,130,246,0.08); }}
.wf-option input[type="radio"] {{ accent-color: var(--accent-blue); width: 16px; height: 16px; cursor: pointer; }}
.wf-label {{ font-weight: 600; font-size: 13px; color: var(--text-primary); }}
.wf-desc {{ font-size: 11px; color: var(--text-muted); margin-top: 2px; }}
.wf-target {{ font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 2px; }}

/* Deploy results in modal */
.deploy-results {{
    margin-top: 10px;
    font-size: 12px;
    font-family: var(--font-mono);
    max-height: 200px;
    overflow-y: auto;
}}
.deploy-results .dr-ok {{ color: var(--accent-green); padding: 2px 0; }}
.deploy-results .dr-err {{ color: var(--accent-red); padding: 2px 0; }}
.deploy-progress {{
    margin-top: 8px;
    padding: 8px 12px;
    border-radius: 6px;
    background: var(--card-bg);
    border: 1px solid var(--border);
    font-size: 12px;
    color: var(--text-secondary);
}}

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

/* Token Bar */
.token-bar {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}}
.token-bar label {{ font-size: 13px; color: var(--text-secondary); white-space: nowrap; }}
.token-bar input {{
    flex: 1;
    min-width: 200px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 12px;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 12px;
}}
.token-bar input:focus {{ outline: none; border-color: var(--accent-blue); }}
.token-bar .connect-btn {{
    background: var(--accent-blue);
    color: white;
    border: none;
    padding: 8px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-family: var(--font-main);
    font-weight: 600;
    font-size: 13px;
    transition: background 0.2s;
}}
.token-bar .connect-btn:hover {{ background: #2563eb; }}
.token-bar .status {{ font-size: 12px; font-family: var(--font-mono); }}
.token-bar .status.ok {{ color: var(--accent-green); }}
.token-bar .status.err {{ color: var(--accent-red); }}

/* Checkbox column */
.cb-cell {{ width: 36px; text-align: center; }}
.repo-cb {{
    width: 16px; height: 16px; cursor: pointer;
    accent-color: var(--accent-blue);
}}
#selectAll {{ width: 16px; height: 16px; cursor: pointer; accent-color: var(--accent-blue); }}
tr.selected {{ background: rgba(59,130,246,0.1) !important; }}

/* Floating Action Toolbar */
.action-toolbar {{
    position: fixed;
    bottom: -80px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-card);
    border: 1px solid var(--accent-blue);
    border-radius: 16px;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    z-index: 1000;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    transition: bottom 0.3s ease;
}}
.action-toolbar.visible {{ bottom: 32px; }}
.action-toolbar .sel-count {{
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--accent-blue);
    font-weight: 600;
    min-width: 120px;
}}
.action-toolbar button {{
    border: none;
    padding: 8px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-family: var(--font-main);
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s;
}}
.btn-archive {{ background: var(--accent-amber); color: #000; }}
.btn-archive:hover {{ background: #d97706; }}
.btn-delete {{ background: var(--accent-red); color: #fff; }}
.btn-delete:hover {{ background: #dc2626; }}
.btn-deselect {{ background: var(--bg-secondary); color: var(--text-secondary); border: 1px solid var(--border) !important; }}
.btn-deselect:hover {{ color: var(--text-primary); }}
.btn-archive:disabled, .btn-delete:disabled {{ opacity: 0.4; cursor: not-allowed; }}

/* Modal */
.modal-overlay {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.7);
    z-index: 2000;
    align-items: center;
    justify-content: center;
}}
.modal-overlay.open {{ display: flex; }}
.modal {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 32px;
    max-width: 520px;
    width: 90%;
}}
.modal h3 {{ font-size: 18px; margin-bottom: 16px; }}
.modal .repo-list {{
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 12px 16px;
    margin: 12px 0;
    max-height: 200px;
    overflow-y: auto;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--text-secondary);
}}
.modal .repo-list div {{ padding: 2px 0; }}
.modal .warning {{ color: var(--accent-red); font-size: 13px; margin: 12px 0; }}
.modal .btn-row {{ display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }}
.modal .btn-cancel {{
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 8px 24px;
    border-radius: 8px;
    cursor: pointer;
    font-family: var(--font-main);
    font-size: 13px;
}}
.modal .btn-confirm {{
    border: none;
    padding: 8px 24px;
    border-radius: 8px;
    cursor: pointer;
    font-family: var(--font-main);
    font-weight: 600;
    font-size: 13px;
    color: #fff;
}}
.modal .btn-confirm.archive {{ background: var(--accent-amber); color: #000; }}
.modal .btn-confirm.delete {{ background: var(--accent-red); }}
.modal .btn-confirm:disabled {{ opacity: 0.5; cursor: wait; }}

/* Activity Log */
.activity-log {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    max-height: 300px;
    overflow-y: auto;
}}
.log-entry {{
    padding: 6px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    display: flex;
    gap: 10px;
}}
.log-entry:last-child {{ border-bottom: none; }}
.log-time {{ color: var(--text-muted); font-family: var(--font-mono); font-size: 11px; min-width: 80px; }}
.log-ok {{ color: var(--accent-green); }}
.log-err {{ color: var(--accent-red); }}
.log-info {{ color: var(--text-secondary); }}

/* Toast */
.toast {{
    position: fixed;
    top: 24px;
    right: 24px;
    background: var(--bg-card);
    border: 1px solid var(--accent-green);
    border-radius: 10px;
    padding: 14px 20px;
    font-size: 13px;
    z-index: 3000;
    opacity: 0;
    transform: translateY(-10px);
    transition: all 0.3s;
    max-width: 400px;
}}
.toast.show {{ opacity: 1; transform: translateY(0); }}
.toast.error {{ border-color: var(--accent-red); }}

/* Responsive */
@media (max-width: 768px) {{
    .container {{ padding: 12px; }}
    .header {{ flex-direction: column; text-align: center; gap: 12px; }}
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .section-header {{ flex-direction: column; gap: 12px; }}
    .action-toolbar {{ padding: 10px 16px; gap: 10px; flex-wrap: wrap; justify-content: center; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Token Connect Bar -->
<div class="token-bar" id="tokenBar">
    <label>🔑 GitHub Token:</label>
    <input type="password" id="ghToken" placeholder="ghp_... or paste token with repo scope" />
    <button class="connect-btn" onclick="connectToken()">Connect</button>
    <span class="status" id="tokenStatus"></span>
</div>

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
        <div class="detail">Cloud Run + 3rd Party</div>
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
                    <th class="cb-cell"><input type="checkbox" id="selectAll" title="Select all" /></th>
                    <th>Repository</th>
                    <th>Tier</th>
                    <th>Action</th>
                    <th>Language</th>
                    <th>Size</th>
                    <th>Last Push</th>
                    <th>Burn/mo</th>
                    <th>Services</th>
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

<!-- Activity Log -->
<div class="section" id="logSection" style="display:none">
    <div class="section-header">
        <h2>📋 Activity Log</h2>
    </div>
    <div class="activity-log" id="activityLog"></div>
</div>

<!-- Footer -->
<div class="footer">
    <p>CHAD Dashboard — BlueFalconInk LLC © {datetime.now().year}</p>
    <p>Generated by <a href="https://github.com/{owner}/ArchitectAIPro_GHActions">ArchitectAIPro_GHActions</a> Agent Orchestration</p>
</div>

</div>

<!-- Floating Action Toolbar -->
<div class="action-toolbar" id="actionToolbar">
    <span class="sel-count" id="selCount">0 selected</span>
    <button class="btn-deploy" id="btnDeploy" disabled onclick="showDeployModal()">
        <span class="spinner"></span>
        <span class="btn-label">🚀 Deploy Workflow</span>
    </button>
    <button class="btn-archive" id="btnArchive" disabled onclick="showModal('archive')">📦 Archive</button>
    <button class="btn-delete" id="btnDelete" disabled onclick="showModal('delete')">🗑️ Delete</button>
    <button class="btn-deselect" onclick="deselectAll()">✕ Clear</button>
</div>

<!-- Confirmation Modal -->
<div class="modal-overlay" id="modalOverlay">
    <div class="modal">
        <h3 id="modalTitle">Confirm Action</h3>
        <p id="modalDesc" style="color:var(--text-secondary);font-size:13px"></p>
        <div class="repo-list" id="modalRepos"></div>
        <p class="warning" id="modalWarning"></p>
        <div class="btn-row">
            <button class="btn-cancel" onclick="closeModal()">Cancel</button>
            <button class="btn-confirm" id="modalConfirm" onclick="executeAction()">Confirm</button>
        </div>
    </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
const DEFAULT_OWNER = '{owner}';
let ghToken = localStorage.getItem('chad_gh_token') || '';
let pendingAction = null;

// Look up the owner for a repo from its table row data-owner attribute
function getRepoOwner(repoName) {{
    const row = document.querySelector(`tr[data-repo="${{repoName}}"]`);
    return (row && row.dataset.owner) || DEFAULT_OWNER;
}}

// ── Token Management ──
async function connectToken() {{
    const input = document.getElementById('ghToken');
    const status = document.getElementById('tokenStatus');
    const token = input.value.trim();
    if (!token) {{ status.className = 'status err'; status.textContent = 'Enter a token'; return; }}
    status.className = 'status'; status.textContent = 'Connecting...';
    try {{
        const r = await fetch('https://api.github.com/user', {{ headers: {{ Authorization: 'token ' + token }} }});
        if (r.ok) {{
            const u = await r.json();
            ghToken = token;
            localStorage.setItem('chad_gh_token', token);
            status.className = 'status ok';
            status.textContent = '✅ Connected as ' + u.login;
            input.value = '••••••••••' + token.slice(-4);
            updateToolbarState();
        }} else {{
            status.className = 'status err'; status.textContent = '❌ Invalid token (' + r.status + ')';
        }}
    }} catch(e) {{ status.className = 'status err'; status.textContent = '❌ ' + e.message; }}
}}

// Auto-restore saved token
(function() {{
    if (ghToken) {{
        document.getElementById('ghToken').value = '••••••••••' + ghToken.slice(-4);
        fetch('https://api.github.com/user', {{ headers: {{ Authorization: 'token ' + ghToken }} }})
            .then(r => r.ok ? r.json() : Promise.reject(r.status))
            .then(u => {{
                document.getElementById('tokenStatus').className = 'status ok';
                document.getElementById('tokenStatus').textContent = '✅ ' + u.login;
            }})
            .catch(() => {{
                document.getElementById('tokenStatus').className = 'status err';
                document.getElementById('tokenStatus').textContent = '⚠️ Saved token expired';
                ghToken = '';
            }});
    }}
}})();

// ── Selection ──
function getSelected() {{
    return [...document.querySelectorAll('.repo-cb:checked')].map(cb => cb.dataset.repo);
}}

function updateToolbarState() {{
    const sel = getSelected();
    const toolbar = document.getElementById('actionToolbar');
    document.getElementById('selCount').textContent = sel.length + ' selected';
    toolbar.classList.toggle('visible', sel.length > 0);
    const hasToken = !!ghToken;
    document.getElementById('btnArchive').disabled = !hasToken || sel.length === 0;
    document.getElementById('btnDelete').disabled = !hasToken || sel.length === 0;
    document.getElementById('btnDeploy').disabled = !hasToken || sel.length === 0;
}}

function deselectAll() {{
    document.querySelectorAll('.repo-cb').forEach(cb => {{ cb.checked = false; cb.closest('tr').classList.remove('selected'); }});
    document.getElementById('selectAll').checked = false;
    updateToolbarState();
}}

document.addEventListener('change', e => {{
    if (e.target.id === 'selectAll') {{
        const checked = e.target.checked;
        document.querySelectorAll('.repo-row').forEach(row => {{
            if (row.style.display !== 'none') {{
                const cb = row.querySelector('.repo-cb');
                cb.checked = checked;
                row.classList.toggle('selected', checked);
            }}
        }});
    }} else if (e.target.classList.contains('repo-cb')) {{
        e.target.closest('tr').classList.toggle('selected', e.target.checked);
    }}
    updateToolbarState();
}});

// ── Filter ──
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
    deselectAll();
}}

// ── Modal ──
function showModal(action) {{
    const repos = getSelected();
    if (!repos.length) return;
    pendingAction = action;
    const overlay = document.getElementById('modalOverlay');
    const title = document.getElementById('modalTitle');
    const desc = document.getElementById('modalDesc');
    const list = document.getElementById('modalRepos');
    const warn = document.getElementById('modalWarning');
    const btn = document.getElementById('modalConfirm');
    list.innerHTML = repos.map(r => '<div>' + getRepoOwner(r) + '/' + r + '</div>').join('');
    if (action === 'archive') {{
        title.textContent = '📦 Archive ' + repos.length + ' repo(s)?';
        desc.textContent = 'Archived repos become read-only. You can unarchive later.';
        warn.textContent = '';
        btn.className = 'btn-confirm archive';
        btn.textContent = 'Archive Now';
    }} else {{
        title.textContent = '🗑️ Delete ' + repos.length + ' repo(s)?';
        desc.textContent = 'This action is PERMANENT and cannot be undone.';
        warn.textContent = '⚠️ All code, issues, pull requests, and wikis will be permanently destroyed.';
        btn.className = 'btn-confirm delete';
        btn.textContent = 'Delete Forever';
    }}
    btn.disabled = false;
    overlay.classList.add('open');
}}

function closeModal() {{
    document.getElementById('modalOverlay').classList.remove('open');
    pendingAction = null;
}}

// ── Activity Log ──
function addLog(type, msg) {{
    const section = document.getElementById('logSection');
    section.style.display = '';
    const log = document.getElementById('activityLog');
    const time = new Date().toLocaleTimeString();
    const cls = type === 'ok' ? 'log-ok' : type === 'err' ? 'log-err' : 'log-info';
    log.insertAdjacentHTML('afterbegin', `<div class="log-entry"><span class="log-time">${{time}}</span><span class="${{cls}}">${{msg}}</span></div>`);
}}

// ── Toast ──
function showToast(msg, isError) {{
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show' + (isError ? ' error' : '');
    setTimeout(() => t.className = 'toast', 4000);
}}

// ── Workflow Deployment ──
const WORKFLOW_OPTIONS = [
    {{ id: 'architecture', label: '🏗️ Architecture Diagrams', desc: 'Auto-generate architecture diagrams on push', target: '.github/workflows/architecture.yml' }},
    {{ id: 'security-scan', label: '🔒 Security Scan', desc: 'SAST, dependency scanning, and container scanning', target: '.github/workflows/security-scan.yml' }},
];

function selectAndDeploy(presetWorkflow) {{
    // Select the repos from the action card, then open deploy modal
    const card = document.getElementById('deployCard');
    if (!card) return;
    let repos = [];
    try {{ repos = JSON.parse(card.dataset.repos || '[]'); }} catch {{}}
    if (!repos.length) return;

    // Check/select those repos in the table
    deselectAll();
    repos.forEach(name => {{
        const cb = document.querySelector(`input.repo-cb[data-repo="${{name}}"]`);
        if (cb) {{ cb.checked = true; cb.closest('tr').classList.add('selected'); }}
    }});
    updateToolbarState();

    // Open deploy modal with preset workflow
    showDeployModal(presetWorkflow);
}}

function showDeployModal(presetWorkflow) {{
    const repos = getSelected();
    if (!repos.length) {{ showToast('Select repos first', true); return; }}
    if (!ghToken) {{ showToast('Connect a GitHub token first', true); return; }}

    pendingAction = 'deploy';
    const overlay = document.getElementById('modalOverlay');
    const title = document.getElementById('modalTitle');
    const desc = document.getElementById('modalDesc');
    const list = document.getElementById('modalRepos');
    const warn = document.getElementById('modalWarning');
    const btn = document.getElementById('modalConfirm');

    title.textContent = '🚀 Deploy Workflow to ' + repos.length + ' repo(s)';
    desc.innerHTML = '<strong>Select a workflow to deploy:</strong>';

    // Build workflow selector
    let wfHtml = '<div class="wf-selector" id="wfSelector">';
    WORKFLOW_OPTIONS.forEach((wf, i) => {{
        const checked = presetWorkflow ? (wf.id === presetWorkflow) : (i === 0);
        const selClass = checked ? ' selected' : '';
        wfHtml += `<label class="wf-option${{selClass}}" data-wf="${{wf.id}}" onclick="selectWorkflow(this)">`;
        wfHtml += `<input type="radio" name="wf_choice" value="${{wf.id}}" ${{checked ? 'checked' : ''}}>`;
        wfHtml += `<div><div class="wf-label">${{wf.label}}</div>`;
        wfHtml += `<div class="wf-desc">${{wf.desc}}</div>`;
        wfHtml += `<div class="wf-target">→ ${{wf.target}}</div></div>`;
        wfHtml += '</label>';
    }});
    wfHtml += '</div>';

    // Build repo list
    wfHtml += '<div style="margin-top:12px;font-size:12px;color:var(--text-muted)">Target repos:</div>';
    list.innerHTML = repos.map(r => `<div>${{getRepoOwner(r)}}/${{r}}</div>`).join('');

    desc.innerHTML = '<strong>Select a workflow to deploy:</strong>' + wfHtml;
    warn.textContent = '';
    btn.className = 'btn-confirm';
    btn.style.background = 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))';
    btn.textContent = '🚀 Deploy Now';
    btn.disabled = false;
    overlay.classList.add('open');
}}

function selectWorkflow(el) {{
    document.querySelectorAll('.wf-option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    el.querySelector('input[type="radio"]').checked = true;
}}

function getSelectedWorkflow() {{
    const radio = document.querySelector('input[name="wf_choice"]:checked');
    return radio ? radio.value : 'architecture';
}}

// ── Execute (archive / delete / deploy) ──
async function executeAction() {{
    const repos = getSelected();
    if (!repos.length || !ghToken || !pendingAction) return;

    if (pendingAction === 'deploy') {{
        await executeDeploy(repos);
        return;
    }}

    const btn = document.getElementById('modalConfirm');
    btn.disabled = true;
    btn.textContent = 'Working...';
    const action = pendingAction;
    let success = 0, failed = 0;

    for (const repo of repos) {{
        try {{
            const repoOwner = getRepoOwner(repo);
            let res;
            if (action === 'archive') {{
                res = await fetch(`https://api.github.com/repos/${{repoOwner}}/${{repo}}`, {{
                    method: 'PATCH',
                    headers: {{ Authorization: 'token ' + ghToken, 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ archived: true }})
                }});
            }} else {{
                res = await fetch(`https://api.github.com/repos/${{repoOwner}}/${{repo}}`, {{
                    method: 'DELETE',
                    headers: {{ Authorization: 'token ' + ghToken }}
                }});
            }}
            if (res.ok || res.status === 204) {{
                success++;
                addLog('ok', `${{action === 'archive' ? '📦 Archived' : '🗑️ Deleted'}}: ${{repoOwner}}/${{repo}}`);
                const row = document.querySelector(`tr[data-repo="${{repo}}"]`);
                if (row) {{
                    if (action === 'delete') {{
                        row.style.opacity = '0.3';
                        row.querySelector('.repo-cb').disabled = true;
                        row.querySelector('.repo-cb').checked = false;
                    }} else {{
                        row.dataset.tier = 'ARCHIVED';
                        row.style.opacity = '0.5';
                        row.querySelector('.repo-cb').checked = false;
                    }}
                }}
            }} else {{
                const err = await res.json().catch(() => ({{}}));
                failed++;
                addLog('err', `Failed ${{repoOwner}}/${{repo}}: ${{res.status}} ${{err.message || ''}}`);
            }}
        }} catch(e) {{
            failed++;
            addLog('err', `Error ${{repoOwner}}/${{repo}}: ${{e.message}}`);
        }}
    }}

    closeModal();
    deselectAll();
    showToast(`${{action === 'archive' ? 'Archived' : 'Deleted'}} ${{success}}/${{repos.length}} repos` + (failed ? ` (${{failed}} failed)` : ''), failed > 0);
}}

async function executeDeploy(repos) {{
    const workflowId = getSelectedWorkflow();
    const wfInfo = WORKFLOW_OPTIONS.find(w => w.id === workflowId) || WORKFLOW_OPTIONS[0];
    const btn = document.getElementById('modalConfirm');
    const warn = document.getElementById('modalWarning');
    btn.disabled = true;
    btn.textContent = 'Deploying...';
    warn.innerHTML = '<div class="deploy-progress" id="deployProgress">Starting deploy...</div>';

    const progress = document.getElementById('deployProgress');

    // Group repos by owner so we can make one server call per owner
    const byOwner = {{}};
    repos.forEach(r => {{
        const o = getRepoOwner(r);
        if (!byOwner[o]) byOwner[o] = [];
        byOwner[o].push(r);
    }});

    try {{
        const useServer = (location.hostname !== '' && location.protocol !== 'file:');

        if (useServer) {{
            progress.textContent = `Deploying ${{wfInfo.label}} to ${{repos.length}} repo(s)...`;
            let allResults = [];
            let totalDeployed = 0;

            for (const [ownerKey, ownerRepos] of Object.entries(byOwner)) {{
                progress.textContent = `Deploying ${{wfInfo.label}} to ${{ownerRepos.length}} ${{ownerKey}} repo(s)...`;
                const resp = await fetch('/api/deploy-workflow', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + ghToken,
                    }},
                    body: JSON.stringify({{ owner: ownerKey, repos: ownerRepos, workflow: workflowId }}),
                }});
                const data = await resp.json();
                if (data.error) {{
                    ownerRepos.forEach(r => allResults.push({{ repo: r, owner: ownerKey, status: 'error', message: data.error }}));
                }} else if (data.results) {{
                    data.results.forEach(r => {{ r.owner = ownerKey; allResults.push(r); }});
                    totalDeployed += (data.deployed || 0);
                }}
            }}

            let html = '';
            allResults.forEach(r => {{
                const full = `${{r.owner}}/${{r.repo}}`;
                if (r.status === 'ok') {{
                    html += `<div class="dr-ok">✅ ${{full}} — ${{r.action || 'deployed'}}</div>`;
                    addLog('ok', `${{wfInfo.label}} deployed to ${{full}}`);
                }} else {{
                    html += `<div class="dr-err">❌ ${{full}} — ${{r.message || 'failed'}}</div>`;
                    addLog('err', `Failed ${{full}}: ${{r.message || 'unknown'}}`);
                }}
            }});
            progress.innerHTML = html;
            const allFailed = allResults.every(r => r.status !== 'ok');
            showToast(`Deployed ${{wfInfo.label}} to ${{totalDeployed}}/${{repos.length}} repos`, allFailed);
        }} else {{
            // Client-side fallback: direct GitHub API
            const templateMap = {{
                'architecture': 'architecture-standalone.yml',
                'security-scan': 'security-scan.yml',
            }};
            const templateFile = templateMap[workflowId] || 'architecture-standalone.yml';
            const templateUrl = `https://api.github.com/repos/${{DEFAULT_OWNER}}/ArchitectAIPro_GHActions/contents/.github/workflows/${{templateFile}}`;
            progress.textContent = 'Fetching workflow template...';
            const tResp = await fetch(templateUrl, {{ headers: {{ Authorization: 'token ' + ghToken }} }});
            if (!tResp.ok) {{ progress.innerHTML = '<div class="dr-err">❌ Could not fetch workflow template</div>'; return; }}
            const templateData = await tResp.json();
            const workflowContent = templateData.content;

            let deployed = 0;
            let html = '';
            for (let i = 0; i < repos.length; i++) {{
                const repo = repos[i];
                const repoOwner = getRepoOwner(repo);
                const full = `${{repoOwner}}/${{repo}}`;
                progress.textContent = `Deploying to ${{full}} (${{i+1}}/${{repos.length}})...`;
                try {{
                    const targetPath = wfInfo.target;
                    const checkUrl = `https://api.github.com/repos/${{repoOwner}}/${{repo}}/contents/${{targetPath}}`;
                    const chk = await fetch(checkUrl, {{ headers: {{ Authorization: 'token ' + ghToken }} }});
                    let sha = null;
                    if (chk.ok) {{ sha = (await chk.json()).sha; }}
                    const putBody = {{
                        message: `ci: deploy ${{workflowId}} workflow via CHAD dashboard [skip ci]`,
                        content: workflowContent,
                        committer: {{ name: 'CHAD Dashboard', email: 'chad-bot@bluefalconink.com' }},
                    }};
                    if (sha) putBody.sha = sha;
                    const putResp = await fetch(checkUrl, {{
                        method: 'PUT',
                        headers: {{ Authorization: 'token ' + ghToken, 'Content-Type': 'application/json' }},
                        body: JSON.stringify(putBody),
                    }});
                    if (putResp.ok) {{
                        deployed++;
                        const action = sha ? 'updated' : 'created';
                        html += `<div class="dr-ok">✅ ${{full}} — ${{action}}</div>`;
                        addLog('ok', `${{wfInfo.label}} deployed to ${{full}}`);
                    }} else {{
                        const err = await putResp.json().catch(() => ({{}}));
                        html += `<div class="dr-err">❌ ${{full}} — ${{err.message || putResp.status}}</div>`;
                        addLog('err', `Failed ${{full}}: ${{err.message || putResp.status}}`);
                    }}
                }} catch (e) {{
                    html += `<div class="dr-err">❌ ${{full}} — ${{e.message}}</div>`;
                }}
            }}
            progress.innerHTML = html;
            showToast(`Deployed ${{wfInfo.label}} to ${{deployed}}/${{repos.length}} repos`, deployed === 0);
        }}
    }} catch (e) {{
        progress.innerHTML = `<div class="dr-err">❌ ${{e.message}}</div>`;
        showToast('Deploy failed: ' + e.message, true);
        addLog('err', 'Deploy error: ' + e.message);
    }} finally {{
        btn.textContent = 'Done';
        setTimeout(() => {{ closeModal(); deselectAll(); }}, 2000);
    }}
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
