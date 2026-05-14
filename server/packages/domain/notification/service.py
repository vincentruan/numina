"""Notification scheduler entry point.

Phase 1: run_scheduled_checks delegates to the backend dispatcher.
The full notification subsystem (rules, sender, channels) stays in
backend/app/services/notification/ until Phase 2.
"""

from sqlalchemy.orm import Session


def run_scheduled_checks(db: Session) -> None:
    """Run all scheduled notification checks. Called by scheduler_worker."""
    # PHASE1_COUPLING: imports backend internals. Remove in Phase 2 when
    # notification logic is fully migrated to packages/domain/notification/.
    try:
        from app.services.notification.dispatcher import (  # noqa: PLC0415
            run_scheduled_checks as _run,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PHASE1_COUPLING: backend package not on PYTHONPATH. "
            "Migrate notification logic to packages/domain/notification/ (Phase 2)."
        ) from exc
    _run(db)
