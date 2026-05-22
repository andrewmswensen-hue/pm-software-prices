#!/usr/bin/env python3
"""
generate_snippets.py - Use the Anthropic API to draft 1-2 sentence newsletter
snippets for each detected price change.

Reads /tmp/detected_changes.json (produced by detect_changes.py).
Writes /tmp/email_snippets.json with the same structure plus a "snippet" field
per change.

Requires the anthropic package and ANTHROPIC_API_KEY env var.

If the API call fails (network error, bad key, etc.), the script still writes
the output file, just without snippets. The email layer then falls back to
raw diff display.
"""
import json
import os
import sys
from pathlib import Path

INPUT_FILE = Path("/tmp/detected_changes.json")
OUTPUT_FILE = Path("/tmp/email_snippets.json")

SYSTEM_PROMPT = """You are an editorial assistant for Peter Lohmann Media (PLM), a property management industry media outlet. PLM tracks software pricing for residential property managers.

Your job: given a detected change in a vendor's pricing, write a single newsletter-style snippet (1 to 2 sentences) that PLM could paste into a LinkedIn post, podcast script, or weekly newsletter.

Style guide:
- Crisp, journalistic, factual.
- Lead with what changed and the dollar impact.
- Include a percentage change when calculating it makes sense.
- Mention competitive context only if it's high-signal (e.g., now above or below a major competitor's price).
- Never use em or en dashes. Use commas, hyphens, parens, or sentence splits instead.
- Do not editorialize about whether the change is good or bad. Just state what happened.
- Plain text. No markdown. No emoji.

Output: just the snippet text, nothing else."""


def build_change_prompt(change: dict) -> str:
    parts = [f"Vendor: {change['vendor']}"]
    parts.append(f"Category: {change['category']}")
    parts.append(f"Pricing model: {change['pricing_model']}")
    if change["modified_tiers"]:
        parts.append("Price changes on existing tiers:")
        for name, old, new in change["modified_tiers"]:
            parts.append(f"  - {name}: was {old}, now {new}")
    if change["added_tiers"]:
        parts.append("New tiers added:")
        for name, price in change["added_tiers"]:
            parts.append(f"  - {name}: {price}")
    if change["removed_tiers"]:
        parts.append("Tiers removed:")
        for name, price in change["removed_tiers"]:
            parts.append(f"  - {name} (was {price})")
    return "\n".join(parts)


def main():
    if not INPUT_FILE.exists():
        print("ERROR: detected_changes.json not found", file=sys.stderr)
        return 2

    payload = json.loads(INPUT_FILE.read_text())
    changes = payload.get("changes", [])

    if not changes:
        OUTPUT_FILE.write_text(json.dumps({**payload, "changes": []}, indent=2))
        print("No changes to process")
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("WARNING: ANTHROPIC_API_KEY not set, skipping snippet generation", file=sys.stderr)
        for c in changes:
            c["snippet"] = None
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2))
        return 0

    try:
        from anthropic import Anthropic
    except ImportError:
        print("WARNING: anthropic package not installed, skipping snippet generation", file=sys.stderr)
        for c in changes:
            c["snippet"] = None
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2))
        return 0

    client = Anthropic(api_key=api_key)

    for c in changes:
        prompt = build_change_prompt(c)
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    text += block.text
            c["snippet"] = text.strip() or None
            print(f"  Snippet generated for {c['vendor']}")
        except Exception as e:
            print(f"  ERROR generating snippet for {c['vendor']}: {e}", file=sys.stderr)
            c["snippet"] = None

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
