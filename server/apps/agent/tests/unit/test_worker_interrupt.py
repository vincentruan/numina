"""Tests for run cancellation and cleanup scheduling in _run_numina_agent.

The ``interrupt()`` / ``type="interrupt"`` event path was removed: DeerFlow's
``ClarificationMiddleware`` intercepts ``ask_clarification`` before the tool
runs (returns ``Command(goto=END)``), so ``interrupt()`` never fires and no
interrupt custom event is ever emitted. Runs now reach ``interrupted`` status
only via user-initiated cancel (``abort_event``); cleanup is always scheduled.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from deerflow.runtime import RunStatus

from apps.agent.services.runtime.worker import _run_numina_agent


async def test_cleanup_called_for_cancelled_runs():
    """schedule_run_cleanup IS called when abort_event is set (cancelled)."""
    record = MagicMock()
    record.run_id = "run-3"
    record.thread_id = "thread-3"
    record.abort_event = asyncio.Event()
    record.abort_event.set()  # Set to simulate cancellation
    record.status = RunStatus.interrupted
    record.metadata = {"family_id": "family-3"}

    bridge = MagicMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()

    run_manager = MagicMock()
    run_manager.set_status = AsyncMock()

    stub_adapter = MagicMock()

    async def typed_stream_dispatch(*args, **kwargs):
        yield ("messages", {"type": "ai", "content": "partial response", "tool_calls": None})
        yield ("end", {})

    stub_adapter.typed_stream_dispatch = typed_stream_dispatch

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

    cleanup_mock = AsyncMock()

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
            new=AsyncMock(return_value=None),
        ),
        patch("apps.agent.services.runtime.worker.schedule_run_cleanup", new=cleanup_mock),
    ):
        MockClient.return_value.get_family_ai_config = AsyncMock(
            return_value=ai_config_envelope
        )
        mock_pii.redact = MagicMock(side_effect=lambda ctx: ctx)

        await _run_numina_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id="family-3",
            user_id="user-3",
            thread_id="thread-3",
            graph_input={"messages": [{"role": "user", "content": "test"}]},
            config={},
        )
        await asyncio.sleep(0.1)

    # Cleanup SHOULD be called for cancelled runs (abort_event set)
    assert cleanup_mock.called, (
        "schedule_run_cleanup should be called for cancelled runs (abort_event set)"
    )
