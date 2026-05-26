#!/usr/bin/env python3
"""
normalize.py — Convert a vendor's native pricing model to per-door equivalent
prices at standard company sizes.

Used by render_dashboard.py and render_readme.py so that "Cost at 500 doors"
and the 100 / 350 / 1000 breakdown are consistent.

All defaults are also surfaced in the dashboard's methodology section so users
can see the assumptions.
"""
import math
import re
from typing import Optional

# --- Standard sizes shown to users -----------------------------------------
CANONICAL_SIZE = 500
SIZE_BREAKDOWN = [100, 350, 1000]
ALL_SIZES = sorted(set([CANONICAL_SIZE] + SIZE_BREAKDOWN))

# --- Conversion assumptions ------------------------------------------------
# These are the universal defaults. Individual vendors can override these via
# their own conversion_assumptions field in vendors.json.
DEFAULT_OCCUPANCY = 0.90               # 90% occupancy
ACTIVE_LISTING_RATIO = 0.60            # 60% of vacancies actively listed at any time
DOORS_PER_USER = 75                    # 1 user per 75 doors managed

ASSUMPTIONS = {
    "occupancy": DEFAULT_OCCUPANCY,
    "active_listing_ratio": ACTIVE_LISTING_RATIO,
    "doors_per_user": DOORS_PER_USER,
    "canonical_size": CANONICAL_SIZE,
    "size_breakdown": SIZE_BREAKDOWN,
}


def extract_dollars(price_str: str) -> Optional[float]:
    """Extract the first dollar amount from a price string. Returns None if not found."""
    if not price_str:
        return None
    match = re.search(r"\$\s?([\d,]+(?:\.\d+)?)", price_str)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def find_highlighted_or_first_tier(tiers: list) -> Optional[dict]:
    """Return the highlighted tier, or the first tier with a dollar amount."""
    for t in tiers:
        if t.get("highlighted") and extract_dollars(t.get("price_display", "")) is not None:
            return t
    for t in tiers:
        if extract_dollars(t.get("price_display", "")) is not None:
            return t
    return None


def find_tier_for_door_count(tiers: list, doors: int) -> Optional[dict]:
    """For flat-tier vendors (like DoorLoop), find the tier that applies to a given
    door count. Tier names may include hints like '≤10 units' or '300+ doors'."""
    parsed = []
    for t in tiers:
        name = t.get("name", "")
        max_doors = None
        # Look for "<=N", "≤N", "up to N", "N+ units"
        m = re.search(r"(?:≤|<=|up to)\s*(\d+)", name)
        if m:
            max_doors = int(m.group(1))
        parsed.append((t, max_doors))
    # Find first tier whose max_doors >= our doors (or no cap)
    for t, max_doors in parsed:
        if max_doors is None or doors <= max_doors:
            if extract_dollars(t.get("price_display", "")) is not None:
                return t
    return find_highlighted_or_first_tier(tiers)


# --- Per-pricing-unit normalizers ------------------------------------------

def normalize_per_unit(vendor: dict, doors: int) -> Optional[str]:
    """For vendors like Property Meld ($1.60/unit). Just doors x unit price."""
    tier = find_highlighted_or_first_tier(vendor.get("tiers", []))
    if tier is None:
        return None
    price = extract_dollars(tier.get("price_display", ""))
    if price is None:
        return None
    return f"${doors * price:,.0f}/mo"


def normalize_per_user(vendor: dict, doors: int, assumptions: dict) -> Optional[str]:
    """For vendors like Aptly ($40/user/mo). Assumes 1 user per N doors."""
    tier = find_highlighted_or_first_tier(vendor.get("tiers", []))
    if tier is None:
        return None
    price = extract_dollars(tier.get("price_display", ""))
    if price is None:
        return None
    dpu = assumptions.get("doors_per_user", DOORS_PER_USER)
    users = max(1, math.ceil(doors / dpu))
    return f"${users * price:,.0f}/mo ({users} users)"


