"""Tests for write_file tool-level progress events.

Covers the emitter ContextVar and the ``write_file_tool.func`` wrapper that
publishes ``tool.progress`` custom events. The wrapper is exercised through
LangChain's real sync tool dispatch so ``tool_call_id`` resolution is proven,
not stubbed.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from apps.agent.services.deerflow_adapter.sync_tool_patch import (
    _apply_write_progress_patch,
)
from apps.agent.services.deerflow_adapter.write_progress_context import (
    emit_write_progress,
    reset_write_progress_emitter,
    set_write_progress_emitter,
)

_WRITE_ARGS = {"path": "/mnt/user-data/workspace/report.md", "content": "hello"}


class _FakeRuntime:
    """Minimal stand-in for langgraph's ToolRuntime."""

    def __init__(self, tool_call_id: str | None = "call_1") -> None:
        self.tool_call_id = tool_call_id


@pytest.fixture
def recorder() -> Iterator[list[dict[str, Any]]]:
    """Install a recording emitter on the ContextVar, restoring it after."""
    events: list[dict[str, Any]] = []

    def _emit(
        status: str, path: str, size_bytes: int | None, tool_call_id: str
    ) -> None:
        events.append(
            {
                "status": status,
                "path": path,
                "size_bytes": size_bytes,
                "tool_call_id": tool_call_id,
            }
        )

    token = set_write_progress_emitter(_emit)
    try:
        yield events
    finally:
        reset_write_progress_emitter(token)


@pytest.fixture
def write_tool() -> Iterator[Any]:
    """Patch the real write_file tool with a stubbed body, then un-patch."""
    from deerflow.sandbox import tools as sandbox_tools

    tool = sandbox_tools.write_file_tool
    original = tool.func
    try:
        yield tool
    finally:
        tool.func = original


def _install_wrapper(tool: Any, body: Any) -> None:
    """Give *tool* a fresh body, then apply the production patch to it."""
    tool.func = body
    _apply_write_progress_patch()


class TestEmitterContextVar:
    def test_emit_is_noop_when_emitter_unset(self) -> None:
        """Without an emitter the helper returns quietly (non-pipeline callers)."""
        emit_write_progress("writing", "/tmp/x.md", None, "call_1")

    def test_emit_swallows_emitter_errors(self) -> None:
        """A failing emitter must not break the write itself."""

        def _boom(*_args: Any) -> None:
            raise RuntimeError("publish exploded")

        token = set_write_progress_emitter(_boom)
        try:
            emit_write_progress("writing", "/tmp/x.md", None, "call_1")
        finally:
            reset_write_progress_emitter(token)


class TestWriteProgressWrapper:
    def test_emits_writing_before_and_done_after(self, recorder, write_tool) -> None:
        """Successful write emits 'writing' then 'done' carrying bytes written."""
        observed: list[str] = []

        def _body(*_args: Any, **_kwargs: Any) -> str:
            observed.append("body ran")
            return "OK"

        _install_wrapper(write_tool, _body)
        result = write_tool.func(_FakeRuntime(), **_WRITE_ARGS)

        assert result == "OK"
        assert [e["status"] for e in recorder] == ["writing", "done"]
        assert recorder[0]["size_bytes"] is None
        assert recorder[1]["size_bytes"] == len("hello")
        assert all(e["path"] == _WRITE_ARGS["path"] for e in recorder)
        assert observed == ["body ran"]

    def test_emits_done_when_body_raises(self, recorder, write_tool) -> None:
        """The 'done' event is emitted from finally, even on an exception."""

        def _body(*_args: Any, **_kwargs: Any) -> str:
            raise ValueError("disk full")

        _install_wrapper(write_tool, _body)
        with pytest.raises(ValueError):
            write_tool.func(_FakeRuntime(), **_WRITE_ARGS)

        assert [e["status"] for e in recorder] == ["writing", "done"]
        assert recorder[1]["size_bytes"] is None

    def test_emits_done_without_size_on_tool_error_result(
        self, recorder, write_tool
    ) -> None:
        """A returned error string reports no byte count."""

        def _body(*_args: Any, **_kwargs: Any) -> str:
            return "Error: path rejected"

        _install_wrapper(write_tool, _body)
        write_tool.func(_FakeRuntime(), **_WRITE_ARGS)

        assert recorder[1]["status"] == "done"
        assert recorder[1]["size_bytes"] is None

    def test_wrapper_is_idempotent(self, recorder, write_tool) -> None:
        """Re-applying the patch does not stack a second wrapper."""

        def _body(*_args: Any, **_kwargs: Any) -> str:
            return "OK"

        _install_wrapper(write_tool, _body)
        first = write_tool.func
        _apply_write_progress_patch()

        assert write_tool.func is first

    def test_no_emitter_set_still_writes(self, write_tool) -> None:
        """Non-pipeline callers have no emitter and must be unaffected."""

        def _body(*_args: Any, **_kwargs: Any) -> str:
            return "OK"

        _install_wrapper(write_tool, _body)
        assert write_tool.func(_FakeRuntime(), **_WRITE_ARGS) == "OK"

    def test_read_file_is_not_wrapped(self) -> None:
        """Only write_file opts into progress; the sibling file tools stay bare."""
        from deerflow.sandbox import tools as sandbox_tools

        assert not getattr(
            sandbox_tools.read_file_tool.func, "_numina_write_progress", False
        )
        assert not getattr(
            sandbox_tools.str_replace_tool.func, "_numina_write_progress", False
        )


