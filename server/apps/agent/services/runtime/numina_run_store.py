"""SQL-backed RunStore for Numina agent persistence.

Implements DeerFlow's RunStore interface using the shared DeerFlow engine.
Supports cross-restart run state recovery and orphan cleanup.

SQL uses named-parameter raw statements (text) — portable across SQLite
(aiosqlite) and PostgreSQL (asyncpg) backends, both provided by DeerFlow's
async engine.

Cancellation safety
-------------------
Every public method wraps its DB work in ``_run_isolated()`` — a helper that
runs the coroutine in an independent ``asyncio.Task``.  This prevents a known
SQLAlchemy / asyncpg issue where task cancellation (e.g. client disconnect
during SSE streaming) propagates into connection-pool ``terminate()`` and
raises a spurious ``CancelledError`` at ERROR level.  The independent task
does not inherit the caller's cancel scope, so the DB session and connection
cleanup complete cleanly even when the caller is cancelled.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.logging import get_logger

logger = get_logger(__name__)

# Table DDL — run_records store mirrors DeerFlow's RunRecord semantics.
# Token columns default to 0 for SQLite; PostgreSQL uses COALESCE-safe types.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS run_records (
    run_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    assistant_id TEXT,
    user_id TEXT,
    model_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    operation_kind TEXT NOT NULL DEFAULT 'run',
    multitask_strategy TEXT NOT NULL DEFAULT 'reject',
    metadata_json TEXT,
    kwargs_json TEXT,
    error TEXT,
    stop_reason TEXT,
    total_input_tokens INTEGER NOT NULL DEFAULT 0,
    total_output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    llm_call_count INTEGER NOT NULL DEFAULT 0,
    lead_agent_tokens INTEGER NOT NULL DEFAULT 0,
    subagent_tokens INTEGER NOT NULL DEFAULT 0,
    middleware_tokens INTEGER NOT NULL DEFAULT 0,
    token_usage_by_model TEXT,
    message_count INTEGER NOT NULL DEFAULT 0,
    last_ai_message TEXT,
    first_human_message TEXT,
    created_at TEXT NOT NULL,
    owner_worker_id TEXT,
    lease_expires_at TEXT,
    updated_at TEXT NOT NULL
)
"""

INDEX_THREAD = "CREATE INDEX IF NOT EXISTS ix_runs_thread ON run_records(thread_id)"
INDEX_STATUS = "CREATE INDEX IF NOT EXISTS ix_runs_status ON run_records(status, created_at)"
# Partial unique index — enforces at most one active (pending/running) run per
# thread. Matches DeerFlow's cross-process thread-uniqueness contract; lets the
# DB reject concurrent inserts atomically instead of a TOCTOU SELECT+INSERT.
INDEX_ACTIVE_UNIQUE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_runs_thread_active "
    "ON run_records(thread_id) WHERE status IN ('pending', 'running')"
)

_ALL_COLUMNS = (
    "run_id, thread_id, assistant_id, user_id, model_name, status, "
    "operation_kind, multitask_strategy, metadata_json, kwargs_json, "
    "error, stop_reason, total_input_tokens, total_output_tokens, "
    "total_tokens, llm_call_count, lead_agent_tokens, subagent_tokens, "
    "middleware_tokens, token_usage_by_model, message_count, "
    "last_ai_message, first_human_message, created_at, owner_worker_id, "
    "lease_expires_at, updated_at"
)


# ---------------------------------------------------------------------------
# Cancellation isolation helper
# ---------------------------------------------------------------------------


async def _run_isolated(coro):
    """Run a DB coroutine in an independent task, shielded from caller cancellation.

    When the caller's task is cancelled (e.g. client disconnect during SSE
    streaming), ``asyncio.CancelledError`` propagates into ``async with session``
    cleanup.  SQLAlchemy's connection-pool ``terminate()`` then fails because
    ``asyncio.shield()`` cannot protect from the *enclosing* cancel scope
    (known asyncpg + SQLAlchemy issue).

    Fix: run the DB operation in a fresh ``asyncio.Task`` which does NOT
    inherit the caller's cancel scope.  The task completes (or rolls back)
    independently, and the caller can be cancelled without affecting the
    connection-pool cleanup.
    """
    task = asyncio.create_task(coro)
    try:
        return await task
    except asyncio.CancelledError:
        # Caller was cancelled but the DB task keeps running independently.
        # Detach: let it finish in the background so the connection is returned
        # to the pool cleanly.  Fire-and-forget is safe here — the task holds
        # its own reference and will complete or log on failure.
        task.add_done_callback(_log_isolated_db_error)
        raise


