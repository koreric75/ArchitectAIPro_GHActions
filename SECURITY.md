# 🔒 Security Policy — Architect AI Pro

## How We Handle Code Context

Architect AI Pro analyzes your codebase to generate architecture diagrams. This document
outlines our security practices and how we protect your code.

---

## 🛡️ Data Handling

### What We Access

- **Repository file structure** (directories and filenames)
- **Source code** (to identify services, endpoints, and dependencies)
- **Configuration files** (e.g., `ARCHITECT_CONFIG.json`, `Dockerfile`, `docker-compose.yml`)
- **Infrastructure-as-Code** (Terraform, CloudFormation, Kubernetes manifests)

### What We Do NOT Store

- ❌ We do **not** store your source code beyond the diagram generation session
- ❌ We do **not** transmit code to third parties
- ❌ We do **not** retain any secrets, credentials, or API keys found in your code
- ❌ We do **not** log or persist raw file contents

---

## 🔐 Authentication & Secrets

### GitHub Actions

- All authentication uses **Workload Identity Federation (WIF)** — no static JSON keys
- GitHub Actions uses short-lived OIDC tokens to impersonate GCP service accounts
- All secrets are stored in **Google Cloud Secret Manager**, never in repository code

### Required Secrets

| Secret | Purpose | Storage |
|--------|---------|---------|
| `ARCHITECT_AI_API_KEY` | Architect AI Pro API authentication | GitHub Org Secrets / GCP Secret Manager |
| `GITHUB_PAT` | GitHub API access for cross-repo reads | GCP Secret Manager |
| `STRIPE_SECRET_KEY` | Stripe payment integration | GCP Secret Manager |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook verification | GCP Secret Manager |
| `GCP_WIF_PROVIDER` | WIF provider reference | GitHub Org Secrets |
| `GCP_SA_EMAIL` | Service account email | GitHub Org Secrets |

---

## 🏗️ Infrastructure Security

### Zero-Trust Architecture

- **No long-lived credentials**: WIF replaces static service account keys
- **Least privilege**: Service accounts have only the permissions they need
- **Attribute conditions**: WIF pool only accepts tokens from `bluefalconink` organization repos
- **Secret rotation**: All secrets are versioned in Secret Manager with rotation policies

### Network Security

- All Cloud Run services are deployed behind **Cloud Armor / WAF**
- Architecture Gallery is publicly accessible but read-only
- Admin endpoints require authenticated access

---

## 📋 Compliance

### The Foreman Audit

Every architecture diagram is automatically audited for:

- **Cloud provider alignment** — Prevents use of unapproved cloud services
- **Security boundary presence** — Requires WAF/ALB in all public-facing architectures
- **PCI compliance** — Payment services must be isolated in a separate boundary
- **Data flow validation** — All connections between services must be explicitly documented

### Keyless Auth Enforcement

The Foreman flags any repository that contains:
- Static `GOOGLE_APPLICATION_CREDENTIALS` JSON files
- Hardcoded API keys or secrets in source code
- Long-lived bearer tokens

---

## 🐛 Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

- **Email**: security@bluefalconink.com
- **Do NOT** open a public GitHub issue for security vulnerabilities
- We will acknowledge receipt within 48 hours
- We aim to provide a fix within 7 business days

---

## 📄 License

This security policy applies to all BlueFalconInk LLC repositories using the Architect AI Pro Standard.

**© 2026 BlueFalconInk LLC. All Rights Reserved.**
