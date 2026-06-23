"""Background agent execution for family-scoped runs.

This is the Numina equivalent of DeerFlow's ``run_agent()`` worker.  Unlike
DeerFlow (which calls ``agent.astream()`` directly on a LangGraph graph built
by ``make_lead_agent``), the Numina version delegates to the existing
``DeerFlowAdapter.typed_stream_dispatch()`` — this preserves Numina's per-family
adapter caching, PII redaction, and audit logging while gaining the
``StreamBridge`` + ``RunManager`` lifecycle.

# [Integrated with Numina Multi-Tenant] — family-scoped agent execution
# Preserves Numina's PII redaction (K.I. #1) and audit logging (K.I. #3)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import FamilyContext
from apps.agent.services.audit_logger import AuditEntry, audit_logger
from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.services.pii_redactor import pii_redactor

from .gc import schedule_run_cleanup

logger = logging.getLogger(__name__)


async def run_family_agent(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    family_id: str,
    user_id: str | None,
    thread_id: str,
    graph_input: dict | None,
    config: dict[str, Any],
    stream_modes: list[str] | None = None,
) -> None:
    """Background agent execution for a family-scoped run.

    Publishes events to the ``StreamBridge`` and uses the ``RunManager`` for
    lifecycle tracking.  Runs inside ``asyncio.create_task()`` so it does not
    block the SSE response.

    Key patterns preserved from DeerFlow ``run_agent``:
    - ``await run_manager.set_status(run_id, RunStatus.running)`` at start
    - ``await bridge.publish(run_id, "metadata", ...)`` as first event
    - ``record.abort_event.is_set()`` checks for cooperative cancellation
    - Terminal status ``success`` / ``error`` / ``interrupted``
    - ``await bridge.publish_end(run_id)`` in ``finally``
    - Deferred ``bridge.cleanup(run_id, delay=60)`` in ``finally``

    # [Copied from DeerFlow Reference] — patterns from runtime/runs/worker.py
    # [Integrated with Numina Multi-Tenant] — family_id scoping
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None

    try:
        # 1. Mark running + publish metadata (DeerFlow pattern)
        await run_manager.set_status(run_id, RunStatus.running)
        await bridge.publish(
            run_id,
            "metadata",
            {
                "run_id": run_id,
                "thread_id": thread_id,
            },
        )

        # 2. Fetch per-family AI config (tenant-isolated)
        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        # 3. Build adapter (uses per-family LRU cache from family_adapter_cache.py)
        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=240,
            subagent_enabled=True,
            plan_mode=False,
        )

        # 4. Extract user message for context
        user_message = ""
        if graph_input and "messages" in graph_input:
            msgs = graph_input["messages"]
            if isinstance(msgs, list) and msgs:
                last = msgs[-1]
                if isinstance(last, dict) and last.get("role") in ("user", "human"):
                    user_message = last.get("content", "")

        # 5. PII redaction (Key Invariant #1)
        context = FamilyContext(family_id=family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # 6. Stream via typed_stream_dispatch → publish to bridge
        capability = "chat"
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name=capability,
            context=redacted,
            thread_id=thread_id,
            enable_thinking=True,
        ):
            # Cooperative cancellation check (DeerFlow pattern)
            if record.abort_event.is_set():
                break

            if sse_type == "end":
                break
            if sse_type == "error":
                await bridge.publish(run_id, "error", data)
                break

            await bridge.publish(run_id, sse_type, data)

        # 7. Terminal status
        if record.abort_event.is_set():
            await run_manager.set_status(run_id, RunStatus.interrupted)
        else:
            await run_manager.set_status(run_id, RunStatus.success)
        success = record.status == RunStatus.success

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning("[run_family_agent] failed run=%s err=%s", run_id, error_type)
        await run_manager.set_status(run_id, RunStatus.error, error=str(exc))
        await bridge.publish(
            run_id,
            "error",
            {"message": str(exc), "name": error_type},
        )

    finally:
        # 8. Audit log (Key Invariant #3)
        audit_logger.log_call(
            AuditEntry(
                family_id=family_id,
                audit_id=run_id,
                user_id=user_id or "",
                capability="chat",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )
        # 9. Publish end sentinel + schedule deferred cleanup (DeerFlow pattern)
        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))
