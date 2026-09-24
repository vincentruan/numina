"""SQLite-backed RunStore for Numina agent persistence.

Implements DeerFlow's RunStore interface using the shared DeerFlow engine.
Supports cross-restart run state recovery and orphan cleanup.

SQL uses named-parameter raw statements (text) — portable across SQLite
(aiosqlite) and PostgreSQL (asyncpg) backends, both provided by DeerFlow's
async engine.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

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

_ALL_COLUMNS = (
    "run_id, thread_id, assistant_id, user_id, model_name, status, "
    "operation_kind, multitask_strategy, metadata_json, kwargs_json, "
    "error, stop_reason, total_input_tokens, total_output_tokens, "
    "total_tokens, llm_call_count, lead_agent_tokens, subagent_tokens, "
    "middleware_tokens, token_usage_by_model, message_count, "
    "last_ai_message, first_human_message, created_at, owner_worker_id, "
    "lease_expires_at, updated_at"
)


class NuminaSqliteRunStore:
    """DeerFlow RunStore implementation backed by the shared async engine."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory
        self._table_ready = False

    async def _ensure_table(self) -> None:
        """Ensure run_records table exists (idempotent, called once)."""
        if self._table_ready:
            return
        async with self._sf() as session, session.begin():
            await session.execute(text(CREATE_TABLE_SQL))
            await session.execute(text(INDEX_THREAD))
            await session.execute(text(INDEX_STATUS))
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
        async with self._sf() as session:
            async with session.begin():
                # Atomic upsert — works on both SQLite and PostgreSQL
                await session.execute(
                    text("""
                        INSERT INTO run_records
                        (run_id, thread_id, assistant_id, user_id, model_name, status,
                         operation_kind, multitask_strategy, metadata_json, kwargs_json,
                         error, stop_reason, created_at, owner_worker_id, lease_expires_at,
                         updated_at)
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

    async def get(self, run_id: str, *, user_id: str | None = None) -> dict[str, Any] | None:
        await self._ensure_table()
        async with self._sf() as session:
            result = await session.execute(
                text(f"SELECT {_ALL_COLUMNS} FROM run_records WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            row = result.first()
        return self._row_to_dict(row) if row else None

    async def list_by_thread(
        self,
        thread_id: str,
        *,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        await self._ensure_table()
        async with self._sf() as session:
            result = await session.execute(
                text(
                    f"SELECT {_ALL_COLUMNS} FROM run_records "
                    "WHERE thread_id = :thread_id ORDER BY created_at DESC LIMIT :limit"
                ),
                {"thread_id": thread_id, "limit": limit},
            )
            rows = result.fetchall()
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

    async def start_run(self, run_id: str) -> bool:
        await self._ensure_table()
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

    async def delete(self, run_id: str) -> None:
        await self._ensure_table()
        async with self._sf() as session, session.begin():
            await session.execute(
                text("DELETE FROM run_records WHERE run_id = :run_id"),
                {"run_id": run_id},
            )

    # -------------------------------------------------------------------------
    # Model + completion
    # -------------------------------------------------------------------------

    async def update_model_name(self, run_id: str, model_name: str | None) -> None:
        await self._ensure_table()
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
        async with self._sf() as session:
            result = await session.execute(text(sql), params)
            rows = result.fetchall()
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

    async def claim_for_takeover(self, run_id: str, new_owner_worker_id: str) -> bool | None:
        """Atomically claim an unowned/expired-lease run for takeover."""
        await self._ensure_table()
        async with self._sf() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        "UPDATE run_records SET owner_worker_id=:owner, updated_at=:now "
                        "WHERE run_id=:run_id "
                        "AND (owner_worker_id IS NULL "
                        "OR lease_expires_at IS NULL OR lease_expires_at < :now)"
                    ),
                    {
                        "owner": new_owner_worker_id,
                        "now": datetime.now(UTC).isoformat(),
                        "run_id": run_id,
                    },
                )
            return bool(result.rowcount > 0)

    async def list_inflight_with_expired_lease(
        self,
        *,
        before: str | None = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """List running runs whose lease has expired (orphan candidates)."""
        await self._ensure_table()
        ts = (now or datetime.now(UTC)).isoformat()
        sql = (
            f"SELECT {_ALL_COLUMNS} FROM run_records "
            "WHERE status = 'running' "
            "AND lease_expires_at IS NOT NULL AND lease_expires_at < :ts"
        )
        params: dict[str, Any] = {"ts": ts}
        if before:
            sql += " AND created_at < :before"
            params["before"] = before
        sql += " ORDER BY created_at ASC"
        async with self._sf() as session:
            result = await session.execute(text(sql), params)
            rows = result.fetchall()
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
        async with self._sf() as session:
            result = await session.execute(text(sql), params)
            row = result.first()
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
