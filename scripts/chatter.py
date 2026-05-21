#!/usr/bin/env python3
"""
chatter.py — Search public Reddit for vendor pricing chatter.

Looks for recent posts in PM-adjacent subreddits that mention a vendor name
alongside pricing keywords ("raise", "expensive", "quote", etc.). Saves results
to data/chatter/YYYY-MM-DD.json so the human reviewer can scan for signals
about gated-vendor pricing.

For V1, Reddit only. LinkedIn/X scraping need auth and proper APIs — V2.

Run:  python scripts/chatter.py
"""

import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDORS_FILE = ROOT / "data" / "vendors.json"
CHATTER_DIR = ROOT / "data" / "chatter"
TODAY = datetime.date.today().isoformat()

USER_AGENT = "PM-Pricing-Tracker/1.0 (research; contact andrew.m.swensen@gmail.com)"

REDDIT_SUBS = ["PropertyManagement", "realestateinvesting", "Landlord", "RealEstate"]

PRICE_KEYWORDS = (
    "price", "pricing", "raise", "raised", "increase", "increased",
    "hike", "expensive", "cost", "quote", "quoted", "charging", "charged",
    "fee", "fees", "billed", "subscription", "renewal",
)


def search_reddit(query: str, sub: str, retries: int = 2):
    encoded = urllib.parse.quote(query)
    url = (
        f"https://www.reddit.com/r/{sub}/search.json"
        f"?q={encoded}&restrict_sr=on&sort=new&t=month&limit=15"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read())
                return payload.get("data", {}).get("children", [])
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited
                time.sleep(5 * (attempt + 1))
                continue
            return []
        except Exception:
            return []
    return []


def looks_price_relevant(post: dict, vendor_name: str) -> bool:
    title = (post.get("title") or "").lower()
    body = ((post.get("selftext") or "")[:1000]).lower()
    blob = title + " " + body
    if vendor_name.lower() not in blob:
        return False
    return any(kw in blob for kw in PRICE_KEYWORDS)


def find_chatter(vendor_name: str) -> list:
    findings = []
    for sub in REDDIT_SUBS:
        children = search_reddit(vendor_name, sub)
        for c in children:
            p = c.get("data", {})
            if looks_price_relevant(p, vendor_name):
                findings.append({
                    "subreddit": sub,
                    "title": p.get("title"),
                    "url": "https://reddit.com" + (p.get("permalink") or ""),
                    "author": p.get("author"),
                    "created_utc": p.get("created_utc"),
                    "score": p.get("score"),
                    "num_comments": p.get("num_comments"),
                    "excerpt": (p.get("selftext") or "")[:300],
                })
        time.sleep(1)  # polite delay between sub queries
    return findings


def main():
    if not VENDORS_FILE.exists():
        print(f"ERROR: {VENDORS_FILE} not found", file=sys.stderr)
        return 2

    with open(VENDORS_FILE) as f:
        data = json.load(f)

    all_findings = {}
    print(f"=== Reddit chatter search — {TODAY} ===")
    for vendor in data["vendors"]:
        name = vendor["name"]
        print(f"  {name:<35} ", end="", flush=True)
        try:
            findings = find_chatter(name)
        except Exception as e:
            print(f"ERROR — {e}")
            continue
        if findings:
            all_findings[name] = findings
            print(f"{len(findings)} matches")
        else:
            print("none")
        time.sleep(1.5)  # respect Reddit's rate limits

    CHATTER_DIR.mkdir(parents=True, exist_ok=True)
    output_file = CHATTER_DIR / f"{TODAY}.json"
    with open(output_file, "w") as f:
        json.dump({
            "date": TODAY,
            "subreddits_searched": REDDIT_SUBS,
            "vendor_count_with_chatter": len(all_findings),
            "findings": all_findings,
        }, f, indent=2)
        f.write("\n")

    print("")
    print(f"Saved to {output_file.relative_to(ROOT)}")
    print(f"Vendors with chatter this week: {len(all_findings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
