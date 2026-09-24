"""Tests for the config-driven simple-app runner in worker.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSimpleAppConfig:
    """Verify the _SimpleAppConfig registry has expected entries and values."""

    def test_simple_apps_registry_has_three_entries(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        assert set(_SIMPLE_APPS.keys()) == {
            "dashboard-narrative",
            "literacy-weekly-report",
            "learning-tutor",
        }

    def test_dashboard_narrative_config(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["dashboard-narrative"]
        assert cfg.skill_name == "dashboard-narrative"
        assert cfg.enable_thinking is True
        assert cfg.enable_reasoning_delta is True
        assert cfg.timeout_seconds == 60
        assert cfg.mcp_servers == []
        assert cfg.memory_enabled is True
        assert cfg.result_event_type == "dashboard_narrative.result"
        assert cfg.result_builder is not None

    def test_literacy_weekly_report_config(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["literacy-weekly-report"]
        assert cfg.skill_name == "literacy-weekly-report"
        assert cfg.enable_thinking is True
        assert cfg.enable_reasoning_delta is True
        assert cfg.timeout_seconds == 120
        assert cfg.mcp_servers is None  # default MCP resolution
        assert cfg.memory_enabled is True
        assert cfg.result_event_type == "literacy_weekly_report.result"

    def test_learning_tutor_config(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["learning-tutor"]
        assert cfg.skill_name == "learning-tutor"
        assert cfg.enable_thinking is False
        assert cfg.enable_reasoning_delta is False
        assert cfg.memory_enabled is False
        assert cfg.result_event_type == ""  # no result event
        assert cfg.result_builder is None

    def test_result_builder_dashboard_narrative(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["dashboard-narrative"]
        payload = cfg.result_builder("narrative text", "thinking text")
        assert payload == {"narrative": "narrative text", "thinking": "thinking text"}

    def test_result_builder_literacy_report(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["literacy-weekly-report"]
        payload = cfg.result_builder("report text", "thinking text")
        assert payload == {"report": "report text", "thinking": "thinking text"}


class TestRunnersDict:
    """Verify the _RUNNERS dispatch dict covers complex apps."""

    def test_runners_dict_has_five_complex_apps(self):
        from apps.agent.services.runtime.worker import _RUNNERS

        assert set(_RUNNERS.keys()) == {
            "asset-report",
            "import-parse",
            "finance-coach",
            "wish-advice",
            "numina",
        }

    def test_simple_and_complex_cover_all_known_apps(self):
        from apps.agent.services.runtime.worker import _RUNNERS, _SIMPLE_APPS

        all_apps = set(_SIMPLE_APPS.keys()) | set(_RUNNERS.keys())
        expected = {
            "numina",
            "asset-report",
            "import-parse",
            "finance-coach",
            "wish-advice",
            "dashboard-narrative",
            "literacy-weekly-report",
            "learning-tutor",
        }
        assert all_apps == expected


class TestRunSimpleApp:
    """Verify the generic runner constructs RunPipeline correctly."""

    @pytest.fixture
    def mock_record(self):
        record = MagicMock()
        record.metadata = {"language": "zh"}
        record.run_id = "test-run-id"
        return record

    @pytest.fixture
    def mock_deps(self):
        bridge = AsyncMock()
        run_manager = AsyncMock()
        return bridge, run_manager

    async def test_dispatch_routes_simple_app_to_generic_runner(self, mock_deps):
        """run_agent should route simple apps to _run_simple_app."""
        from apps.agent.services.runtime.worker import run_agent

        bridge, run_manager = mock_deps
        record = MagicMock()
        record.metadata = {"app": "dashboard-narrative", "language": "zh"}
        record.run_id = "test-run-id"

        with (
            patch(
                "apps.agent.services.runtime.worker._run_simple_app",
                new_callable=AsyncMock,
            ) as mock_run,
            patch(
                "apps.agent.services.runtime.worker.set_family_sandbox_context",
            ),
            patch(
                "apps.agent.services.runtime.worker.reset_family_sandbox_context",
            ),
        ):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )
            mock_run.assert_awaited_once()
            cfg_arg = mock_run.call_args.args[0]
            assert cfg_arg.app_name == "dashboard-narrative"

    async def test_dispatch_routes_complex_app_to_runners_dict(self, mock_deps):
        """run_agent should route complex apps (e.g. asset-report) through _RUNNERS."""
        from apps.agent.services.runtime.worker import (
            _RUNNERS,
            _run_asset_report_agent,
        )

        # Verify _RUNNERS dict maps to the actual function objects
        assert _RUNNERS["asset-report"] is _run_asset_report_agent
        assert _RUNNERS["numina"] is not None  # _run_numina_agent exists

    async def test_unknown_app_publishes_error(self, mock_deps):
        """run_agent should publish error frame for unknown app names."""
        from apps.agent.services.runtime.worker import run_agent

        bridge, run_manager = mock_deps
        record = MagicMock()
        record.metadata = {"app": "nonexistent-app"}
        record.run_id = "test-run-id"

        with (
            patch(
                "apps.agent.services.runtime.worker.set_family_sandbox_context",
            ),
            patch(
                "apps.agent.services.runtime.worker.reset_family_sandbox_context",
            ),
        ):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )
        # Verify error status was set (proves ValueError was caught)
        run_manager.set_status.assert_called_once()
        call_args = run_manager.set_status.call_args
        assert call_args.args[1].value == "error"  # RunStatus.error

    async def test_run_simple_app_passes_config_to_pipeline(
        self, mock_record, mock_deps
    ):
        """_run_simple_app should construct RunPipeline with config params."""
        from apps.agent.services.runtime.worker import (
            _SIMPLE_APPS,
            _run_simple_app,
        )

        bridge, run_manager = mock_deps
        cfg = _SIMPLE_APPS["dashboard-narrative"]

        mock_pipeline = AsyncMock()
        mock_pipeline.run_skill = AsyncMock()
        mock_pipeline.ai_text = "test narrative"
        mock_pipeline.thinking_text = "test thinking"
        # async with mock_pipeline as p: → p must be mock_pipeline
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.agent.services.runtime.run_pipeline.RunPipeline",
        ) as mock_rp:
            mock_rp.return_value = mock_pipeline
            await _run_simple_app(
                cfg,
                bridge=bridge,
                run_manager=run_manager,
                record=mock_record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )

        mock_pipeline.run_skill.assert_awaited_once()
        call_kwargs = mock_pipeline.run_skill.call_args
        assert call_kwargs.kwargs.get("enable_reasoning_delta") is True

    async def test_run_simple_app_publishes_result_event_for_dashboard(
        self, mock_record, mock_deps
    ):
        """dashboard-narrative should publish dashboard_narrative.result event."""
        from apps.agent.services.runtime.worker import (
            _SIMPLE_APPS,
            _run_simple_app,
        )

        bridge, run_manager = mock_deps
        cfg = _SIMPLE_APPS["dashboard-narrative"]

        mock_pipeline = AsyncMock()
        mock_pipeline.run_skill = AsyncMock()
        mock_pipeline.ai_text = "narrative text"
        mock_pipeline.thinking_text = "thinking text"
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.agent.services.runtime.run_pipeline.RunPipeline",
        ) as mock_rp:
            mock_rp.return_value = mock_pipeline
            await _run_simple_app(
                cfg,
                bridge=bridge,
                run_manager=run_manager,
                record=mock_record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )

        # Verify bridge.publish was called with result event
        # bridge.publish(run_id, channel, data) — data dict is args[2]
        publish_calls = [
            c
            for c in bridge.publish.call_args_list
            if len(c.args) >= 3
            and isinstance(c.args[2], dict)
            and c.args[2].get("type") == "dashboard_narrative.result"
        ]
        assert len(publish_calls) == 1
        payload = publish_calls[0].args[2]["payload"]
        assert payload == {
            "narrative": "narrative text",
            "thinking": "thinking text",
        }

    async def test_run_simple_app_no_result_event_for_learning_tutor(
        self, mock_record, mock_deps
    ):
        """learning-tutor should NOT publish a result event."""
        from apps.agent.services.runtime.worker import (
            _SIMPLE_APPS,
            _run_simple_app,
        )

        bridge, run_manager = mock_deps
        cfg = _SIMPLE_APPS["learning-tutor"]

        mock_pipeline = AsyncMock()
        mock_pipeline.run_skill = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "apps.agent.services.runtime.run_pipeline.RunPipeline",
        ) as mock_rp:
            mock_rp.return_value = mock_pipeline
            await _run_simple_app(
                cfg,
                bridge=bridge,
                run_manager=run_manager,
                record=mock_record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )

        # No custom result event should be published
        custom_publishes = [
            c
            for c in bridge.publish.call_args_list
            if len(c.args) >= 3
            and isinstance(c.args[2], dict)
            and c.args[2].get("type", "").endswith(".result")
        ]
        assert len(custom_publishes) == 0
