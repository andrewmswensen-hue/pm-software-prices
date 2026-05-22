#!/usr/bin/env python3
"""
build_email.py - Assemble the HTML email body from /tmp/email_snippets.json.

Writes /tmp/email_body.html. The GitHub Actions email step reads this file
and sends it as the message body.

Subject line is also written to /tmp/email_subject.txt for the workflow to
pick up via GITHUB_OUTPUT.
"""
import html
import json
import sys
from pathlib import Path

INPUT_FILE = Path("/tmp/email_snippets.json")
HTML_OUTPUT = Path("/tmp/email_body.html")
SUBJECT_OUTPUT = Path("/tmp/email_subject.txt")

DASHBOARD_URL = "https://andrewmswensen-hue.github.io/pm-software-prices/"
REPO_URL = "https://github.com/andrewmswensen-hue/pm-software-prices"


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def render_change(c: dict) -> str:
    rows = []
    if c.get("modified_tiers"):
        for name, old, new in c["modified_tiers"]:
            rows.append(
                f'<li><strong>{esc(name)}:</strong> '
                f'<span style="color:#9ca3af;text-decoration:line-through">{esc(old)}</span> '
                f'<span style="color:#dc2626;font-weight:600">{esc(new)}</span></li>'
            )
    if c.get("added_tiers"):
        for name, price in c["added_tiers"]:
            rows.append(
                f'<li><strong>{esc(name)}:</strong> new tier at <strong>{esc(price)}</strong></li>'
            )
    if c.get("removed_tiers"):
        for name, price in c["removed_tiers"]:
            rows.append(
                f'<li><strong>{esc(name)}:</strong> tier removed (was {esc(price)})</li>'
            )

    snippet_html = ""
    if c.get("snippet"):
        snippet_html = f'''
        <div style="background:#f9fafb;border-left:3px solid #1e40af;padding:14px 18px;border-radius:4px;margin:14px 0;font-size:15px;line-height:1.55;color:#1c1917">
          {esc(c["snippet"])}
        </div>
        '''

    return f'''
    <div style="border:1px solid #e7e5e4;border-radius:8px;padding:20px 24px;margin-bottom:18px;background:#fff">
      <h3 style="margin:0 0 4px;font-size:17px">
        <a href="{esc(c["pricing_url"])}" style="color:#1c1917;text-decoration:none">{esc(c["vendor"])}</a>
      </h3>
      <p style="margin:0 0 12px;color:#78716c;font-size:13px">{esc(c["category"])} - {esc(c["pricing_model"])}</p>
      {snippet_html}
      <ul style="margin:8px 0 0;padding-left:20px;color:#1c1917;font-size:14px;line-height:1.7">
        {"".join(rows)}
      </ul>
    </div>
    '''


def main():
    if not INPUT_FILE.exists():
        print("ERROR: email_snippets.json not found", file=sys.stderr)
        return 2

    payload = json.loads(INPUT_FILE.read_text())
    changes = payload.get("changes", [])
    date = payload.get("date", "")

    if not changes:
        # Nothing to email
        HTML_OUTPUT.write_text("")
        SUBJECT_OUTPUT.write_text("")
        return 0

    count = len(changes)
    word = "vendor" if count == 1 else "vendors"
    subject = f"PM Pricing Tracker: {count} {word} changed this week"
    SUBJECT_OUTPUT.write_text(subject)

    change_blocks = "".join(render_change(c) for c in changes)

    body = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body style="margin:0;padding:0;background:#fafaf9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1c1917">
<div style="max-width:680px;margin:0 auto;padding:32px 24px">

  <div style="background:#fff;border-radius:12px;padding:28px;border:1px solid #e7e5e4">

    <h1 style="margin:0 0 6px;font-size:24px;letter-spacing:-0.02em">PM Pricing Tracker</h1>
    <p style="margin:0 0 24px;color:#78716c;font-size:14px">Weekly update for {esc(date)}</p>

    <div style="background:#fef3c7;border-radius:6px;padding:14px 18px;margin-bottom:24px;color:#92400e;font-weight:500">
      {count} {word} changed pricing this week.
    </div>

    {change_blocks}

    <div style="margin-top:32px;padding-top:24px;border-top:1px solid #e7e5e4;text-align:center">
      <a href="{DASHBOARD_URL}" style="display:inline-block;background:#1c1917;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:500;font-size:14px">View full dashboard</a>
    </div>

    <p style="margin:24px 0 0;color:#78716c;font-size:12px;line-height:1.55;text-align:center">
      Tracker maintained by Peter Lohmann Media.<br>
      <a href="{REPO_URL}" style="color:#78716c">View source on GitHub</a>
    </p>

  </div>

</div>
</body>
</html>
'''

    HTML_OUTPUT.write_text(body)
    print(f"Email body assembled for {count} change(s). Subject: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
