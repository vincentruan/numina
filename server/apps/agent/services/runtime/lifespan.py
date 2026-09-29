"""FastAPI lifespan bootstrap and teardown for runtime singletons.

Manages the lifecycle of:
- ``app.state.stream_bridge`` — StreamBridge for cross-process event passing (Redis only, lazy init)
- ``app.state.run_manager`` — ``RunManager`` for run lifecycle tracking

# [Copied from DeerFlow Reference] — StreamBridge + RunManager singleton pattern
# [Integrated with Numina Multi-Tenant] — shared instances across all families
# Agent uses Redis StreamBridge for cross-process event sharing with backend.
# StreamBridge is lazy-initialized on first SSE request — no Redis connection
# at startup if no AI traffic arrives.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from deerflow.runtime import RunManager, StreamBridge
from fastapi import FastAPI, HTTPException, Request

from packages.core.logging import get_logger

from .gc import drain_inflight_runs, reconcile_orphaned_runs

logger = get_logger(__name__)


async def init_runtime(app: FastAPI) -> None:
    """Initialize ``RunManager`` on ``app.state``.

    StreamBridge is NOT created here — it is lazy-initialized on the first
    request that needs it (see ``get_stream_bridge``).  This avoids opening
    a Redis connection at startup when no AI traffic has arrived yet.

    Call from the FastAPI lifespan startup block, after the DeerFlow
    persistence engine and checkpointer have been initialised but before
    ``yield``.
    """
    # Initialize the lazy-init lock for StreamBridge
    app.state._stream_bridge_lock = asyncio.Lock()

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
        "[runtime] RunManager initialized (persistent_store=%s, stream_bridge=lazy)",
        store is not None,
    )


def _create_persistent_run_store() -> Any | None:
    """Build a NuminaSqlRunStore from the DeerFlow engine, or None.

    Non-fatal: when the DeerFlow persistence engine has not been initialized
    (e.g. tests, or engine init failed at startup), RunManager falls back to
    in-memory storage (store=None) and the AITask-based orphan fallback in
    gc.py remains active.
    """
    try:
        from deerflow.persistence.engine import get_session_factory

        from .numina_run_store import NuminaSqlRunStore

        session_factory = get_session_factory()
        if session_factory is None:
            logger.info("[runtime] DeerFlow session factory unavailable; using in-memory RunStore")
            return None
        return NuminaSqlRunStore(session_factory)
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

    logger.info("[runtime] RunManager + StreamBridge shut down")


def get_run_manager(request: Request) -> RunManager:
    """Dependency getter — returns the ``RunManager`` from ``app.state``."""
    val = getattr(request.app.state, "run_manager", None)
    if val is None:
        raise HTTPException(status_code=503, detail="Run manager not available")
    return val


async def get_stream_bridge(request: Request) -> StreamBridge:
    """Lazy-init Redis StreamBridge on first use.

    Agent and backend are separate processes — only Redis works for
    cross-process event sharing.  No memory fallback: a memory bridge in
    the agent process is invisible to the backend's bridge_consumer.

    Raises HTTP 503 if Redis is unreachable (AI cannot function without it).
    """
    # Fast path: already initialized
    bridge = getattr(request.app.state, "stream_bridge", None)
    if bridge is not None:
        return bridge

    # Slow path: initialize under lock
    lock: asyncio.Lock = request.app.state._stream_bridge_lock
    async with lock:
        # Double-check after acquiring lock
        bridge = getattr(request.app.state, "stream_bridge", None)
        if bridge is not None:
            return bridge

        from apps.agent.app.config import settings
        from packages.stream_bridge import make_stream_bridge
        from packages.stream_bridge.config import StreamBridgeConfig

        # Priority: STREAM_BRIDGE_REDIS_URL > REDIS_URL > Docker default
        redis_url = (
            settings.STREAM_BRIDGE_REDIS_URL
            or os.environ.get("REDIS_URL", "")
            or "redis://redis:6379/0"
        )

        try:
            from redis.asyncio import Redis as AsyncRedis

            client = AsyncRedis.from_url(redis_url, decode_responses=True)
            await client.ping()
            await client.aclose()
        except Exception as e:
            logger.error("Redis unavailable for StreamBridge (%s)", e)
            raise HTTPException(
                status_code=503,
                detail="Stream bridge unavailable: Redis connection failed",
            ) from e

        config = StreamBridgeConfig(
            type="redis",
            redis_url=redis_url,
            queue_maxsize=256,
            stream_ttl_seconds=86400,
        )
        bridge = make_stream_bridge(config)
        request.app.state.stream_bridge = bridge
        logger.info("Lazy-initialized StreamBridge (type=redis, url=%s)", redis_url)
        return bridge
