#!/usr/bin/env python3
"""
migrate_v1_2.py — One-time migration applying:

1. New `pricing_unit` field per vendor, controlling how normalization works:
   - per_unit, per_user, per_listing, flat_tier (normalizable)
   - per_lead, per_event, native_only, variable, gated, starts_at (not normalized)

2. Category restructuring:
   - NEW: Lead Generation (AllPropertyManagement, PropertyManagement.com)
   - NEW: Sales & Marketing Services (PMW)
   - NEW: Business Tools (Slack, Notion, Google Workspace, Gusto, Xero, QBO, ProfitCoach, APM Help)
   - NEW: Listings Marketplaces (Zillow, Apartments.com)
   - Existing categories: PM Software, Maintenance, Leasing, Resident Benefits,
     CRM/Workflow, Inspections, Payments, Industry Association

3. `data_pending` flag for vendors we know need follow-up research
   (Buildium calculator, Boom rates, Rentvine flesh-out, EZ Repair confirmation,
   zInspector tier from user invoice)

4. Computed normalized_pricing field via normalize.py

Run once, then keep as historical record. Safe to re-run; it overwrites fields
not data the user has updated manually.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from normalize import compute_normalized_pricing, ASSUMPTIONS

VENDORS_FILE = ROOT / "data" / "vendors.json"


# Per-vendor reassignments
VENDOR_UPDATES = {
    "appfolio":              {"pricing_unit": "gated",        "category": "PM Software"},
    "buildium":              {"pricing_unit": "starts_at",    "category": "PM Software", "data_pending": "Calculator pricing for 100/350/1000 doors needed from buildium.com/pricing"},
    "property-meld":         {"pricing_unit": "per_unit",     "category": "Maintenance"},
    "second-nature":         {"pricing_unit": "gated",        "category": "Resident Benefits"},
    "propertyware":          {"pricing_unit": "per_unit",     "category": "PM Software"},
    "aptly":                 {"pricing_unit": "per_user",     "category": "CRM/Workflow"},
    "leadsimple":            {"pricing_unit": "per_unit",     "category": "CRM/Workflow", "data_pending": "Hybrid pricing model — Operations tier is per-door, others per-user. Normalizing using Operations tier."},
    "rentvine":              {"pricing_unit": "per_unit",     "category": "PM Software",  "data_pending": "Confirm '$1.50/unit' is true unit price, not 'starts at'"},
    "zillow-rental-manager": {"pricing_unit": "variable",     "category": "Listings Marketplaces"},
    "apartments-com":        {"pricing_unit": "gated",        "category": "Listings Marketplaces"},
    "narpm":                 {"pricing_unit": "native_only",  "category": "Industry Association"},
    "slack":                 {"pricing_unit": "native_only",  "category": "Business Tools"},
    "notion":                {"pricing_unit": "native_only",  "category": "Business Tools"},
    "google-workspace":      {"pricing_unit": "native_only",  "category": "Business Tools"},
    "profitcoach":           {"pricing_unit": "native_only",  "category": "Business Tools"},
    "zinspector":            {"pricing_unit": "native_only",  "category": "Inspections", "data_pending": "Confirm tier + monthly cost from RLPMG's current zInspector invoice"},
    "propertymanagement-com":{"pricing_unit": "gated",        "category": "Lead Generation"},
    "doorloop":              {"pricing_unit": "flat_tier",    "category": "PM Software"},
    "haven":                 {"pricing_unit": "gated",        "category": "Resident Benefits"},
    "showmojo":              {"pricing_unit": "per_unit",     "category": "Leasing"},
    "tenant-turner":         {"pricing_unit": "per_unit",     "category": "Leasing"},
    "rentengine":            {"pricing_unit": "per_listing",  "category": "Leasing"},
    "gusto":                 {"pricing_unit": "native_only",  "category": "Business Tools"},
    "xero":                  {"pricing_unit": "native_only",  "category": "Business Tools"},
    "quickbooks-online":     {"pricing_unit": "native_only",  "category": "Business Tools"},
    "pmw":                   {"pricing_unit": "native_only",  "category": "Sales & Marketing Services"},
    "eliseai":               {"pricing_unit": "gated",        "category": "Leasing"},
    "apm-help":              {"pricing_unit": "gated",        "category": "Business Tools"},
    "all-property-management": {"pricing_unit": "per_lead",   "category": "Lead Generation"},
    "boom":                  {"pricing_unit": "per_event",    "category": "Payments", "data_pending": "Need per-screening and per-unit/mo rates for BoomScreen and BoomReport"},
    "ez-repair-hotline":     {"pricing_unit": "per_unit",     "category": "Maintenance", "data_pending": "Confirm $1.49/mo is per-unit (vendor doesn't specify on Wix page)"},
}


def main():
    with open(VENDORS_FILE) as f:
        data = json.load(f)

    for v in data["vendors"]:
        slug = v["slug"]
        if slug not in VENDOR_UPDATES:
            print(f"WARNING: unknown vendor slug {slug}")
            continue

        updates = VENDOR_UPDATES[slug]
        v["pricing_unit"] = updates["pricing_unit"]
        v["category"] = updates["category"]

        if "data_pending" in updates:
            v["data_pending"] = updates["data_pending"]
        else:
            v.pop("data_pending", None)

        # Compute normalized pricing (only for normalizable units, otherwise None)
        normalized = compute_normalized_pricing(v)
        if normalized is not None:
            v["normalized_pricing"] = normalized
        else:
            v.pop("normalized_pricing", None)

    # Metadata updates
    data["metadata"]["version"] = "1.2"
    data["metadata"]["normalization_defaults"] = ASSUMPTIONS
    data["metadata"]["normalization_note"] = (
        "Per-door equivalent prices computed using these defaults: "
        f"{ASSUMPTIONS['occupancy']*100:.0f}% occupancy, "
        f"{ASSUMPTIONS['active_listing_ratio']*100:.0f}% of vacancies actively listed, "
        f"1 user per {ASSUMPTIONS['doors_per_user']} doors. "
        "Vendors with native_only pricing (Slack, Notion, etc.) show their published pricing. "
        "Vendors with starts_at qualifiers need a calculator we don't have access to."
    )

    with open(VENDORS_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    # Print summary
    by_unit = {}
    by_cat = {}
    pending = 0
    normalized_count = 0
    for v in data["vendors"]:
        by_unit[v["pricing_unit"]] = by_unit.get(v["pricing_unit"], 0) + 1
        by_cat[v["category"]] = by_cat.get(v["category"], 0) + 1
        if v.get("data_pending"):
            pending += 1
        if v.get("normalized_pricing"):
            normalized_count += 1

    print("Migration v1.2 complete.")
    print("")
    print("By pricing unit:")
    for unit, n in sorted(by_unit.items(), key=lambda x: -x[1]):
        print(f"  {unit:<15} {n}")
    print("")
    print("By category:")
    for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat:<30} {n}")
    print("")
    print(f"Vendors with computed normalized_pricing: {normalized_count}")
    print(f"Vendors with data_pending flag:           {pending}")


if __name__ == "__main__":
    main()
