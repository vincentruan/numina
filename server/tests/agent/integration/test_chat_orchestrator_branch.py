"""Integration test: orchestrator dispatches chat via ChatAdapter, not _build_context."""
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from apps.agent.services.orchestrator import Orchestrator
from apps.agent.services.deerflow_adapter.adapter import StreamChunk


@pytest.fixture
def mock_orchestrator():
    """Create orchestrator with mocked ChatAdapter."""
    orchestrator = Orchestrator()
    # Mock ChatAdapter.stream to return fake chunks
    async def fake_stream(**kwargs):
        yield StreamChunk(type="text", content="answer")
    orchestrator._chat_adapter = MagicMock()
    orchestrator._chat_adapter.stream = fake_stream
    return orchestrator


@pytest.mark.asyncio
async def test_chat_branch_uses_chat_adapter_not_build_context(mock_orchestrator):
    """chat capability must skip _build_context and route via ChatAdapter."""
    chat_called = {"called": False, "web_search": None}

    async def fake_stream(**kwargs):
        chat_called["called"] = True
        chat_called["web_search"] = kwargs.get("web_search")
        yield StreamChunk(type="text", content="answer")

    mock_orchestrator._chat_adapter.stream = fake_stream

    build_context_called = {"called": False}

    async def fake_build_context(*args, **kwargs):
        build_context_called["called"] = True
        from apps.agent.schemas.context import FamilyContext
        return FamilyContext(family_id="100")

    # Patch _build_context on orchestrator
    mock_orchestrator._build_context = fake_build_context

    # Mock BackendClient, config fetch, and session_journal
    with patch("apps.agent.services.orchestrator.session_journal") as mock_journal, \
         patch("apps.agent.services.orchestrator.BackendClient") as bc_cls:
        mock_journal.write_session_start = MagicMock()
        mock_journal.write_user_message = MagicMock()
        mock_journal.write_assistant_message = MagicMock()
        mock_journal.write_session_end = MagicMock()
        bc = bc_cls.return_value
        bc.get_family_ai_configs = AsyncMock(return_value={
            "ai_enabled": True,
            "allowed_capabilities": ["chat"],
            "admin_only_capabilities": [],
            "member_role": "admin",
            "providers": [{
                "config_id": "cfg1",
                "ai_model_id": "gpt-4",
                "ai_provider": "openai",
                "api_key": "k",
                "model_1_capabilities": ["text_generation"],
            }],
        })
        bc.reset_circuit_success = AsyncMock()
        bc.report_circuit_event = AsyncMock()

        chunks = []
        async for line in mock_orchestrator.stream_dispatch_events(
            capability="chat",
            family_id="100",
            task_id="t-1",
            user_id="u-1",
            thread_id="th-1",
            free_text="hi",
            enable_thinking_override=False,
            web_search=True,
        ):
            chunks.append(line)

    assert chat_called["called"] is True
    assert chat_called["web_search"] is True
    assert build_context_called["called"] is False, "chat should NOT call _build_context"
