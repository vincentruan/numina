#!/usr/bin/env python3
"""Sync upstream os-taxonomy data and detect changes against the local translated package.

Usage:
    cd server
    uv run python ../.claude/skills/learning-content-translate/scripts/sync-taxonomy.py [--init] [--dry-run]

Modes:
    (default)   Pull latest upstream, compare against packages/os_taxonomy/, print change summary
    --init      Initialize submodule if not present, then do full compare
    --dry-run   Show what would change without writing anything
    --json      Output change summary as JSON (for scripting)

The upstream data lives in a git submodule at:
    .claude/skills/learning-content-translate/references/os-taxonomy/
Sync via: git submodule update --init --remote .claude/skills/learning-content-translate/references/os-taxonomy
Override path via LEARNING_TAXONOMY_DIR env var.
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
SERVER_ROOT = REPO_ROOT / "server"
SUBMODULE_PATH = ".claude/skills/learning-content-translate/references/os-taxonomy"
UPSTREAM_DIR = REPO_ROOT / SUBMODULE_PATH
PACKAGE_DIR = SERVER_ROOT / "packages" / "os_taxonomy"
UPSTREAM_REPO = "git@github.com:withmarbleapp/os-taxonomy.git"

# Fields that indicate content change (cosmetic changes like centrality don't trigger retranslation)
TOPIC_CONTENT_FIELDS = ("name", "description", "evidence", "assessmentPrompt")
CLUSTER_CONTENT_FIELDS = ("summary",)


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd or UPSTREAM_DIR,
        capture_output=True,
        text=True,
        check=True,
    )


def ensure_upstream(init: bool = False) -> Path:
    """Ensure upstream submodule is initialized and up to date.

    Returns the upstream data directory path.
    """
    import os

    data_dir = Path(os.environ.get("LEARNING_TAXONOMY_DIR", UPSTREAM_DIR))

    if not data_dir.exists() or not (data_dir / ".git").exists():
        if not init:
            print(
                f"Upstream submodule not initialized at {data_dir}. "
                f"Run with --init or:\n"
                f"  git submodule update --init --remote {SUBMODULE_PATH}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Initializing os-taxonomy submodule → {data_dir}")
        subprocess.run(
            ["git", "submodule", "update", "--init", "--remote", SUBMODULE_PATH],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
    else:
        # Pull latest via submodule update --remote
        print(f"Pulling latest from upstream...")
        result = subprocess.run(
            ["git", "submodule", "update", "--remote", SUBMODULE_PATH],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if not result.stdout.strip():
            print("  Already up to date.")
        else:
            print(f"  Updated.")

    return data_dir


def get_upstream_commit() -> str:
    """Get the current commit hash of the upstream repo."""
    result = run_git("rev-parse", "--short", "HEAD")
    return result.stdout.strip()


def load_json(path: Path) -> dict:
    """Load a JSON file, returning empty dict if not found."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def index_topics_by_id(topics: list[dict]) -> dict[str, dict]:
    """Index topics by their stable `id` field."""
    return {t["id"]: t for t in topics}


def index_clusters_by_key(clusters: list[dict]) -> dict[str, dict]:
    """Index clusters by (subject, domain, ageRangeStart) composite key."""
    return {
        f"{c['subject']}|{c['domain']}|{c.get('ageRangeStart', 0)}": c
        for c in clusters
    }


def detect_topic_changes(
    upstream: dict[str, dict],
    current: dict[str, dict],
) -> tuple[list[str], list[str], list[str]]:
    """Detect new, modified, and removed topic IDs.

    A topic is "modified" if any content field (name, description, evidence,
    assessmentPrompt) differs. Centrality changes are NOT considered modifications.
    """
    upstream_ids = set(upstream.keys())
    current_ids = set(current.keys())

    new_ids = sorted(upstream_ids - current_ids)
    removed_ids = sorted(current_ids - upstream_ids)

    modified_ids = []
    for tid in sorted(upstream_ids & current_ids):
        u = upstream[tid]
        c = current[tid]
        for field in TOPIC_CONTENT_FIELDS:
            if u.get(field) != c.get(field):
                modified_ids.append(tid)
                break

    return new_ids, modified_ids, removed_ids


def detect_cluster_changes(
    upstream: dict[str, dict],
    current: dict[str, dict],
) -> tuple[list[str], list[str], list[str]]:
    """Detect new, modified, and removed clusters."""
    upstream_keys = set(upstream.keys())
    current_keys = set(current.keys())

    new_keys = sorted(upstream_keys - current_keys)
    removed_keys = sorted(current_keys - upstream_keys)

    modified_keys = []
    for key in sorted(upstream_keys & current_keys):
        u = upstream[key]
        c = current[key]
        for field in CLUSTER_CONTENT_FIELDS:
            if u.get(field) != c.get(field):
                modified_keys.append(key)
                break

    return new_keys, modified_keys, removed_keys


