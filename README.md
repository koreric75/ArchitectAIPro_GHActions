# 🏗️ The BlueFalconInk Architecture Standard

## "Documentation as Code, Governance as Service"

![Arch-Status](https://img.shields.io/badge/BlueFalconInk-Standard-1E40AF)
![License](https://img.shields.io/badge/license-Proprietary-blue)

This repository defines the automated architectural standards for all **BlueFalconInk** projects. We leverage **Architect AI Pro** to ensure that every repository is born with professional, compliant, and synchronized technical blueprints.

---

## 🚀 The Workflow: "The Foreman"

Every project in the BlueFalconInk ecosystem follows an autonomous lifecycle:

1. **Standardized Genesis**: New repositories are created from the `bluefalconink-template`, inheriting the core CI/CD pipeline and `ARCHITECT_CONFIG.json`.
2. **AI Synthesis**: Upon every push to `main`, **Architect AI Pro** analyzes the codebase and generates a Mermaid.js architecture diagram.
3. **The Foreman Audit**: Our "Foreman AI" script audits the diagram against our global building codes (Cloud provider alignment, security subgraphs, and brand identity).
4. **Self-Healing**: If a violation is detected, a remediation loop triggers to automatically correct the diagram and re-submit it for approval.
5. **Global Visibility**: Validated diagrams are instantly published to our [Architecture Gallery](https://arch.bluefalconink.com).

---

## 🛠️ Global Standards (`ARCHITECT_CONFIG.json`)

To maintain consistency across our portfolio, all AI-generated diagrams must adhere to:

- **Primary Stack**: AWS (Amazon Web Services)
- **Security First**: Mandatory WAF, ALB, and Private Subnet visualization for data layers.
- **Visual Identity**:
  - Theme: Dark
  - Primary Color: `#1E40AF` (Blue Falcon Blue)
- **Output Format**: Mermaid.js (native GitHub rendering)
- **Container Orchestration**: Kubernetes (EKS)
- **Database Standards**: PostgreSQL, Redis
- **API Standard**: GraphQL

---

## 🏢 The BlueFalconInk Flagships

| Project | Domain | Description |
|---------|--------|-------------|
| **ArchitectAI Pro** | Architecture/AI | The engine behind the BlueFalconInk Standard |
| **ProposalBuddyAI** | Automation/Bids | Ruthless Automation — 80% reduction in technical assessment drag |
| **Clipstream** | Media/RC Hobby | Media engine for @BlueFalconRCandMedia |
| **Instructional Video Site** | Education/SaaS | Subscription-based how-to videos: IT, Cooking, Music |

---

## 📂 Repository Structure

```
.
├── .github/
│   ├── workflows/
│   │   ├── arch-sync.yml          # Architecture diagram automation
│   │   └── deploy-infra.yml       # Infrastructure GitOps pipeline
│   └── scripts/
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
├── ARCHITECT_CONFIG.json          # BlueFalconInk building codes
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
| Security Layer | 🔴 Critical | Requires WAF/ALB/Security subgraph |
| Mermaid Syntax | 🔴 Critical | Validates output is renderable |
| Branding | 📝 Note | Ensures BlueFalconInk identity |
| Data Flow | ⚠️ Warning | Verifies directional arrows exist |
| CDN Presence | ⚠️ Warning | Required for content delivery |
| PCI Compliance | ⚠️ Warning | Payment boundary separation |

---

## 🚀 Quick Start

### For New Repositories

1. Create from the `bluefalconink-template`
2. Push code to `main`
3. The workflow auto-generates `docs/architecture.md`
4. The Foreman audits compliance
5. Diagram appears in the [Gallery](https://arch.bluefalconink.com)

### For Local Development

```bash
# Run the Foreman audit locally
python .github/scripts/foreman_audit.py --file docs/architecture.md --config ARCHITECT_CONFIG.json

# Run the safety check
python .github/scripts/safety_check.py --file docs/architecture.md

# Run production readiness audit
python .github/scripts/production_readiness.py --config ARCHITECT_CONFIG.json

# Start the Gallery locally
cd gallery
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
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

**© 2026 BlueFalconInk. All Rights Reserved.**
