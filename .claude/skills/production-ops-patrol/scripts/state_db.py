#!/usr/bin/env python3
"""
state_db.py — SQLite state management for production ops patrol.

Manages:
  - audit_log: every patrol run and action taken
  - fingerprints: known exception fingerprints with first/last seen counts
  - restart_history: automatic restart actions with timestamps
  - cooldown tracking: per-container restart cooldown enforcement

Database location: ~/.hermes/state/production-ops-patrol.db

Subcommands:
  init                          — Create/initialize the database
  record-patrol                 — Record a patrol run result
  record-action                 — Record an action (restart, issue link, etc.)
  query-fingerprint             — Check if a fingerprint is known
  check-cooldown                — Check if a container is past cooldown
  check-restart-limit           — Check if a container has exceeded restart limit
  record-restart                — Record a restart action
  history                       — Show recent patrol history
  fingerprints                  — Show known fingerprints
"""

import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


DB_DIR = Path.home() / ".hermes" / "state"
DB_PATH = DB_DIR / "production-ops-patrol.db"


def _get_conn() -> sqlite3.Connection:
    """Get or create the SQLite database."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patrol_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            result TEXT NOT NULL CHECK(result IN ('HEALTHY','CODE_DEFECT','RECOVERABLE_ENV','HUMAN_INTERVENTION')),
            summary TEXT,
            details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patrol_id TEXT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            container TEXT,
            reason TEXT,
            fingerprint TEXT,
            details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS fingerprints (
            fingerprint TEXT PRIMARY KEY,
            exception_type TEXT,
            normalized_key TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            occurrence_count INTEGER DEFAULT 1,
            classification TEXT,
            github_issue TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS restart_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            container TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            patrol_id TEXT,
            reason TEXT,
            success INTEGER,
            recovery_verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_restart_container_time ON restart_history(container, timestamp);
        CREATE INDEX IF NOT EXISTS idx_fingerprint_last_seen ON fingerprints(last_seen);
    """)
    conn.commit()


def record_patrol(conn: sqlite3.Connection, patrol_id: str, result: str,
                  summary: str, details: str) -> None:
    """Record a patrol run."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO audit_log (patrol_id, timestamp, result, summary, details) VALUES (?, ?, ?, ?, ?)",
        (patrol_id, now, result, summary, details),
    )
    conn.commit()
    print(json.dumps({"status": "ok", "patrol_id": patrol_id, "result": result}))


def record_action(conn: sqlite3.Connection, action: str, container: str | None = None,
                  reason: str | None = None, fingerprint: str | None = None,
                  patrol_id: str | None = None, details: str | None = None) -> None:
    """Record an action taken during patrol."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO action_log (patrol_id, timestamp, action, container, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (patrol_id, now, action, container, reason, fingerprint, details),
    )
    conn.commit()
    print(json.dumps({"status": "ok", "action": action, "container": container}))


def query_fingerprint(conn: sqlite3.Connection, fingerprint: str) -> None:
    """Query a fingerprint in the database."""
    row = conn.execute(
        "SELECT * FROM fingerprints WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()
    if row:
        result = dict(row)
        result["known"] = True
    else:
        result = {"known": False, "fingerprint": fingerprint}
    print(json.dumps(result))


def upsert_fingerprint(conn: sqlite3.Connection, fingerprint: str,
                       exception_type: str, normalized_key: str,
                       classification: str | None = None) -> None:
    """Insert or update a fingerprint record."""
    now = datetime.now(timezone.utc).isoformat()
    existing = conn.execute(
        "SELECT occurrence_count FROM fingerprints WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE fingerprints SET last_seen = ?, occurrence_count = occurrence_count + 1,
               classification = COALESCE(?, classification) WHERE fingerprint = ?""",
            (now, classification, fingerprint),
        )
    else:
        conn.execute(
            """INSERT INTO fingerprints (fingerprint, exception_type, normalized_key,
               first_seen, last_seen, occurrence_count, classification)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (fingerprint, exception_type, normalized_key, now, now, classification),
        )
    conn.commit()


def check_cooldown(conn: sqlite3.Connection, container: str, cooldown_seconds: int) -> None:
    """Check if a container is past its cooldown period."""
    cutoff = datetime.fromtimestamp(
        time.time() - cooldown_seconds, tz=timezone.utc
    ).isoformat()
    recent = conn.execute(
        "SELECT timestamp FROM restart_history WHERE container = ? AND timestamp > ? ORDER BY timestamp DESC LIMIT 1",
        (container, cutoff),
    ).fetchone()

    if recent:
        print(json.dumps({
            "allowed": False,
            "container": container,
            "reason": f"Last restart at {recent['timestamp']}, cooldown {cooldown_seconds}s not elapsed",
        }))
    else:
        print(json.dumps({"allowed": True, "container": container}))


def check_restart_limit(conn: sqlite3.Connection, container: str, max_per_hour: int) -> None:
    """Check if a container has exceeded the hourly restart limit."""
    one_hour_ago = datetime.fromtimestamp(
        time.time() - 3600, tz=timezone.utc
    ).isoformat()
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM restart_history WHERE container = ? AND timestamp > ?",
        (container, one_hour_ago),
    ).fetchone()["cnt"]

    if count >= max_per_hour:
        print(json.dumps({
            "allowed": False,
            "container": container,
            "reason": f"{count} restarts in last hour, limit is {max_per_hour}",
            "count": count,
        }))
    else:
        print(json.dumps({
            "allowed": True,
            "container": container,
            "count": count,
            "remaining": max_per_hour - count,
        }))


