"""Tests for interrupt event detection in run_family_agent.

Task 4: Worker must detect interrupt events from the adapter stream and set
run status to ``interrupted`` (not ``cancelled``), and skip the 300s cleanup GC
so the checkpoint survives for resume after human input.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from deerflow.runtime import RunStatus

from apps.agent.services.runtime.worker import run_family_agent


async def test_interrupt_event_sets_status_to_interrupted():
    """Interrupt event in stream sets status to interrupted, not cancelled."""
    record = MagicMock()
    record.run_id = "run-1"
    record.thread_id = "thread-1"
    record.abort_event = asyncio.Event()  # not set
    record.status = RunStatus.interrupted
    record.metadata = {"family_id": "family-1"}

    bridge = MagicMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()

    run_manager = MagicMock()
    run_manager.set_status = AsyncMock()

    stub_adapter = MagicMock()

    async def typed_stream_dispatch(*args, **kwargs):
        yield ("messages", {"type": "ai", "content": "I need clarification", "tool_calls": None})
        yield ("custom", {"type": "interrupt", "question": "Which account?"})
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
            graph_input={"messages": [{"role": "user", "content": "show my assets"}]},
            config={},
        )
        await asyncio.sleep(0.1)

    # Verify status set to interrupted
    status_calls = [call for call in run_manager.set_status.call_args_list]
    final_status_call = status_calls[-1]
    assert final_status_call.args[1] == RunStatus.interrupted, (
        f"Expected RunStatus.interrupted, got {final_status_call.args[1]}"
    )


async def test_cleanup_skipped_for_interrupted_runs():
    """schedule_run_cleanup NOT called when interrupt event detected."""
    record = MagicMock()
    record.run_id = "run-2"
    record.thread_id = "thread-2"
    record.abort_event = asyncio.Event()
    record.status = RunStatus.interrupted
    record.metadata = {"family_id": "family-2"}

    bridge = MagicMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()

    run_manager = MagicMock()
    run_manager.set_status = AsyncMock()

    stub_adapter = MagicMock()

    async def typed_stream_dispatch(*args, **kwargs):
        yield ("custom", {"type": "interrupt", "question": "Which one?"})
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

        await run_family_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id="family-2",
            user_id="user-2",
            thread_id="thread-2",
            graph_input={"messages": [{"role": "user", "content": "test"}]},
            config={},
        )
        await asyncio.sleep(0.1)

    # Cleanup should NOT be called for interrupted runs
    assert not cleanup_mock.called, (
        "schedule_run_cleanup should not be called for interrupted runs"
    )


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

        await run_family_agent(
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
