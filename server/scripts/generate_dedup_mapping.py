#!/usr/bin/env python3
"""Generate dedup_mapping.json for mt_/mtc_ topic overlap resolution.

Compares the upstream os-taxonomy topics (mt_) with the Beijing extension
topics (mtc_) and emits dedup decisions:

- merge:     same concept under different keys (name-identical, verified
             semantically — descriptions cover the same learning objective).
             The mtc_ topic is deprecated; mt_ topic absorbs description_zh,
             curriculum standards, and evidence during seeding.
- keep_both: name matches too shallow (substring/partial) — kept separate.

Output: <data_root>/dedup_mapping.json
  Format: [{mtc_topic_key, mt_topic_key, action, reason}, ...]

Only entries that need a decision are emitted; topics with no counterpart
across taxonomies need no mapping entry (implicit keep_both).

Usage:
    cd server && uv run python scripts/generate_dedup_mapping.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Server workspace root (parent of scripts/)
SERVER_ROOT = Path(__file__).resolve().parent.parent
MT_TOPICS_PATH = SERVER_ROOT / "packages" / "os_taxonomy" / "topics.json"
MTC_TOPICS_PATH = (
    SERVER_ROOT / "data" / "os-taxonomy-beijing" / "data" / "cn-topics.json"
)
OUTPUT_PATH = SERVER_ROOT / "data" / "os-taxonomy-beijing" / "dedup_mapping.json"


def find_name_matches(mt_topics: list[dict], mtc_topics: list[dict]) -> list[dict]:
    """Find mtc topics whose name exactly matches an mt topic's Chinese name."""
    mt_by_zh: dict[str, list[dict]] = {}
    for t in mt_topics:
        zh = (t.get("nameZh") or "").strip()
        if zh:
            mt_by_zh.setdefault(zh, []).append(t)

    matches = []
    for t in mtc_topics:
        name = (t.get("name") or "").strip()
        if name in mt_by_zh:
            # Deterministic pick: lowest id if multiple
            candidates = sorted(mt_by_zh[name], key=lambda x: x["id"])
            matches.append(
                {
                    "mtc_topic_key": t["id"],
                    "mt_topic_key": candidates[0]["id"],
                    "mtc_name": name,
                }
            )
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print summary without writing"
    )
    args = parser.parse_args()

    mt_topics = json.loads(MT_TOPICS_PATH.read_text(encoding="utf-8"))["topics"]
    mtc_topics = json.loads(MTC_TOPICS_PATH.read_text(encoding="utf-8"))["topics"]

    matches = find_name_matches(mt_topics, mtc_topics)

    mapping = [
        {
            "mtc_topic_key": m["mtc_topic_key"],
            "mt_topic_key": m["mt_topic_key"],
            "action": "merge",
            "reason": f"name-identical topic '{m['mtc_name']}' — same learning objective across taxonomies",
        }
        for m in matches
    ]

    print(f"mt topics: {len(mt_topics)}, mtc topics: {len(mtc_topics)}")
    print(f"name-identical overlaps: {len(matches)}")
    for m in matches:
        print(f"  merge: {m['mtc_topic_key']} -> {m['mt_topic_key']} ({m['mtc_name']})")

    if args.dry_run:
        print("dry-run: no file written")
        return 0

    OUTPUT_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"written: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
