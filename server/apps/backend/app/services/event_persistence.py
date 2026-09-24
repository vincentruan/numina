"""Event Persistence Consumer — writes Redis bridge events to DeerFlow's DbRunEventStore.

Translates StreamBridge events (messages, custom, end, error) into
DbRunEventStore.put() calls for permanent event logging. Uses the DeerFlow
async engine initialized at backend startup.

The consumer is called from _spawn_lifecycle_consumer for each event.
Failures are non-fatal (logged and skipped) to avoid blocking task completion.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Module-level store singleton (lazy init)
_event_store: Any = None
_init_error: str | None = None

# Rate-limited failure logging: WARNING for first N failures, DEBUG after.
_MAX_WARNING_FAILURES = 10
_failure_count: int = 0


def is_healthy() -> bool:
    """Return True if event persistence is initialized and operational."""
    return _event_store is not None


def health_detail() -> dict[str, str | None]:
    """Return health-check detail for event persistence."""
    if _event_store is not None:
        return {"status": "ok"}
    return {"status": "disabled", "reason": _init_error or "not initialized"}


def _get_event_store() -> Any | None:
    """Return the DbRunEventStore singleton, or None if init failed."""
    return _event_store


async def init_event_store() -> None:
    """Initialize the DeerFlow async engine + DbRunEventStore.

    Called from backend lifespan. Points at the same DeerFlow DB as the agent
    (DEERFLOW_DB_PATH or DEERFLOW_DB_URL env vars). Non-fatal: if init fails,
    event persistence is silently disabled.
    """
    global _event_store, _init_error

    try:
        import os
        import re as _re
        from pathlib import Path

        from deerflow.persistence.engine import get_session_factory, init_engine

        db_url = os.environ.get("DEERFLOW_DB_URL")
        is_postgres = bool(db_url and db_url.startswith(("postgresql", "postgres")))

        if not is_postgres:
            # Default: local SQLite using the agent's checkpointer DB path.
            # DeerFlow DB lives at {DATA_ROOT}/db/deerflow-checkpoints.db —
            # same file the agent's checkpointer writes to, so the backend
            # and agent share one run_events table.
            db_path = os.environ.get("DEERFLOW_DB_PATH")
            if not db_path:
                data_root = os.environ.get(
                    "DATA_ROOT", str(Path("~/.numina/data").expanduser())
                )
                db_path = str(Path(data_root) / "db" / "deerflow-checkpoints.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite+aiosqlite:///{db_path}"

        if is_postgres and db_url:
            # asyncpg URL rewrite (mirrors agent lifespan)
            db_url = _re.sub(r"^postgresql(\+\w+)?://", "postgresql+asyncpg://", db_url)
            await init_engine(backend="postgres", url=db_url)
        else:
            # Directory already ensured above; sqlite_dir="" skips DeerFlow's
            # redundant mkdir.
            await init_engine(backend="sqlite", url=db_url)

        session_factory = get_session_factory()
        if session_factory is None:
            _init_error = "get_session_factory() returned None (memory backend?)"
            logger.warning("[event_persistence] %s", _init_error)
            return

        from deerflow.runtime.events.store.db import DbRunEventStore

        _event_store = DbRunEventStore(session_factory=session_factory)
        # init_engine auto-creates DeerFlow tables (incl. run_events); no
        # separate create_all needed.
        logger.info("[event_persistence] DbRunEventStore initialized")
    except Exception as e:
        _init_error = str(e)
        logger.warning(
            "[event_persistence] init failed (event persistence disabled): %s",
            e,
            exc_info=True,
        )


# Event type mapping: bridge event → DbRunEventStore event_type/category
_EVENT_TYPE_MAP = {
    "messages": ("llm.ai.response", "messages"),
    "custom": ("trace", "custom"),
    "end": ("run.end", "lifecycle"),
    "error": ("run.error", "lifecycle"),
    "metadata": ("run.metadata", "lifecycle"),
    "values": ("values", "state"),
}


async def persist_event(
    *,
    thread_id: str,
    run_id: str,
    event_type: str,
    event_data: Any,
    family_id: int,
) -> None:
    """Persist a single bridge event to DbRunEventStore.

    Non-fatal: all exceptions are caught and logged.
    """
    store = _get_event_store()
    if store is None:
        return  # persistence not initialized

    try:
        mapped = _EVENT_TYPE_MAP.get(event_type, ("trace", event_type))
        df_event_type, df_category = mapped

        import json

        content = json.dumps(event_data, default=str, ensure_ascii=False) if not isinstance(event_data, str) else event_data
        metadata = {"family_id": str(family_id), "bridge_event_type": event_type}

        await store.put(
            thread_id=thread_id,
            run_id=run_id,
            event_type=df_event_type,
            category=df_category,
            content=content[:10000],  # cap content size
            metadata=metadata,
        )
    except Exception:
        global _failure_count
        _failure_count += 1
        if _failure_count <= _MAX_WARNING_FAILURES:
            logger.warning(
                "[event_persistence] persist failed (non-fatal, %d/%d) event=%s run=%s",
                _failure_count,
                _MAX_WARNING_FAILURES,
                event_type,
                run_id,
                exc_info=True,
            )
        else:
            logger.debug(
                "[event_persistence] persist failed (non-fatal) event=%s run=%s",
                event_type,
                run_id,
                exc_info=True,
            )
