#!/usr/bin/env python3
"""Sync the Beijing taxonomy (os-taxonomy-beijing) data clone.

Usage:
    python .claude/skills/learning-content-translate/scripts/sync-beijing-taxonomy.py [--dry-run]

Pulls the latest data from the Beijing taxonomy repo at
    server/data/os-taxonomy-beijing/
and prints the current commit hash plus the follow-up steps
(dedup + re-seed). No LLM translation is needed — the Beijing
dataset is pre-translated Chinese.

    --dry-run   Show what would happen (commit + next steps) without
                running git pull.
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
BEIJING_DIR = REPO_ROOT / "server" / "data" / "os-taxonomy-beijing"
BEIJING_REPO = "https://github.com/luw2007/os-taxonomy-beijing.git"

NEXT_STEPS = """\

Next steps (run from the repo root):

  1. Dedup pipeline — merge Beijing data, resolve duplicates:
       cd server
       uv run python -m os_taxonomy.dedup --source beijing --fallback

  2. Review the generated dedup_mapping.json (which Beijing entries
     were merged vs kept).

  3. Re-seed the DB with Beijing data:
       cd server
       uv run python scripts/seed_learning_topics.py --source beijing \
         --data-dir server/data/os-taxonomy-beijing/data

No LLM translation is needed — the Beijing dataset is pre-translated.
"""


def run_git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in the Beijing clone and return the result."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def commit_hash(cwd: Path) -> str | None:
    """Return the short HEAD hash, or None if not a git repo."""
    result = run_git("rev-parse", "--short", "HEAD", cwd=cwd)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def is_git_repo(cwd: Path) -> bool:
    """True if `cwd` is inside an initialized git repository."""
    return run_git("rev-parse", "--is-inside-work-tree", cwd=cwd).returncode == 0


def sync(dry_run: bool = False) -> None:
    if not BEIJING_DIR.exists() or not is_git_repo(BEIJING_DIR):
        print(f"Beijing taxonomy not initialized at {BEIJING_DIR}", file=sys.stderr)
        print(
            "Initialize it first with:\n"
            f"  cd {BEIJING_DIR.parent}\n"
            f"  git clone {BEIJING_REPO} os-taxonomy-beijing",
            file=sys.stderr,
        )
        sys.exit(1)

    if dry_run:
        print(f"[dry-run] Would run: git -C {BEIJING_DIR} pull")
    else:
        print(f"Pulling latest Beijing taxonomy from {BEIJING_REPO} ...")
        result = run_git("pull", cwd=BEIJING_DIR)
        if result.returncode != 0:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            print("git pull failed — check network / SSH access and retry.", file=sys.stderr)
            sys.exit(1)
        out = (result.stdout + result.stderr).strip()
        print("  " + out.replace("\n", "\n  ") if out else "  Already up to date.")

    head = commit_hash(BEIJING_DIR)
    print(f"\nBeijing taxonomy @ {BEIJING_DIR}")
    print(f"  Current commit: {head or 'unknown (not a git repo)'}")
    print(NEXT_STEPS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pull latest os-taxonomy-beijing data and print follow-up steps"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without running git pull",
    )
    args = parser.parse_args()
    sync(dry_run=args.dry_run)
