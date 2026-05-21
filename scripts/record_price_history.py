#!/usr/bin/env python3
"""
record_price_history.py — Append a new price_history entry to any vendor
whose current tier prices differ from their last recorded snapshot.

Called weekly from the GitHub Actions workflow after vendors.json has been
manually updated with any new prices the human reviewer found in the diff.

Run: python scripts/record_price_history.py
"""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDORS_FILE = ROOT / "data" / "vendors.json"
TODAY = datetime.date.today().isoformat()


def current_tier_snapshot(vendor):
    return {
        t["name"]: t.get("price_display", "")
        for t in vendor.get("tiers", [])
    }


def main():
    if not VENDORS_FILE.exists():
        print(f"ERROR: {VENDORS_FILE} not found", file=sys.stderr)
        return 2

    with open(VENDORS_FILE) as f:
        data = json.load(f)

    new_entries = 0
    for v in data["vendors"]:
        if v["status"] not in ("public_full", "public_partial", "js_rendered", "bot_blocked"):
            continue

        history = v.setdefault("price_history", [])
        current = current_tier_snapshot(v)

        if not history:
            history.append({"date": TODAY, "tiers": current})
            new_entries += 1
            print(f"  {v['name']:<40} first snapshot recorded")
            continue

        last = history[-1].get("tiers", {})
        if current != last:
            history.append({"date": TODAY, "tiers": current})
            new_entries += 1
            print(f"  {v['name']:<40} CHANGE recorded")
        else:
            # No change — don't append a duplicate entry
            pass

    with open(VENDORS_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print("")
    print(f"Price-history entries added this run: {new_entries}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
