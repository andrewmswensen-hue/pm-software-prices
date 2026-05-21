#!/usr/bin/env python3
"""
render_dashboard.py — Build the live HTML dashboard at docs/index.html.

Reads data/vendors.json and produces a clean, mobile-friendly static page that
can be served by GitHub Pages from the /docs folder. The page includes:
  - Header + transparency scorecard
  - Recent Notable Changes (auto-derived from price_history diffs)
  - Hall of Shame (vendors with zero pricing visible publicly)
  - Filterable, sortable table of all vendors with tracking-since indicators

The dashboard is fully static — no fetches, no build tools, no JS framework.
Tiny inline JS handles category filtering only.

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

CATEGORY_ORDER = [
    "PM Software", "Maintenance", "Leasing", "Resident Benefits",
    "Listings/Marketing", "Inspections", "CRM/Workflow",
    "Communications", "Finance", "Payments", "Industry Association",
]


def esc(s):
    if s is None:
        return ""
    return html.escape(str(s))


def render_tiers(tiers):
    if not tiers:
        return '<span style="color:#78716c">—</span>'
    parts = []
    for t in tiers:
        name = esc(t.get("name", ""))
        price = esc(t.get("price_display", ""))
        qualifier = esc(t.get("qualifier", ""))
        highlighted = "highlighted" if t.get("highlighted") else ""
        if qualifier:
            parts.append(
                f'<div class="tier"><span class="tier-name {highlighted}">{name}:</span> '
                f'<span class="qualifier">{qualifier}</span> {price}</div>'
            )
        else:
            parts.append(
                f'<div class="tier"><span class="tier-name {highlighted}">{name}:</span> {price}</div>'
            )
    return "".join(parts)


def compute_recent_changes(vendors):
    """Look at each vendor's price_history. If it has 2+ entries, compute the diff
    between the most recent and the prior entry. Return a sorted list of changes."""
    changes = []
    for v in vendors:
        history = v.get("price_history", [])
        if len(history) < 2:
            continue
        prev_entry = history[-2]
        curr_entry = history[-1]
        prev_tiers = prev_entry.get("tiers", {})
        curr_tiers = curr_entry.get("tiers", {})

        for tier_name, new_price in curr_tiers.items():
            old_price = prev_tiers.get(tier_name)
            if old_price is None:
                changes.append({
                    "date": curr_entry["date"],
                    "vendor": v["name"],
                    "pricing_url": v.get("pricing_url", ""),
                    "kind": "tier_added",
                    "tier": tier_name,
                    "new": new_price,
                })
            elif old_price != new_price:
                changes.append({
                    "date": curr_entry["date"],
                    "vendor": v["name"],
                    "pricing_url": v.get("pricing_url", ""),
                    "kind": "price_changed",
                    "tier": tier_name,
                    "old": old_price,
                    "new": new_price,
                })

        for tier_name, old_price in prev_tiers.items():
            if tier_name not in curr_tiers:
                changes.append({
                    "date": curr_entry["date"],
                    "vendor": v["name"],
                    "pricing_url": v.get("pricing_url", ""),
                    "kind": "tier_removed",
                    "tier": tier_name,
                    "old": old_price,
                })

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
    for c in changes[:10]:  # cap at 10 most recent
        if c["kind"] == "price_changed":
            badge = '<span class="change-badge price">Price change</span>'
            body = f'<strong>{esc(c["tier"])}</strong>: <span class="old-price">{esc(c["old"])}</span> → <span class="new-price">{esc(c["new"])}</span>'
        elif c["kind"] == "tier_added":
            badge = '<span class="change-badge added">New tier</span>'
            body = f'<strong>{esc(c["tier"])}</strong>: {esc(c["new"])}'
        else:  # tier_removed
            badge = '<span class="change-badge removed">Tier removed</span>'
            body = f'<strong>{esc(c["tier"])}</strong> (was {esc(c["old"])})'

        items_html.append(f'''
        <li class="change-item">
          <div class="change-date">{esc(c["date"])}</div>
          <div class="change-body">
            <a href="{esc(c["pricing_url"])}" target="_blank" rel="noopener" class="change-vendor">{esc(c["vendor"])}</a>
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
    total_trackable = total - gated

    # Earliest tracking_since date
    tracking_dates = [v.get("tracking_since") for v in vendors if v.get("tracking_since")]
    tracking_start = min(tracking_dates) if tracking_dates else meta["last_updated"]

    shamed = [v for v in vendors if v["status"] == "gated"]
    shamed.sort(key=lambda v: (v["category"], v["name"]))

    recent_changes = compute_recent_changes(vendors)
    recent_changes_html = render_recent_changes(recent_changes, total_trackable, tracking_start)

    categories_present = sorted(
        {v["category"] for v in vendors if v["status"] != "gated"},
        key=lambda c: CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99,
    )

    # Hall of Shame cards
    shame_cards_html = []
    for v in shamed:
        intel_html = ""
        if v.get("third_party_intel"):
            intel_html = (
                f'<p class="intel"><strong>What operators report:</strong> '
                f'{esc(v["third_party_intel"])}</p>'
            )
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
        notes_html = esc(v.get("notes", "")) if v.get("notes") else ""
        tracking_since = v.get("tracking_since", "")
        history_count = len(v.get("price_history", []))
        history_cell = f'<div class="history-cell"><span class="tracking-since">Tracking since {esc(tracking_since)}</span><span class="data-points">{history_count} data point{"s" if history_count != 1 else ""}</span></div>'

        row = f'''
            <tr data-category="{esc(v["category"])}" data-status="{esc(v["status"])}">
              <td class="vendor">
                <a href="{esc(v["pricing_url"])}" target="_blank" rel="noopener">{esc(v["name"])}</a>
                <span class="category-tag">{esc(v["category"])}</span>
              </td>
              <td><span class="badge {esc(v["status"])}">{emoji} {label}</span></td>
              <td class="tiers">{render_tiers(v.get("tiers", []))}</td>
              <td class="history">{history_cell}</td>
              <td class="notes">{notes_html}</td>
            </tr>
        '''
        table_rows_html.append(row)

    # Filter buttons
    filter_buttons_html = '<button class="filter-btn active" data-filter="all">All</button>'
    for cat in categories_present:
        filter_buttons_html += (
            f'<button class="filter-btn" data-filter="{esc(cat)}">{esc(cat)}</button>'
        )

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
<header>
  <div class="container">
    <h1>PM Software Pricing Tracker</h1>
    <p class="subtitle">A weekly snapshot of pricing across the software residential property managers actually use. We publish every change so PMs can make informed buying decisions — even when vendors would rather you call sales.</p>
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

  <div class="scorecard">
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
    <div class="stat manual">
      <div class="number">{manual}</div>
      <div class="label">Verified manually</div>
    </div>
  </div>

  {recent_changes_html}

  <section id="hall-of-shame">
    <h2>🔒 Hall of Shame</h2>
    <p class="section-desc">These vendors publish <strong>zero pricing publicly</strong>. We don't shame vendors who have a custom "Enterprise" tier alongside listed prices — that's standard. We shame the ones who show nothing at all.</p>
    <div class="shame-grid">
      {"".join(shame_cards_html)}
    </div>
  </section>

  <section id="all-vendors">
    <h2>📋 All Tracked Vendors</h2>
    <p class="section-desc">Filter by category. Click any vendor name to visit their pricing page directly.</p>

    <div class="filters">
      {filter_buttons_html}
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Vendor</th>
            <th>Status</th>
            <th>Pricing</th>
            <th>History</th>
            <th>Notes</th>
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
    <h3>How this works</h3>
    <p>Every Monday, an automated job visits each public pricing page, snapshots it, and compares it to the previous week. Any change — a new tier, a price increase, a removed plan — is committed to this repo. The full pricing history lives in the git log and in each vendor's <code>price_history</code> record.</p>
    <p>For vendors with gated pricing, we monitor Reddit (r/PropertyManagement, r/realestateinvesting, r/Landlord, r/RealEstate) for operator-reported numbers, and pull pricing context from AppFolio's quarterly earnings calls (they're publicly traded on NASDAQ as APPF).</p>
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
    print(f"docs/index.html generated — {len(vendors)} vendors ({gated} in Hall of Shame), {len(recent_changes)} recent changes")


if __name__ == "__main__":
    render()
