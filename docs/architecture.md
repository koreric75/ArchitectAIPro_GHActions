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
%% Architect AI Pro — System Architecture
%% BlueFalconInk LLC | https://github.com/koreric75/ArchitectAIPro_GHActions
%%
%% This diagram shows the three main workflows:
%%   1. Architecture Diagram Generation (the core product)
%%   2. CHAD Weekly Governance (automated repo health)
%%   3. Deployed Web Services (dashboard + gallery)

flowchart TB

    %% =====================================================================
    %% FLOW 1: Architecture Diagram Generation Pipeline
    %% This is the core product — auto-generates architecture diagrams
    %% for any repo on every code push to main.
    %% =====================================================================

    subgraph Flow1["① Diagram Generation Pipeline — runs on every code push"]
        direction LR

        Push([Developer pushes code to main])
        Trigger[GitHub Actions\narch-sync.yml]
        Scan[generate_diagram.py\nScans repo: file tree,\nDockerfiles, Terraform,\nAPI routes, configs]
        Config[(ARCHITECT_CONFIG.json\nBuilding codes: GCP only,\nTerraform, Cloud Run,\nsecurity boundaries)]
        PromptGuard[prompt_guard.py\nSanitize input,\nblock injection]
        Gemini([Gemini 2.5 Flash API\nGenerates Mermaid diagram\nfrom repo context])
        Foreman[foreman_audit.py\nCompliance check:\ncloud provider, branding,\nsecurity layers, IaC]
        Pass{Audit\npassed?}
        Remediate[Auto-remediate\nvia Gemini re-prompt\nwith violation report]
        Plugins[Export Plugins\nDraw.io XML, PNG,\nExcalidraw JSON]
        Commit[Commit to repo:\ndocs/architecture.md\ndocs/architecture.mermaid\ndocs/architecture.png]

        Push --> Trigger
        Trigger --> Scan
        Config -.->|building codes| Scan
        Scan --> PromptGuard
        PromptGuard --> Gemini
        Gemini --> Foreman
        Foreman --> Pass
        Pass -->|Yes| Plugins
        Pass -->|No| Remediate
        Remediate --> Gemini
        Plugins --> Commit
    end

    %% =====================================================================
    %% FLOW 2: CHAD Governance — Weekly Automated Repo Health
    %% Audits ALL repos, generates an advisory dashboard, and
    %% optionally cleans up stale repos.
    %% =====================================================================

    subgraph Flow2["② CHAD Governance — runs weekly on Monday 06:00 UTC"]
        direction LR

        Cron([Weekly schedule or\nmanual dispatch])
        Auditor[repo_auditor.py\nScans all GitHub repos:\nbranding, staleness,\nbranch hygiene, secrets]
        GHAPI([GitHub API\nFetch repo metadata,\nfile contents, commits])
        AuditReport[(audit_report.json\nPer-repo scores,\nrecommendations)]
        DashGen[dashboard_generator.py\nBuilds interactive HTML\nwith charts and tables]
        DashHTML[(dashboard.html\nAdvisory dashboard)]
        Cleanup[cleanup_agent.py\nArchive stale repos,\nfix branding, deploy\nworkflows to new repos]
        CommitCHAD[Commit reports to\nArchitectAIPro_GHActions\nrepo]

        Cron --> Auditor
        Auditor --> GHAPI
        GHAPI --> AuditReport
        AuditReport --> DashGen
        DashGen --> DashHTML
        AuditReport --> Cleanup
        DashHTML --> CommitCHAD
        Cleanup -.->|dry-run by default| CommitCHAD
    end

    %% =====================================================================
    %% FLOW 3: Deployed Services on GCP Cloud Run
    %% =====================================================================

    subgraph Flow3["③ Deployed Services — GCP Cloud Run"]
        direction LR

        Browser([User opens browser])

        subgraph DashSvc["CHAD Dashboard — Flask on Cloud Run"]
            DashApp[dashboard-server.py\nServes audit dashboard\nand on-demand audit API]
            DashStatic[(docs/dashboard.html\ndocs/audit_report.json)]
        end

        subgraph GallerySvc["Architecture Gallery — FastAPI on Cloud Run"]
            GalleryApp[gallery/main.py\nFetches diagrams from\nall BlueFalconInk repos\nvia GitHub API]
            GalleryCache[(In-memory cache\n10-min TTL)]
        end

        Browser -->|chad-dashboard URL| DashApp
        DashApp --> DashStatic
        Browser -->|gallery URL| GalleryApp
        GalleryApp --> GalleryCache
    end

    %% =====================================================================
    %% FLOW 4: Security Scanning — runs on every push
    %% =====================================================================

    subgraph Flow4["④ Security Scans — runs on every push"]
        direction LR

        SecPush([Push to main])
        SAST[Bandit\nPython SAST]
        DepScan[pip-audit + Safety\nDependency CVEs]
        ContScan[Trivy\nContainer image scan]
        SARIF[(GitHub Security Tab\nSARIF reports)]

        SecPush --> SAST
        SecPush --> DepScan
        SecPush --> ContScan
        SAST --> SARIF
        DepScan --> SARIF
        ContScan --> SARIF
    end

    %% =====================================================================
    %% Cross-flow connections
    %% =====================================================================

    Commit -.->|architecture files\nserved by gallery| GalleryApp
    CommitCHAD -.->|dashboard + audit data\nserved by dashboard| DashApp
    DashApp -.->|can trigger\non-demand audit| Auditor

    %% =====================================================================
    %% Infrastructure (shared context)
    %% =====================================================================

    subgraph Infra["Infrastructure"]
        direction LR
        TF[Terraform\ncloud_run.tf, wif.tf]
        AR[(Artifact Registry\nDocker images)]
        CB[Cloud Build\nci/cd for containers]

        TF -.-> AR
        CB --> AR
    end

    CB -.->|deploy| DashApp
    CB -.->|deploy| GalleryApp

    %% =====================================================================
    %% Styles
    %% =====================================================================

    classDef trigger fill:#F59E0B,color:#1F2937,stroke:#D97706,stroke-width:2px
    classDef process fill:#1E3A5F,color:#BFDBFE,stroke:#3B82F6,stroke-width:1px
    classDef external fill:#7C3AED,color:#EDE9FE,stroke:#8B5CF6,stroke-width:2px
    classDef data fill:#0F172A,color:#E2E8F0,stroke:#475569,stroke-width:1px
    classDef decision fill:#DC2626,color:#FEE2E2,stroke:#EF4444,stroke-width:2px
    classDef security fill:#065F46,color:#D1FAE5,stroke:#10B981,stroke-width:1px
    classDef infra fill:#374151,color:#F9FAFB,stroke:#6B7280,stroke-width:1px

    class Push,Cron,Browser,SecPush trigger
    class Trigger,Scan,PromptGuard,Foreman,Remediate,Plugins,Commit process
    class Auditor,DashGen,Cleanup,CommitCHAD,DashApp,GalleryApp process
    class Gemini,GHAPI external
    class Config,AuditReport,DashHTML,DashStatic,GalleryCache,SARIF data
    class Pass decision
    class SAST,DepScan,ContScan security
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
