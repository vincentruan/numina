"""Garbage collection orchestration for run lifecycle management.

Provides shutdown drain, orphan reconciliation, and deferred cleanup — all
wrapping DeerFlow's RunManager built-in methods.

# [Copied from DeerFlow Reference] — patterns from deps.py and manager.py
# [Integrated with Numina Multi-Tenant] — no tenant-specific GC yet; shared
# RunManager across all families. Phase 2 may add per-family GC when a
# persistent RunStore is introduced.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from deerflow.runtime import RunManager

logger = logging.getLogger(__name__)


async def drain_inflight_runs(run_manager: RunManager, *, timeout: float = 5.0) -> None:
    """Bounded drain of in-flight runs on shutdown.

    Calls ``run_manager.shutdown(timeout)`` when the vendored RunManager
    supports it — some versions only expose ``cancel`` per-run. Uses
    ``asyncio.shield`` so a second SIGINT during the drain does not
    abandon the process — critical for Kubernetes rolling deployments
    where SIGTERM followed by SIGKILL is the normal shutdown sequence.

    # [Copied from DeerFlow Reference] — drain pattern from deps.py
    """
    if not hasattr(run_manager, "shutdown"):
        logger.debug("RunManager.shutdown not available in this DeerFlow version (no-op drain)")
        return
    drain = asyncio.create_task(run_manager.shutdown(timeout=timeout))
    try:
        await asyncio.shield(drain)
    except asyncio.CancelledError:
        # Second cancellation during drain — shield should protect but
        # asyncio.shield does NOT protect against the outer task being
        # cancelled, only against the inner task being cancelled when
        # the outer is cancelled. Retry once.
        try:
            await asyncio.shield(drain)
        except Exception:
            logger.exception("In-flight run drain failed after shutdown cancellation")
        raise
    except Exception:
        logger.exception("Failed to drain in-flight runs during shutdown")


async def reconcile_orphaned_runs(
    run_manager: RunManager, *, error: str
) -> list[dict[str, Any]]:
    """Mark persisted pending/running runs as error after process restart.

    When ``RunManager`` has no persistent store (``store=None``), this is a
    no-op.  Wired here so the integration point is live when a ``RunStore``
    is added in Phase 2.

    # [Copied from DeerFlow Reference] — from manager.py

    Note: ``reconcile_orphaned_inflight_runs`` is not available in all DeerFlow
    versions. Fall back gracefully when the method is missing.
    """
    if hasattr(run_manager, "reconcile_orphaned_inflight_runs"):
        return await run_manager.reconcile_orphaned_inflight_runs(error=error)
    logger.debug("reconcile_orphaned_inflight_runs not available in this DeerFlow version (no-op)")
    return []


async def schedule_run_cleanup(
    run_manager: RunManager, run_id: str, *, delay: float = 300
) -> None:
    """Deferred removal of a ``RunRecord`` from the in-memory registry.

    After the run has ended and all consumers have drained buffered events,
    remove the record so it does not accumulate indefinitely.  Default 300s
    (5 minutes) gives late subscribers time to join and replay.

    # [Copied from DeerFlow Reference] — from manager.py
    """
    await run_manager.cleanup(run_id, delay=delay)
