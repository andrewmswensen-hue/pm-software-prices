#!/usr/bin/env python3
"""
detect_changes.py - Identify vendors with price changes recorded today.

Looks at each vendor's price_history. A change is "fresh" if the most-recent
entry's date equals today AND it differs from the prior entry.

Writes /tmp/detected_changes.json with structured change data for downstream
steps (snippet generation, email body assembly).

Prints the integer count of changes to stdout so the GitHub Actions workflow
can gate downstream steps on it.

Exit codes:
  0 - success (whether or not changes were detected)
  2 - vendors.json missing or unreadable
"""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDORS_FILE = ROOT / "data" / "vendors.json"
OUTPUT_FILE = Path("/tmp/detected_changes.json")
TODAY = datetime.date.today().isoformat()


def diff_tier_maps(old: dict, new: dict):
    """Return three lists: added tiers, removed tiers, modified tiers (old, new)."""
    added = [(name, price) for name, price in new.items() if name not in old]
    removed = [(name, price) for name, price in old.items() if name not in new]
    modified = [
        (name, old[name], new[name])
        for name in new
        if name in old and old[name] != new[name]
    ]
    return added, removed, modified


def main():
    if not VENDORS_FILE.exists():
        print("0")
        return 2

    with open(VENDORS_FILE) as f:
        data = json.load(f)

    fresh_changes = []
    for v in data["vendors"]:
        history = v.get("price_history", [])
        if len(history) < 2:
            continue
        latest = history[-1]
        if latest.get("date") != TODAY:
            continue

        prev = history[-2]
        added, removed, modified = diff_tier_maps(
            prev.get("tiers", {}),
            latest.get("tiers", {}),
        )
        if not (added or removed or modified):
            continue

        fresh_changes.append({
            "vendor": v["name"],
            "slug": v["slug"],
            "category": v["category"],
            "pricing_url": v.get("pricing_url", ""),
            "pricing_model": v.get("pricing_model", ""),
            "added_tiers": added,
            "removed_tiers": removed,
            "modified_tiers": modified,
        })

    OUTPUT_FILE.write_text(json.dumps({"date": TODAY, "changes": fresh_changes}, indent=2))
    print(len(fresh_changes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
