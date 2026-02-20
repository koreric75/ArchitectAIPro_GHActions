# 🏗️ The BlueFalconInk LLC Architecture Standard

## "Documentation as Code, Governance as Service"

![Arch-Status](https://img.shields.io/badge/BlueFalconInk%20LLC-Standard-1E40AF)
![License](https://img.shields.io/badge/license-Proprietary-blue)

This repository defines the automated architectural standards for all **BlueFalconInk LLC** projects. We leverage **Architect AI Pro** to ensure that every repository is born with professional, compliant, and synchronized technical blueprints.

---

## 🚀 The Workflow: "The Foreman"

Every project in the BlueFalconInk LLC ecosystem follows an autonomous lifecycle:

1. **Standardized Genesis**: New repositories are created from the `bluefalconink-template`, inheriting the core CI/CD pipeline and `ARCHITECT_CONFIG.json`.
2. **AI Synthesis**: Upon every push to `main`, **Architect AI Pro** scans the repo source code and calls the **Google Gemini API** directly to generate a Mermaid.js architecture diagram.
3. **The Foreman Audit**: Our "Foreman AI" script audits the diagram against our global building codes (Cloud provider alignment, security subgraphs, and brand identity).
4. **Self-Healing**: If a violation is detected, a remediation loop calls Gemini again with the violation report to automatically correct the diagram.
5. **Global Visibility**: Validated diagrams are instantly published to our [Architecture Gallery](https://arch.bluefalconink.com).

### Powered By

| Component | Technology |
|-----------|------------|
| AI Engine | Google Gemini (`gemini-2.5-flash`) via direct API |
| Live App | [Architect AI Pro](https://architect-ai-pro-mobile-edition-484078543321.us-west1.run.app/) on Cloud Run |
| Diagram Format | Mermaid.js (native GitHub rendering) |
| Audit Engine | Foreman AI (Python) |

---

## 🛠️ Global Standards (`ARCHITECT_CONFIG.json`)

To maintain consistency across our portfolio, all AI-generated diagrams must adhere to:

- **Primary Stack**: Google Cloud Platform (GCP)
- **Security First**: Mandatory Cloud Armor, Load Balancer, and VPC visualization for data layers.
- **Visual Identity**:
  - Theme: Dark
  - Primary Color: `#1E40AF` (Blue Falcon Blue)
- **Output Format**: Mermaid.js (native GitHub rendering)
- **Container Orchestration**: Cloud Run (serverless containers)
- **Database Standards**: Cloud SQL (PostgreSQL), Cloud Memorystore (Redis), Firestore
- **API Standard**: REST/GraphQL

---

## 🏢 The BlueFalconInk LLC Flagships

| Project | Domain | Description |
|---------|--------|-------------|
| **ArchitectAI Pro** | Architecture/AI | The engine behind the BlueFalconInk LLC Standard |
| **ProposalBuddyAI** | Automation/Bids | Ruthless Automation — 80% reduction in technical assessment drag |
| **Clipstream** | Media/RC Hobby | Media engine for @BlueFalconRCandMedia |
| **Instructional Video Site** | Education/SaaS | Subscription-based how-to videos: IT, Cooking, Music |

---

## 📂 Repository Structure

```
.
├── .github/
│   ├── workflows/
│   │   ├── arch-sync.yml              # Main workflow (standalone + reusable)
│   │   ├── architecture-caller.yml    # Template: copy to your repo
│   │   └── deploy-infra.yml           # Infrastructure GitOps pipeline
│   └── scripts/
│       ├── generate_diagram.py    # Gemini API diagram generator
│       ├── foreman_audit.py       # The Foreman - compliance audit engine
│       ├── safety_check.py        # Quick safety check script
│       └── production_readiness.py # Production launch checklist
├── gallery/
│   ├── main.py                    # FastAPI Architecture Gallery
│   ├── templates/index.html       # Gallery frontend with Mermaid.js
│   ├── requirements.txt           # Python dependencies
│   ├── Dockerfile                 # Container for Cloud Run
│   └── service.yaml               # Knative service definition
├── terraform/
│   ├── main.tf                    # Core infrastructure (SA, Secrets)
│   ├── wif.tf                     # Workload Identity Federation
│   └── cloud_run.tf               # Cloud Run service provisioning
├── PROMPT_LIBRARY/
│   ├── saas.md                    # SaaS platform prompt
│   ├── video_streaming.md         # Video/streaming prompt
│   ├── ai_ml_pipeline.md          # AI/ML architecture prompt
│   ├── iot_telemetry.md           # IoT/telemetry prompt
│   └── proposal_automation.md     # Proposal automation prompt
├── PLUGINS/
│   ├── mermaid_to_drawio.py       # Export to Draw.io XML
│   └── mermaid_to_excalidraw.py   # Export to Excalidraw JSON
├── docs/
│   └── architecture.md            # Auto-generated architecture diagram
├── ARCHITECT_CONFIG.json          # BlueFalconInk LLC building codes
├── REMEDIATION_PROMPT.md          # Self-healing prompt template
├── SECURITY.md                    # Security & code context policy
└── README.md                      # This file
```

---

## 🔒 Governance & Infrastructure

Our infrastructure is managed via **Terraform** using a GitOps model:

- **Zero-Trust**: We utilize Workload Identity Federation (WIF) for secure, keyless communication between GitHub Actions and Google Cloud Platform.
- **Scalability**: All automation is hosted on **Google Cloud Run**, ensuring a serverless, low-overhead management environment.
- **Secret Management**: All API keys (GitHub PAT, Architect AI API Key, Stripe Keys) are stored in Google Cloud Secret Manager — never in code.

---

## 🛡️ The "Foreman" Audit Engine

The Foreman AI performs the following checks on every architecture diagram:

| Check | Level | Description |
|-------|-------|-------------|
| Cloud Provider Alignment | 🔴 Critical | Flags non-standard cloud providers |
| Security Layer | 🔴 Critical | Requires Cloud Armor/Load Balancer/Security subgraph |
| Mermaid Syntax | 🔴 Critical | Validates output is renderable |
| Branding | 📝 Note | Ensures BlueFalconInk LLC identity |
| Data Flow | ⚠️ Warning | Verifies directional arrows exist |
| CDN Presence | ⚠️ Warning | Required for content delivery |
| PCI Compliance | ⚠️ Warning | Payment boundary separation |

---

## 🚀 Quick Start

### Add to Any BlueFalconInk Repo (Recommended)

1. Copy `.github/workflows/architecture-caller.yml` into your repo
2. Add `GEMINI_API_KEY` to your repo's **Settings → Secrets → Actions**
3. Optionally add `ARCHITECT_CONFIG.json` to customize building codes
4. Push code to `main` — the diagram auto-generates at `docs/architecture.md`
5. On PRs, a bot comment previews the diagram before merge

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

### Run Audits Locally

```bash
# Foreman compliance audit
python .github/scripts/foreman_audit.py --file docs/architecture.md --config ARCHITECT_CONFIG.json

# Quick safety check
python .github/scripts/safety_check.py --file docs/architecture.md

# Production readiness audit
python .github/scripts/production_readiness.py --config ARCHITECT_CONFIG.json

# Start the Gallery locally
cd gallery && pip install -r requirements.txt && uvicorn main:app --reload --port 8080
```

### Infrastructure Deployment

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

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

**© 2026 BlueFalconInk LLC. All Rights Reserved.**
