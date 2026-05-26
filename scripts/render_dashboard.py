#!/usr/bin/env python3
"""
render_dashboard.py — Build the live HTML dashboard at docs/index.html.

v1.2: Restructured to lead with "Cost at 500 doors" canonical price plus an
expandable per-size breakdown (100 / 350 / 1000). Native-pricing vendors
(Slack, Notion, etc.) show their published tiers without door normalization.
Vendors needing follow-up data are flagged with a "data pending" marker.

Reads data/vendors.json. Pure static output, no fetches or JS frameworks.
HTML <details> elements handle the row expansion without custom JS.

Run:  python scripts/render_dashboard.py
"""

import html
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDORS_FILE = ROOT / "data" / "vendors.json"
DOCS_DIR = ROOT / "docs"
INDEX_FILE = DOCS_DIR / "index.html"

STATUS_LABELS = {
    "public_full": ("✅", "Public"),
    "public_partial": ("🟡", "Partial"),
    "gated": ("🔒", "Hidden"),
    "js_rendered": ("⚙️", "Manual"),
    "bot_blocked": ("🚫", "Manual"),
}

# Order categories appear on the dashboard
CATEGORY_ORDER = [
    "PM Software",
    "Maintenance",
    "Leasing",
    "Resident Benefits",
    "Inspections",
    "CRM/Workflow",
    "Payments",
    "Lead Generation",
    "Listings Marketplaces",
    "Sales & Marketing Services",
    "Industry Association",
    "Business Tools",
]


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def render_tiers_list(tiers):
    """Render a vendor's full tier list as HTML."""
    if not tiers:
        return '<span style="color:#78716c">No tier data</span>'
    parts = []
    for t in tiers:
        name = esc(t.get("name", ""))
        price = esc(t.get("price_display", ""))
        qualifier = esc(t.get("qualifier", ""))
        highlighted = "highlighted" if t.get("highlighted") else ""
        if qualifier:
            parts.append(
                f'<li class="tier"><span class="tier-name {highlighted}">{name}:</span> '
                f'<span class="qualifier">{qualifier}</span> {price}</li>'
            )
        else:
            parts.append(
                f'<li class="tier"><span class="tier-name {highlighted}">{name}:</span> {price}</li>'
            )
    return '<ul class="tier-list">' + "".join(parts) + "</ul>"


def render_size_breakdown(normalized: dict, canonical_size: int):
    """Render the 100/350/1000 breakdown (excluding the canonical size which is shown
    separately)."""
    if not normalized:
        return ""
    parts = []
    for size_str in sorted(normalized.keys(), key=int):
        size = int(size_str)
        if size == canonical_size:
            continue
        val = normalized.get(size_str) or "(no data)"
        parts.append(
            f'<li><span class="size-label">{size} doors:</span> <span class="size-price">{esc(val)}</span></li>'
        )
    if not parts:
        return ""
    return '<ul class="size-breakdown-list">' + "".join(parts) + "</ul>"


def render_pricing_cell(vendor: dict, canonical_size: int) -> str:
    """The big new column. Format depends on pricing_unit:
       - Normalizable units: big canonical price + expand
       - native_only: native tier list
       - variable: variable label + expand
       - starts_at / data_pending: pending marker + expand showing partial info
    """
    pricing_unit = vendor.get("pricing_unit")
    normalized = vendor.get("normalized_pricing") or {}
    canonical = normalized.get(str(canonical_size))
    data_pending = vendor.get("data_pending")
    tiers = vendor.get("tiers", [])

    # Build the expand section common to all rows
    expand_inner = ""
    if normalized:
        expand_inner += '<div class="expand-section"><div class="expand-label">At other sizes</div>'
        expand_inner += render_size_breakdown(normalized, canonical_size)
        expand_inner += "</div>"
    if data_pending:
        expand_inner += (
            '<div class="expand-section data-pending-note">'
            f'<div class="expand-label">📊 Data pending</div>'
            f'<p>{esc(data_pending)}</p>'
            '</div>'
        )
    if tiers:
        expand_inner += (
            '<div class="expand-section">'
            '<div class="expand-label">Native tiers as published</div>'
            f'{render_tiers_list(tiers)}'
            '</div>'
        )

    expand_html = ""
    if expand_inner:
        expand_html = (
            '<details class="row-expand">'
            '<summary>See details</summary>'
            f'<div class="expand-body">{expand_inner}</div>'
            '</details>'
        )

    # Build the headline content
    if canonical:
        primary = (
            f'<div class="canonical-price">{esc(canonical)}</div>'
            f'<div class="canonical-label">at {canonical_size} doors</div>'
        )
    elif pricing_unit == "native_only":
        # No door normalization; show native pricing inline as the primary view
        primary = (
            '<div class="native-pricing-label">Native pricing</div>'
            '<div class="canonical-label">not normalized to per-door</div>'
        )
    elif pricing_unit == "variable":
        primary = (
            '<div class="variable-label">Variable</div>'
            '<div class="canonical-label">different price per customer</div>'
        )
    elif pricing_unit == "per_lead":
        primary = (
            '<div class="variable-label">Per-lead</div>'
            '<div class="canonical-label">cost depends on lead volume</div>'
        )
    elif pricing_unit == "per_event":
        primary = (
            '<div class="variable-label">Per-event</div>'
            '<div class="canonical-label">cost depends on volume</div>'
        )
    elif pricing_unit == "starts_at" or data_pending:
        primary = (
            '<div class="pending-label">📊 Data pending</div>'
            '<div class="canonical-label">needs calculator or invoice data</div>'
        )
    else:
        primary = '<div class="canonical-label">(no pricing data)</div>'

    return f'<div class="pricing-cell-inner">{primary}{expand_html}</div>'