def normalize_per_listing(vendor: dict, doors: int, assumptions: dict) -> Optional[str]:
    """For vendors like RentEngine ($45/listing). Computes expected monthly listings
    from doors x (1 - occupancy) x active_listing_ratio.

    Caveat: this assumes 'per listing' means per active listing per month. RentEngine's
    model is actually one-time-per-new-listing, so the formula approximates monthly
    spend assuming steady-state turnover."""
    tier = find_highlighted_or_first_tier(vendor.get("tiers", []))
    if tier is None:
        return None
    price = extract_dollars(tier.get("price_display", ""))
    if price is None:
        return None
    occ = assumptions.get("occupancy", DEFAULT_OCCUPANCY)
    alr = assumptions.get("active_listing_ratio", ACTIVE_LISTING_RATIO)
    expected_listings = doors * (1 - occ) * alr
    listing_cost = expected_listings * price
    # Many per-listing vendors also have monthly minimums
    notes_min = re.search(r"\$([\d,]+)\s*(?:/mo|monthly)?\s*min", vendor.get("notes", "") or "")
    if notes_min:
        min_monthly = float(notes_min.group(1).replace(",", ""))
        if min_monthly > listing_cost:
            return f"${min_monthly:,.0f}/mo (min)"
    return f"${listing_cost:,.0f}/mo (~{expected_listings:.0f} listings)"


def normalize_flat_tier(vendor: dict, doors: int) -> Optional[str]:
    """For vendors like DoorLoop with discrete tiers tied to door brackets."""
    tier = find_tier_for_door_count(vendor.get("tiers", []), doors)
    if tier is None:
        return None
    price = extract_dollars(tier.get("price_display", ""))
    if price is None:
        return None
    return f"${price:,.0f}/mo ({tier.get('name', 'tier')})"


def normalize_starts_at(vendor: dict, doors: int) -> Optional[str]:
    """For vendors like Buildium that show 'starts at' tiers tied to portfolio size.
    Without a calculator we cannot compute exact prices for arbitrary sizes, so we
    return None and the dashboard shows 'data pending'."""
    return None


# --- Public API ------------------------------------------------------------

def compute_normalized_pricing(vendor: dict) -> Optional[dict]:
    """Returns a dict {size_str: price_display} for the canonical size and breakdown
    sizes, or None if this vendor's pricing model can't be normalized to per-door."""
    pricing_unit = vendor.get("pricing_unit")

    if pricing_unit in (None, "gated", "variable", "native_only", "per_lead", "per_event"):
        return None

    # Vendors with "starts at" qualifiers on tiers need a calculator we don't have
    tiers = vendor.get("tiers", [])
    if pricing_unit == "starts_at" or any(t.get("qualifier") == "starts at" for t in tiers):
        return None

    assumptions = vendor.get("conversion_assumptions", ASSUMPTIONS)

    result = {}
    for size in ALL_SIZES:
        if pricing_unit == "per_unit":
            val = normalize_per_unit(vendor, size)
        elif pricing_unit == "per_user":
            val = normalize_per_user(vendor, size, assumptions)
        elif pricing_unit == "per_listing":
            val = normalize_per_listing(vendor, size, assumptions)
        elif pricing_unit == "flat_tier":
            val = normalize_flat_tier(vendor, size)
        else:
            val = None
        result[str(size)] = val

    if all(v is None for v in result.values()):
        return None
    return result


if __name__ == "__main__":
    # Self-test
    print("ASSUMPTIONS:", ASSUMPTIONS)
    test_vendor = {
        "pricing_unit": "per_unit",
        "tiers": [
            {"name": "Core", "price_display": "$1.60/unit"},
            {"name": "Ops", "price_display": "$2.00/unit", "highlighted": True},
        ],
    }
    print("Property Meld normalized:", compute_normalized_pricing(test_vendor))
