#!/usr/bin/env python3
"""
BlueFalconInk LLC — Token Budget Manager

Centralized API budget tracking to prevent runaway costs across all agents.
Tracks GitHub API calls, Gemini API calls, and compute minutes.
Enforces hard limits and provides cost projections.

Usage (as module):
    from token_budget import BudgetManager
    budget = BudgetManager.load("docs/token_budget.json")
    budget.can_spend("github_api", 50)
    budget.record("github_api", 50)
    budget.save()

Usage (CLI):
    python token_budget.py --status
    python token_budget.py --reset
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


class BudgetManager:
    """
    Manages API call budgets across multiple categories:
    - github_api: GitHub REST API calls (rate limit: 5000/hour)
    - gemini_api: Gemini API calls (rate limit varies by model)
    - ci_minutes: GitHub Actions compute minutes
    - storage_mb: GitHub repo storage
    """

    DEFAULT_LIMITS = {
        "github_api": {
            "hourly_limit": 4500,        # Leave 500 buffer from 5000/hr
            "daily_limit": 50000,
            "monthly_limit": 500000,
            "cost_per_call": 0,           # Free for authenticated
        },
        "gemini_api": {
            "hourly_limit": 50,           # Conservative for flash
            "daily_limit": 500,
            "monthly_limit": 10000,
            "cost_per_call": 0.00035,     # ~$0.35/1000 for flash
        },
        "ci_minutes": {
            "hourly_limit": 30,
            "daily_limit": 200,
            "monthly_limit": 2000,        # Free tier is 2000 min/mo
            "cost_per_call": 0.008,       # $0.008/min for Linux
        },
    }

    def __init__(self, budget_file: str = "docs/token_budget.json"):
        self.budget_file = Path(budget_file)
        self.data = self._load()

    def _load(self) -> dict:
        """Load existing budget or create new."""
        if self.budget_file.exists():
            try:
                return json.loads(self.budget_file.read_text())
            except json.JSONDecodeError:
                pass

        return {
            "created": datetime.now(timezone.utc).isoformat(),
            "limits": self.DEFAULT_LIMITS,
            "usage": {},
            "alerts": [],
            "total_cost": 0,
        }

    def save(self):
        """Persist budget state."""
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.budget_file.write_text(json.dumps(self.data, indent=2))

    def _current_periods(self) -> dict:
        """Get current time period keys."""
        now = datetime.now(timezone.utc)
        return {
            "hour": now.strftime("%Y-%m-%dT%H"),
            "day": now.strftime("%Y-%m-%d"),
            "month": now.strftime("%Y-%m"),
        }

    def _get_usage(self, category: str, period_key: str) -> int:
        """Get usage for a category in a time period."""
        usage = self.data.get("usage", {})
        return usage.get(category, {}).get(period_key, 0)

    def _set_usage(self, category: str, period_key: str, value: int):
        """Set usage for a category in a time period."""
        if "usage" not in self.data:
            self.data["usage"] = {}
        if category not in self.data["usage"]:
            self.data["usage"][category] = {}
        self.data["usage"][category][period_key] = value

    def can_spend(self, category: str, amount: int = 1) -> bool:
        """Check if spending is within budget."""
        limits = self.data.get("limits", {}).get(category, {})
        periods = self._current_periods()

        # Check hourly
        hourly = self._get_usage(category, periods["hour"])
        if hourly + amount > limits.get("hourly_limit", float("inf")):
            return False

        # Check daily
        daily = self._get_usage(category, periods["day"])
        if daily + amount > limits.get("daily_limit", float("inf")):
            return False

        # Check monthly
        monthly = self._get_usage(category, periods["month"])
        if monthly + amount > limits.get("monthly_limit", float("inf")):
            return False

        return True

    def record(self, category: str, amount: int = 1, cost: Optional[float] = None):
        """Record usage."""
        periods = self._current_periods()
        limits = self.data.get("limits", {}).get(category, {})

        for period_name, key in periods.items():
            current = self._get_usage(category, key)
            self._set_usage(category, key, current + amount)

        # Track cost
        if cost is None:
            cost = amount * limits.get("cost_per_call", 0)
        self.data["total_cost"] = self.data.get("total_cost", 0) + cost

        # Check for alerts
        monthly = self._get_usage(category, periods["month"])
        monthly_limit = limits.get("monthly_limit", float("inf"))
        if monthly_limit and monthly / monthly_limit > 0.8:
            alert = f"⚠️ {category}: {monthly}/{monthly_limit} monthly ({monthly/monthly_limit*100:.0f}%)"
            if alert not in self.data.get("alerts", []):
                self.data.setdefault("alerts", []).append(alert)
                print(alert)

    def get_status(self) -> dict:
        """Get comprehensive budget status."""
        periods = self._current_periods()
        status = {}

        for category, limits in self.data.get("limits", {}).items():
            hourly = self._get_usage(category, periods["hour"])
            daily = self._get_usage(category, periods["day"])
            monthly = self._get_usage(category, periods["month"])

            h_lim = limits.get("hourly_limit", 0)
            d_lim = limits.get("daily_limit", 0)
            m_lim = limits.get("monthly_limit", 0)

            status[category] = {
                "hourly": {"used": hourly, "limit": h_lim, "pct": (hourly/h_lim*100) if h_lim else 0},
                "daily": {"used": daily, "limit": d_lim, "pct": (daily/d_lim*100) if d_lim else 0},
                "monthly": {"used": monthly, "limit": m_lim, "pct": (monthly/m_lim*100) if m_lim else 0},
                "cost": monthly * limits.get("cost_per_call", 0),
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "categories": status,
            "total_cost": self.data.get("total_cost", 0),
            "alerts": self.data.get("alerts", []),
        }

    def reset(self):
        """Reset all usage counters."""
        self.data["usage"] = {}
        self.data["alerts"] = []
        self.data["total_cost"] = 0
        print("🔄 Budget counters reset")

    def cleanup_old_periods(self, keep_days: int = 30):
        """Remove usage data older than keep_days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        for category in self.data.get("usage", {}):
            keys_to_remove = [k for k in self.data["usage"][category] if k < cutoff and "T" not in k]
            for k in keys_to_remove:
                del self.data["usage"][category][k]


