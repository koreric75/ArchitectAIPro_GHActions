#!/usr/bin/env python3
"""
BlueFalconInk Safety Check - Legacy Audit Script

Simplified version of the Foreman audit for quick CLI checks.

Usage:
    python safety_check.py --file docs/architecture.md
"""

import json
import re
import sys
import argparse
from pathlib import Path


def audit_diagram(diagram_text: str, config_path: str) -> list:
    """Audit a diagram against the BlueFalconInk building codes."""
    with open(config_path, "r") as f:
        config = json.load(f)

    violations = []
    preferred_cloud = config["technical_constraints"]["preferred_cloud"]

    # Check 1: Cloud Provider Alignment
    non_standard = {
        "AWS": ["Azure", "Google Cloud Functions", "GCP Compute"],
        "Azure": ["AWS Lambda", "S3", "EC2"],
        "GCP": ["AWS Lambda", "Azure Functions", "EC2"],
    }
    for provider in non_standard.get(preferred_cloud, []):
        if provider in diagram_text:
            violations.append(
                f"❌ Violation: Found {provider} components in a "
                f"{preferred_cloud}-mandated project."
            )

    # Check 2: Security Layer Presence
    if config["diagram_rules"]["include_security_layer"]:
        if "subgraph Security" not in diagram_text and "WAF" not in diagram_text:
            violations.append(
                "⚠️ Warning: No explicit 'Security' boundary found in architecture."
            )

    # Check 3: Naming Conventions / Branding
    org_name = config.get("org_name", "BlueFalconInk")
    if org_name not in diagram_text and "BlueFalcon" not in diagram_text:
        violations.append(
            f"📝 Note: Diagram is missing {org_name} branding elements."
        )

    # Check 4: CDN presence for streaming services
    if config["diagram_rules"].get("cloud_cdn"):
        cdn_keywords = ["CloudFront", "CDN", "Cloud CDN"]
        if not any(kw in diagram_text for kw in cdn_keywords):
            violations.append(
                "⚠️ Warning: CDN not detected in architecture. "
                "Required for streaming/content delivery."
            )

    return violations


def main():
    parser = argparse.ArgumentParser(description="BlueFalconInk Safety Check")
    parser.add_argument("--file", required=True, help="Path to architecture diagram")
    parser.add_argument(
        "--config",
        default="ARCHITECT_CONFIG.json",
        help="Path to config (default: ARCHITECT_CONFIG.json)",
    )
    args = parser.parse_args()

    with open(args.file, "r") as f:
        diagram_text = f.read()

    violations = audit_diagram(diagram_text, args.config)

    if violations:
        print("\n🏗️ Foreman AI Safety Check Results:\n")
        for v in violations:
            print(f"  {v}")
        print()

        # Fail on critical violations (❌)
        critical = [v for v in violations if v.startswith("❌")]
        if critical:
            print(f"🔴 FAILED: {len(critical)} critical violation(s).")
            sys.exit(1)
        else:
            print(f"🟡 PASSED with {len(violations)} warning(s)/note(s).")
            sys.exit(0)
    else:
        print("✅ All BlueFalconInk standards met.")
        sys.exit(0)


if __name__ == "__main__":
    main()
