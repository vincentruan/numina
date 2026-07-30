"""Snapshot scheduler entry point.

Phase 2: auto_generate_daily_snapshots delegates to the backend service via lazy import.
The full snapshot logic (Asset/Family/Liability queries, ExchangeRateService)
stays in apps/backend/app/services/snapshot.py until Phase 3.

NOTE: scheduler_worker containers must include apps/backend/ in their image
(or this job must be disabled) until Phase 3 extracts the snapshot logic
fully into this package.
"""

from sqlalchemy.orm import Session


def auto_generate_daily_snapshots(db: Session) -> None:
    """Generate today's snapshots for all families. Called by scheduler_worker."""
    # PHASE2_COUPLING: imports backend internals. Remove in Phase 3 when
    # snapshot logic is fully migrated to packages/domain/snapshot/.
    try:
        from apps.backend.app.services.snapshot import (
            auto_generate_daily_snapshots as _run,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Snapshot service not available: apps/backend must be present in the Python path. "
            "Full extraction to packages/domain/snapshot/ is deferred to Phase 3."
        ) from exc
    _run(db)
