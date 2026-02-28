#!/usr/bin/env python3
"""
BlueFalconInk LLC Foreman AI - Architecture Audit Script

The "Foreman" ensures every generated architecture diagram complies with
the BlueFalconInk LLC Building Code defined in ARCHITECT_CONFIG.json.

Usage:
    python foreman_audit.py --file docs/architecture.md --config ARCHITECT_CONFIG.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict


class Violation:
    """Represents a single compliance violation."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    NOTE = "NOTE"

    def __init__(self, level: str, category: str, message: str, remediation: str = ""):
        self.level = level
        self.category = category
        self.message = message
        self.remediation = remediation

    def __str__(self):
        icons = {self.CRITICAL: "❌", self.WARNING: "⚠️", self.NOTE: "📝"}
        return f"{icons.get(self.level, '❓')} [{self.level}] {self.category}: {self.message}"


def load_config(config_path: str) -> dict:
    """Load and validate the ARCHITECT_CONFIG.json."""
    with open(config_path, "r") as f:
        return json.load(f)


def load_diagram(file_path: str) -> str:
    """Load the architecture diagram content."""
    with open(file_path, "r") as f:
        return f.read()


def check_cloud_provider_alignment(diagram: str, config: dict) -> List[Violation]:
    """Check 1: Ensure only the preferred cloud provider is referenced."""
    violations = []
    preferred = config.get("technical_constraints", {}).get("preferred_cloud", "GCP")

    non_standard_providers = {
        "AWS": ["Azure", "Google Cloud", "GCP", "DigitalOcean", "Heroku"],
        "Azure": ["AWS", "Amazon", "Google Cloud", "GCP", "DigitalOcean"],
        "GCP": ["AWS", "Amazon", "Azure", "DigitalOcean", "Heroku"],
    }

    blocklist = non_standard_providers.get(preferred, [])
    for provider in blocklist:
        if provider.lower() in diagram.lower():
            violations.append(
                Violation(
                    Violation.CRITICAL,
                    "Cloud Provider",
                    f"Found '{provider}' components in a {preferred}-mandated project.",
                    f"Replace all {provider} references with equivalent {preferred} services.",
                )
            )

    return violations


def check_security_layer(diagram: str, config: dict) -> List[Violation]:
    """Check 2: Ensure a Security boundary/subgraph exists."""
    violations = []
    rules = config.get("diagram_rules", {})
    compliance = config.get("compliance", {})

    if rules.get("include_security_layer") or compliance.get("require_security_subgraph"):
        security_patterns = [
            r"subgraph\s+Security",
            r"subgraph\s+.*[Ss]ecurity",
            r"Cloud Armor",
            r"Firewall",
            r"WAF",
            r"Load Balancer",
            r"IAP",
            r"Identity.Aware.Proxy",
        ]
        has_security = any(re.search(p, diagram) for p in security_patterns)
        if not has_security:
            violations.append(
                Violation(
                    Violation.CRITICAL,
                    "Security",
                    "No explicit 'Security' boundary found in architecture.",
                    "Add a 'subgraph SecuritySG [\"Security\"]' block containing Cloud Armor, Load Balancer, or firewall components.",
                )
            )

    # Check for Cloud Armor / LB on public endpoints
    if compliance.get("require_cloud_armor_for_public") or compliance.get("require_waf_alb_for_public"):
        if "Public" in diagram or "Internet" in diagram:
            security_terms = ["Cloud Armor", "Load Balancer", "WAF", "ALB", "IAP"]
            has_protection = any(term in diagram for term in security_terms)
            if not has_protection:
                violations.append(
                    Violation(
                        Violation.WARNING,
                        "Security",
                        "Public-facing endpoints detected without Cloud Armor or Load Balancer protection.",
                        "Add Cloud Armor and/or a Load Balancer between public traffic and application services.",
                    )
                )

    return violations


def check_branding(diagram: str, config: dict) -> List[Violation]:
    """Check 3: Ensure BlueFalconInk LLC + Architect AI Pro branding elements are present."""
    violations = []
    compliance = config.get("compliance", {})
    org_name = config.get("org_name", "BlueFalconInk LLC")

    if compliance.get("require_branding"):
        # --- Check 3a: Organization name must appear ---
        if org_name not in diagram and "BlueFalcon" not in diagram:
            violations.append(
                Violation(
                    Violation.CRITICAL,
                    "Branding — Organization",
                    f"Diagram is missing {org_name} branding elements.",
                    f"Add '{org_name}' as a title or annotation in the diagram.",
                )
            )

        # --- Check 3b: Architect AI Pro attribution must appear ---
        if "Architect AI Pro" not in diagram:
            violations.append(
                Violation(
                    Violation.WARNING,
                    "Branding — Tool Attribution",
                    "Diagram is missing Architect AI Pro attribution.",
                    "Add '%% Generated by Architect AI Pro | BlueFalconInk LLC' as a comment, "
                    "and include a FOOTER node: FOOTER[\"🏗️ Created with Architect AI Pro | BlueFalconInk LLC\"]",
                )
            )

        # --- Check 3c: Brand color (#1E40AF) must be applied ---
        if "#1E40AF" not in diagram and "#1e40af" not in diagram:
            violations.append(
                Violation(
                    Violation.WARNING,
                    "Branding — Color Identity",
                    f"Diagram is missing the {org_name} brand color (#1E40AF — Blue Falcon Blue).",
                    "Apply 'style SecuritySG fill:#1E40AF,color:#BFDBFE' to the Security subgraph.",
                )
            )

    return violations


