"""Notification scheduler entry point.

Phase 2: run_scheduled_checks delegates to the backend dispatcher via lazy import.
The full notification subsystem (rules, sender, channels) stays in
apps/backend/app/services/notification/ until Phase 3.

NOTE: scheduler_worker containers must include apps/backend/ in their image
(or this job must be disabled) until Phase 3 extracts the notification logic
fully into this package.
"""

from sqlalchemy.orm import Session


def run_scheduled_checks(db: Session) -> None:
    """Run all scheduled notification checks. Called by scheduler_worker."""
    # PHASE2_COUPLING: imports backend internals. Remove in Phase 3 when
    # notification logic is fully migrated to packages/domain/notification/.
    try:
        from apps.backend.app.services.notification.dispatcher import (  # noqa: PLC0415
            run_scheduled_checks as _run,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Notification dispatcher not available: apps/backend must be present in the Python path. "
            "Full extraction to packages/domain/notification/ is deferred to Phase 3."
        ) from exc
    _run(db)
