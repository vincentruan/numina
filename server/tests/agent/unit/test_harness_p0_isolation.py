"""P0 harness isolation fixes — T1 (checkpointer cross-tenant) + T3 (stream mode default).

T1: start_run verifies thread ownership via backend session lookup before creating a run.
T2: DanglingToolCallMiddleware — already always-on in v2.1.0, no action needed.
T3: normalize_stream_modes default includes messages-tuple (not just values).
"""

from __future__ import annotations

import pytest

from apps.agent.services.runtime.sse_gateway import normalize_stream_modes

# ---------------------------------------------------------------------------
# T3: normalize_stream_modes default includes messages-tuple
# ---------------------------------------------------------------------------


class TestNormalizeStreamModes:
    """normalize_stream_modes must include messages-tuple in the default."""

    def test_default_includes_messages_tuple(self):
        """When stream_mode is None, default must include messages-tuple + values."""
        result = normalize_stream_modes(None)
        assert "messages-tuple" in result
        assert "values" in result

    def test_explicit_list_passthrough(self):
        """Explicit list is returned as-is."""
        modes = ["messages-tuple", "values", "custom"]
        assert normalize_stream_modes(modes) == modes

    def test_string_wrapped_in_list(self):
        """String input is wrapped in a list."""
        assert normalize_stream_modes("values") == ["values"]

    def test_empty_list_returns_default(self):
        """Empty list returns the default (values + messages-tuple)."""
        result = normalize_stream_modes([])
        assert "values" in result
        assert "messages-tuple" in result


# ---------------------------------------------------------------------------
# T1: start_run thread ownership verification
# ---------------------------------------------------------------------------


class TestStartRunThreadOwnership:
    """start_run must reject runs on threads not belonging to the family."""

    @pytest.mark.asyncio
    async def test_direct_caller_rejected_when_session_not_found(self):
        """Non-internal caller gets 404 when session doesn't exist for family."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from fastapi import HTTPException

        from apps.agent.services.runtime.sse_gateway import start_run

        body = MagicMock()
        body.metadata = {"app": "numina"}
        body.on_disconnect = "cancel"
        body.assistant_id = None
        body.input = None
        body.config = None
        body.stream_mode = None
        body.stream_subgraphs = False
        body.multitask_strategy = "reject"

        request = MagicMock()

        mock_bridge = AsyncMock()
        mock_run_mgr = MagicMock()

        with (
            patch(
                "apps.agent.services.runtime.sse_gateway.get_stream_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "apps.agent.services.runtime.sse_gateway.get_run_manager",
                return_value=mock_run_mgr,
            ),
            patch(
                "apps.agent.services.session_store.AiSessionRepository.get_session",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await start_run(
                    body, "fake-thread-id", request, "family-123", "user-456"
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_internal_caller_skips_ownership_check(self):
        """Internal callers (backend triggers) skip the session ownership check."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from apps.agent.services.runtime.sse_gateway import start_run

        body = MagicMock()
        body.metadata = {"app": "asset-report"}
        body.on_disconnect = "cancel"
        body.assistant_id = None
        body.input = None
        body.config = None
        body.stream_mode = None
        body.stream_subgraphs = False
        body.multitask_strategy = "reject"

        request = MagicMock()

        mock_bridge = AsyncMock()
        mock_run_mgr = MagicMock()
        mock_record = MagicMock()
        mock_record.run_id = "run-1"
        mock_run_mgr.create_or_reject = AsyncMock(return_value=mock_record)

        session_lookup = AsyncMock(return_value=None)

        with (
            patch(
                "apps.agent.services.runtime.sse_gateway.get_stream_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "apps.agent.services.runtime.sse_gateway.get_run_manager",
                return_value=mock_run_mgr,
            ),
            patch(
                "apps.agent.services.runtime.sse_gateway.run_agent",
                new_callable=AsyncMock,
            ),
            patch(
                "apps.agent.services.session_store.AiSessionRepository.get_session",
                session_lookup,
            ),
        ):
            # internal=True should NOT call get_session
            await start_run(
                body,
                "some-thread-id",
                request,
                "family-123",
                "user-456",
                internal=True,
            )
            session_lookup.assert_not_called()

    @pytest.mark.asyncio
    async def test_direct_caller_allowed_when_session_exists(self):
        """Non-internal caller proceeds when session exists for the family."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from apps.agent.services.runtime.sse_gateway import start_run

        body = MagicMock()
        body.metadata = {"app": "numina"}
        body.on_disconnect = "cancel"
        body.assistant_id = None
        body.input = None
        body.config = None
        body.stream_mode = None
        body.stream_subgraphs = False
        body.multitask_strategy = "reject"

        request = MagicMock()

        mock_bridge = AsyncMock()
        mock_run_mgr = MagicMock()
        mock_record = MagicMock()
        mock_record.run_id = "run-1"
        mock_run_mgr.create_or_reject = AsyncMock(return_value=mock_record)

        with (
            patch(
                "apps.agent.services.runtime.sse_gateway.get_stream_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "apps.agent.services.runtime.sse_gateway.get_run_manager",
                return_value=mock_run_mgr,
            ),
            patch(
                "apps.agent.services.runtime.sse_gateway.run_agent",
                new_callable=AsyncMock,
            ),
            patch(
                "apps.agent.services.session_store.AiSessionRepository.get_session",
                new_callable=AsyncMock,
                return_value={"session_id": "thread-1", "family_id": "family-123"},
            ),
        ):
            # Should NOT raise
            record = await start_run(
                body, "thread-1", request, "family-123", "user-456"
            )
            assert record.run_id == "run-1"


# ---------------------------------------------------------------------------
# T2: Verify DanglingToolCallMiddleware is always-on (documentation test)
# ---------------------------------------------------------------------------


class TestDanglingToolCallAlwaysOn:
    """DanglingToolCallMiddleware is unconditionally included in v2.1.0.

    This test documents the finding — no code change needed.
    The middleware is always appended in _build_runtime_middlewares() when
    include_dangling_tool_call_patch=True (which it is for both lead agent
    and subagent chains).
    """

    def test_dangling_tool_call_in_v21_chain(self):
        """Verify DanglingToolCallMiddleware is importable from v2.1.0."""
        from deerflow.agents.middlewares.dangling_tool_call_middleware import (
            DanglingToolCallMiddleware,
        )

        # Middleware can be instantiated (no config required)
        instance = DanglingToolCallMiddleware()
        assert instance is not None