def check_data_flow(diagram: str, config: dict) -> List[Violation]:
    """Check 4: Ensure data flow arrows are present when required."""
    violations = []
    rules = config.get("diagram_rules", {})

    if rules.get("show_data_flow"):
        flow_patterns = [r"-->", r"==>", r"-.->", r"-->>"]
        has_flow = any(re.search(p, diagram) for p in flow_patterns)
        if not has_flow:
            violations.append(
                Violation(
                    Violation.WARNING,
                    "Data Flow",
                    "No data flow connections detected in the diagram.",
                    "Add directional arrows (-->, ==>) to show data flow between components.",
                )
            )

    return violations


def check_subscription_compliance(diagram: str, config: dict) -> List[Violation]:
    """Check 5: Validate subscription-service specific requirements."""
    violations = []
    flagships = config.get("flagships", {})

    for name, flagship in flagships.items():
        subscription = flagship.get("subscription", {})
        if not subscription:
            continue

        # Check for CDN requirement
        if subscription.get("require_cdn"):
            cdn_patterns = ["CloudFront", "CDN", "Cloud CDN", "Fastly"]
            has_cdn = any(p.lower() in diagram.lower() for p in cdn_patterns)
            if not has_cdn:
                violations.append(
                    Violation(
                        Violation.WARNING,
                        "Performance",
                        f"No CDN detected for subscription service '{name}'.",
                        "Add Cloud CDN or equivalent CDN for low-latency content delivery.",
                    )
                )

        # Check for security boundary around payment
        if subscription.get("require_security_boundary"):
            if subscription.get("provider", "").lower() in diagram.lower():
                if "subgraph" not in diagram.lower():
                    violations.append(
                        Violation(
                            Violation.WARNING,
                            "PCI Compliance",
                            f"Payment provider '{subscription['provider']}' found without security boundary.",
                            "Wrap payment components in a dedicated 'subgraph PaymentSG [\"Payment\"]' boundary.",
                        )
                    )

    return violations


def check_mermaid_validity(diagram: str) -> List[Violation]:
    """Check 6: Basic Mermaid syntax validation."""
    violations = []

    # Check for mermaid code block
    if "```mermaid" not in diagram and "graph " not in diagram and "flowchart " not in diagram:
        violations.append(
            Violation(
                Violation.CRITICAL,
                "Syntax",
                "No valid Mermaid diagram syntax detected.",
                "Ensure the diagram starts with a Mermaid diagram type (graph, flowchart, C4Context, etc.).",
            )
        )

    return violations


def generate_report(violations: List[Violation], repo_name: str = "") -> str:
    """Generate the Foreman Inspection Report."""
    critical_count = sum(1 for v in violations if v.level == Violation.CRITICAL)
    warning_count = sum(1 for v in violations if v.level == Violation.WARNING)
    note_count = sum(1 for v in violations if v.level == Violation.NOTE)

    status = "🟢 Passed" if critical_count == 0 else "🔴 Failed Inspection"

    report = f"""
### 🏗️ Foreman AI Inspection Report

**Project:** `{repo_name or 'Unknown'}`
**Status:** {status}
**Violations:** {critical_count} Critical | {warning_count} Warnings | {note_count} Notes

---

"""
    if violations:
        report += "**Findings:**\n\n"
        for v in violations:
            report += f"- {v}\n"
            if v.remediation:
                report += f"  - *Remediation:* {v.remediation}\n"
        report += "\n"
    else:
        report += "✅ All BlueFalconInk LLC standards met. Architecture is compliant.\n"

    return report


def run_audit(file_path: str, config_path: str) -> int:
    """Run the full Foreman audit and return exit code."""
    config = load_config(config_path)
    diagram = load_diagram(file_path)

    # Run all checks
    violations: List[Violation] = []
    violations.extend(check_mermaid_validity(diagram))
    violations.extend(check_cloud_provider_alignment(diagram, config))
    violations.extend(check_security_layer(diagram, config))
    violations.extend(check_branding(diagram, config))
    violations.extend(check_data_flow(diagram, config))
    violations.extend(check_subscription_compliance(diagram, config))

    # Generate and output report
    repo_name = Path(file_path).parent.parent.name
    report = generate_report(violations, repo_name)
    print(report)

    # Save report for remediation pipeline
    report_path = Path(file_path).parent.parent / "foreman_report.txt"
    with open(report_path, "w") as f:
        f.write(report)

    # Fail build on critical violations
    critical_count = sum(1 for v in violations if v.level == Violation.CRITICAL)
    if critical_count > 0:
        print(f"\n🔴 BUILD FAILED: {critical_count} critical violation(s) detected.")
        return 1

    print("\n🟢 Foreman audit passed.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="BlueFalconInk LLC Foreman AI - Architecture Compliance Audit"
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the architecture diagram file (e.g., docs/architecture.md)",
    )
    parser.add_argument(
        "--config",
        default="ARCHITECT_CONFIG.json",
        help="Path to ARCHITECT_CONFIG.json (default: ARCHITECT_CONFIG.json)",
    )
    args = parser.parse_args()

    exit_code = run_audit(args.file, args.config)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
