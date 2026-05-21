#!/usr/bin/env python3
"""
migrate_v1_1.py — One-time migration applying:
  1. Reclassifications based on user feedback + re-audit:
     - Aptly: gated → public_full ($40/$80/user/mo, custom enterprise)
     - All Property Management: gated → public_full (per-lead price table)
     - EZ Repair Hotline: gated → public_partial ($1.49/mo, unit unclear)
     - RentEngine: public_partial → public_full (custom enterprise = footnote)
  2. New framework principle: "Custom Enterprise" tier alongside listed prices
     is a footnote, NOT shame. Hall of Shame = zero pricing visible publicly.
  3. New schema fields per vendor:
     - tracking_since: date we started tracking
     - price_history: array of {date, tiers} snapshots — basis for sparklines

Run once, then delete or keep as historical record.
"""
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDORS_FILE = ROOT / "data" / "vendors.json"
TODAY = datetime.date.today().isoformat()


def main():
    with open(VENDORS_FILE) as f:
        data = json.load(f)

    for v in data["vendors"]:
        slug = v["slug"]

        if slug == "aptly":
            v["status"] = "public_full"
            v["pricing_model"] = "Per-user monthly or annual"
            v["tiers"] = [
                {"name": "Essential", "price_display": "$40/user/mo"},
                {"name": "Premium", "price_display": "$80/user/mo", "highlighted": True},
                {"name": "Enterprise", "price_display": "Custom"},
            ]
            v["notes"] = (
                "Priced per-user, not per-door — unusual in PM software and friendly to "
                "smaller teams. Monthly and annual billing both offered. Enterprise tier "
                "is custom-quoted but Essential and Premium are fully posted."
            )
            v.pop("shame_line", None)
            v.pop("third_party_intel", None)

        elif slug == "all-property-management":
            v["status"] = "public_full"
            v["pricing_model"] = "Pay-per-lead, by property type and size (minimum bid)"
            v["tiers"] = [
                {"name": "Residential (Single/Condo)", "price_display": "$40–$145/lead"},
                {"name": "Vacation rentals", "price_display": "$65–$70/lead"},
                {"name": "Associations (HOA/Condo)", "price_display": "$75–$150/lead"},
                {"name": "Commercial", "price_display": "$85–$135/lead", "highlighted": True},
                {"name": "Specialized (parking, biotech)", "price_display": "$95–$105/lead"},
            ]
            v["notes"] = (
                "Per-lead minimum bids vary by property type, unit count, and "
                "square footage. No monthly fees, no contracts. PMs can bid above "
                "the minimum for priority placement."
            )
            v.pop("shame_line", None)
            v.pop("third_party_intel", None)

        elif slug == "ez-repair-hotline":
            v["status"] = "public_partial"
            v["pricing_model"] = "Subscription — unit basis not specified"
            v["tiers"] = [
                {"name": "Listed price", "price_display": "$1.49/mo", "qualifier": "starts at"},
            ]
            v["notes"] = (
                "Price ($1.49/mo) shown as an image on a Wix subdomain — but the "
                "page never says whether that's per property, per unit, per call, "
                "or a flat fee. Confirm the unit basis before signing."
            )
            v["shame_line"] = (
                "Pricing is visible — but as an image on a Wix subdomain, with "
                "no unit clarification. Better than nothing, worse than transparent."
            )

        elif slug == "rentengine":
            # Custom enterprise tier is now a footnote, not partial-grade
            v["status"] = "public_full"
            # Update notes to reflect this lens
            v["notes"] = (
                "Standard tier is fully priced ($45/listing + $250/mo min). "
                "One-time onboarding fee amount not visible. Custom tier for "
                "2,000+ doors is sales-quoted (standard for enterprise tier)."
            )

        # SOFTEN remaining shame lines so they target ZERO pricing, not "custom enterprise"
        if slug == "appfolio":
            v["shame_line"] = (
                "Names three tiers (Core / Plus / Max), shows zero dollar amounts. "
                "AppFolio is publicly traded — they disclose pricing dynamics in "
                "quarterly earnings calls, just not on their pricing page."
            )
        elif slug == "second-nature":
            v["shame_line"] = (
                "Residents are told they'll pay $20–$80/mo. What the PM actually "
                "earns or pays? Not disclosed. The whole margin is invisible."
            )
        elif slug == "apartments-com":
            v["shame_line"] = (
                "Three tier names — Basic, Pro, Enterprise. Zero dollar amounts for any of them. "
                "Whatever you pay for advertising, the property next door probably pays less."
            )
        elif slug == "propertymanagement-com":
            v["shame_line"] = (
                "Branded as 'zero pay-to-play' for rankings — but won't say what the "
                "optional PM profile upgrade actually costs."
            )
        elif slug == "haven":
            v["shame_line"] = (
                "An AI company building tools for the PM industry — and they "
                "won't even publish what their tools cost. Demo-led pricing only."
            )
        elif slug == "eliseai":
            v["shame_line"] = (
                "Not even a pricing page exists. /pricing returns 404. They didn't "
                "bother gating it — they didn't bother making one."
            )
        elif slug == "apm-help":
            v["shame_line"] = (
                "They publicly market '60+ pricing models' for bookkeeping. None "
                "of those 60+ models appear on the website. Customization is fine; "
                "total opacity is not."
            )

    # Add tracking_since and price_history to all trackable vendors
    trackable = ("public_full", "public_partial", "js_rendered", "bot_blocked")
    for v in data["vendors"]:
        if v["status"] in trackable:
            v.setdefault("tracking_since", TODAY)
            if "price_history" not in v:
                current_tiers = {
                    t["name"]: t.get("price_display", "")
                    for t in v.get("tiers", [])
                }
                v["price_history"] = [{"date": TODAY, "tiers": current_tiers}]

    # Update metadata
    data["metadata"]["last_updated"] = TODAY
    data["metadata"]["version"] = "1.1"
    data["metadata"]["classification_framework"] = (
        "Hall of Shame = zero pricing visible publicly. "
        "A 'Custom Enterprise' tier alongside listed prices is a footnote, not shame."
    )

    with open(VENDORS_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    # Print summary
    counts = {"public_full": 0, "public_partial": 0, "gated": 0, "js_rendered": 0, "bot_blocked": 0}
    for v in data["vendors"]:
        counts[v["status"]] = counts.get(v["status"], 0) + 1

    print("Migration complete.")
    print(f"  public_full:    {counts['public_full']}")
    print(f"  public_partial: {counts['public_partial']}")
    print(f"  gated:          {counts['gated']}")
    print(f"  js_rendered:    {counts['js_rendered']}")
    print(f"  bot_blocked:    {counts['bot_blocked']}")


if __name__ == "__main__":
    main()
