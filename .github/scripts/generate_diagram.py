#!/usr/bin/env python3
"""
BlueFalconInk LLC — Architect AI Pro: Diagram Generator

Scans a repository's source code, reads ARCHITECT_CONFIG.json building codes,
and calls the Gemini API to generate a Mermaid.js architecture diagram.

This script powers the GitHub Action that auto-generates architecture diagrams
for any BlueFalconInk repo.

Usage:
    python generate_diagram.py \
        --config ARCHITECT_CONFIG.json \
        --output docs/architecture.md \
        --scan-dir . \
        [--remediate violations.txt]

Environment:
    GEMINI_API_KEY  — Google Gemini API key (required)
"""

import argparse
import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# File extensions we scan for architecture context
CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt",
    ".cs", ".rb", ".php", ".swift", ".dart", ".vue", ".svelte",
}
CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".env.example",
}
INFRA_FILES = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile", "Procfile", "serverless.yml", "serverless.yaml",
    "vercel.json", "netlify.toml", "fly.toml", "render.yaml",
    "cloudbuild.yaml", "appspec.yml",
}
INFRA_PATTERNS = {"*.tf", "*.tfvars", "*.hcl"}

# Directories to skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".next", ".nuxt", "dist",
    "build", "out", ".venv", "venv", "env", ".tox", "vendor",
    ".terraform", "coverage", ".nyc_output", ".cache",
}

MAX_FILE_SIZE = 50_000  # bytes — skip huge files
MAX_FILES_TO_SCAN = 80  # cap the number of files we send to Gemini
MAX_CONTEXT_CHARS = 120_000  # cap total context sent


# ---------------------------------------------------------------------------
# Repo Scanner
# ---------------------------------------------------------------------------

def scan_repo(root: str) -> dict:
    """Walk the repo and gather a file tree + key file contents."""
    root_path = Path(root).resolve()
    tree_lines = []
    file_contents = {}
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune skip dirs
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        rel_dir = Path(dirpath).relative_to(root_path)
        depth = len(rel_dir.parts)
        indent = "  " * depth
        dir_name = rel_dir.name or "."
        tree_lines.append(f"{indent}{dir_name}/")

        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            rel_path = fpath.relative_to(root_path)
            ext = fpath.suffix.lower()

            tree_lines.append(f"{indent}  {fname}")

            # Decide if we should read this file
            should_read = (
                ext in CODE_EXTENSIONS
                or ext in CONFIG_EXTENSIONS
                or fname in INFRA_FILES
                or fname.lower() in {"readme.md", "readme.rst", "readme.txt"}
                or fname.lower().startswith("package")
                or fname.lower() in {"requirements.txt", "pyproject.toml", "cargo.toml", "go.mod", "go.sum"}
                or any(fpath.match(p) for p in INFRA_PATTERNS)
            )

            if not should_read:
                continue
            if files_scanned >= MAX_FILES_TO_SCAN:
                continue
            if fpath.stat().st_size > MAX_FILE_SIZE:
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                total_chars = sum(len(c) for c in file_contents.values())
                if total_chars + len(content) > MAX_CONTEXT_CHARS:
                    # Truncate to fit
                    remaining = MAX_CONTEXT_CHARS - total_chars
                    if remaining > 500:
                        content = content[:remaining] + "\n... [truncated]"
                    else:
                        continue
                file_contents[str(rel_path)] = content
                files_scanned += 1
            except Exception:
                pass

    return {
        "tree": "\n".join(tree_lines),
        "files": file_contents,
    }


# ---------------------------------------------------------------------------
# Prompt Engineering
# ---------------------------------------------------------------------------

