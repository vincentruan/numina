"""Snapshot scheduler entry point.

Phase 1: auto_generate_daily_snapshots delegates to the backend service.
The full snapshot logic (Asset/Family/Liability queries, ExchangeRateService)
stays in backend/app/services/snapshot.py until Phase 2.
"""

from sqlalchemy.orm import Session


def auto_generate_daily_snapshots(db: Session) -> None:
    """Generate today's snapshots for all families. Called by scheduler_worker."""
    # Delegate to backend service for Phase 1.
    # Phase 2: move full implementation here and remove this import.
    from app.services.snapshot import (  # noqa: PLC0415
        auto_generate_daily_snapshots as _run,
    )
    _run(db)
