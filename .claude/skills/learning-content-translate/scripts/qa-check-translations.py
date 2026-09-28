#!/usr/bin/env python3
"""Check translation quality and coverage from the JSON package (source of truth).

Usage:
    cd server
    uv run python ../.claude/skills/learning-content-translate/scripts/qa-check-translations.py

Reads from server/packages/os_taxonomy/ — the authoritative translated data.
The DB is a derived runtime cache for multi-node cluster sharing; this script
does NOT depend on DB state.

Shows:
    - Coverage stats (translated / total)
    - High-centrality topic spot-check (30 topics)
    - Missing translations report
"""

import json
import sys
from pathlib import Path

# Paths
SERVER_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent / "server"
PACKAGE_DIR = SERVER_ROOT / "packages" / "os_taxonomy"


def load_package_topics() -> list[dict]:
    """Load topics from the JSON package (source of truth)."""
    path = PACKAGE_DIR / "topics.json"
    if not path.exists():
        print(f"Package not found at {path}. Run translate-to-package.py first.", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("topics", [])


def load_package_clusters() -> list[dict]:
    """Load clusters from the JSON package."""
    path = PACKAGE_DIR / "clusters.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("clusters", [])


def check_quality(limit: int = 30, min_centrality: float = 0.5) -> None:
    """Check translation quality and coverage from the JSON package."""
    topics = load_package_topics()
    clusters = load_package_clusters()

    # --- Coverage stats ---
    total = len(topics)
    translated = sum(1 for t in topics if t.get("nameZh") and t.get("descriptionZh"))
    partial = sum(
        1 for t in topics
        if (t.get("nameZh") or t.get("descriptionZh"))
        and not (t.get("nameZh") and t.get("descriptionZh"))
    )
    untranslated = total - translated - partial

    cluster_total = len(clusters)
    cluster_translated = sum(1 for c in clusters if c.get("summaryZh"))

    print("=" * 80)
    print("Translation Coverage (from packages/os_taxonomy/ — source of truth)")
    print("=" * 80)
    print(f"Topics:     {translated}/{total} translated"
          f" ({translated * 100 // total}%)"
          f"  [{partial} partial, {untranslated} untranslated]")
    print(f"Clusters:   {cluster_translated}/{cluster_total} translated"
          f" ({cluster_translated * 100 // cluster_total if cluster_total else 0}%)"
          if cluster_total else "Clusters:   0")

    # Per-subject breakdown
    subjects: dict[str, dict[str, int]] = {}
    for t in topics:
        subj = t.get("subject", "Unknown")
        if subj not in subjects:
            subjects[subj] = {"total": 0, "translated": 0}
        subjects[subj]["total"] += 1
        if t.get("nameZh") and t.get("descriptionZh"):
            subjects[subj]["translated"] += 1

    print()
    print(f"{'Subject':30s} | {'Translated':>10s} | {'Total':>6s} | {'Coverage':>8s}")
    print("-" * 65)
    for subj in sorted(subjects.keys()):
        s = subjects[subj]
        pct = s["translated"] * 100 // s["total"] if s["total"] else 0
        print(f"{subj:30s} | {s['translated']:>10d} | {s['total']:>6d} | {pct:>7d}%")

    # --- Spot check: high-centrality topics ---
    high_value = sorted(
        [t for t in topics if t.get("centrality", 0) > min_centrality],
        key=lambda t: t.get("centrality", 0),
        reverse=True,
    )[:limit]

    if high_value:
        print()
        print(f"Spot-check: top {len(high_value)} high-centrality topics (centrality > {min_centrality})")
        print("-" * 100)
        print(f"{'Subject':15s} | {'English':35s} | {'Chinese':35s} | {'OK?'}")
        print("-" * 100)
        for t in high_value:
            name_en = t.get("name", "")[:35]
            name_zh = t.get("nameZh", "")[:35]
            has_zh = "✓" if t.get("nameZh") else "✗ MISSING"
            print(f"{t.get('subject', '')[:15]:15s} | {name_en:35s} | {name_zh:35s} | {has_zh}")

    # --- High-value untranslated ---
    high_untranslated = [
        t for t in topics
        if not t.get("nameZh") and t.get("centrality", 0) > 0.3
    ]
    if high_untranslated:
        print()
        print(f"⚠ {len(high_untranslated)} high-value topics (centrality > 0.3) still untranslated:")
        for t in sorted(high_untranslated, key=lambda x: x.get("centrality", 0), reverse=True)[:10]:
            print(f"  {t['id']}  centrality={t.get('centrality', 0):.3f}  {t.get('subject', '')} / {t.get('name', '')}")
    else:
        print()
        print("✓ All high-value topics (centrality > 0.3) are translated.")

    # --- Assessment prompt check ---
    empty_prompts = sum(
        1 for t in topics
        if t.get("nameZh") and not t.get("assessmentPromptZh")
    )
    if empty_prompts:
        print(f"⚠ {empty_prompts} translated topics missing assessmentPromptZh")


if __name__ == "__main__":
    check_quality()