def build_system_prompt(config: dict) -> str:
    """Build the system instruction using ARCHITECT_CONFIG building codes."""
    org = config.get("org_name", "BlueFalconInk LLC")
    cloud = config.get("technical_constraints", {}).get("preferred_cloud", "AWS")
    iac = config.get("technical_constraints", {}).get("iac_tool", "Terraform")
    orch = config.get("technical_constraints", {}).get("container_orchestration", "Kubernetes")
    dbs = ", ".join(config.get("technical_constraints", {}).get("database_defaults", []))
    api_std = config.get("technical_constraints", {}).get("api_standard", "GraphQL")
    flagships = config.get("flagships", {})

    flagship_lines = ""
    for name, info in flagships.items():
        flagship_lines += f"  - {name}: {info.get('description', '')} (domain: {info.get('domain', '')})\n"

    compliance = config.get("compliance", {})
    compliance_rules = ""
    if compliance.get("require_security_subgraph"):
        compliance_rules += "  - MUST include a `subgraph Security` block.\n"
    if compliance.get("require_waf_alb_for_public"):
        compliance_rules += "  - All public endpoints MUST route through WAF/ALB/API Gateway.\n"
    if compliance.get("pci_compliance_for_payments"):
        compliance_rules += "  - Payment flows MUST be in an isolated `subgraph Payment` boundary.\n"
    if compliance.get("require_branding"):
        compliance_rules += f"  - Diagram title MUST include '{org}'.\n"
    if compliance.get("block_non_standard_providers"):
        compliance_rules += f"  - Only use {cloud} services. No mixing cloud providers.\n"

    return textwrap.dedent(f"""\
        You are Architect AI Pro — the official architecture diagram generator for {org}.

        YOUR ROLE:
        You analyze source code repositories and produce comprehensive, accurate Mermaid.js
        architecture diagrams that follow the {org} Building Code.

        BUILDING CODE STANDARDS:
        - Preferred Cloud: {cloud}
        - Infrastructure as Code: {iac}
        - Container Orchestration: {orch}
        - Database Defaults: {dbs}
        - API Standard: {api_std}

        FLAGSHIP PRODUCTS:
        {flagship_lines}

        COMPLIANCE RULES:
        {compliance_rules}

        OUTPUT REQUIREMENTS:
        1. Output ONLY a valid Mermaid.js code block wrapped in triple backticks with `mermaid` language identifier.
        2. The diagram MUST be a `graph TD` or `flowchart TD` (top-down) layout.
        3. Use `subgraph` blocks to group related components (Frontend, Backend, Database, Security, etc.).
        4. Show data flow arrows with descriptive labels.
        5. Include a comment at the top: `%% Generated by Architect AI Pro for {org}`
        6. The diagram title MUST include '{org}'.
        7. Keep the diagram readable — no more than 40 nodes. Group trivial files into service blocks.
        8. Identify the ACTUAL architecture from the source code — do not invent services that don't exist.
        9. Show external integrations (APIs, databases, queues, CDNs, auth providers) as distinct nodes.
        10. For subscription/payment services, show the Stripe/payment boundary clearly.

        DO NOT include any explanation, markdown headings, or text outside the mermaid code block.
        DO NOT wrap the output in any additional markdown formatting — ONLY the fenced mermaid block.
    """)


def build_user_prompt(scan_result: dict, repo_name: str) -> str:
    """Build the user prompt with repo context."""
    tree = scan_result["tree"]
    files = scan_result["files"]

    file_sections = ""
    for fpath, content in files.items():
        file_sections += f"\n--- {fpath} ---\n{content}\n"

    return textwrap.dedent(f"""\
        Analyze the following repository and generate its architecture diagram.

        REPOSITORY: {repo_name}

        FILE TREE:
        ```
        {tree}
        ```

        KEY FILE CONTENTS:
        {file_sections}

        Based on this codebase, generate a comprehensive Mermaid.js architecture diagram
        showing the system's components, data flows, external integrations, and security boundaries.
    """)


def build_remediation_prompt(violations: str, current_diagram: str, config: dict) -> str:
    """Build a remediation prompt when the current diagram failed audit."""
    org = config.get("org_name", "BlueFalconInk LLC")
    cloud = config.get("technical_constraints", {}).get("preferred_cloud", "AWS")

    return textwrap.dedent(f"""\
        The following architecture diagram FAILED the {org} Foreman compliance audit.

        CURRENT DIAGRAM:
        ```mermaid
        {current_diagram}
        ```

        VIOLATIONS DETECTED:
        {violations}

        REMEDIATION INSTRUCTIONS:
        1. Fix ALL violations listed above.
        2. Do NOT remove existing logic unless it directly conflicts with standards.
        3. Ensure valid Mermaid.js syntax that renders on GitHub.
        4. Add a `subgraph Security` block if missing.
        5. Replace non-standard cloud references with {cloud} equivalents.
        6. Ensure public endpoints route through WAF/ALB/API Gateway.
        7. Include '{org}' in the diagram title.
        8. For subscription services, ensure a clear `subgraph Payment` boundary.
        9. Add CDN (CloudFront) for content delivery paths.
        10. Add comment: `%% Remediated by Architect AI Pro Foreman`

        Output ONLY the corrected Mermaid.js code block. No explanations.
    """)


# ---------------------------------------------------------------------------
# Gemini API Caller
# ---------------------------------------------------------------------------

