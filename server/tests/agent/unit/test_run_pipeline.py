"""Layered unit tests for RunPipeline (F2 strategy).

Each test verifies one scaffolding behavior in isolation, mocking the other
steps. The interface under test is RunPipeline's __aenter__ / __aexit__ /
run_skill / properties.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_mcp_context_assert():
    """Mock assert_mcp_context_complete so tests don't need to set up
    sandbox ContextVars (set_family_sandbox_context, etc.)."""
    with patch(
        "apps.agent.services.runtime.sandbox_provider.assert_mcp_context_complete",
    ):
        yield


def _make_record(run_id: str = "run-1") -> RunRecord:
    """Build a minimal RunRecord for testing."""
    record = MagicMock(spec=RunRecord)
    record.run_id = run_id
    record.status = RunStatus.running
    record.abort_event = asyncio.Event()
    record.metadata = {"app": "finance-coach"}
    return record


def _make_bridge() -> MagicMock:
    bridge = MagicMock(spec=StreamBridge)
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()
    return bridge


def _make_run_manager() -> MagicMock:
    rm = MagicMock(spec=RunManager)
    rm.set_status = AsyncMock()
    return rm


def _mock_config(providers: list[dict] | None = None) -> dict:
    """Build a mock AI config response."""
    if providers is None:
        providers = [
            {"config_id": "cfg-1", "is_active": True, "circuit_state": "closed"}
        ]
    return {"providers": providers}


# ---------------------------------------------------------------------------
# __aenter__ tests
# ---------------------------------------------------------------------------


class TestRunPipelineEnter:
    """Tests for RunPipeline.__aenter__ (scaffolding setup)."""

    @pytest.mark.asyncio
    async def test_sets_status_running_and_publishes_metadata(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            async with RunPipeline(
                app_name="finance-coach",
                family_id="fam-1",
                user_id="user-1",
                thread_id="thread-1",
                record=record,
                bridge=bridge,
                run_manager=run_manager,
            ):
                pass

        # Verify set_status(running) was called
        run_manager.set_status.assert_any_await("run-1", RunStatus.running)
        # Verify metadata was published
        bridge.publish.assert_any_await(
            "run-1", "metadata", {"run_id": "run-1", "thread_id": "thread-1"}
        )

    @pytest.mark.asyncio
    async def test_raises_when_no_providers(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value={"providers": []})
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="未配置 AI 供应商"):
                async with RunPipeline(
                    app_name="finance-coach",
                    family_id="fam-1",
                    user_id="user-1",
                    thread_id="thread-1",
                    record=record,
                    bridge=bridge,
                    run_manager=run_manager,
                ):
                    pass

    @pytest.mark.asyncio
    async def test_raises_when_all_providers_circuit_open(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        # All providers have circuit_state="open"
        providers = [
            {"config_id": "cfg-1", "is_active": True, "circuit_state": "open"},
            {"config_id": "cfg-2", "is_active": True, "circuit_state": "open"},
        ]

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(
                return_value=_mock_config(providers)
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="所有 provider 均已熔断"):
                async with RunPipeline(
                    app_name="finance-coach",
                    family_id="fam-1",
                    user_id="user-1",
                    thread_id="thread-1",
                    record=record,
                    bridge=bridge,
                    run_manager=run_manager,
                ):
                    pass

    @pytest.mark.asyncio
    async def test_sets_active_skill_on_enter(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        mock_set_active_skill = MagicMock(return_value="token-xyz")

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
                mock_set_active_skill,
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.reset_active_skill",
                MagicMock(),
            ),
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            async with RunPipeline(
                app_name="finance-coach",
                family_id="fam-1",
                user_id="user-1",
                thread_id="thread-1",
                record=record,
                bridge=bridge,
                run_manager=run_manager,
            ):
                pass

        mock_set_active_skill.assert_called_once_with("finance-coach")


# ---------------------------------------------------------------------------
# __aexit__ tests
# ---------------------------------------------------------------------------


class TestRunPipelineExit:
    """Tests for RunPipeline.__aexit__ (cleanup + terminal frames)."""

    @pytest.mark.asyncio
    async def test_resets_active_skill_on_success(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        record.status = RunStatus.success
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        mock_reset_active_skill = MagicMock()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
                mock_reset_active_skill,
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.audit_logger"
            ) as mock_audit,
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            async with RunPipeline(
                app_name="finance-coach",
                family_id="fam-1",
                user_id="user-1",
                thread_id="thread-1",
                record=record,
                bridge=bridge,
                run_manager=run_manager,
            ):
                pass

        mock_reset_active_skill.assert_called_once_with("token-1")
        # Verify audit log was called
        mock_audit.log_call.assert_called_once()
        # Verify end frame was published
        bridge.publish.assert_any_await("run-1", "end", {"status": "complete"})

    @pytest.mark.asyncio
    async def test_publishes_error_frame_on_exception(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
                "apps.agent.services.runtime.run_pipeline._fire_and_forget_circuit_report"
            ) as mock_circuit,
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="test error"):
                async with RunPipeline(
                    app_name="finance-coach",
                    family_id="fam-1",
                    user_id="user-1",
                    thread_id="thread-1",
                    record=record,
                    bridge=bridge,
                    run_manager=run_manager,
                ):
                    raise ValueError("test error")

        # Verify error frame was published
        bridge.publish.assert_any_await(
            "run-1", "error", {"message": "test error", "name": "ValueError"}
        )
        # Verify circuit report was scheduled
        mock_circuit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reraises_cancelled_error(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            with pytest.raises(asyncio.CancelledError):
                async with RunPipeline(
                    app_name="finance-coach",
                    family_id="fam-1",
                    user_id="user-1",
                    thread_id="thread-1",
                    record=record,
                    bridge=bridge,
                    run_manager=run_manager,
                ):
                    raise asyncio.CancelledError()

    @pytest.mark.asyncio
    async def test_cancelled_error_still_runs_audit_and_end_frame(self):
        """Critical #1 fix: CancelledError path must not skip audit/end/cleanup."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
                "apps.agent.services.runtime.run_pipeline.audit_logger"
            ) as mock_audit,
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            with pytest.raises(asyncio.CancelledError):
                async with RunPipeline(
                    app_name="finance-coach",
                    family_id="fam-1",
                    user_id="user-1",
                    thread_id="thread-1",
                    record=record,
                    bridge=bridge,
                    run_manager=run_manager,
                ):
                    raise asyncio.CancelledError()

        # Verify audit log was called even on cancellation
        mock_audit.log_call.assert_called_once()
        # Verify end frame was published with interrupted status
        bridge.publish.assert_any_await("run-1", "end", {"status": "interrupted"})
        # Verify run_manager was set to interrupted
        run_manager.set_status.assert_any_await("run-1", RunStatus.interrupted)

    @pytest.mark.asyncio
    async def test_set_error_is_state_only_and_publishes_in_aexit(self):
        """Critical #2 fix: set_error() stores state; __aexit__ publishes error frame."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
                "apps.agent.services.runtime.run_pipeline.audit_logger"
            ) as mock_audit,
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            async with RunPipeline(
                app_name="asset-report",
                family_id="fam-1",
                user_id="user-1",
                thread_id="thread-1",
                record=record,
                bridge=bridge,
                run_manager=run_manager,
            ) as p:
                # Simulate post-stream error (like asset-report persist failure)
                p.set_error("结构化结果保存失败", error_type="PersistError")
                # set_error should be state-only — no tasks scheduled yet
                assert p._post_stream_error_message == "结构化结果保存失败"
                assert p._error_type == "PersistError"
                assert p._completion_status == "error"
                assert p._success is False

        # After __aexit__: error frame should be published
        bridge.publish.assert_any_await(
            "run-1",
            "error",
            {"message": "结构化结果保存失败", "name": "PersistError"},
        )
        # Run status should be set to error
        run_manager.set_status.assert_any_await(
            "run-1", RunStatus.error, error="结构化结果保存失败"
        )
        # Audit log should reflect failure
        mock_audit.log_call.assert_called_once()
        audit_entry = mock_audit.log_call.call_args[0][0]
        assert audit_entry.success is False
        assert audit_entry.error_type == "PersistError"
        # End frame should have error status
        bridge.publish.assert_any_await("run-1", "end", {"status": "error"})


# ---------------------------------------------------------------------------
# run_skill tests
# ---------------------------------------------------------------------------


class TestRunPipelineRunSkill:
    """Tests for RunPipeline.run_skill (streaming + collection)."""

    @pytest.mark.asyncio
    async def test_collects_ai_response_parts(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        # Mock adapter.typed_stream_dispatch to yield some frames
        async def mock_stream(*args, **kwargs):
            yield "messages", {"type": "ai", "content": "Hello "}
            yield "messages", {"type": "ai", "content": "world"}
            yield "end", {}

        mock_adapter = MagicMock()
        mock_adapter.typed_stream_dispatch = mock_stream

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
            patch(
                "apps.agent.services.runtime.run_pipeline._resolve_numina_mcp_servers",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.create_family_adapter",
                return_value=mock_adapter,
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.set_active_skill",
                return_value="token-1",
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.reset_active_skill",
                MagicMock(),
            ),
            patch("apps.agent.services.runtime.run_pipeline.pii_redactor") as mock_pii,
            patch("apps.agent.services.runtime.run_pipeline.audit_logger"),
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client
            mock_pii.redact.return_value = MagicMock()

            async with RunPipeline(
                app_name="finance-coach",
                family_id="fam-1",
                user_id="user-1",
                thread_id="thread-1",
                record=record,
                bridge=bridge,
                run_manager=run_manager,
            ) as p:
                await p.run_skill("test message")
                assert p.ai_text == "Hello world"
                assert p.ai_response_parts == ["Hello ", "world"]

    @pytest.mark.asyncio
    async def test_captures_cumulative_usage(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        async def mock_stream(*args, **kwargs):
            yield "messages", {"type": "ai", "content": "test"}
            yield (
                "end",
                {
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                    }
                },
            )

        mock_adapter = MagicMock()
        mock_adapter.typed_stream_dispatch = mock_stream

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
            patch(
                "apps.agent.services.runtime.run_pipeline._resolve_numina_mcp_servers",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.create_family_adapter",
                return_value=mock_adapter,
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.set_active_skill",
                return_value="token-1",
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.reset_active_skill",
                MagicMock(),
            ),
            patch("apps.agent.services.runtime.run_pipeline.pii_redactor"),
            patch("apps.agent.services.runtime.run_pipeline.audit_logger"),
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            async with RunPipeline(
                app_name="finance-coach",
                family_id="fam-1",
                user_id="user-1",
                thread_id="thread-1",
                record=record,
                bridge=bridge,
                run_manager=run_manager,
            ) as p:
                await p.run_skill("test message")
                assert p.cumulative_usage == {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                }


# ---------------------------------------------------------------------------
# Properties tests
# ---------------------------------------------------------------------------


class TestRunPipelineProperties:
    """Tests for RunPipeline properties."""

    @pytest.mark.asyncio
    async def test_completion_status_defaults_to_error(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            try:
                async with RunPipeline(
                    app_name="finance-coach",
                    family_id="fam-1",
                    user_id="user-1",
                    thread_id="thread-1",
                    record=record,
                    bridge=bridge,
                    run_manager=run_manager,
                ) as p:
                    # Before exception, status is still "error" (default)
                    assert p.completion_status == "error"
                    raise RuntimeError("test")
            except RuntimeError:
                pass

    @pytest.mark.asyncio
    async def test_completion_status_is_complete_on_success(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        record.status = RunStatus.success
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
            patch("apps.agent.services.runtime.run_pipeline.audit_logger"),
            patch(
                "apps.agent.services.agent_registry.get_agent_registry",
                return_value=MagicMock(get=AsyncMock(return_value=None)),
            ),
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            async with RunPipeline(
                app_name="finance-coach",
                family_id="fam-1",
                user_id="user-1",
                thread_id="thread-1",
                record=record,
                bridge=bridge,
                run_manager=run_manager,
            ) as p:
                pass

        # After successful exit, status is "complete"
        assert p.completion_status == "complete"

    @pytest.mark.asyncio
    async def test_ai_text_concatenates_parts(self):
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient"
            ) as mock_client_cls,
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
        ):
            mock_client = AsyncMock()
            mock_client.get_family_ai_config = AsyncMock(return_value=_mock_config())
            mock_client_cls.return_value = mock_client

            try:
                async with RunPipeline(
                    app_name="finance-coach",
                    family_id="fam-1",
                    user_id="user-1",
                    thread_id="thread-1",
                    record=record,
                    bridge=bridge,
                    run_manager=run_manager,
                ) as p:
                    # Manually populate ai_response_parts
                    p.ai_response_parts = ["Part 1", " Part 2", " Part 3"]
                    assert p.ai_text == "Part 1 Part 2 Part 3"
                    raise RuntimeError("test")
            except RuntimeError:
                pass