def print_status(budget: BudgetManager):
    """Print a formatted status report."""
    status = budget.get_status()
    print(f"\n📊 CHAD Token Budget Status")
    print(f"{'='*60}")

    for cat, info in status["categories"].items():
        print(f"\n  {cat.upper()}")
        for period in ("hourly", "daily", "monthly"):
            p = info[period]
            bar_len = 30
            filled = int(bar_len * p["pct"] / 100) if p["pct"] else 0
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"    {period:>8}: [{bar}] {p['used']:>6}/{p['limit']:>6} ({p['pct']:.1f}%)")
        print(f"    Est cost: ${info['cost']:.4f}")

    print(f"\n  Total estimated cost: ${status['total_cost']:.4f}")

    if status["alerts"]:
        print(f"\n  ⚠️  Active Alerts:")
        for a in status["alerts"]:
            print(f"    {a}")


@staticmethod
def load(path: str = "docs/token_budget.json") -> "BudgetManager":
    return BudgetManager(path)


BudgetManager.load = load


def main():
    parser = argparse.ArgumentParser(description="CHAD Token Budget Manager")
    parser.add_argument("--status", action="store_true", help="Show budget status")
    parser.add_argument("--reset", action="store_true", help="Reset all counters")
    parser.add_argument("--file", default="docs/token_budget.json", help="Budget file path")
    args = parser.parse_args()

    budget = BudgetManager(args.file)

    if args.reset:
        budget.reset()
        budget.save()
    elif args.status:
        print_status(budget)
    else:
        print_status(budget)

    budget.save()


if __name__ == "__main__":
    main()