def call_gemini(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """Call the Gemini API and return the response text."""
    url = GEMINI_API_URL.format(model=GEMINI_MODEL)

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
            "topP": 0.95,
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    print(f"🤖 Calling Gemini ({GEMINI_MODEL})...")
    response = requests.post(url, json=payload, headers=headers, timeout=120)

    if response.status_code != 200:
        print(f"❌ Gemini API error: {response.status_code}")
        print(response.text[:1000])
        sys.exit(1)

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        print("❌ No candidates returned from Gemini")
        print(json.dumps(data, indent=2)[:1000])
        sys.exit(1)

    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    if not text:
        print("❌ Empty response from Gemini")
        sys.exit(1)

    return text


# ---------------------------------------------------------------------------
# Output Processing
# ---------------------------------------------------------------------------

def extract_mermaid(text: str) -> str:
    """Extract the Mermaid code block from the Gemini response."""
    # Try to find ```mermaid ... ```
    pattern = r"```mermaid\s*\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find bare mermaid content (starts with graph/flowchart)
    for prefix in ["graph ", "flowchart ", "sequenceDiagram", "classDiagram", "erDiagram"]:
        if prefix in text:
            start = text.index(prefix)
            # Find the end (next ``` or end of text)
            end = text.find("```", start)
            if end == -1:
                end = len(text)
            return text[start:end].strip()

    # Last resort — return as-is
    return text.strip()


def format_output(mermaid_code: str, repo_name: str, config: dict) -> str:
    """Format the Mermaid diagram into a complete architecture.md document."""
    org = config.get("org_name", "BlueFalconInk LLC")

    return textwrap.dedent(f"""\
        # 🏗️ Architecture Diagram — {repo_name}

        > Auto-generated by **Architect AI Pro** for **{org}**
        > Last updated: {{{{ date }}}}

        ```mermaid
        {mermaid_code}
        ```

        ---

        ## Building Code Compliance

        | Standard | Requirement |
        |----------|-------------|
        | Cloud Provider | {config.get('technical_constraints', {}).get('preferred_cloud', 'AWS')} |
        | IaC | {config.get('technical_constraints', {}).get('iac_tool', 'Terraform')} |
        | Orchestration | {config.get('technical_constraints', {}).get('container_orchestration', 'Kubernetes')} |
        | API Standard | {config.get('technical_constraints', {}).get('api_standard', 'GraphQL')} |
        | Security Boundary | Required |
        | WAF/ALB for Public | Required |

        ---

        *Generated by [Architect AI Pro](https://github.com/koreric75/ArchitectAIPro_GHActions) — {org} Standard*
    """).replace("{{ date }}", __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M UTC"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Architect AI Pro — Diagram Generator")
    parser.add_argument("--config", required=True, help="Path to ARCHITECT_CONFIG.json")
    parser.add_argument("--output", required=True, help="Output path (e.g., docs/architecture.md)")
    parser.add_argument("--scan-dir", default=".", help="Root directory to scan (default: .)")
    parser.add_argument("--repo-name", default=None, help="Repository name (auto-detected from git if omitted)")
    parser.add_argument("--remediate", default=None, help="Path to violations file for remediation mode")
    args = parser.parse_args()

    # Get API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        sys.exit(1)

    # Load config
    print(f"📋 Loading config from {args.config}")
    config = json.loads(Path(args.config).read_text())

    # Detect repo name
    repo_name = args.repo_name
    if not repo_name:
        repo_name = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1]
    if not repo_name:
        repo_name = Path(args.scan_dir).resolve().name
    print(f"📦 Repository: {repo_name}")

    # Build system prompt
    system_prompt = build_system_prompt(config)

    if args.remediate:
        # Remediation mode
        print("🔧 Running in REMEDIATION mode")
        violations = Path(args.remediate).read_text()
        current_diagram = ""
        if Path(args.output).exists():
            content = Path(args.output).read_text()
            mermaid_match = re.search(r"```mermaid\s*\n(.*?)```", content, re.DOTALL)
            if mermaid_match:
                current_diagram = mermaid_match.group(1)
        user_prompt = build_remediation_prompt(violations, current_diagram, config)
    else:
        # Normal generation mode
        print(f"🔍 Scanning {args.scan_dir} for source code...")
        scan_result = scan_repo(args.scan_dir)
        print(f"   📁 File tree: {len(scan_result['tree'].splitlines())} entries")
        print(f"   📄 Files read: {len(scan_result['files'])}")
        user_prompt = build_user_prompt(scan_result, repo_name)

    # Call Gemini
    response_text = call_gemini(system_prompt, user_prompt, api_key)

    # Extract and format
    mermaid_code = extract_mermaid(response_text)

    if not mermaid_code:
        print("❌ Failed to extract Mermaid diagram from response")
        print("Raw response (first 2000 chars):")
        print(response_text[:2000])
        sys.exit(1)

    print(f"✅ Generated Mermaid diagram ({len(mermaid_code)} chars)")

    # Validate basic Mermaid syntax
    valid_starts = ["graph ", "flowchart ", "sequenceDiagram", "classDiagram", "erDiagram", "%%"]
    if not any(mermaid_code.lstrip().startswith(s) for s in valid_starts):
        print("⚠️  Warning: Diagram may not start with valid Mermaid syntax")

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    full_doc = format_output(mermaid_code, repo_name, config)
    output_path.write_text(full_doc)
    print(f"📄 Written to {args.output}")

    # Also write raw mermaid for other tools
    raw_path = output_path.with_suffix(".mermaid")
    raw_path.write_text(mermaid_code)
    print(f"📄 Raw Mermaid written to {raw_path}")

    print("🏁 Done!")


if __name__ == "__main__":
    main()
