"""FastAPI lifespan bootstrap and teardown for runtime singletons.

Manages the lifecycle of:
- ``app.state.stream_bridge`` — ``MemoryStreamBridge`` for inter-thread event passing
- ``app.state.run_manager`` — ``RunManager`` for run lifecycle tracking

# [Copied from DeerFlow Reference] — MemoryStreamBridge + RunManager singleton pattern
# [Integrated with Numina Multi-Tenant] — shared instances across all families
"""

from __future__ import annotations

import logging

from deerflow.runtime import MemoryStreamBridge, RunManager, StreamBridge
from fastapi import FastAPI, HTTPException, Request

from .gc import drain_inflight_runs, reconcile_orphaned_runs

logger = logging.getLogger(__name__)


async def init_runtime(app: FastAPI) -> None:
    """Initialize ``RunManager`` + ``StreamBridge`` on ``app.state``.

    Call from the FastAPI lifespan startup block, after the DeerFlow
    persistence engine and checkpointer have been initialised but before
    ``yield`` (so the singletons are available for the entire serving
    lifetime).

    # [Copied from DeerFlow Reference] — MemoryStreamBridge with bounded queue
    # [Integrated with Numina Multi-Tenant] — single shared instance
    """
    # [Copied from DeerFlow Reference] — MemoryStreamBridge with bounded queue
    app.state.stream_bridge = MemoryStreamBridge(queue_maxsize=256)

    # [Copied from DeerFlow Reference] — RunManager, in-memory only for Phase 1
    app.state.run_manager = RunManager(store=None)

    # Orphan reconciliation (no-op without persistent store, wired for Phase 2)
    await reconcile_orphaned_runs(
        app.state.run_manager,
        error="Agent restarted before run reached a durable final state.",
    )

    logger.info("[runtime] StreamBridge + RunManager initialized")


async def shutdown_runtime(app: FastAPI) -> None:
    """Drain in-flight runs then close the bridge.

    **MUST be called BEFORE** ``close_shared_checkpointer()`` in the lifespan
    shutdown block.  Draining runs while the checkpointer is still open lets
    each settled run flush its final checkpoint.  Closing the bridge first
    prevents new subscriptions.

    # [Copied from DeerFlow Reference] — shutdown ordering from deps.py
    """
    run_manager = getattr(app.state, "run_manager", None)
    if run_manager is not None:
        await drain_inflight_runs(run_manager, timeout=5.0)

    bridge: StreamBridge | None = getattr(app.state, "stream_bridge", None)
    if bridge is not None:
        await bridge.close()

    logger.info("[runtime] StreamBridge + RunManager shut down")


def get_run_manager(request: Request) -> RunManager:
    """Dependency getter — returns the ``RunManager`` from ``app.state``."""
    val = getattr(request.app.state, "run_manager", None)
    if val is None:
        raise HTTPException(status_code=503, detail="Run manager not available")
    return val


def get_stream_bridge(request: Request) -> StreamBridge:
    """Dependency getter — returns the ``StreamBridge`` from ``app.state``."""
    val = getattr(request.app.state, "stream_bridge", None)
    if val is None:
        raise HTTPException(status_code=503, detail="Stream bridge not available")
    return val