def record_restart(conn: sqlite3.Connection, container: str, patrol_id: str | None = None,
                   reason: str | None = None, success: bool = True) -> None:
    """Record a restart action."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO restart_history (container, timestamp, patrol_id, reason, success) VALUES (?, ?, ?, ?, ?)",
        (container, now, patrol_id, reason, 1 if success else 0),
    )
    conn.commit()
    print(json.dumps({"status": "ok", "container": container, "timestamp": now}))


def show_history(conn: sqlite3.Connection, limit: int = 10) -> None:
    """Show recent patrol history."""
    rows = conn.execute(
        "SELECT patrol_id, timestamp, result, summary FROM audit_log ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))


def show_fingerprints(conn: sqlite3.Connection, limit: int = 20) -> None:
    """Show known fingerprints."""
    rows = conn.execute(
        """SELECT fingerprint, exception_type, first_seen, last_seen,
           occurrence_count, classification, github_issue
           FROM fingerprints ORDER BY last_seen DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Patrol state database management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    subparsers.add_parser("init", help="Initialize the database")

    # record-patrol
    p = subparsers.add_parser("record-patrol", help="Record a patrol run")
    p.add_argument("--result", required=True, choices=["HEALTHY", "CODE_DEFECT", "RECOVERABLE_ENV", "HUMAN_INTERVENTION"])
    p.add_argument("--summary", required=True)
    p.add_argument("--details", default="{}")
    p.add_argument("--patrol-id", default=None)

    # record-action
    p = subparsers.add_parser("record-action", help="Record an action")
    p.add_argument("--action", required=True)
    p.add_argument("--container", default=None)
    p.add_argument("--reason", default=None)
    p.add_argument("--fingerprint", default=None)
    p.add_argument("--patrol-id", default=None)
    p.add_argument("--details", default=None)

    # query-fingerprint
    p = subparsers.add_parser("query-fingerprint", help="Query a fingerprint")
    p.add_argument("--fingerprint", required=True)

    # upsert-fingerprint
    p = subparsers.add_parser("upsert-fingerprint", help="Insert/update a fingerprint")
    p.add_argument("--fingerprint", required=True)
    p.add_argument("--exception-type", required=True)
    p.add_argument("--normalized-key", required=True)
    p.add_argument("--classification", default=None)

    # check-cooldown
    p = subparsers.add_parser("check-cooldown", help="Check restart cooldown")
    p.add_argument("--container", required=True)
    p.add_argument("--cooldown-seconds", type=int, default=300)

    # check-restart-limit
    p = subparsers.add_parser("check-restart-limit", help="Check restart rate limit")
    p.add_argument("--container", required=True)
    p.add_argument("--max-per-hour", type=int, default=3)

    # record-restart
    p = subparsers.add_parser("record-restart", help="Record a restart")
    p.add_argument("--container", required=True)
    p.add_argument("--patrol-id", default=None)
    p.add_argument("--reason", default=None)
    p.add_argument("--success", type=lambda x: x.lower() == "true", default=True)

    # history
    p = subparsers.add_parser("history", help="Show patrol history")
    p.add_argument("--limit", type=int, default=10)

    # fingerprints
    p = subparsers.add_parser("fingerprints", help="Show known fingerprints")
    p.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()
    conn = _get_conn()
    init_db(conn)

    if args.command == "init":
        print(json.dumps({"status": "ok", "db_path": str(DB_PATH)}))
    elif args.command == "record-patrol":
        record_patrol(conn, args.patrol_id or f"patrol-{int(time.time())}",
                      args.result, args.summary, args.details)
    elif args.command == "record-action":
        record_action(conn, args.action, args.container, args.reason,
                      args.fingerprint, args.patrol_id, args.details)
    elif args.command == "query-fingerprint":
        query_fingerprint(conn, args.fingerprint)
    elif args.command == "upsert-fingerprint":
        upsert_fingerprint(conn, args.fingerprint, args.exception_type,
                          args.normalized_key, args.classification)
    elif args.command == "check-cooldown":
        check_cooldown(conn, args.container, args.cooldown_seconds)
    elif args.command == "check-restart-limit":
        check_restart_limit(conn, args.container, args.max_per_hour)
    elif args.command == "record-restart":
        record_restart(conn, args.container, args.patrol_id, args.reason, args.success)
    elif args.command == "history":
        show_history(conn, args.limit)
    elif args.command == "fingerprints":
        show_fingerprints(conn, args.limit)

    conn.close()


if __name__ == "__main__":
    main()
