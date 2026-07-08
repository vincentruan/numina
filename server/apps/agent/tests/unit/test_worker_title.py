"""Tests for run_family_agent — title sync is scheduled from the finally block.

Regression guard: the worker's ``finally`` block must schedule
``sync_title_from_checkpoint`` (which reads the title DeerFlow's
TitleMiddleware wrote to the checkpoint) — NOT the old
``generate_and_save_title`` which made a redundant second LLM call. The sync
takes ``(thread_id, family_id)`` as positional args plus kwargs
(``ai_config``, ``user_message``, ``ai_response``) used to generate an LLM
title when the checkpoint only has the sync ``[SKILL:chat]`` fallback.

Calls ``run_family_agent`` directly with stubbed dependencies, bypassing the
FastAPI lifespan layer (the v2 SSE contract tests are pre-existing broken on
this branch) to isolate the worker's wiring.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from deerflow.runtime import RunStatus

from apps.agent.services.runtime.worker import run_family_agent


async def test_run_family_agent_schedules_title_sync_from_checkpoint():
    """sync_title_from_checkpoint is scheduled with (thread_id, family_id)."""
    # --- record / bridge / run_manager stubs ---
    record = MagicMock()
    record.run_id = "run-1"
    record.thread_id = "thread-1"
    record.abort_event = asyncio.Event()  # not set → run completes
    record.status = RunStatus.success
    record.metadata = {"family_id": "family-1"}

    bridge = MagicMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()

    run_manager = MagicMock()
    run_manager.set_status = AsyncMock()

    # --- stub adapter: one AI message then end ---
    stub_adapter = MagicMock()

    async def typed_stream_dispatch(*args, **kwargs):
        yield ("messages", {"type": "ai", "content": "hello", "tool_calls": None})
        yield ("end", {})

    stub_adapter.typed_stream_dispatch = typed_stream_dispatch

    # --- ai_config envelope: provider keys nested under "providers" ---
    ai_config_envelope = {
        "ai_enabled": True,
        "providers": [
            {
                "is_active": True,
                "ai_provider": "openai",
                "api_key": "test-key",
                "ai_base_url": "http://localhost:11434/v1",
                "ai_model_id": "gpt-4o-mini",
            }
        ],
    }

    title_sync_mock = AsyncMock(return_value=None)

    with (
        patch("apps.agent.services.runtime.worker.BackendClient") as MockClient,
        patch(
            "apps.agent.services.runtime.worker.create_family_adapter",
            return_value=stub_adapter,
        ),
        patch("apps.agent.services.runtime.worker.pii_redactor") as mock_pii,
        patch("apps.agent.services.runtime.worker.audit_logger"),
        patch("apps.agent.services.runtime.worker.AuditEntry"),
        patch(
            "apps.agent.services.runtime.worker.generate_suggestions",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "apps.agent.services.runtime.worker.sync_title_from_checkpoint",
            new=title_sync_mock,
        ),
        patch("apps.agent.services.runtime.worker.schedule_run_cleanup", new_callable=AsyncMock),
    ):
        MockClient.return_value.get_family_ai_config = AsyncMock(
            return_value=ai_config_envelope
        )
        mock_pii.redact = MagicMock(side_effect=lambda ctx: ctx)

        await run_family_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id="family-1",
            user_id="user-1",
            thread_id="thread-1",
            graph_input={"messages": [{"role": "user", "content": "summarize my assets"}]},
            config={},
        )
        # Drain the fire-and-forget tasks created in the finally block.
        await asyncio.sleep(0.1)

    # Title sync is scheduled with positional (thread_id, family_id) plus kwargs
    # (ai_config, user_message, ai_response) for LLM title generation when the
    # checkpoint title is a [SKILL:chat] fallback.
    assert title_sync_mock.called, "sync_title_from_checkpoint was not invoked"
    assert title_sync_mock.call_args.args == ("thread-1", "family-1"), (
        f"expected (thread-1, family-1), got: {title_sync_mock.call_args.args}"
    )
