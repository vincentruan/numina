"""CLI entry point for the reconciliation system.

Usage:
    python -m apps.backend.app.reconcile check
    python -m apps.backend.app.reconcile dry-run
    python -m apps.backend.app.reconcile apply
    python -m apps.backend.app.reconcile verify
    python -m apps.backend.app.reconcile repair
    python -m apps.backend.app.reconcile report
"""

from __future__ import annotations

import json
import sys

from apps.backend.app.reconcile.runner import RunMode


def _parse_mode(args: list[str]) -> RunMode:
    if not args:
        return RunMode.NORMAL

    cmd = args[0].lower().replace("_", "-")
    mode_map = {
        "check": RunMode.CHECK_ONLY,
        "check-only": RunMode.CHECK_ONLY,
        "dry-run": RunMode.DRY_RUN,
        "dryrun": RunMode.DRY_RUN,
        "apply": RunMode.NORMAL,
        "normal": RunMode.NORMAL,
        "verify": RunMode.VERIFY,
        "repair": RunMode.REPAIR,
        "offline": RunMode.OFFLINE,
        "strict": RunMode.STRICT,
        "report": RunMode.CHECK_ONLY,  # report is check-only + formatted output
    }

    if cmd not in mode_map:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(sorted(mode_map.keys()))}")
        sys.exit(2)

    return mode_map[cmd]


def main() -> None:
    args = sys.argv[1:]
    is_report = args and args[0].lower() == "report"
    is_json = "--json" in args
    args = [a for a in args if a != "--json"]

    mode = _parse_mode(args)

    # Initialize the application minimally
    from apps.backend.app.database import SessionLocal, engine
    from apps.backend.app.reconcile.lock import create_lock_provider
    from apps.backend.app.reconcile.registry import get_all_resources
    from apps.backend.app.reconcile.runner import DesiredStateRunner

    db = SessionLocal()
    try:
        lock_provider = create_lock_provider(engine)
        resources = get_all_resources()
        runner = DesiredStateRunner(
            resources=resources,
            engine=engine,
            db=db,
            mode=mode,
            lock_provider=lock_provider,
        )
        report = runner.run()
    finally:
        db.close()

    # Output
    if is_json or is_report:
        if is_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(report.summary_text())
    else:
        print(report.summary_text())

    # Exit code
    if not report.success:
        sys.exit(1)
    if mode == RunMode.VERIFY:
        drifted = any(
            r.status.value == "drifted" for r in report.results
        )
        if drifted:
            sys.exit(1)


if __name__ == "__main__":
    main()
