"""Integration smoke tests for the new Gateway path in agent_dispatch.py."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.path_manager import PathManager


@pytest.fixture
def tmp_data_root(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def pm(tmp_data_root):
    return PathManager(data_root=tmp_data_root)


@pytest.fixture
def sample_agent_config():
    return {
        "agent_name": "asset-health-advisor",
        "soul_md": "You are a professional asset advisor.",
        "skills": ["family-asset-checkup"],
        "tool_groups": [],
        "model": None,
        "subagent_enabled": False,
        "is_enabled": True,
    }


@pytest.fixture
def sample_ai_config():
    return {
        "ai_enabled": True,
        "providers": [
            {
                "config_id": "cfg-001",
                "ai_provider": "anthropic",
                "ai_model_id": "claude-sonnet-4-6",
                "api_key": "sk-test-key",
                "model_1_capabilities": ["text_generation", "deep_thinking"],
            }
        ],
    }


async def aiter(items):
    for item in items:
        yield item


def _mock_client_instance(sample_agent_config, sample_ai_config):
    """Create a mock BackendClient instance with all required async methods."""
    instance = MagicMock()
    instance.get_agent_config = AsyncMock(return_value=sample_agent_config)
    instance.get_family_ai_config = AsyncMock(return_value=sample_ai_config)
    instance.get_enabled_skills = AsyncMock(return_value=[])
    instance.get_enabled_mcp_servers = AsyncMock(return_value=[])
    return instance


class TestStreamAgentDispatchGateway:
    async def test_emits_phase_connecting_event(self, pm, sample_agent_config, sample_ai_config):
        """First yielded event must be phase.connecting."""
        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
        ):
            MockClient.return_value = _mock_client_instance(sample_agent_config, sample_ai_config)
            mock_select.return_value = (
                sample_ai_config["providers"][0], "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            mock_graph = MagicMock()
            mock_graph.astream = MagicMock(return_value=aiter([]))

            with patch("apps.agent.services.agent_dispatch.make_lead_agent", mock_graph):
                from apps.agent.services.agent_dispatch import stream_agent_dispatch
                events = []
                async for line in stream_agent_dispatch(
                    agent_id=1, family_id="12345678901234567",
                    user_id="12345678901234568",
                    thread_id=None, message="测试消息",
                ):
                    events.append(json.loads(line.strip()))

        assert len(events) >= 1
        assert events[0]["type"] == "phase.connecting"

    async def test_emits_error_when_agent_disabled(self, pm, sample_ai_config):
        """Disabled agent must yield capability.error event."""
        disabled_config = {"agent_name": "disabled-agent", "is_enabled": False}
        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
        ):
            instance = MagicMock()
            instance.get_agent_config = AsyncMock(return_value=disabled_config)
            MockClient.return_value = instance

            from apps.agent.services.agent_dispatch import stream_agent_dispatch
            events = []
            async for line in stream_agent_dispatch(
                agent_id=1, family_id="12345678901234567",
                user_id="12345678901234568",
                thread_id=None, message="测试消息",
            ):
                events.append(json.loads(line.strip()))

            error_events = [e for e in events if e["type"] == "capability.error"]
            assert len(error_events) == 1
            assert "禁用" in error_events[0]["error"]["message"]

    async def test_passes_app_config_to_make_lead_agent(self, pm, sample_agent_config, sample_ai_config):
        """make_lead_agent must receive RunnableConfig with app_config in configurable."""
        captured_config = {}

        def capture_make_lead_agent(config):
            captured_config.update(config)
            mock_graph = MagicMock()
            mock_graph.astream = MagicMock(return_value=aiter([]))
            return mock_graph

        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
            patch("apps.agent.services.agent_dispatch.make_lead_agent", side_effect=capture_make_lead_agent),
        ):
            MockClient.return_value = _mock_client_instance(sample_agent_config, sample_ai_config)
            mock_select.return_value = (
                sample_ai_config["providers"][0], "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            from apps.agent.services.agent_dispatch import stream_agent_dispatch
            async for _ in stream_agent_dispatch(
                agent_id=1, family_id="12345678901234567",
                user_id="12345678901234568",
                thread_id=None, message="测试消息",
            ):
                pass

        assert "configurable" in captured_config
        configurable = captured_config["configurable"]
        assert "app_config" in configurable
        assert "thread_id" in configurable

    async def test_uses_provided_thread_id(self, pm, sample_agent_config, sample_ai_config):
        """When thread_id is provided, it must be used (not generated)."""
        expected_tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        captured_config = {}

        def capture_make_lead_agent(config):
            captured_config.update(config)
            mock_graph = MagicMock()
            mock_graph.astream = MagicMock(return_value=aiter([]))
            return mock_graph

        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
            patch("apps.agent.services.agent_dispatch.make_lead_agent", side_effect=capture_make_lead_agent),
        ):
            MockClient.return_value = _mock_client_instance(sample_agent_config, sample_ai_config)
            mock_select.return_value = (
                sample_ai_config["providers"][0], "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            from apps.agent.services.agent_dispatch import stream_agent_dispatch
            async for _ in stream_agent_dispatch(
                agent_id=1, family_id="12345678901234567",
                user_id="12345678901234568",
                thread_id=expected_tid, message="测试消息",
            ):
                pass

        assert captured_config["configurable"]["thread_id"] == expected_tid

    async def test_generates_thread_id_when_none(self, pm, sample_agent_config, sample_ai_config):
        """When thread_id is None, a UUID must be generated."""
        captured_config = {}

        def capture_make_lead_agent(config):
            captured_config.update(config)
            mock_graph = MagicMock()
            mock_graph.astream = MagicMock(return_value=aiter([]))
            return mock_graph

        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
            patch("apps.agent.services.agent_dispatch.make_lead_agent", side_effect=capture_make_lead_agent),
        ):
            MockClient.return_value = _mock_client_instance(sample_agent_config, sample_ai_config)
            mock_select.return_value = (
                sample_ai_config["providers"][0], "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            from apps.agent.services.agent_dispatch import stream_agent_dispatch
            async for _ in stream_agent_dispatch(
                agent_id=1, family_id="12345678901234567",
                user_id="12345678901234568",
                thread_id=None, message="测试消息",
            ):
                pass

        tid = captured_config["configurable"]["thread_id"]
        uuid.UUID(tid)  # validates format

    async def test_user_id_passed_to_runnable_config(self, pm, sample_agent_config, sample_ai_config):
        """user_id in RunnableConfig must be the actual user_id, not family_id."""
        captured_config = {}

        def capture_make_lead_agent(config):
            captured_config.update(config)
            mock_graph = MagicMock()
            mock_graph.astream = MagicMock(return_value=aiter([]))
            return mock_graph

        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
            patch("apps.agent.services.agent_dispatch.make_lead_agent", side_effect=capture_make_lead_agent),
        ):
            MockClient.return_value = _mock_client_instance(sample_agent_config, sample_ai_config)
            mock_select.return_value = (
                sample_ai_config["providers"][0], "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            from apps.agent.services.agent_dispatch import stream_agent_dispatch
            async for _ in stream_agent_dispatch(
                agent_id=1, family_id="12345678901234567",
                user_id="99999999999999999",
                thread_id=None, message="测试消息",
            ):
                pass

        assert captured_config["configurable"]["user_id"] == "99999999999999999"

    async def test_end_event_includes_execution_time(self, pm, sample_agent_config, sample_ai_config):
        """End event must include a positive execution_time_ms."""
        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
        ):
            MockClient.return_value = _mock_client_instance(sample_agent_config, sample_ai_config)
            mock_select.return_value = (
                sample_ai_config["providers"][0], "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            mock_graph = MagicMock()
            mock_graph.astream = MagicMock(return_value=aiter([]))

            with patch("apps.agent.services.agent_dispatch.make_lead_agent", mock_graph):
                from apps.agent.services.agent_dispatch import stream_agent_dispatch
                events = []
                async for line in stream_agent_dispatch(
                    agent_id=1, family_id="12345678901234567",
                    user_id="12345678901234568",
                    thread_id=None, message="测试消息",
                ):
                    events.append(json.loads(line.strip()))

        end_events = [e for e in events if e["type"] == "capability.end"]
        assert len(end_events) == 1
        assert end_events[0]["result"]["execution_time_ms"] >= 0

    async def test_skills_and_mcp_fetched_from_backend(self, pm, sample_agent_config, sample_ai_config):
        """Skills and MCP servers must be fetched from BackendClient."""
        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
        ):
            instance = _mock_client_instance(sample_agent_config, sample_ai_config)
            MockClient.return_value = instance
            mock_select.return_value = (
                sample_ai_config["providers"][0], "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            mock_graph = MagicMock()
            mock_graph.astream = MagicMock(return_value=aiter([]))

            with patch("apps.agent.services.agent_dispatch.make_lead_agent", mock_graph):
                from apps.agent.services.agent_dispatch import stream_agent_dispatch
                async for _ in stream_agent_dispatch(
                    agent_id=1, family_id="12345678901234567",
                    user_id="12345678901234568",
                    thread_id=None, message="测试消息",
                ):
                    pass

            instance.get_enabled_skills.assert_awaited_once()
            instance.get_enabled_mcp_servers.assert_awaited_once()