def _log_isolated_db_error(task: asyncio.Task) -> None:
    """Log unhandled errors from detached DB tasks (best-effort)."""
    if not task.cancelled():
        exc = task.exception()
        if exc:
            logger.warning(
                "isolated DB task failed: %s", type(exc).__name__, exc_info=exc
            )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class NuminaSqlRunStore:
    """DeerFlow RunStore implementation backed by the shared async engine."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory
        self._table_ready = False
        self._dialect: str | None = None

    async def _get_dialect(self) -> str:
        """Detect and cache the database dialect name."""
        if self._dialect is None:

            async def _do():
                async with self._sf() as session:
                    self._dialect = session.bind.dialect.name

            await _run_isolated(_do())
        return self._dialect

    async def _ensure_table(self) -> None:
        """Ensure run_records table exists (idempotent, called once)."""
        if self._table_ready:
            return

        async def _do():
            async with self._sf() as session, session.begin():
                await session.execute(text(CREATE_TABLE_SQL))
                await session.execute(text(INDEX_THREAD))
                await session.execute(text(INDEX_STATUS))
                await session.execute(text(INDEX_ACTIVE_UNIQUE))

        await _run_isolated(_do())
        self._table_ready = True

    # -------------------------------------------------------------------------
    # Core CRUD
    # -------------------------------------------------------------------------

    async def put(
        self,
        run_id: str,
        *,
        thread_id: str,
        assistant_id: str | None = None,
        user_id: str | None = None,
        model_name: str | None = None,
        status: str = "pending",
        operation_kind: str = "run",
        multitask_strategy: str = "reject",
        metadata: dict[str, Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        error: str | None = None,
        stop_reason: str | None = None,
        created_at: str | None = None,
        owner_worker_id: str | None = None,
        lease_expires_at: str | None = None,
    ) -> None:
        await self._ensure_table()
        now = datetime.now(UTC).isoformat()
        params = {
            "run_id": run_id,
            "thread_id": thread_id,
            "assistant_id": assistant_id,
            "user_id": user_id,
            "model_name": model_name,
            "status": status,
            "operation_kind": operation_kind,
            "multitask_strategy": multitask_strategy,
            "metadata_json": json.dumps(metadata, default=str, ensure_ascii=False) if metadata else None,
            "kwargs_json": json.dumps(kwargs, default=str, ensure_ascii=False) if kwargs else None,
            "error": error,
            "stop_reason": stop_reason,
            "created_at": created_at or now,
            "owner_worker_id": owner_worker_id,
            "lease_expires_at": lease_expires_at,
            "updated_at": now,
        }

        async def _do():
            async with self._sf() as session, session.begin():
                # Atomic upsert — works on both SQLite and PostgreSQL
                await session.execute(
                        text("""
                            INSERT INTO run_records
                            (run_id, thread_id, assistant_id, user_id, model_name, status,
                             operation_kind, multitask_strategy, metadata_json, kwargs_json,
                             error, stop_reason, created_at, owner_worker_id,
                             lease_expires_at, updated_at)
                            VALUES
                            (:run_id, :thread_id, :assistant_id, :user_id, :model_name, :status,
                             :operation_kind, :multitask_strategy, :metadata_json, :kwargs_json,
                             :error, :stop_reason, :created_at, :owner_worker_id,
                             :lease_expires_at, :updated_at)
                            ON CONFLICT (run_id) DO UPDATE SET
                                thread_id=:thread_id,
                                assistant_id=:assistant_id,
                                user_id=:user_id,
                                model_name=:model_name,
                                status=:status,
                                operation_kind=:operation_kind,
                                multitask_strategy=:multitask_strategy,
                                metadata_json=:metadata_json,
                                kwargs_json=:kwargs_json,
                                error=:error,
                                stop_reason=:stop_reason,
                                owner_worker_id=:owner_worker_id,
                                lease_expires_at=:lease_expires_at,
                                updated_at=:updated_at
                        """),
                        params,
                    )

        await _run_isolated(_do())

    async def get(self, run_id: str, *, user_id: str | None = None) -> dict[str, Any] | None:
        await self._ensure_table()

        async def _do():
            async with self._sf() as session:
                result = await session.execute(
                    text(f"SELECT {_ALL_COLUMNS} FROM run_records WHERE run_id = :run_id"),
                    {"run_id": run_id},
                )
                return result.first()

        row = await _run_isolated(_do())
        return self._row_to_dict(row) if row else None

    async def list_by_thread(
        self,
        thread_id: str,
        *,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        await self._ensure_table()

        async def _do():
            async with self._sf() as session:
                result = await session.execute(
                    text(
                        f"SELECT {_ALL_COLUMNS} FROM run_records "
                        "WHERE thread_id = :thread_id ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"thread_id": thread_id, "limit": limit},
                )
                return result.fetchall()

        rows = await _run_isolated(_do())
        return [self._row_to_dict(r) for r in rows]

    async def update_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        stop_reason: str | None = None,
    ) -> bool | None:
        await self._ensure_table()

        async def _do():
            async with self._sf() as session:
                async with session.begin():
                    result = await session.execute(
                        text(
                            "UPDATE run_records SET status=:status, error=:error, "
                            "stop_reason=:stop_reason, updated_at=:now "
                            "WHERE run_id=:run_id"
                        ),
                        {
                            "status": status,
                            "error": error,
                            "stop_reason": stop_reason,
                            "now": datetime.now(UTC).isoformat(),
                            "run_id": run_id,
                        },
                    )
                return bool(result.rowcount > 0)

        return await _run_isolated(_do())

    async def start_run(self, run_id: str) -> bool:
        await self._ensure_table()

        async def _do():
            async with self._sf() as session:
                async with session.begin():
                    result = await session.execute(
                        text(
                            "UPDATE run_records SET status='running', "
                            "updated_at=:now WHERE run_id=:run_id AND status='pending'"
                        ),
                        {"now": datetime.now(UTC).isoformat(), "run_id": run_id},
                    )
                return bool(result.rowcount > 0)

        return await _run_isolated(_do())

    async def delete(self, run_id: str) -> None:
        await self._ensure_table()

        async def _do():
            async with self._sf() as session, session.begin():
                await session.execute(
                    text("DELETE FROM run_records WHERE run_id = :run_id"),
                    {"run_id": run_id},
                )

        await _run_isolated(_do())

    # -------------------------------------------------------------------------
    # Atomic admission (DeerFlow RunStore interface)
    # -------------------------------------------------------------------------

    async def create_thread_operation_atomic(
        self,
        run_id: str,
        *,
        thread_id: str,
        owner_worker_id: str,
        lease_expires_at: str | None,
        operation_kind: str = "run",
        multitask_strategy: str = "reject",
        assistant_id: str | None = None,
        user_id: str | None = None,
        model_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        created_at: str | None = None,
        grace_seconds: int = 10,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Atomically create a run with cross-process thread-uniqueness.

        - For ``reject``: INSERT, let the partial unique index enforce
          single-active-run. Raises ``IntegrityError`` on conflict (caller
          converts to ConflictError).
        - For ``interrupt`` / ``rollback``: find inflight runs, mark them
          interrupted (unless lease still valid and owned by another worker),
          then INSERT. Returns ``(new_run_dict, claimed_run_dicts)``.

        Matches DeerFlow's ``RunRepository.create_thread_operation_atomic``
        contract (see ``deerflow/persistence/run/sql.py``).
        """
        await self._ensure_table()
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        created_iso = created_at or now_iso
        cutoff = (now - timedelta(seconds=grace_seconds)).isoformat()
        dialect = await self._get_dialect()

        async def _do():
            async with self._sf() as session:
                async with session.begin():
                    claimed: list[dict[str, Any]] = []

                    if multitask_strategy in ("interrupt", "rollback"):
                        # Find active runs for this thread and claim them.
                        # PostgreSQL: use SELECT FOR UPDATE for row-level locking
                        # SQLite: relies on database-level serialization (no FOR UPDATE)
                        for_update = " FOR UPDATE" if dialect == "postgresql" else ""
                        result = await session.execute(
                            text(
                                f"SELECT {_ALL_COLUMNS} FROM run_records "
                                "WHERE thread_id = :thread_id "
                                "AND status IN ('pending', 'running')"
                                f"{for_update}"
                            ),
                            {"thread_id": thread_id},
                        )
                        active_rows = [self._row_to_dict(r) for r in result.fetchall()]

                        for row in active_rows:
                            row_lease = row.get("lease_expires_at")
                            lease_valid = row_lease is not None and row_lease >= cutoff
                            row_owner = row.get("owner_worker_id")

                            if lease_valid and row_owner != owner_worker_id:
                                from deerflow.runtime.runs.manager import ConflictError

                                raise ConflictError(
                                    f"Thread {thread_id} already has an active run "
                                    "owned by another worker"
                                )

                            if row.get("operation_kind") != "run" and lease_valid:
                                from deerflow.runtime.runs.manager import ConflictError

                                raise ConflictError(
                                    f"Thread {thread_id} has an active checkpoint write"
                                )

                            # Mark as interrupted
                            await session.execute(
                                text(
                                    "UPDATE run_records SET status='interrupted', "
                                    "error='Cancelled by newer run', "
                                    "owner_worker_id=:owner, updated_at=:now "
                                    "WHERE run_id=:run_id"
                                ),
                                {
                                    "owner": owner_worker_id,
                                    "now": now_iso,
                                    "run_id": row["run_id"],
                                },
                            )
                            row["status"] = "interrupted"
                            row["error"] = "Cancelled by newer run"
                            row["owner_worker_id"] = owner_worker_id
                            claimed.append(row)

                    # Insert the new run record. For ``reject`` strategy, the
                    # partial unique index ``ix_runs_thread_active`` enforces
                    # thread-uniqueness atomically — a conflicting INSERT raises
                    # IntegrityError, which RunManager converts to ConflictError.
                    await session.execute(
                        text(
                            """
                            INSERT INTO run_records
                            (run_id, thread_id, assistant_id, user_id, model_name, status,
                             operation_kind, multitask_strategy, metadata_json, kwargs_json,
                             owner_worker_id, lease_expires_at, created_at, updated_at)
                            VALUES
                            (:run_id, :thread_id, :assistant_id, :user_id, :model_name, 'pending',
                             :operation_kind, :multitask_strategy, :metadata_json, :kwargs_json,
                             :owner_worker_id, :lease_expires_at, :created_at, :updated_at)
                            """
                        ),
                        {
                            "run_id": run_id,
                            "thread_id": thread_id,
                            "assistant_id": assistant_id,
                            "user_id": user_id,
                            "model_name": model_name,
                            "operation_kind": operation_kind,
                            "multitask_strategy": multitask_strategy,
                            "metadata_json": json.dumps(metadata, default=str, ensure_ascii=False)
                            if metadata
                            else "{}",
                            "kwargs_json": json.dumps(kwargs, default=str, ensure_ascii=False)
                            if kwargs
                            else "{}",
                            "owner_worker_id": owner_worker_id,
                            "lease_expires_at": lease_expires_at,
                            "created_at": created_iso,
                            "updated_at": now_iso,
                        },
                    )

                # Fetch the inserted row after commit
                new_row_result = await session.execute(
                    text(f"SELECT {_ALL_COLUMNS} FROM run_records WHERE run_id = :run_id"),
                    {"run_id": run_id},
                )
                new_row = self._row_to_dict(new_row_result.first())
                return new_row, claimed

        return await _run_isolated(_do())

    # -------------------------------------------------------------------------
    # Model + completion
    # -------------------------------------------------------------------------

    async def update_model_name(self, run_id: str, model_name: str | None) -> None:
        await self._ensure_table()

        async def _do():
            async with self._sf() as session, session.begin():
                await session.execute(
                    text(
                        "UPDATE run_records SET model_name=:model_name, updated_at=:now "
                        "WHERE run_id=:run_id"
                    ),
                    {
                        "model_name": model_name,
                        "now": datetime.now(UTC).isoformat(),
                        "run_id": run_id,
                    },
                )

        await _run_isolated(_do())

    async def update_run_completion(
        self,
        run_id: str,
        *,
        status: str,
        total_input_tokens: int = 0,
        total_output_tokens: int = 0,
        total_tokens: int = 0,
        llm_call_count: int = 0,
        lead_agent_tokens: int = 0,
        subagent_tokens: int = 0,
        middleware_tokens: int = 0,
        token_usage_by_model: dict[str, dict[str, int]] | None = None,
        message_count: int = 0,
        last_ai_message: str | None = None,
        first_human_message: str | None = None,
        error: str | None = None,
    ) -> bool | None:
        """Persist final completion fields; never replace a conflicting terminal state."""
        await self._ensure_table()

        async def _do():
            async with self._sf() as session:
                async with session.begin():
                    result = await session.execute(
                        text(
                            "UPDATE run_records SET status=:status, error=:error, "
                            "total_input_tokens=:total_input_tokens, "
                            "total_output_tokens=:total_output_tokens, "
                            "total_tokens=:total_tokens, "
                            "llm_call_count=:llm_call_count, "
                            "lead_agent_tokens=:lead_agent_tokens, "
                            "subagent_tokens=:subagent_tokens, "
                            "middleware_tokens=:middleware_tokens, "
                            "token_usage_by_model=:token_usage_by_model, "
                            "message_count=:message_count, "
                            "last_ai_message=:last_ai_message, "
                            "first_human_message=:first_human_message, "
                            "updated_at=:now "
                            "WHERE run_id=:run_id AND status NOT IN ('completed', 'failed', 'cancelled')"
                        ),
                        {
                            "status": status,
                            "error": error,
                            "total_input_tokens": total_input_tokens,
                            "total_output_tokens": total_output_tokens,
                            "total_tokens": total_tokens,
                            "llm_call_count": llm_call_count,
                            "lead_agent_tokens": lead_agent_tokens,
                            "subagent_tokens": subagent_tokens,
                            "middleware_tokens": middleware_tokens,
                            "token_usage_by_model": json.dumps(
                                token_usage_by_model, default=str, ensure_ascii=False
                            )
                            if token_usage_by_model
                            else None,
                            "message_count": message_count,
                            "last_ai_message": last_ai_message,
                            "first_human_message": first_human_message,
                            "now": datetime.now(UTC).isoformat(),
                            "run_id": run_id,
                        },
                    )
                return bool(result.rowcount > 0)

        return await _run_isolated(_do())

    # -------------------------------------------------------------------------
    # Pending / inflight listing
    # -------------------------------------------------------------------------

    async def _list_by_status(self, status: str, before: str | None = None) -> list[dict[str, Any]]:
        await self._ensure_table()
        sql = f"SELECT {_ALL_COLUMNS} FROM run_records WHERE status = :status"
        params: dict[str, Any] = {"status": status}
        if before:
            sql += " AND created_at < :before"
            params["before"] = before
        sql += " ORDER BY created_at ASC"

        async def _do():
            async with self._sf() as session:
                result = await session.execute(text(sql), params)
                return result.fetchall()

        rows = await _run_isolated(_do())
        return [self._row_to_dict(r) for r in rows]

    async def list_pending(self, *, before: str | None = None) -> list[dict[str, Any]]:
        return await self._list_by_status("pending", before=before)

    async def list_inflight(self, *, before: str | None = None) -> list[dict[str, Any]]:
        return await self._list_by_status("running", before=before)

    # -------------------------------------------------------------------------
    # Lease management
    # -------------------------------------------------------------------------

    async def update_lease(
        self,
        run_id: str,
        expires_at: str,
        *,
        lease_duration_seconds: float = 300.0,
        owner_worker_id: str | None = None,
    ) -> bool:
        """Renew a lease; only succeeds when the current lease is expired/absent
        (prevents stealing a live lease from another worker)."""
        await self._ensure_table()
        now_iso = datetime.now(UTC).isoformat()

        async def _do():
            async with self._sf() as session:
                async with session.begin():
                    result = await session.execute(
                        text(
                            "UPDATE run_records SET lease_expires_at=:expires_at, "
                            "owner_worker_id=:owner, updated_at=:now "
                            "WHERE run_id=:run_id "
                            "AND (lease_expires_at IS NULL OR lease_expires_at <= :now)"
                        ),
                        {
                            "expires_at": expires_at,
                            "owner": owner_worker_id,
                            "now": now_iso,
                            "run_id": run_id,
                        },
                    )
                return bool(result.rowcount > 0)

        return await _run_isolated(_do())

    async def claim_for_takeover(
        self,
        run_id: str,
        *,
        grace_seconds: int,
        error: str,
        stop_reason: str | None = None,
    ) -> bool:
        """Atomically mark an expired-lease active run as ``error``.

        Only rows whose lease has expired past *grace_seconds* (or whose
        lease is NULL — pre-ownership data) are updated.  Matches the
        DeerFlow base-store contract.
        """
        await self._ensure_table()
        cutoff = (datetime.now(UTC) - timedelta(seconds=grace_seconds)).isoformat()
        now_iso = datetime.now(UTC).isoformat()

        async def _do():
            async with self._sf() as session:
                async with session.begin():
                    result = await session.execute(
                        text(
                            "UPDATE run_records "
                            "SET status='error', error=:error, "
                            "stop_reason=:stop_reason, updated_at=:now "
                            "WHERE run_id=:run_id "
                            "AND status IN ('pending', 'running') "
                            "AND (lease_expires_at IS NULL OR lease_expires_at < :cutoff)"
                        ),
                        {
                            "error": error,
                            "stop_reason": stop_reason,
                            "now": now_iso,
                            "run_id": run_id,
                            "cutoff": cutoff,
                        },
                    )
                return bool(result.rowcount > 0)

        return await _run_isolated(_do())

    async def list_inflight_with_expired_lease(
        self,
        *,
        before: str | None = None,
        grace_seconds: int = 10,
    ) -> list[dict[str, Any]]:
        """List running/pending runs whose lease has expired (orphan candidates).

        Rows with a NULL lease (pre-ownership data) are also returned so they
        can be reclaimed, matching the DeerFlow reference implementation.
        """
        await self._ensure_table()
        cutoff = (datetime.now(UTC) - timedelta(seconds=grace_seconds)).isoformat()
        before_iso = before if before else datetime.now(UTC).isoformat()
        sql = (
            f"SELECT {_ALL_COLUMNS} FROM run_records "
            "WHERE status IN ('pending', 'running') "
            "AND created_at <= :before "
            "AND (lease_expires_at IS NULL OR lease_expires_at < :cutoff)"
        )
        params: dict[str, Any] = {"before": before_iso, "cutoff": cutoff}
        sql += " ORDER BY created_at ASC"

        async def _do():
            async with self._sf() as session:
                result = await session.execute(text(sql), params)
                return result.fetchall()

        rows = await _run_isolated(_do())
        return [self._row_to_dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # Token aggregation
    # -------------------------------------------------------------------------

    async def aggregate_tokens_by_thread(
        self,
        thread_id: str,
        *,
        include_active: bool = False,
    ) -> dict[str, Any]:
        await self._ensure_table()
        sql = (
            "SELECT "
            "COALESCE(SUM(total_input_tokens), 0), "
            "COALESCE(SUM(total_output_tokens), 0), "
            "COALESCE(SUM(total_tokens), 0), "
            "COALESCE(SUM(llm_call_count), 0) "
            "FROM run_records WHERE thread_id = :thread_id"
        )
        params: dict[str, Any] = {"thread_id": thread_id}
        if not include_active:
            sql += " AND status IN ('completed', 'failed', 'cancelled')"

        async def _do():
            async with self._sf() as session:
                result = await session.execute(text(sql), params)
                return result.first()

        row = await _run_isolated(_do())
        if not row:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "llm_calls": 0}
        return {
            "input_tokens": int(row[0] or 0),
            "output_tokens": int(row[1] or 0),
            "total_tokens": int(row[2] or 0),
            "llm_calls": int(row[3] or 0),
        }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        d = dict(row._mapping)
        d["metadata"] = (
            json.loads(d["metadata_json"]) if d.get("metadata_json") else {}
        )
        d["kwargs"] = json.loads(d["kwargs_json"]) if d.get("kwargs_json") else {}
        d["token_usage_by_model"] = (
            json.loads(d["token_usage_by_model"]) if d.get("token_usage_by_model") else None
        )
        d.pop("metadata_json", None)
        d.pop("kwargs_json", None)
        d.pop("token_usage_by_model_json", None)
        return d
