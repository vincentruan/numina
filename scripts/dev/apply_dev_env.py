#!/usr/bin/env python3
"""scripts/dev/apply_dev_env.py — Apply dev environment overrides to .env

Called by dev-all.sh / dev-all.ps1 before starting dev servers.
Adjusts DATABASE_URL and cache/Redis settings based on DB= and CACHE= params.

Rules:
  - If the requested type matches the current type, preserve existing connection
    details (URL, username, password, host, port).
  - If the type differs, update to a sensible dev default and print a notice.
  - Never delete user-customized connection info when the type already matches.

Usage:
    python scripts/dev/apply_dev_env.py [--db sqlite|pgsql] [--cache memory|redis]
"""

from __future__ import annotations

import argparse
import os
import sys

# Fix Windows console encoding (GBK can't print Unicode symbols)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
import re
import sys
from pathlib import Path

# ── defaults ──────────────────────────────────────────────────────────────

DEV_PGSQL_URL = "postgresql://numina:numinapass@localhost:5432/numina"
DEV_DEERFLOW_PGSQL_URL = "postgresql://numina:numinapass@localhost:5432/numina_deerflow"
DEV_REDIS_URL = "redis://localhost:6379/0"
DEV_SQLITE_URL = "sqlite:////app/.numina/data/db/numina.db"

# Keys relevant to each dimension
DB_KEYS = {"DATABASE_URL", "DEERFLOW_DB_URL"}
CACHE_KEYS = {"CACHE_BACKEND", "STREAM_BRIDGE_TYPE", "REDIS_URL"}


def parse_env(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Preserves comments/order via separate list."""
    result: dict[str, str] = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        result[key.strip()] = value.strip()
    return result


def detect_db_type(url: str) -> str:
    """Detect DB type from a DATABASE_URL."""
    if not url:
        return "sqlite"
    url_lower = url.lower()
    if url_lower.startswith("sqlite"):
        return "sqlite"
    if url_lower.startswith(("postgresql", "postgres")):
        return "pgsql"
    return "unknown"


def detect_cache_type(env: dict[str, str]) -> str:
    """Detect cache type from env vars."""
    backend = env.get("CACHE_BACKEND", "memory").lower()
    if backend == "redis":
        return "redis"
    bridge = env.get("STREAM_BRIDGE_TYPE", "").lower()
    if bridge == "redis":
        return "redis"
    return "memory"


def apply_db(env: dict[str, str], target: str) -> list[str]:
    """Apply DB changes. Returns list of notice messages."""
    notices: list[str] = []
    current_url = env.get("DATABASE_URL", "")
    current_type = detect_db_type(current_url)

    if target == current_type:
        # Type matches — preserve user's connection details
        return notices

    # Type differs — update
    if target == "pgsql":
        notices.append(f"  DATABASE_URL: {current_type} → pgsql")
        notices.append(f"    → {DEV_PGSQL_URL}")
        env["DATABASE_URL"] = DEV_PGSQL_URL
        # Set DEERFLOW_DB_URL if not already pgsql
        deerflow_url = env.get("DEERFLOW_DB_URL", "")
        if detect_db_type(deerflow_url) != "pgsql":
            env["DEERFLOW_DB_URL"] = DEV_DEERFLOW_PGSQL_URL
            notices.append(f"  DEERFLOW_DB_URL: → {DEV_DEERFLOW_PGSQL_URL}")
    elif target == "sqlite":
        notices.append(f"  DATABASE_URL: {current_type} → sqlite")
        notices.append(f"    → {DEV_SQLITE_URL}")
        env["DATABASE_URL"] = DEV_SQLITE_URL
        # Remove DEERFLOW_DB_URL if it was pgsql (not needed for sqlite)
        deerflow_url = env.get("DEERFLOW_DB_URL", "")
        if detect_db_type(deerflow_url) == "pgsql":
            del env["DEERFLOW_DB_URL"]
            notices.append("  DEERFLOW_DB_URL: removed (not needed for sqlite)")

    return notices


def apply_cache(env: dict[str, str], target: str) -> list[str]:
    """Apply cache/Redis changes. Returns list of notice messages."""
    notices: list[str] = []
    current_type = detect_cache_type(env)

    if target == current_type:
        # Type matches — preserve user's connection details
        return notices

    if target == "redis":
        notices.append("  CACHE_BACKEND: memory → redis")
        notices.append("  STREAM_BRIDGE_TYPE: → redis")
        notices.append(f"  REDIS_URL: → {DEV_REDIS_URL}")
        env["CACHE_BACKEND"] = "redis"
        env["STREAM_BRIDGE_TYPE"] = "redis"
        # Only set REDIS_URL if not already set to a redis URL
        current_redis = env.get("REDIS_URL", "")
        if not current_redis.startswith("redis://"):
            env["REDIS_URL"] = DEV_REDIS_URL
        else:
            notices[-1] = f"  REDIS_URL: preserved ({current_redis})"
    elif target == "memory":
        notices.append("  CACHE_BACKEND: redis → memory")
        notices.append("  STREAM_BRIDGE_TYPE: redis → memory")
        env["CACHE_BACKEND"] = "memory"
        env["STREAM_BRIDGE_TYPE"] = "memory"
        # Don't remove REDIS_URL — user might want to keep it for other uses
        # Just note it's inactive
        if env.get("REDIS_URL"):
            notices.append("  REDIS_URL: kept (inactive with memory backend)")

    return notices


def write_env(env_path: Path, env: dict[str, str]) -> None:
    """Update .env file, preserving comments and order where possible."""
    if not env_path.exists():
        # Create new .env
        lines = [f"{k}={v}" for k, v in env.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    original_lines = env_path.read_text(encoding="utf-8").splitlines()
    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in original_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" not in stripped:
            new_lines.append(line)
            continue
        key, _, _ = stripped.partition("=")
        key = key.strip()
        if key in env:
            new_lines.append(f"{key}={env[key]}")
            updated_keys.add(key)
        else:
            # Key was removed (e.g., DEERFLOW_DB_URL)
            continue

    # Append any new keys not in original
    for key, value in env.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply dev env overrides")
    parser.add_argument("--db", choices=["sqlite", "pgsql"], default="sqlite",
                        help="Database type (default: sqlite)")
    parser.add_argument("--cache", choices=["memory", "redis"], default="memory",
                        help="Cache backend (default: memory)")
    parser.add_argument("--env-file", default=".env",
                        help="Path to .env file (default: .env)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show changes without writing")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    env = parse_env(env_path)

    all_notices: list[str] = []
    all_notices.extend(apply_db(env, args.db))
    all_notices.extend(apply_cache(env, args.cache))

    if not all_notices:
        print(f"  .env already matches DB={args.db}, CACHE={args.cache} — no changes needed")
        return 0

    print(f"  .env adjustments for DB={args.db}, CACHE={args.cache}:")
    for notice in all_notices:
        print(notice)

    if args.dry_run:
        print("  (dry-run — no changes written)")
        return 0

    write_env(env_path, env)
    print("  ✓ .env updated")

    # Check prerequisites
    if args.db == "pgsql":
        print("")
        print("  ⚠ PostgreSQL mode requires a running PostgreSQL instance.")
        print("    Ensure PostgreSQL is accessible at the DATABASE_URL above.")
    if args.cache == "redis":
        print("")
        print("  ⚠ Redis mode requires a running Redis instance.")
        print(f"    Ensure Redis is accessible at {env.get('REDIS_URL', DEV_REDIS_URL)}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
