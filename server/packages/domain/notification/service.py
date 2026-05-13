"""Notification scheduler entry point.

Phase 1: run_scheduled_checks delegates to the backend dispatcher.
The full notification subsystem (rules, sender, channels) stays in
backend/app/services/notification/ until Phase 2.
"""

from sqlalchemy.orm import Session


def run_scheduled_checks(db: Session) -> None:
    """Run all scheduled notification checks. Called by scheduler_worker."""
    # Delegate to backend dispatcher for Phase 1.
    # Phase 2: move rules/sender/dispatcher here and remove this import.
    from app.services.notification.dispatcher import (  # noqa: PLC0415
        run_scheduled_checks as _run,
    )
    _run(db)
