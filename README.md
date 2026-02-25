# 🏗️ ArchitectAIPro GHActions — BlueFalconInk LLC Automation Hub

## "Documentation as Code, Governance as Service"

![Arch-Status](https://img.shields.io/badge/BlueFalconInk%20LLC-Standard-1E40AF)
![License](https://img.shields.io/badge/license-Proprietary-blue)
![Gemini](https://img.shields.io/badge/Powered%20by-Google%20Gemini-4285F4)
![Cloud Run](https://img.shields.io/badge/Deployed%20on-Cloud%20Run-34A853)

This repository is the **central automation hub** for all **BlueFalconInk LLC** projects. It contains the AI-driven architecture diagram pipeline, the CHAD advisory dashboard, agent orchestration workflows, and infrastructure-as-code — all governed by **Architect AI Pro**.

---

## Table of Contents

- [Overview](#-overview)
- [Architecture Diagram Pipeline](#-architecture-diagram-pipeline)
- [CHAD Advisory Dashboard](#-chad-advisory-dashboard)
- [The Foreman Audit Engine](#-the-foreman-audit-engine)
- [Repository Structure](#-repository-structure)
- [Flagships](#-the-bluefalconink-llc-flagships)
- [Quick Start](#-quick-start)
- [Global Standards](#-global-standards-architect_configjson)
- [Infrastructure & Governance](#-infrastructure--governance)
- [Market Positioning](#-market-positioning)

---

## 🔭 Overview

Every project in the BlueFalconInk LLC ecosystem follows an autonomous lifecycle:

1. **AI Synthesis** — On every push to `main`, **Architect AI Pro** scans the repo source code and calls the **Google Gemini API** to generate architecture diagrams in Mermaid.js, Draw.io XML, and PNG formats.
2. **The Foreman Audit** — A compliance engine audits the diagram against global "building codes" (cloud alignment, security subgraphs, brand identity).
3. **Self-Healing** — If violations are detected, a remediation loop calls Gemini again with the violation report to automatically correct the diagram.
4. **CHAD Orchestration** — A weekly agent pipeline audits all repositories for staleness, branding compliance, and architecture coverage, then publishes results to the CHAD advisory dashboard.

---

## 🧬 Architecture Diagram Pipeline

The core pipeline generates professional, standards-compliant architecture diagrams for any repo:

| Step | Description | Output |
|------|-------------|--------|
| 1. Source Scan | Scans repo code, configs, Dockerfiles, IaC | Context for Gemini |
| 2. Gemini Generation | Calls `gemini-2.5-flash` with domain-specific prompts | Mermaid.js code |
| 3. Draw.io Export | Converts Mermaid → Draw.io XML with branded styling | `.drawio` file |
| 4. PNG Rendering | Renders Draw.io XML → PNG via `drawio-desktop` (headless) | `.png` file |
| 5. Commit | Writes all outputs to `docs/` and commits to repo | `architecture.md`, `.drawio`, `.mermaid`, `.png` |

### Powered By

| Component | Technology |
|-----------|------------|
| AI Engine | Google Gemini (`gemini-2.5-flash`) via direct REST API |
| Live App | [Architect AI Pro](https://architect-ai-pro-mobile-edition-484078543321.us-west1.run.app/) on Cloud Run |
| Diagram Formats | Mermaid.js, Draw.io XML, PNG |
| Audit Engine | Foreman AI (Python) |
| Draw.io Renderer | `drawio-desktop` v24.7.17 (headless via `xvfb-run`) |

### Deployed Across All Active Repos

Architecture diagrams are auto-generated on push for these repositories:

| Repo | Status |
|------|--------|
| [ArchitectAIPro_GHActions](https://github.com/koreric75/ArchitectAIPro_GHActions) | ✅ Synced |
| [ArchitectAIPro](https://github.com/koreric75/ArchitectAIPro) | ✅ Synced |
| [ProposalBuddyAI](https://github.com/koreric75/ProposalBuddyAI) | ✅ Synced |
| [clipstream](https://github.com/koreric75/clipstream) | ✅ Synced |
| [polymath-hub](https://github.com/koreric75/polymath-hub) | ✅ Synced |
| [videogamedev](https://github.com/koreric75/videogamedev) | ✅ Synced |
| [BlueFalconInkLanding](https://github.com/koreric75/BlueFalconInkLanding) | ✅ Synced |

---

## 📊 CHAD Advisory Dashboard

**CHAD** (Centralized Hub for Architectural Decision-making) provides org-wide visibility into all repositories:

- **Live Dashboard**: [chad-dashboard on Cloud Run](https://chad-dashboard-42380604425.us-central1.run.app)
- **Weekly automated audits** via `chad-ops.yml` (every Monday 06:00 UTC)
- **On-demand refresh** via manual workflow dispatch or the `/api/refresh` endpoint

### Dashboard Features

| Feature | Description |
|---------|-------------|
| Repo Tiering | Automatic classification: Core, Active, Stale, Dead, Archived |
| Interactive Controls | Select repos → Archive or Delete directly from the dashboard |
| Token Connect | Enter a GitHub PAT to enable write operations (stored in browser only) |
| Activity Log | Timestamped record of all actions taken |
| Filter Buttons | Filter by tier: All, Core, Active, Stale, Dead, Forks |
| Monthly Burn Estimate | Per-repo cost estimation for GCP resources |

### CHAD Agent Scripts

| Script | Purpose |
|--------|---------|
| `repo_auditor.py` | Scans all repos via GitHub API for classification, staleness, branding, architecture coverage |
| `dashboard_generator.py` | Generates the interactive HTML dashboard from audit JSON |
| `cleanup_agent.py` | Automated archive, branding fix, config deployment (dry-run safe) |
| `token_budget.py` | API budget tracking across GitHub, Gemini, and CI minutes |

---

## 🛡️ The Foreman Audit Engine

The Foreman AI performs the following checks on every architecture diagram:

| Check | Level | Description |
|-------|-------|-------------|
| Cloud Provider Alignment | 🔴 Critical | Flags non-standard cloud providers |
| Security Layer | 🔴 Critical | Requires Cloud Armor / Load Balancer / Security subgraph |
| Mermaid Syntax | 🔴 Critical | Validates output is renderable |
| Branding | 📝 Note | Ensures BlueFalconInk LLC identity |
| Data Flow | ⚠️ Warning | Verifies directional arrows exist |
| CDN Presence | ⚠️ Warning | Required for content delivery |
| PCI Compliance | ⚠️ Warning | Payment boundary separation |

---

## 📂 Repository Structure

```
.
├── .github/
│   ├── workflows/
│   │   ├── arch-sync.yml                  # Reusable architecture sync workflow
│   │   ├── architecture-caller.yml        # Template: copy to your repo
│   │   ├── architecture-standalone.yml    # Self-contained diagram pipeline
│   │   ├── chad-ops.yml                   # CHAD agent orchestration (weekly)
│   │   └── deploy-infra.yml               # Terraform GitOps pipeline
│   └── scripts/
│       ├── generate_diagram.py            # Gemini API → Mermaid → Draw.io → PNG
│       ├── foreman_audit.py               # Compliance audit engine
│       ├── safety_check.py                # Quick safety check script
│       ├── production_readiness.py        # Production launch checklist
│       ├── repo_auditor.py                # CHAD: cross-repo audit agent
│       ├── dashboard_generator.py         # CHAD: interactive HTML dashboard
│       ├── cleanup_agent.py               # CHAD: auto-archive/branding agent
│       └── token_budget.py                # CHAD: API budget tracker
├── gallery/
│   ├── main.py                            # FastAPI Architecture Gallery
│   ├── templates/index.html               # Gallery frontend with Mermaid.js
│   ├── requirements.txt                   # Python dependencies
│   ├── Dockerfile                         # Container for Cloud Run
│   └── service.yaml                       # Knative service definition
├── terraform/
│   ├── main.tf                            # Core infrastructure (SA, Secrets)
│   ├── wif.tf                             # Workload Identity Federation
│   └── cloud_run.tf                       # Cloud Run service provisioning
├── PROMPT_LIBRARY/
│   ├── README.md                          # Prompt library overview
│   ├── saas.md                            # SaaS platform prompt
│   ├── video_streaming.md                 # Video/streaming prompt
│   ├── ai_ml_pipeline.md                  # AI/ML architecture prompt
│   ├── iot_telemetry.md                   # IoT/telemetry prompt
│   └── proposal_automation.md             # Proposal automation prompt
├── PLUGINS/
│   ├── README.md                          # Plugin overview
│   ├── mermaid_to_drawio.py               # Export to Draw.io XML
│   └── mermaid_to_excalidraw.py           # Export to Excalidraw JSON
├── docs/
│   ├── architecture.md                    # Auto-generated architecture diagram
│   ├── architecture.mermaid               # Raw Mermaid source
│   ├── architecture.drawio                # Draw.io XML
│   ├── architecture.png                   # Rendered PNG diagram
│   ├── audit_report.json                  # Latest CHAD audit report
│   └── dashboard.html                     # CHAD advisory dashboard (generated)
├── Dockerfile.dashboard                   # CHAD dashboard container image
├── cloudbuild-dashboard.yaml              # Cloud Build config for dashboard
├── dashboard-server.py                    # Flask server for Cloud Run dashboard
├── ARCHITECT_CONFIG.json                  # Global building codes
├── REMEDIATION_PROMPT.md                  # Self-healing prompt template
├── SECURITY.md                            # Security & code context policy
└── README.md                              # This file
```

---

## 🏢 The BlueFalconInk LLC Flagships

| Project | Domain | Description | Status |
|---------|--------|-------------|--------|
| [**ArchitectAI Pro**](https://github.com/koreric75/ArchitectAIPro) | Architecture/AI | The engine behind the BlueFalconInk LLC Standard | Active |
| [**ProposalBuddyAI**](https://github.com/koreric75/ProposalBuddyAI) | Automation/Bids | Ruthless Automation — 80% reduction in technical assessment drag | Active |
| [**Clipstream**](https://github.com/koreric75/clipstream) | Media/Video | Media engine for BlueFalconInk LLC | Active |
| [**polymath-hub**](https://github.com/koreric75/polymath-hub) | Platform | Central platform hub for BlueFalconInk services | Active |
| [**videogamedev**](https://github.com/koreric75/videogamedev) | Gaming/Dev | Game development and prototyping | Active |
| [**BlueFalconInkLanding**](https://github.com/koreric75/BlueFalconInkLanding) | Web | Corporate landing page | Active |

---

## 🚀 Quick Start

### Add Architecture Diagrams to Any Repo

1. Copy `.github/workflows/architecture-caller.yml` into your repo's `.github/workflows/` directory.
2. Add `GEMINI_API_KEY` to your repo's **Settings → Secrets and variables → Actions**.
3. Optionally add `ARCHITECT_CONFIG.json` to customize building codes.
4. Push code to `main` — the diagram auto-generates at `docs/architecture.md` (plus `.drawio`, `.mermaid`, and `.png`).

### Run the Generator Locally

```bash
# Set your Gemini API key
export GEMINI_API_KEY="your-key-here"

# Generate a diagram for the current repo
pip install requests
python .github/scripts/generate_diagram.py \
  --config ARCHITECT_CONFIG.json \
  --output docs/architecture.md \
  --scan-dir .
```

### Run CHAD Audit Locally

```bash
# Set your GitHub token
export GITHUB_TOKEN="your-github-pat"

# Audit all repos
pip install requests
python .github/scripts/repo_auditor.py \
  --owner koreric75 \
  --output docs/audit_report.json

# Generate dashboard
python .github/scripts/dashboard_generator.py \
  --input docs/audit_report.json \
  --output docs/dashboard.html
```

### Run Foreman Audits Locally

```bash
# Compliance audit
python .github/scripts/foreman_audit.py \
  --file docs/architecture.md \
  --config ARCHITECT_CONFIG.json

# Quick safety check
python .github/scripts/safety_check.py --file docs/architecture.md

# Production readiness
python .github/scripts/production_readiness.py --config ARCHITECT_CONFIG.json
```

### Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

---

## 🛠️ Global Standards (`ARCHITECT_CONFIG.json`)

All AI-generated diagrams adhere to these standards:

| Standard | Value |
|----------|-------|
| Primary Cloud | Google Cloud Platform (GCP) |
| Security Layer | Mandatory Cloud Armor, Load Balancer, VPC visualization |
| Container Runtime | Cloud Run (serverless) |
| Database Defaults | Cloud SQL (PostgreSQL), Firestore, Cloud Memorystore (Redis) |
| API Standard | REST / GraphQL |
| IaC Tool | Terraform |
| Diagram Output | Mermaid.js, Draw.io XML, PNG |
| Visual Identity | Dark theme, primary color `#1E40AF` (Blue Falcon Blue) |

---

## 🔒 Infrastructure & Governance

### GCP Project

| Resource | Value |
|----------|-------|
| Project ID | `bluefalconink` |
| Region | `us-central1` |
| Artifact Registry | `bluefalconink-apps` (Docker, `us-central1`) |
| Cloud Run: CHAD Dashboard | [chad-dashboard](https://chad-dashboard-42380604425.us-central1.run.app) |
| Cloud Run: Architect AI Pro | [architect-ai-pro](https://architect-ai-pro-mobile-edition-484078543321.us-west1.run.app/) |

### Security Model

- **Zero-Trust Auth**: Workload Identity Federation (WIF) for keyless GitHub Actions ↔ GCP communication.
- **Secret Management**: All API keys stored in GCP Secret Manager and GitHub Actions Secrets — never in code.
- **Least Privilege**: Service accounts have only the minimum required permissions.
- **Automated Auditing**: The Foreman flags hardcoded credentials, static JSON keys, and missing security boundaries.

### Required Secrets

| Secret | Purpose | Location |
|--------|---------|----------|
| `GEMINI_API_KEY` | Gemini API for diagram generation | GitHub Actions Secrets (per repo) |
| `GH_PAT` | Cross-repo audit access (private repos) | GitHub Actions Secrets (this repo) |
| `GCP_WIF_PROVIDER` | Workload Identity Federation provider | GitHub Actions Secrets |
| `GCP_SA_EMAIL` | Service account email for WIF | GitHub Actions Secrets |

---

## 🤝 Market Positioning

**Architect AI Pro** bridges the gap between the code editor and the executive boardroom:

> *"GitHub Copilot helps you write code; Architect AI Pro ensures you're building the right system."*

### Product Pillars

1. **The Digital Foreman** — Automated audit engine enforcing "Building Codes" on every PR
2. **Snapshot-to-XML** — Converting napkins/sketches into editable architecture
3. **Governance-as-Code** — GitHub Actions integration preventing "Architectural Drift"

### Tagline

> **Automated Governance. Living Blueprints. Ruthless Consistency.**

---

## 🎯 Our Philosophy

> *"If it isn't documented, it doesn't exist. If it isn't automated, it's technical debt."*

---

<p align="center">
  <strong>© BlueFalconInk LLC. All rights reserved.</strong><br>
  <sub>Powered by Architect AI Pro · Google Gemini · Google Cloud Run</sub>
</p>