def compute_recent_changes(vendors):
    changes = []
    for v in vendors:
        history = v.get("price_history", [])
        if len(history) < 2:
            continue
        prev = history[-2].get("tiers", {})
        curr = history[-1].get("tiers", {})
        date = history[-1]["date"]
        for tier_name, new_price in curr.items():
            old_price = prev.get(tier_name)
            if old_price is None:
                changes.append({"date": date, "vendor": v["name"], "kind": "tier_added",
                                "tier": tier_name, "new": new_price, "url": v.get("pricing_url", "")})
            elif old_price != new_price:
                changes.append({"date": date, "vendor": v["name"], "kind": "price_changed",
                                "tier": tier_name, "old": old_price, "new": new_price, "url": v.get("pricing_url", "")})
        for tier_name, old_price in prev.items():
            if tier_name not in curr:
                changes.append({"date": date, "vendor": v["name"], "kind": "tier_removed",
                                "tier": tier_name, "old": old_price, "url": v.get("pricing_url", "")})
    changes.sort(key=lambda c: c["date"], reverse=True)
    return changes


def render_recent_changes(changes, total_trackable, tracking_start):
    if not changes:
        return f'''
    <section id="recent-changes" class="changes-empty">
      <h2>📈 Recent Notable Changes</h2>
      <div class="empty-state">
        <p><strong>No price changes detected yet.</strong></p>
        <p>We started tracking <strong>{total_trackable}</strong> vendors on <strong>{esc(tracking_start)}</strong>. We'll surface any price hikes, new tiers, or removed plans here as they're detected. Check back next Monday.</p>
      </div>
    </section>
        '''
    items_html = []
    for c in changes[:10]:
        if c["kind"] == "price_changed":
            badge = '<span class="change-badge price">Price change</span>'
            body = f'<strong>{esc(c["tier"])}</strong>: <span class="old-price">{esc(c["old"])}</span> &rarr; <span class="new-price">{esc(c["new"])}</span>'
        elif c["kind"] == "tier_added":
            badge = '<span class="change-badge added">New tier</span>'
            body = f'<strong>{esc(c["tier"])}</strong>: {esc(c["new"])}'
        else:
            badge = '<span class="change-badge removed">Tier removed</span>'
            body = f'<strong>{esc(c["tier"])}</strong> (was {esc(c["old"])})'
        items_html.append(f'''
        <li class="change-item">
          <div class="change-date">{esc(c["date"])}</div>
          <div class="change-body">
            <a href="{esc(c["url"])}" target="_blank" rel="noopener" class="change-vendor">{esc(c["vendor"])}</a>
            {badge}
            <div class="change-detail">{body}</div>
          </div>
        </li>
        ''')
    return f'''
    <section id="recent-changes">
      <h2>📈 Recent Notable Changes</h2>
      <p class="section-desc">Pricing moves detected since we started tracking. Newest first.</p>
      <ul class="change-list">
        {"".join(items_html)}
      </ul>
    </section>
    '''


def render_methodology(assumptions, note):
    return f'''
    <section id="methodology-section" class="methodology-card">
      <h2>🧮 How "Cost at 500 doors" is calculated</h2>
      <p class="section-desc">
        For vendors who price per door or per unit, we multiply by 500. For vendors who price by user, listing, or other unit, we apply standard assumptions to convert to a comparable monthly number. Numbers are best-effort, not vendor-confirmed quotes.
      </p>
      <ul class="assumptions-list">
        <li><strong>Canonical company size:</strong> {assumptions["canonical_size"]} doors</li>
        <li><strong>Breakdown sizes also shown:</strong> {", ".join(str(s) for s in assumptions["size_breakdown"])} doors</li>
        <li><strong>Default occupancy:</strong> {int(assumptions["occupancy"]*100)}%</li>
        <li><strong>Active listings at any time:</strong> {int(assumptions["active_listing_ratio"]*100)}% of vacancies</li>
        <li><strong>Users per door (for per-user pricing):</strong> 1 user per {assumptions["doors_per_user"]} doors</li>
      </ul>
      <p class="assumptions-note">{esc(note)}</p>
    </section>
    '''


