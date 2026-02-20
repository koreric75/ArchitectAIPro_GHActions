#!/usr/bin/env python3
"""
BlueFalconInk Production Readiness Audit

Validates that all production prerequisites are met before deployment.
Checks secrets, configuration, CDN, and compliance requirements.

Usage:
    python production_readiness.py --config ARCHITECT_CONFIG.json
"""

import argparse
import json
import os
import sys


def check_production_readiness(config_path: str) -> list:
    """Run production readiness checks."""
    failures = []
    warnings = []

    # Load config
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        failures.append(f"❌ Cannot load config: {e}")
        return failures

    # Check 1: Required environment secrets
    required_secrets = {
        "ARCHITECT_AI_API_KEY": "Architect AI Pro API key",
        "STRIPE_LIVE_SECRET": "Stripe live secret key",
    }

    for secret_name, description in required_secrets.items():
        if not os.getenv(secret_name):
            warnings.append(
                f"⚠️ Missing environment variable: {secret_name} ({description})"
            )

    # Check 2: CDN configuration
    if config.get("diagram_rules", {}).get("cloud_cdn"):
        print("  ✅ CDN enabled in configuration")
    else:
        failures.append("❌ CDN not enabled in ARCHITECT_CONFIG.json")

    # Check 3: Security compliance
    compliance = config.get("compliance", {})
    if compliance.get("require_security_subgraph"):
        print("  ✅ Security subgraph requirement enabled")
    else:
        warnings.append("⚠️ Security subgraph not required in compliance settings")

    if compliance.get("pci_compliance_for_payments"):
        print("  ✅ PCI compliance checks enabled")
    else:
        warnings.append("⚠️ PCI compliance not enabled for payment services")

    # Check 4: Flagship definitions
    flagships = config.get("flagships", {})
    if len(flagships) == 0:
        failures.append("❌ No flagships defined in ARCHITECT_CONFIG.json")
    else:
        print(f"  ✅ {len(flagships)} flagship(s) configured")
        for name, details in flagships.items():
            print(f"     - {name}: {details.get('domain', 'N/A')}")

    # Check 5: Styling / branding
    styling = config.get("styling", {})
    if styling.get("primary_color") == "#1E40AF":
        print("  ✅ BlueFalconInk brand color configured")
    else:
        warnings.append("⚠️ Primary color is not BlueFalconInk standard (#1E40AF)")

    return failures + warnings


def main():
    parser = argparse.ArgumentParser(
        description="BlueFalconInk Production Readiness Audit"
    )
    parser.add_argument(
        "--config",
        default="ARCHITECT_CONFIG.json",
        help="Path to ARCHITECT_CONFIG.json",
    )
    args = parser.parse_args()

    print("\n📋 BlueFalconInk Production Readiness Audit\n")
    print("=" * 50)

    issues = check_production_readiness(args.config)

    print("\n" + "=" * 50)

    if issues:
        print("\nIssues Found:\n")
        for issue in issues:
            print(f"  {issue}")

        critical = [i for i in issues if i.startswith("❌")]
        if critical:
            print(f"\n🔴 FAILED: {len(critical)} critical issue(s) must be resolved.")
            sys.exit(1)
        else:
            print(f"\n🟡 PASSED with {len(issues)} warning(s).")
            sys.exit(0)
    else:
        print("\n✅ All production readiness checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