def sync(dry_run: bool = False, init: bool = False, output_json: bool = False) -> dict:
    """Run the sync and return change summary.

    Returns a dict with change details for scripting.
    """
    # Ensure upstream
    upstream_dir = ensure_upstream(init=init)
    data_dir = upstream_dir / "data" if (upstream_dir / "data").is_dir() else upstream_dir
    commit = get_upstream_commit()

    # Load upstream data
    upstream_topics_raw = load_json(data_dir / "topics.json")
    upstream_clusters_raw = load_json(data_dir / "clusters.json")
    upstream_deps_raw = load_json(data_dir / "dependencies.json")

    upstream_topics = index_topics_by_id(upstream_topics_raw.get("topics", []))
    upstream_clusters = index_clusters_by_key(upstream_clusters_raw.get("clusters", []))

    # Load current package data
    current_topics_raw = load_json(PACKAGE_DIR / "topics.json")
    current_clusters_raw = load_json(PACKAGE_DIR / "clusters.json")

    current_topics = index_topics_by_id(current_topics_raw.get("topics", []))
    current_clusters = index_clusters_by_key(current_clusters_raw.get("clusters", []))

    # Detect changes
    new_topic_ids, modified_topic_ids, removed_topic_ids = detect_topic_changes(
        upstream_topics, current_topics
    )
    new_cluster_keys, modified_cluster_keys, removed_cluster_keys = detect_cluster_changes(
        upstream_clusters, current_clusters
    )

    # Dependency count comparison
    upstream_dep_count = len(upstream_deps_raw.get("dependencies", []))
    current_dep_count = len(load_json(PACKAGE_DIR / "dependencies.json").get("dependencies", []))
    deps_changed = upstream_dep_count != current_dep_count or not (PACKAGE_DIR / "dependencies.json").exists()

    # Summary
    topics_needing_translation = len(new_topic_ids) + len(modified_topic_ids)
    clusters_needing_translation = len(new_cluster_keys) + len(modified_cluster_keys)

    summary = {
        "upstream": {
            "version": upstream_topics_raw.get("version", "unknown"),
            "commit": commit,
            "topicCount": len(upstream_topics),
            "clusterCount": len(upstream_clusters),
            "dependencyCount": upstream_dep_count,
        },
        "changes": {
            "newTopics": new_topic_ids,
            "modifiedTopics": modified_topic_ids,
            "removedTopics": removed_topic_ids,
            "newClusters": new_cluster_keys,
            "modifiedClusters": modified_cluster_keys,
            "removedClusters": removed_cluster_keys,
            "dependenciesChanged": deps_changed,
        },
        "translationNeeded": {
            "topics": topics_needing_translation,
            "clusters": clusters_needing_translation,
        },
    }

    if output_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary

    # Human-readable output
    version = upstream_topics_raw.get("version", "unknown")
    if not str(version).startswith("v"):
        version = f"v{version}"
    print(f"\nos-taxonomy sync complete")
    print(f"  Upstream: {version} "
          f"({summary['upstream']['topicCount']} topics, "
          f"{summary['upstream']['clusterCount']} clusters, "
          f"{summary['upstream']['dependencyCount']} dependencies)")
    print(f"  Commit: {commit}")
    print()

    if not any([
        new_topic_ids, modified_topic_ids, removed_topic_ids,
        new_cluster_keys, modified_cluster_keys, removed_cluster_keys,
        deps_changed,
    ]):
        print("  No changes detected. Package is up to date.")
        return summary

    print("  Changes detected:")
    if new_topic_ids:
        print(f"    New topics:       {len(new_topic_ids)}")
    if modified_topic_ids:
        print(f"    Modified topics:  {len(modified_topic_ids)}")
    if removed_topic_ids:
        print(f"    Removed topics:   {len(removed_topic_ids)}")
    if new_cluster_keys:
        print(f"    New clusters:     {len(new_cluster_keys)}")
    if modified_cluster_keys:
        print(f"    Modified clusters:{len(modified_cluster_keys)}")
    if removed_cluster_keys:
        print(f"    Removed clusters: {len(removed_cluster_keys)}")
    if deps_changed:
        print(f"    Dependencies:     updated ({upstream_dep_count} edges)")
    print()

    if topics_needing_translation or clusters_needing_translation:
        print(f"  → Run translate-to-package.py to translate "
              f"{topics_needing_translation + clusters_needing_translation} items "
              f"({topics_needing_translation} topics + {clusters_needing_translation} clusters)")
    else:
        print("  No translations needed (only removals or dependency updates).")

    if dry_run and (removed_topic_ids or removed_cluster_keys):
        print()
        print("  Removed items (dry run — not applying):")
        for tid in removed_topic_ids[:10]:
            name = current_topics[tid].get("name", "?")
            print(f"    topic: {tid} — {name}")
        if len(removed_topic_ids) > 10:
            print(f"    ... and {len(removed_topic_ids) - 10} more")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync os-taxonomy upstream and detect changes")
    parser.add_argument("--init", action="store_true", help="Clone upstream repo if not present")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    sync(dry_run=args.dry_run, init=args.init, output_json=args.json)
