"""FastAPI lifespan bootstrap and teardown for runtime singletons.

Manages the lifecycle of:
- ``app.state.stream_bridge`` — StreamBridge for event passing (Redis for cross-process, memory fallback)
- ``app.state.run_manager`` — ``RunManager`` for run lifecycle tracking

# [Copied from DeerFlow Reference] — StreamBridge + RunManager singleton pattern
# [Integrated with Numina Multi-Tenant] — shared instances across all families
# Agent uses Redis StreamBridge for cross-process event sharing with backend.
"""

from __future__ import annotations

import logging
from typing import Any

from deerflow.runtime import RunManager, StreamBridge
from fastapi import FastAPI, HTTPException, Request

from packages.stream_bridge import make_stream_bridge
from packages.stream_bridge.config import StreamBridgeConfig

from .gc import drain_inflight_runs, reconcile_orphaned_runs

logger = logging.getLogger(__name__)


async def init_runtime(app: FastAPI) -> None:
    """Initialize ``RunManager`` + ``StreamBridge`` on ``app.state``.

    Agent uses Redis StreamBridge for cross-process event sharing.
    Backend subscribes to the same Redis Stream directly.
    Falls back to memory bridge if Redis is unavailable (dev only).

    Call from the FastAPI lifespan startup block, after the DeerFlow
    persistence engine and checkpointer have been initialised but before
    ``yield`` (so the singletons are available for the entire serving
    lifetime).
    """
    from apps.agent.app.config import settings

    # Determine Redis URL for StreamBridge
    redis_url = settings.STREAM_BRIDGE_REDIS_URL or "redis://redis:6379/0"

    try:
        # Verify Redis connectivity before creating the bridge
        from redis.asyncio import Redis as AsyncRedis

        client = AsyncRedis.from_url(redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()

        config = StreamBridgeConfig(
            type="redis",
            redis_url=redis_url,
            queue_maxsize=256,
            stream_ttl_seconds=86400,
        )
        app.state.stream_bridge = make_stream_bridge(config)
        logger.info("Initialized StreamBridge (type=redis, url=%s)", redis_url)
    except Exception as e:
        logger.warning("Redis bridge unavailable (%s), falling back to memory", e)
        config = StreamBridgeConfig(type="memory", queue_maxsize=256)
        app.state.stream_bridge = make_stream_bridge(config)

    # [Copied from DeerFlow Reference] — RunManager, persistent store (U5)
    # when the DeerFlow engine is available; falls back to in-memory
    # (store=None) when the engine was not initialized.
    store = _create_persistent_run_store()
    app.state.run_manager = RunManager(store=store)
    app.state.run_store = store

    # Orphan reconciliation (no-op without persistent store, wired for Phase 2)
    await reconcile_orphaned_runs(
        app.state.run_manager,
        error="Agent restarted before run reached a durable final state.",
    )

    logger.info(
        "[runtime] StreamBridge + RunManager initialized (persistent_store=%s)",
        store is not None,
    )


def _create_persistent_run_store() -> Any | None:
    """Build a NuminaSqliteRunStore from the DeerFlow engine, or None.

    Non-fatal: when the DeerFlow persistence engine has not been initialized
    (e.g. tests, or engine init failed at startup), RunManager falls back to
    in-memory storage (store=None) and the AITask-based orphan fallback in
    gc.py remains active.
    """
    try:
        from deerflow.persistence.engine import get_session_factory

        from .numina_run_store import NuminaSqliteRunStore

        session_factory = get_session_factory()
        if session_factory is None:
            logger.info("[runtime] DeerFlow session factory unavailable; using in-memory RunStore")
            return None
        return NuminaSqliteRunStore(session_factory)
    except Exception:
        logger.warning(
            "[runtime] persistent RunStore init failed; using in-memory store",
            exc_info=True,
        )
        return None


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
