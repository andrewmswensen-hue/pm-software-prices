#!/usr/bin/env python3
"""
render_readme.py — Regenerate README.md from data/vendors.json.

The README *is* the public dashboard. This script rebuilds it from the JSON
source of truth so the dashboard stays in sync with the data.

Run:  python scripts/render_readme.py
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDORS_FILE = ROOT / "data" / "vendors.json"
README_FILE = ROOT / "README.md"

STATUS_BADGE = {
    "public_full": "✅ Public",
    "public_partial": "🟡 Partial",
    "gated": "🔒 Hidden",
    "js_rendered": "⚙️ Manual",
    "bot_blocked": "🚫 Manual",
}

# Categories ordered for the dashboard layout
CATEGORY_ORDER = [
    "PM Software",
    "Maintenance",
    "Leasing",
    "Resident Benefits",
    "Listings/Marketing",
    "Inspections",
    "CRM/Workflow",
    "Communications",
    "Finance",
    "Payments",
    "Industry Association",
]


def format_tier(tier: dict) -> str:
    name = tier.get("name", "")
    price = tier.get("price_display", "")
    qualifier = tier.get("qualifier", "")
    bold = tier.get("highlighted", False)

    name_str = f"**{name}**" if bold else name
    if qualifier:
        price_str = f"{qualifier} {price}"
    else:
        price_str = price
    return f"{name_str}: {price_str}"


def render():
    with open(VENDORS_FILE) as f:
        data = json.load(f)

    vendors = data["vendors"]
    meta = data["metadata"]

    counts = defaultdict(int)
    for v in vendors:
        counts[v["status"]] += 1

    total = len(vendors)
    public_full = counts.get("public_full", 0)
    public_partial = counts.get("public_partial", 0)
    gated = counts.get("gated", 0)
    manual = counts.get("js_rendered", 0) + counts.get("bot_blocked", 0)

    L = []  # lines

    # Header
    L.append("# 💰 PM Software Pricing Tracker")
    L.append("")
    L.append(
        f"**Last updated:** {meta['last_updated']} &nbsp;·&nbsp; "
        f"**Vendors tracked:** {total} &nbsp;·&nbsp; "
        f"**Maintained by:** {meta['maintainer']}"
    )
    L.append("")
    L.append(
        "> A weekly snapshot of pricing across the software residential property "
        "managers actually use. We publish every change so PMs can make informed "
        "buying decisions — even when vendors would rather you call sales."
    )
    L.append("")
    L.append(f"**Editorial north star:** *\"{meta['editorial_stance']}\"*")
    L.append("")
    L.append("---")
    L.append("")

    # Scorecard
    L.append("## 📊 Transparency Scorecard")
    L.append("")
    L.append(f"- ✅ **{public_full}** vendors publish full pricing")
    L.append(f"- 🟡 **{public_partial}** publish partial pricing (\"starts at\" / model only)")
    L.append(f"- 🔒 **{gated}** hide pricing entirely — see Hall of Shame below")
    if manual > 0:
        L.append(f"- ⚙️ **{manual}** publish pricing but block automated tracking (verified manually)")
    L.append("")
    L.append("---")
    L.append("")

    # Hall of Shame
    shamed = [v for v in vendors if v["status"] == "gated"]
    if shamed:
        L.append("## 🔒 Hall of Shame")
        L.append("")
        L.append(
            "These vendors expect property managers to sit through a sales call before "
            "learning the price. Their competitors mostly don't."
        )
        L.append("")
        for v in shamed:
            L.append(f"### {v['name']}")
            L.append(f"*{v['pricing_model']}*")
            L.append("")
            if v.get("shame_line"):
                L.append(f"> {v['shame_line']}")
                L.append("")
            if v.get("third_party_intel"):
                L.append(f"**What we hear from operators:** {v['third_party_intel']}")
                L.append("")
            L.append(f"[Visit the (un)pricing page →]({v['pricing_url']})")
            L.append("")
        L.append("---")
        L.append("")

    # Pricing tables by category
    by_category = defaultdict(list)
    for v in vendors:
        if v["status"] == "gated":
            continue  # already covered in Hall of Shame
        by_category[v["category"]].append(v)

    L.append("## 📋 Pricing by Category")
    L.append("")

    for category in CATEGORY_ORDER:
        if category not in by_category:
            continue
        cat_vendors = by_category[category]

        L.append(f"### {category}")
        L.append("")
        L.append("| Vendor | Status | Tiers |")
        L.append("|---|---|---|")
        for v in cat_vendors:
            badge = STATUS_BADGE.get(v["status"], v["status"])
            tier_strs = [format_tier(t) for t in v.get("tiers", [])]
            tiers_cell = "<br>".join(tier_strs) if tier_strs else "—"
            L.append(f"| [{v['name']}]({v['pricing_url']}) | {badge} | {tiers_cell} |")
        L.append("")

        # Per-vendor notes (collapsed under category)
        notes_block = []
        for v in cat_vendors:
            if v.get("notes"):
                notes_block.append(f"- **{v['name']}** — {v['notes']}")
        if notes_block:
            L.append("<details>")
            L.append(f"<summary>Notes ({len(notes_block)})</summary>")
            L.append("")
            L.extend(notes_block)
            L.append("")
            L.append("</details>")
            L.append("")

    L.append("---")
    L.append("")

    # Methodology
    L.append("## 🛠️ How this works")
    L.append("")
    L.append(
        "Every Monday, an automated job visits each public pricing page, snapshots it, "
        "and compares it to the previous week. Any change — a new tier, a price increase, "
        "a removed plan — is committed to this repo. **The full pricing history is in "
        "[git log](../../commits/main).**"
    )
    L.append("")
    L.append(
        "For vendors with **gated** pricing, we monitor LinkedIn, Reddit, and X for "
        "operator-reported numbers, and pull pricing context from AppFolio's quarterly "
        "earnings calls (NASDAQ: APPF). When operators we trust share what they pay, "
        "we add it as third-party intel and cite the source."
    )
    L.append("")
    L.append(
        "**This is not vendor-confirmed pricing.** Always validate with the vendor "
        "before signing anything."
    )
    L.append("")
    L.append(
        "**Spotted an error or a price change?** "
        "[Open an issue](../../issues/new) — we update as soon as we can verify."
    )
    L.append("")
    L.append("---")
    L.append("")
    L.append(
        "*Tracker built and maintained by [Peter Lohmann Media](https://peterlohmann.com). "
        f"Editorial north star: \"{meta['editorial_stance']}\"*"
    )
    L.append("")

    README_FILE.write_text("\n".join(L))
    print(f"README.md regenerated — {len(L)} lines, {total} vendors")


if __name__ == "__main__":
    render()