class TestRealToolNodeDispatch:
    def test_tool_call_id_flows_from_langgraph(self, recorder, write_tool) -> None:
        """tool_call_id comes from the injected runtime through real dispatch.

        Drives a compiled LangGraph through ToolNode so the id is resolved by
        LangChain rather than supplied by the test.
        """

        def _body(*_args: Any, **_kwargs: Any) -> str:
            return "OK"

        _install_wrapper(write_tool, _body)

        from langchain_core.messages import AIMessage
        from langgraph.graph import END, START, MessagesState, StateGraph
        from langgraph.prebuilt import ToolNode

        def _call_model(_state: Any) -> dict[str, Any]:
            return {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "write_file",
                                "args": dict(_WRITE_ARGS),
                                "id": "call_from_graph",
                            }
                        ],
                    )
                ]
            }

        graph = StateGraph(MessagesState)
        graph.add_node("model", _call_model)
        graph.add_node("tools", ToolNode([write_tool]))
        graph.add_edge(START, "model")
        graph.add_edge("model", "tools")
        graph.add_edge("tools", END)

        for _ in graph.compile().stream({"messages": []}):
            pass

        assert len(recorder) == 2
        assert {e["tool_call_id"] for e in recorder} == {"call_from_graph"}


class TestRunPipelineEmitter:
    """The pipeline installs an emitter that publishes through its bridge."""

    @pytest.fixture(autouse=True)
    def _mock_mcp_context_assert(self) -> Iterator[None]:
        """The pipeline asserts MCP context completeness on entry.

        These tests exercise the emitter, not sandbox ContextVar propagation,
        so the guard is stubbed the same way ``test_run_pipeline`` does.
        """
        from unittest.mock import patch

        with patch(
            "apps.agent.services.runtime.sandbox_provider.assert_mcp_context_complete",
        ):
            yield

    @staticmethod
    def _enter_patches() -> Any:
        from unittest.mock import AsyncMock, MagicMock, patch

        return (
            patch("apps.agent.services.runtime.run_pipeline.BackendClient"),
            patch(
                "apps.agent.services.runtime.run_pipeline._resolve_numina_mcp_servers",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.create_family_adapter",
                return_value=MagicMock(),
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.set_active_skill",
                return_value="token-1",
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.reset_active_skill",
                MagicMock(),
            ),
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        )

    @pytest.mark.asyncio
    async def test_write_progress_publishes_custom_event(self) -> None:
        """A write reports 'writing' then 'done' as tool.progress frames."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

        from apps.agent.services.deerflow_adapter.write_progress_context import (
            emit_write_progress,
        )
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = MagicMock(spec=RunRecord)
        record.run_id = "run-1"
        record.status = RunStatus.running
        record.abort_event = asyncio.Event()
        record.metadata = {"app": "asset-report"}

        bridge = MagicMock(spec=StreamBridge)
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        p_backend, p_mcp, p_adapt, p_set, p_reset, p_reg = self._enter_patches()
        with p_backend as backend_cls, p_mcp, p_adapt, p_set, p_reset, p_reg:
            backend_cls.return_value.get_family_ai_config = AsyncMock(
                return_value={"providers": [{"config_id": "c", "is_active": True}]}
            )
            async with RunPipeline(
                app_name="asset-report",
                family_id="fam-1",
                user_id="u1",
                thread_id="th-1",
                record=record,
                bridge=bridge,
                run_manager=MagicMock(spec=RunManager),
            ):
                emit_write_progress("writing", "/mnt/x.md", None, "call_9")
                emit_write_progress("done", "/mnt/x.md", 5, "call_9")
                await asyncio.sleep(0)  # let scheduled publishes run

        frames = [
            call.args
            for call in bridge.publish.await_args_list
            if call.args[1] == "custom"
        ]
        assert [f[2]["status"] for f in frames] == ["writing", "done"]
        assert frames[0][2]["tool_id"] == "call_9"
        assert frames[0][2]["type"] == "tool.progress"
        assert "size_bytes" not in frames[0][2]  # omitted when unknown
        assert frames[1][2]["size_bytes"] == 5
        assert all("progress_message" in f[2] for f in frames)

    @pytest.mark.asyncio
    async def test_emitter_dropped_after_exit(self) -> None:
        """The ContextVar is reset so the next run does not inherit it."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

        from apps.agent.services.deerflow_adapter.write_progress_context import (
            get_write_progress_emitter,
        )
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = MagicMock(spec=RunRecord)
        record.run_id = "run-2"
        record.status = RunStatus.running
        record.abort_event = asyncio.Event()
        record.metadata = {"app": "asset-report"}

        bridge = MagicMock(spec=StreamBridge)
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        p_backend, p_mcp, p_adapt, p_set, p_reset, p_reg = self._enter_patches()
        with p_backend as backend_cls, p_mcp, p_adapt, p_set, p_reset, p_reg:
            backend_cls.return_value.get_family_ai_config = AsyncMock(
                return_value={"providers": [{"config_id": "c", "is_active": True}]}
            )
            async with RunPipeline(
                app_name="asset-report",
                family_id="fam-1",
                user_id="u1",
                thread_id="th-1",
                record=record,
                bridge=bridge,
                run_manager=MagicMock(spec=RunManager),
            ):
                assert get_write_progress_emitter() is not None

        assert get_write_progress_emitter() is None
