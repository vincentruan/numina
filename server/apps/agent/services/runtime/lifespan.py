"""FastAPI lifespan bootstrap and teardown for runtime singletons.

Manages the lifecycle of:
- ``app.state.stream_bridge`` — StreamBridge for event passing (memory or redis)
- ``app.state.run_manager`` — ``RunManager`` for run lifecycle tracking

# [Copied from DeerFlow Reference] — StreamBridge + RunManager singleton pattern
# [Integrated with Numina Multi-Tenant] — shared instances across all families
# [Cache Abstraction] — Use memory bridge by default, redis when STREAM_BRIDGE_TYPE=redis
"""

from __future__ import annotations

import logging
import os

from deerflow.runtime import RunManager, StreamBridge
from fastapi import FastAPI, HTTPException, Request

from packages.db.stream_bridge import make_stream_bridge
from packages.db.stream_bridge.config import StreamBridgeConfig

from .gc import drain_inflight_runs, reconcile_orphaned_runs

logger = logging.getLogger(__name__)


async def init_runtime(app: FastAPI) -> None:
    """Initialize ``RunManager`` + ``StreamBridge`` on ``app.state``.

    Call from the FastAPI lifespan startup block, after the DeerFlow
    persistence engine and checkpointer have been initialised but before
    ``yield`` (so the singletons are available for the entire serving
    lifetime).

    # [Copied from DeerFlow Reference] — StreamBridge with bounded queue
    # [Integrated with Numina Multi-Tenant] — single shared instance
    # [Cache Abstraction] — Memory bridge by default, Redis when configured
    """
    # Cache abstraction: use memory bridge by default (single-process dev/test),
    # Redis when STREAM_BRIDGE_TYPE=redis (multi-process deployment).
    # This allows local development without requiring Redis, while supporting
    # Redis or other cache providers in production via configuration.
    bridge_type = os.getenv("STREAM_BRIDGE_TYPE", "memory")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    config = StreamBridgeConfig(
        type=bridge_type,
        redis_url=redis_url,
        queue_maxsize=256,
        stream_ttl_seconds=86400,
    )
    app.state.stream_bridge = make_stream_bridge(config)
    logger.info(f"Initialized StreamBridge (type={bridge_type})")

    # [Copied from DeerFlow Reference] — RunManager, in-memory only for Phase 1
    app.state.run_manager = RunManager(store=None)

    # Orphan reconciliation (no-op without persistent store, wired for Phase 2)
    await reconcile_orphaned_runs(
        app.state.run_manager,
        error="Agent restarted before run reached a durable final state.",
    )

    logger.info(f"[runtime] StreamBridge (Redis: {redis_url}) + RunManager initialized")


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
