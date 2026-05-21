#!/usr/bin/env python3
"""
weekly_update.py — The everything-script.

What it does each Monday:
  1. Loads data/vendors.json
  2. For each vendor with public pricing, fetches the pricing page
  3. Strips it to plain text, saves a snapshot in data/snapshots/YYYY-MM-DD/
  4. Compares against last week's snapshot — flags price changes
  5. Updates vendors.json (last_checked, change_log)
  6. Prints a summary the human can paste into a commit message

Uses only the Python standard library — no pip install required.

Run:  python scripts/weekly_update.py
"""

import datetime
import json
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDORS_FILE = ROOT / "data" / "vendors.json"
SNAPSHOTS_DIR = ROOT / "data" / "snapshots"
TODAY = datetime.date.today().isoformat()

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

TRACKABLE_STATUSES = {"public_full", "public_partial"}


def load_vendors():
    with open(VENDORS_FILE) as f:
        return json.load(f)


def save_vendors(data):
    with open(VENDORS_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def fetch_page(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="ignore"), resp.status
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"URLError: {e.reason}"
    except Exception as e:
        return None, f"Error: {type(e).__name__}: {e}"


def html_to_text(html: str) -> str:
    """Strip HTML to plain text, removing scripts/styles/nav/footer."""
    for tag in ("script", "style", "nav", "footer", "header", "noscript"):
        html = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


PRICE_PATTERN = re.compile(
    r"\$\s?[\d,]+(?:\.\d+)?"
    r"(?:\s*[-–]\s*\$?[\d,.]+)?"
    r"(?:\s*/\s*(?:mo|month|year|yr|user|unit|seat|door|listing|employee|applicant|contractor|member))?",
    re.IGNORECASE,
)


def extract_prices(text: str) -> set:
    """Find all $X / X/mo patterns. Helps surface what's price-relevant in a diff."""
    return {re.sub(r"\s+", "", p).lower() for p in PRICE_PATTERN.findall(text)}


def find_previous_snapshot(slug: str):
    """Return the most recent snapshot for this slug from any date BEFORE today."""
    if not SNAPSHOTS_DIR.exists():
        return None
    candidates = sorted(SNAPSHOTS_DIR.glob(f"*/{slug}.txt"))
    candidates = [p for p in candidates if p.parent.name < TODAY]
    return candidates[-1] if candidates else None


def main():
    if not VENDORS_FILE.exists():
        print(f"ERROR: {VENDORS_FILE} not found", file=sys.stderr)
        return 2

    data = load_vendors()
    today_dir = SNAPSHOTS_DIR / TODAY
    today_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "checked": 0,
        "baselines": [],
        "no_change": [],
        "changed": [],
        "errors": [],
    }

    for vendor in data["vendors"]:
        name = vendor["name"]
        slug = vendor["slug"]
        url = vendor.get("pricing_url")
        status = vendor.get("status")

        if status not in TRACKABLE_STATUSES:
            continue

        if not url:
            summary["errors"].append((name, "missing pricing_url"))
            continue

        print(f"  {name:<35} ", end="", flush=True)
        html, code = fetch_page(url)
        if html is None:
            print(f"FAILED — {code}")
            summary["errors"].append((name, code))
            continue

        text = html_to_text(html)
        snapshot_path = today_dir / f"{slug}.txt"
        snapshot_path.write_text(text)

        summary["checked"] += 1

        prev = find_previous_snapshot(slug)
        if prev is None:
            print("baseline saved")
            summary["baselines"].append(name)
            vendor["last_checked"] = TODAY
            continue

        prev_text = prev.read_text()
        prev_prices = extract_prices(prev_text)
        new_prices = extract_prices(text)
        added = sorted(new_prices - prev_prices)
        removed = sorted(prev_prices - new_prices)

        if added or removed:
            print(f"CHANGED  +{added}  -{removed}")
            summary["changed"].append({
                "vendor": name,
                "added": added,
                "removed": removed,
            })
            vendor["last_changed"] = TODAY
            vendor.setdefault("change_log", []).append({
                "date": TODAY,
                "added": added,
                "removed": removed,
            })
        else:
            print("no change")
            summary["no_change"].append(name)

        vendor["last_checked"] = TODAY

    data["metadata"]["last_updated"] = TODAY
    save_vendors(data)

    # Print a clean summary
    print("")
    print(f"=== Weekly Update Summary — {TODAY} ===")
    print(f"  Trackable vendors checked: {summary['checked']}")
    print(f"  Baselines saved:           {len(summary['baselines'])}")
    print(f"  No change:                 {len(summary['no_change'])}")
    print(f"  Changes detected:          {len(summary['changed'])}")
    print(f"  Fetch errors:              {len(summary['errors'])}")
    print("")

    if summary["changed"]:
        print("Changes:")
        for c in summary["changed"]:
            print(f"  • {c['vendor']}: +{c['added']}  -{c['removed']}")
        print("")

    if summary["errors"]:
        print("Errors:")
        for name, err in summary["errors"]:
            print(f"  ! {name}: {err}")
        print("")

    return 0


if __name__ == "__main__":
    sys.exit(main())