def render():
    with open(VENDORS_FILE) as f:
        data = json.load(f)

    vendors = data["vendors"]
    meta = data["metadata"]
    assumptions = meta.get("normalization_defaults", {})
    canonical_size = assumptions.get("canonical_size", 500)
    methodology_note = meta.get("normalization_note", "")

    counts = defaultdict(int)
    pending = 0
    for v in vendors:
        counts[v["status"]] += 1
        if v.get("data_pending"):
            pending += 1

    total = len(vendors)
    public_full = counts.get("public_full", 0)
    public_partial = counts.get("public_partial", 0)
    gated = counts.get("gated", 0)
    manual = counts.get("js_rendered", 0) + counts.get("bot_blocked", 0)
    total_trackable = total - gated

    tracking_dates = [v.get("tracking_since") for v in vendors if v.get("tracking_since")]
    tracking_start = min(tracking_dates) if tracking_dates else meta["last_updated"]

    shamed = [v for v in vendors if v["status"] == "gated"]
    shamed.sort(key=lambda v: (v["category"], v["name"]))

    recent_changes = compute_recent_changes(vendors)
    recent_changes_html = render_recent_changes(recent_changes, total_trackable, tracking_start)
    methodology_html = render_methodology(assumptions, methodology_note)

    # Categories present (excluding gated which is in Hall of Shame)
    categories_present = sorted(
        {v["category"] for v in vendors if v["status"] != "gated"},
        key=lambda c: CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99,
    )

    # Shame cards
    shame_cards_html = []
    for v in shamed:
        intel_html = ""
        if v.get("third_party_intel"):
            intel_html = f'<p class="intel"><strong>What operators report:</strong> {esc(v["third_party_intel"])}</p>'
        shame_line = v.get("shame_line", "")
        card = f'''
            <div class="shame-card">
              <h3>{esc(v["name"])}</h3>
              <p class="model">{esc(v["pricing_model"])}</p>
              {'<blockquote>' + esc(shame_line) + '</blockquote>' if shame_line else ''}
              {intel_html}
              <a href="{esc(v["pricing_url"])}" target="_blank" rel="noopener">View their (un)pricing page →</a>
            </div>
        '''
        shame_cards_html.append(card)

    # Table rows
    non_gated = [v for v in vendors if v["status"] != "gated"]
    non_gated.sort(key=lambda v: (
        CATEGORY_ORDER.index(v["category"]) if v["category"] in CATEGORY_ORDER else 99,
        v["name"],
    ))

    table_rows_html = []
    for v in non_gated:
        emoji, label = STATUS_LABELS.get(v["status"], ("", v["status"]))
        pending_badge = ""
        if v.get("data_pending"):
            pending_badge = ' <span class="pending-badge">data pending</span>'
        history_count = len(v.get("price_history", []))
        tracking_since = v.get("tracking_since", "")
        history_cell = (
            f'<div class="history-cell">'
            f'<span class="tracking-since">Since {esc(tracking_since)}</span>'
            f'<span class="data-points">{history_count} pt{"s" if history_count != 1 else ""}</span>'
            f'</div>'
        )

        pricing_cell_html = render_pricing_cell(v, canonical_size)

        row = f'''
            <tr data-category="{esc(v["category"])}" data-status="{esc(v["status"])}">
              <td class="vendor">
                <a href="{esc(v["pricing_url"])}" target="_blank" rel="noopener">{esc(v["name"])}</a>{pending_badge}
                <span class="category-tag">{esc(v["category"])}</span>
              </td>
              <td><span class="badge {esc(v["status"])}">{emoji} {label}</span></td>
              <td class="pricing-cell">{pricing_cell_html}</td>
              <td class="history">{history_cell}</td>
            </tr>
        '''
        table_rows_html.append(row)

    # Filter buttons
    filter_buttons_html = '<button class="filter-btn active" data-filter="all">All</button>'
    for cat in categories_present:
        filter_buttons_html += f'<button class="filter-btn" data-filter="{esc(cat)}">{esc(cat)}</button>'

    html_out = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>PM Software Pricing Tracker</title>
<meta name="description" content="A weekly-updated dashboard tracking pricing across the software residential property managers actually use.">
<link rel="stylesheet" href="styles.css">
</head>
<body>

