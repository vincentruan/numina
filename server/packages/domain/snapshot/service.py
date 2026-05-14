"""Snapshot scheduler entry point.

Phase 1: auto_generate_daily_snapshots delegates to the backend service.
The full snapshot logic (Asset/Family/Liability queries, ExchangeRateService)
stays in backend/app/services/snapshot.py until Phase 2.
"""

from sqlalchemy.orm import Session


def auto_generate_daily_snapshots(db: Session) -> None:
    """Generate today's snapshots for all families. Called by scheduler_worker."""
    # PHASE1_COUPLING: imports backend internals. Remove in Phase 2 when
    # snapshot logic is fully migrated to packages/domain/snapshot/.
    try:
        from app.services.snapshot import (  # noqa: PLC0415
            auto_generate_daily_snapshots as _run,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PHASE1_COUPLING: backend package not on PYTHONPATH. "
            "Migrate snapshot logic to packages/domain/snapshot/ (Phase 2)."
        ) from exc
    _run(db)
