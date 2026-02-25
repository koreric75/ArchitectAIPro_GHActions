# 🔒 Security Policy — BlueFalconInk LLC

**Effective Date**: February 2026
**Applies To**: All repositories under [koreric75](https://github.com/koreric75) using the Architect AI Pro Standard.

---

## How We Handle Code Context

Architect AI Pro analyzes your codebase to generate architecture diagrams. This document outlines our security practices and how we protect your code.

---

## 🛡️ Data Handling

### What We Access

- **Repository file structure** (directories and filenames)
- **Source code** (to identify services, endpoints, and dependencies)
- **Configuration files** (e.g., `ARCHITECT_CONFIG.json`, `Dockerfile`, `docker-compose.yml`)
- **Infrastructure-as-Code** (Terraform, CloudFormation, Kubernetes manifests)

### What We Do NOT Store

- ❌ We do **not** store your source code beyond the diagram generation session
- ❌ We do **not** transmit code to unauthorized third parties
- ❌ We do **not** retain any secrets, credentials, or API keys found in your code
- ❌ We do **not** log or persist raw file contents

### AI Provider Data Policy

Architecture diagrams are generated via the **Google Gemini API** (`gemini-2.5-flash`). Code snippets sent to Gemini for diagram generation are subject to [Google's Gemini API data handling policy](https://ai.google.dev/gemini-api/terms). API-mode requests are **not used for model training** per Google's data governance terms.

---

## 🔐 Authentication & Secrets

### GitHub Actions

- All GCP authentication uses **Workload Identity Federation (WIF)** — no static JSON keys.
- GitHub Actions uses short-lived OIDC tokens to impersonate GCP service accounts.
- All secrets are stored in **GitHub Actions Secrets** and **Google Cloud Secret Manager** — never in repository code.

### Required Secrets

| Secret | Purpose | Storage Location |
|--------|---------|------------------|
| `GEMINI_API_KEY` | Google Gemini API for diagram generation | GitHub Actions Secrets (per repo) |
| `GH_PAT` | GitHub PAT for cross-repo audits (private repo visibility) | GitHub Actions Secrets (this repo) |
| `GCP_WIF_PROVIDER` | Workload Identity Federation provider reference | GitHub Actions Secrets |
| `GCP_SA_EMAIL` | Service account email for WIF impersonation | GitHub Actions Secrets |

### CHAD Dashboard

The CHAD advisory dashboard deployed on Cloud Run uses a `GITHUB_TOKEN` environment variable for the `/api/refresh` endpoint. This token:

- Is stored as a **Cloud Run environment variable** (encrypted at rest by GCP).
- Is a GitHub Personal Access Token (classic) with `repo`, `delete_repo`, and `workflow` scopes.
- Is **never exposed** to the browser. Dashboard interactive controls (archive/delete) require the user to enter their own PAT client-side, which is stored only in the browser's `localStorage` and sent directly to the GitHub API — it never transits through our server.

---

## 🏗️ Infrastructure Security

### Zero-Trust Architecture

- **No long-lived credentials**: WIF replaces static service account keys.
- **Least privilege**: Service accounts have only the permissions they need.
- **Attribute conditions**: The WIF pool only accepts OIDC tokens from repositories owned by the configured GitHub owner.
- **Secret rotation**: All secrets are versioned in Secret Manager; rotate regularly.

### Container Security

- All Docker images are built via **Google Cloud Build** and stored in **Artifact Registry** (`us-central1-docker.pkg.dev/bluefalconink/bluefalconink-apps/`).
- Base images use `python:3.11-slim` with minimal attack surface.
- No root processes in containers; Cloud Run enforces sandboxed execution.

### Network Security

- All Cloud Run services enforce **HTTPS-only** connections (TLS managed by Google).
- The CHAD dashboard is publicly accessible but read-only without a valid GitHub PAT.
- Write operations (archive/delete) require an authenticated PAT entered by the user.

---

## 📋 Compliance

### The Foreman Audit

Every architecture diagram is automatically audited for:

| Check | Description |
|-------|-------------|
| **Cloud provider alignment** | Prevents use of unapproved cloud services |
| **Security boundary presence** | Requires WAF/ALB in all public-facing architectures |
| **PCI compliance** | Payment services must be isolated in a separate boundary |
| **Data flow validation** | All connections between services must be explicitly documented |
| **Credential detection** | Flags hardcoded API keys, static JSON key files, and long-lived bearer tokens |

### Keyless Auth Enforcement

The Foreman flags any repository that contains:

- Static `GOOGLE_APPLICATION_CREDENTIALS` JSON files
- Hardcoded API keys or secrets in source code
- Long-lived bearer tokens

---

## 🐛 Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities.
2. Email **security@bluefalconink.com** with a detailed description.
3. We will acknowledge receipt within **48 hours**.
4. We aim to provide a fix within **7 business days**.

### Scope

This policy covers:
- The `ArchitectAIPro_GHActions` repository and all automation scripts
- The CHAD dashboard (Cloud Run service)
- The Architecture Gallery (Cloud Run service)
- All Terraform-managed infrastructure under the `bluefalconink` GCP project

---

## 📄 License

This security policy applies to all BlueFalconInk LLC repositories using the Architect AI Pro Standard.

**© BlueFalconInk LLC. All rights reserved.**