<nav class="topnav">
  <div class="container nav-inner">
    <a href="#top" class="nav-brand">PM Pricing</a>
    <div class="nav-links">
      <a href="#scorecard">Scorecard</a>
      <a href="#recent-changes">Recent Changes</a>
      <a href="#methodology-section">How it's Calculated</a>
      <a href="#hall-of-shame">Hall of Shame</a>
      <a href="#all-vendors">All Vendors</a>
    </div>
  </div>
</nav>

<header id="top">
  <div class="container">
    <h1>PM Software Pricing Tracker</h1>
    <p class="subtitle">A weekly snapshot of pricing across the software residential property managers actually use. We normalize prices to "Cost at 500 doors" so you can compare apples to apples, even when one vendor charges per door and another charges per user.</p>
    <div class="meta">
      <span>Last updated <strong>{esc(meta["last_updated"])}</strong></span>
      <span class="dot">·</span>
      <span><strong>{total}</strong> vendors tracked</span>
      <span class="dot">·</span>
      <span>Tracking since <strong>{esc(tracking_start)}</strong></span>
    </div>
    <div class="north-star">
      <strong>Editorial north star:</strong> "{esc(meta["editorial_stance"])}"
    </div>
  </div>
</header>

<main class="container">

  <div class="scorecard" id="scorecard">
    <div class="stat public">
      <div class="number">{public_full}</div>
      <div class="label">Publish full pricing</div>
    </div>
    <div class="stat partial">
      <div class="number">{public_partial}</div>
      <div class="label">Publish partial pricing</div>
    </div>
    <div class="stat gated">
      <div class="number">{gated}</div>
      <div class="label">Hide pricing entirely</div>
    </div>
    <div class="stat pending">
      <div class="number">{pending}</div>
      <div class="label">Need follow-up data</div>
    </div>
  </div>

  {recent_changes_html}

  {methodology_html}

  <section id="hall-of-shame">
    <h2>🔒 Hall of Shame</h2>
    <p class="section-desc">These vendors publish <strong>zero pricing publicly</strong>. We don't shame vendors who have a custom "Enterprise" tier alongside listed prices — that's standard. We shame the ones who show nothing at all.</p>
    <div class="shame-grid">
      {"".join(shame_cards_html)}
    </div>
  </section>

  <section id="all-vendors">
    <h2>📋 All Tracked Vendors</h2>
    <p class="section-desc">Filter by category. Click "See details" inside any row for tier-level pricing, breakdowns at 100 / 350 / 1000 doors, or follow-up notes.</p>

    <div class="filters">
      {filter_buttons_html}
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Vendor</th>
            <th>Status</th>
            <th>Cost at {canonical_size} doors</th>
            <th>History</th>
          </tr>
        </thead>
        <tbody id="vendor-rows">
          {"".join(table_rows_html)}
        </tbody>
      </table>
    </div>
  </section>

</main>

<footer>
  <div class="container">
    <h3 id="methodology">How this works</h3>
    <p>Every Monday, an automated job visits each public pricing page, snapshots it, and compares it to the previous week. Any change — a new tier, a price increase, a removed plan — is committed to this repo. The full pricing history lives in the git log and in each vendor's <code>price_history</code> record.</p>
    <p>For vendors with gated pricing, we monitor Reddit (r/PropertyManagement, r/realestateinvesting, r/Landlord, r/RealEstate) for operator-reported numbers, and pull pricing context from AppFolio's quarterly earnings calls (NASDAQ: APPF).</p>
    <p><strong>Classification framework:</strong> {esc(meta.get("classification_framework", ""))}</p>
    <p><strong>This is not vendor-confirmed pricing.</strong> Always validate with the vendor before signing.</p>
    <p><strong>Spotted an error or a price change?</strong> Open an issue on the repo and we update as soon as we can verify.</p>
    <p>
      <a class="repo-link" href="https://github.com/andrewmswensen-hue/pm-software-prices" target="_blank" rel="noopener">View source on GitHub →</a>
    </p>
  </div>
</footer>

<script>
  const buttons = document.querySelectorAll('.filter-btn');
  const rows = document.querySelectorAll('#vendor-rows tr');
  buttons.forEach(btn => {{
    btn.addEventListener('click', () => {{
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter;
      rows.forEach(row => {{
        if (filter === 'all' || row.dataset.category === filter) {{
          row.style.display = '';
        }} else {{
          row.style.display = 'none';
        }}
      }});
    }});
  }});
</script>

</body>
</html>
'''

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(html_out)
    print(f"docs/index.html generated — {len(vendors)} vendors ({gated} in Hall of Shame), {len(recent_changes)} recent changes, {pending} data-pending")


if __name__ == "__main__":
    render()
