#!/usr/bin/env python3
"""
notify.py — Format and output patrol report.

Reads the patrol JSON data and formats a human-readable audit report.
No external dependencies, no network calls — pure formatting.

Usage:
    echo '<patrol json>' | python notify.py --format markdown
    echo '<patrol json>' | python notify.py --format json
"""

import argparse
import json
import sys
from datetime import datetime, timezone


def format_markdown(patrol: dict) -> str:
    """Format patrol data as a markdown report."""
    dims = patrol.get("dimensions", {})
    lines = []

    lines.append("# 🏥 Production Patrol Report")
    lines.append("")
    lines.append(f"**Patrol ID:** {patrol.get('patrol_id', 'N/A')}")
    lines.append(f"**Time:** {patrol.get('timestamp', 'N/A')}")
    lines.append(f"**Window:** {patrol.get('window_minutes', 60)} minutes")
    lines.append(f"**Result:** {patrol.get('overall_result', 'N/A')}")
    lines.append("")

    # Dimension summary table
    lines.append("## Status Overview")
    lines.append("")
    lines.append("| Dimension | Status | Details |")
    lines.append("|-----------|--------|---------|")

    dim_status = patrol.get("dimension_status", {})
    for dim_key, info in dim_status.items():
        icon = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(info.get("status", "ok"), "❓")
        lines.append(f"| {dim_key} | {icon} {info.get('status', 'unknown').upper()} | {info.get('detail', '')} |")

    # Anomalies
    anomalies = patrol.get("anomalies", [])
    if anomalies:
        lines.append("")
        lines.append("## Anomalies Detected")
        lines.append("")
        for a in anomalies:
            lines.append(f"### {a.get('title', 'Unknown Anomaly')}")
            lines.append(f"- **Classification:** {a.get('classification', 'UNKNOWN')}")
            lines.append(f"- **Fingerprint:** `{a.get('fingerprint', 'N/A')}`")
            lines.append(f"- **Container:** {a.get('container', 'N/A')}")
            lines.append(f"- **First seen:** {a.get('first_seen', 'this patrol')}")
            lines.append(f"- **Occurrences:** {a.get('occurrences', 1)}")
            if a.get("description"):
                lines.append(f"- **Description:** {a['description']}")
            lines.append("")

    # Actions taken
    actions = patrol.get("actions_taken", [])
    if actions:
        lines.append("## Actions Taken")
        lines.append("")
        for act in actions:
            lines.append(f"- **{act.get('action', 'unknown')}** on `{act.get('container', 'N/A')}` — {act.get('reason', '')}")
    else:
        lines.append("## Actions Taken")
        lines.append("")
        lines.append("No actions taken.")

    # Revision info
    revision = dims.get("G_revision", {})
    if revision:
        lines.append("")
        lines.append("## Revision")
        lines.append("")
        lines.append(f"- **Backend image:** `{revision.get('backend_image', 'unknown')}`")
        lines.append(f"- **Agent image:** `{revision.get('agent_image', 'unknown')}`")

    lines.append("")
    lines.append("---")
    lines.append(f"_Report generated at {datetime.now(timezone.utc).isoformat()}_")
    return "\n".join(lines)


def format_json(patrol: dict) -> str:
    """Output patrol data as JSON (passthrough with formatting)."""
    return json.dumps(patrol, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Patrol report formatter")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    data = json.load(sys.stdin)

    if args.format == "markdown":
        print(format_markdown(data))
    else:
        print(format_json(data))


if __name__ == "__main__":
    main()
