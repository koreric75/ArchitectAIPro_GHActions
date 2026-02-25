# 🏗️ Architect AI Pro — System Architecture

> **BlueFalconInk LLC** | [Live App](https://architect-ai-pro-mobile-edition-484078543321.us-west1.run.app/) | [GitHub Actions](https://github.com/koreric75/ArchitectAIPro_GHActions)

![BlueFalconInk LLC](https://img.shields.io/badge/BlueFalconInk%20LLC-Standard-1E40AF)
![Gemini](https://img.shields.io/badge/Powered%20by-Gemini%202.5%20Flash-4285F4)

## What This System Does

Architect AI Pro is a **GitHub Actions-based pipeline** that automatically generates, audits, and commits architecture diagrams for any repository. It has three main functions:

| # | Workflow | Trigger | What It Does |
|---|---------|---------|-------------|
| ① | **Diagram Generation** | Every push to `main` | Scans repo source → calls Gemini API → generates Mermaid diagram → audits for compliance → commits `docs/architecture.md` |
| ② | **CHAD Governance** | Weekly (Monday 06:00 UTC) | Audits all GitHub repos for health (staleness, branding, secrets) → generates advisory dashboard → optionally archives/cleans repos |
| ③ | **Security Scans** | Every push to `main` | Runs Bandit (SAST), pip-audit + Safety (dependencies), Trivy (containers) → uploads SARIF to GitHub Security tab |

Two Cloud Run services serve the generated artifacts:
- **CHAD Dashboard** (Flask) — Serves the audit dashboard + on-demand audit API
- **Architecture Gallery** (FastAPI) — Fetches and renders diagrams from all BlueFalconInk repos

---

## Architecture Diagram

The diagram below shows how data flows through each of the four workflows, and how they connect to each other and to deployed services.

![Architecture](architecture.png)

<details>
<summary>📄 View Mermaid Source</summary>

```mermaid
flowchart TB
    %% Architect AI Pro — System Architecture
    %% BlueFalconInk LLC

    %% ── FLOW 1: Diagram Generation Pipeline ──

    subgraph Flow1["① Diagram Generation — on every code push"]
        direction LR
        Push(["Developer pushes<br/>code to main"])
        Trigger["GitHub Actions<br/>arch-sync.yml"]
        Scan["generate_diagram.py<br/>Scans repo file tree"]
        Config[("ARCHITECT_CONFIG.json<br/>Building codes")]
        Guard["prompt_guard.py<br/>Sanitize + block injection"]
        Gemini(["Gemini 2.5 Flash<br/>Generates Mermaid"])
        Foreman["foreman_audit.py<br/>Compliance check"]
        Pass{"Audit<br/>passed?"}
        Fix["Auto-remediate<br/>via Gemini re-prompt"]
        Export["Export Plugins<br/>Draw.io, PNG, Excalidraw"]
        Save["Commit to repo<br/>docs/architecture.*"]

        Push --> Trigger --> Scan
        Config -.-> Scan
        Scan --> Guard --> Gemini --> Foreman --> Pass
        Pass -- Yes --> Export --> Save
        Pass -- No --> Fix --> Gemini
    end

    %% ── FLOW 2: CHAD Governance — Weekly ──

    subgraph Flow2["② CHAD Governance — weekly Monday 06:00 UTC"]
        direction LR
        Cron(["Scheduled or<br/>manual trigger"])
        Audit["repo_auditor.py<br/>Scan all GitHub repos"]
        GH(["GitHub API"])
        Report[("audit_report.json")]
        DashGen["dashboard_generator.py<br/>Build HTML dashboard"]
        HTML[("dashboard.html")]
        Clean["cleanup_agent.py<br/>Archive, fix branding"]
        SaveCHAD["Commit reports<br/>to repo"]

        Cron --> Audit --> GH --> Report
        Report --> DashGen --> HTML --> SaveCHAD
        Report --> Clean -.-> SaveCHAD
    end

    %% ── FLOW 3: Deployed Services ──

    subgraph Flow3["③ Cloud Run Services"]
        direction LR
        User(["Browser"])

        subgraph Dash["CHAD Dashboard — Flask"]
            DashApp["dashboard-server.py<br/>Audit dashboard + API"]
            DashData[("dashboard.html<br/>audit_report.json")]
        end

        subgraph Gallery["Arch Gallery — FastAPI"]
            GallApp["gallery/main.py<br/>Diagram viewer"]
            Cache[("In-memory cache<br/>10-min TTL")]
        end

        User -- dashboard URL --> DashApp --> DashData
        User -- gallery URL --> GallApp --> Cache
    end

    %% ── FLOW 4: Security Scans ──

    subgraph Flow4["④ Security Scans — on every push"]
        direction LR
        SPush(["Push to main"])
        SAST["Bandit SAST"]
        Deps["pip-audit + Safety"]
        Cont["Trivy container scan"]
        SARIF[("GitHub Security Tab<br/>SARIF reports")]

        SPush --> SAST --> SARIF
        SPush --> Deps --> SARIF
        SPush --> Cont --> SARIF
    end

    %% ── Cross-flow connections ──

    Save -.-> GallApp
    SaveCHAD -.-> DashApp
    DashApp -.-> Audit

    %% ── Infrastructure ──

    subgraph Infra["Infrastructure"]
        direction LR
        TF["Terraform"]
        AR[("Artifact Registry")]
        CB["Cloud Build"]
        TF -.-> AR
        CB --> AR
    end

    CB -.-> DashApp
    CB -.-> GallApp

    %% ── Styles ──

    classDef trigger fill:#F59E0B,color:#1F2937,stroke:#D97706,stroke-width:2px
    classDef process fill:#1E3A5F,color:#BFDBFE,stroke:#3B82F6
    classDef api fill:#7C3AED,color:#EDE9FE,stroke:#8B5CF6,stroke-width:2px
    classDef data fill:#0F172A,color:#E2E8F0,stroke:#475569
    classDef decide fill:#DC2626,color:#FEE2E2,stroke:#EF4444,stroke-width:2px
    classDef sec fill:#065F46,color:#D1FAE5,stroke:#10B981
    classDef infra fill:#374151,color:#F9FAFB,stroke:#6B7280

    class Push,Cron,User,SPush trigger
    class Trigger,Scan,Guard,Foreman,Fix,Export,Save process
    class Audit,DashGen,Clean,SaveCHAD,DashApp,GallApp process
    class Gemini,GH api
    class Config,Report,HTML,DashData,Cache,SARIF data
    class Pass decide
    class SAST,Deps,Cont sec
    class TF,AR,CB infra
```

</details>

---

## Key Components

### ① Diagram Generation Pipeline

| Script | Purpose |
|--------|---------|
| `generate_diagram.py` | Scans repo file tree, Dockerfiles, Terraform, API routes. Builds a context payload and sends it to Gemini 2.5 Flash to generate a Mermaid architecture diagram. |
| `prompt_guard.py` | Sanitizes repo content before sending to LLM. Detects prompt injection patterns, strips secrets. |
| `foreman_audit.py` | Validates the generated diagram against `ARCHITECT_CONFIG.json` building codes (GCP-only, Terraform, security boundaries, branding). |
| `plugin_loader.py` | Secure sandboxed execution of export plugins (Draw.io, Excalidraw) with SHA-256 hash verification. |

### ② CHAD Governance Agents

| Script | Purpose |
|--------|---------|
| `repo_auditor.py` | Scans all GitHub repos. Evaluates branding compliance, staleness, branch hygiene, secrets health. Produces `audit_report.json`. |
| `dashboard_generator.py` | Transforms audit data into an interactive HTML advisory dashboard with charts and per-repo scorecards. |
| `cleanup_agent.py` | Executes recommendations: archive stale repos, fix branding, deploy architecture workflows to unconfigured repos. Dry-run by default. |

### ③ Deployed Services

| Service | Stack | URL |
|---------|-------|-----|
| CHAD Dashboard | Flask 3.1 + Gunicorn on Cloud Run | `chad-dashboard-42380604425.us-central1.run.app` |
| Architecture Gallery | FastAPI 0.115 + uvicorn on Cloud Run | `architect-ai-pro-mobile-edition-484078543321.us-west1.run.app` |

### ④ Security

| Tool | Scope | Output |
|------|-------|--------|
| Bandit | Python SAST | SARIF → GitHub Security tab |
| pip-audit + Safety | Dependency CVEs | SARIF → GitHub Security tab |
| Trivy | Container image vulnerabilities | SARIF → GitHub Security tab |
| Dependabot | Automated dependency PRs | Weekly PRs for pip + GitHub Actions |

---

## 📋 Building Code Compliance

| Standard | Requirement | Status |
|----------|-------------|--------|
| Cloud Provider | GCP | ✅ Enforced |
| IaC | Terraform | ✅ Enforced |
| Orchestration | Cloud Run | ✅ Enforced |
| API Standard | REST/GraphQL | ✅ Enforced |
| Security Boundary | Required | ✅ Enforced |
| Brand Identity | BlueFalconInk LLC | ✅ Enforced |

---

*© BlueFalconInk LLC. All rights reserved. Automated Governance. Living Blueprints. Ruthless Consistency.*
