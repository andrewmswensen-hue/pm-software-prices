# PM Software Pricing Tracker

A weekly-updated public dashboard that tracks pricing changes across ~30 software vendors used by residential property managers. Built for Peter Lohmann Media (PLM).

## What this is

A GitHub repo whose **README.md is the dashboard**. Anyone can view it at the repo URL. Each weekly commit captures that week's prices, so `git log` is the pricing history.

**Editorial north star:** "Would it help the average property manager to know this?" Vendors with gated pricing are publicly flagged ("name and shame"). See `memory/plm-editorial-stance.md` in `~/.claude/projects/.../memory/` for the full editorial posture.

**Hard rule:** Do NOT use Peter's Crane community as a data source. See `memory/no-crane-data-sourcing.md`.

## How it works

```
Monday 9 AM ET
   ↓
/schedule runs scripts/weekly_update.py
   ↓
1. Fetch each public pricing page → save to data/snapshots/YYYY-MM-DD/
2. Compare to last week's snapshot → detect any changes
3. Update data/vendors.json with new pricing + change log
4. Regenerate README.md from vendors.json
5. Run chatter monitoring: search Reddit/X/LinkedIn for vendor pricing mentions
6. (Quarterly) Pull AppFolio earnings call for pricing commentary
7. Commit + push to GitHub with summary in the commit message
```

## File structure

```
PM-Pricing-Tracker/
├── CLAUDE.md                    ← This file
├── README.md                    ← The dashboard (auto-generated, do not hand-edit)
├── data/
│   ├── vendors.json             ← Master vendor data
│   ├── snapshots/YYYY-MM-DD/    ← Weekly text snapshots per vendor
│   └── chatter/YYYY-MM-DD.json  ← Weekly Reddit/X/LinkedIn findings
├── scripts/
│   ├── weekly_update.py         ← The everything-script
│   ├── render_readme.py         ← Generates README.md from vendors.json
│   └── chatter.py               ← Social media chatter search
└── .gitignore
```

## Data schema

`data/vendors.json` is the source of truth. Schema:

```json
{
  "last_updated": "YYYY-MM-DD",
  "vendors": [
    {
      "name": "Buildium",
      "category": "PM Software",
      "homepage": "https://www.buildium.com/",
      "pricing_url": "https://www.buildium.com/pricing/",
      "status": "public_partial",
      "pricing_model": "Flat monthly, scales with units",
      "tiers": [
        {"name": "Essential", "price_display": "$62/mo", "qualifier": "starts at"}
      ],
      "notes": "5,000+ units needs sales contact.",
      "last_checked": "YYYY-MM-DD",
      "last_changed": "YYYY-MM-DD or null",
      "change_log": []
    }
  ]
}
```

**Status values:**
- `public_full` — full pricing visible, automatable
- `public_partial` — "starts at" or partial tiers visible
- `gated` — contact sales required; name-and-shame treatment
- `js_rendered` — public but needs Playwright (V2)
- `bot_blocked` — blocks HTTP fetches; needs Playwright or manual (V2)

## To-do (V2)

- Playwright integration for the 3 JS-rendered / bot-blocked vendors
- GitHub Pages site for a nicer public-facing presentation
- Webhook to post weekly updates to PLM newsletter draft
- "Hall of Shame" page that lives separately with deeper commentary
- Open-source the data so others can contribute via PR

## Manual updates

If a gated vendor's pricing is learned through a tip, a LinkedIn post, or a podcast guest:

1. Edit `data/vendors.json` for that vendor
2. Add an entry to `change_log` with date + source
3. Run `python scripts/render_readme.py` to regenerate the README
4. Commit with a message like `Manual update: Aptly pricing per LinkedIn post by [name]`

## Maintenance notes

- The weekly job is configured via `/schedule` — see scheduled task list to inspect/edit
- If a vendor moves their pricing page, update `pricing_url` in `vendors.json`
- If a vendor stops gating (or starts gating), update `status` and tweak `tiers`
- Don't commit secrets — there are no API keys needed for V1
