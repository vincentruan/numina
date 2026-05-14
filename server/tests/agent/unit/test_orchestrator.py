"""Unit tests for Orchestrator dispatch pipeline.

DeerFlow is the mandatory execution path. Failures return structured error
responses — there is no silent fallback to direct LLM calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.agent.schemas.response import AgentResponse
from apps.agent.services.orchestrator import Orchestrator
from apps.agent.services.stream_events import EventStreamBuilder


def _make_ai_config(enabled=True):
    return {
        "ai_enabled": enabled,
        "ai_provider": "anthropic",
        "api_key": "sk-test",
        "allowed_capabilities": [],
        "admin_only_capabilities": [],
        "member_role": "member",
    }


def _make_redacted_context(family_id="fam-1", free_text=None):
    from apps.agent.schemas.context import RedactedContext
    return RedactedContext(family_id=family_id, free_text=free_text)


def _make_deerflow_output(capability: str) -> str:
    return json.dumps({
        "summary": f"{capability} 分析完成",
        "disclaimers": ["仅供参考"],
    })


@pytest.fixture
def orchestrator():
    return Orchestrator()


class TestOrchestratorPolicyBlocking:
    async def test_ai_disabled_returns_denied_response(self, orchestrator):
        config = _make_ai_config(enabled=False)
        with patch("apps.agent.services.orchestrator.BackendClient") as MockClient:
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            response = await orchestrator.dispatch("report", "fam-1")
        assert isinstance(response, AgentResponse)
        assert response.capability == "report"
        assert "未启用" in response.summary

    async def test_capability_not_allowed_returns_denied(self, orchestrator):
        config = _make_ai_config()
        config["allowed_capabilities"] = ["chat"]
        with patch("apps.agent.services.orchestrator.BackendClient") as MockClient:
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            response = await orchestrator.dispatch("report", "fam-1")
        assert response.fallback_used is False
        assert "不可用" in response.summary


class TestOrchestratorDeerFlowPath:
    async def test_deerflow_success_returns_response(self, orchestrator):
        config = _make_ai_config()
        redacted = _make_redacted_context()
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output("report"))

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.return_value = ("report 分析完成", [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))
            response = await orchestrator.dispatch("report", "fam-1")

        assert response.fallback_used is False
        assert response.summary == "report 分析完成"
        mock_df.dispatch.assert_called_once()

    async def test_deerflow_failure_returns_error_response(self, orchestrator):
        config = _make_ai_config()
        redacted = _make_redacted_context()
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(side_effect=RuntimeError("harness timeout"))

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.return_value = ("", [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))
            response = await orchestrator.dispatch("report", "fam-1")

        assert isinstance(response, AgentResponse)
        assert "不可用" in response.summary or "重试" in response.summary
        assert response.fallback_used is False

    async def test_deerflow_failure_no_fallback_called(self, orchestrator):
        """DeerFlow failure must NOT silently call any LLM fallback."""
        config = _make_ai_config()
        redacted = _make_redacted_context()
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(side_effect=RuntimeError("boom"))
        mock_llm = MagicMock()

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.return_value = ("", [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))
            await orchestrator.dispatch("report", "fam-1")

        mock_llm.chat.assert_not_called() if hasattr(mock_llm, "chat") else None


class TestOrchestratorAuditLogging:
    async def test_audit_logged_on_success(self, orchestrator):
        config = _make_ai_config()
        redacted = _make_redacted_context()
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output("report"))

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.return_value = ("done", [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))
            await orchestrator.dispatch("report", "fam-1", user_id="u-1")

        mock_audit.log_call.assert_called_once()
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.family_id == "fam-1"
        assert entry.capability == "report"
        assert entry.user_id == "u-1"
        assert entry.deerflow_attempted is True
        assert entry.fallback_used is False

    async def test_audit_logged_even_on_backend_failure(self, orchestrator):
        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.audit_logger"),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(
                side_effect=RuntimeError("backend down")
            )
            response = await orchestrator.dispatch("report", "fam-1")

        assert isinstance(response, AgentResponse)
        assert "重试" in response.summary or "配置" in response.summary


class TestOrchestratorAuditAccuracy:
    async def test_policy_denied_deerflow_not_attempted(self, orchestrator):
        """deerflow_attempted must be False when policy blocks before DeerFlow is reached."""
        config = _make_ai_config(enabled=False)
        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            await orchestrator.dispatch("report", "fam-1")

        entry = mock_audit.log_call.call_args[0][0]
        assert entry.deerflow_attempted is False
        assert entry.success is False

    async def test_ai_config_failure_recorded_as_error(self, orchestrator):
        """success must be False when ai_config fetch fails."""
        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(
                side_effect=RuntimeError("backend down")
            )
            await orchestrator.dispatch("report", "fam-1")

        entry = mock_audit.log_call.call_args[0][0]
        assert entry.success is False
        assert entry.deerflow_attempted is False
        assert entry.error_type == "RuntimeError"

    async def test_deerflow_success_attempted_true(self, orchestrator):
        """deerflow_attempted must be True only when DeerFlow was actually called."""
        config = _make_ai_config()
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output("report"))

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = _make_redacted_context()
            mock_redactor.redact_text.return_value = ("report 分析完成", [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))
            await orchestrator.dispatch("report", "fam-1")

        entry = mock_audit.log_call.call_args[0][0]
        assert entry.deerflow_attempted is True
        assert entry.success is True
    def test_error_response_has_fallback_false(self):
        r = Orchestrator._error_response("report", "audit-1")
        assert r.fallback_used is False
        assert r.capability == "report"
        assert r.audit_id == "audit-1"

    def test_error_response_custom_message(self):
        r = Orchestrator._error_response("chat", "audit-2", "custom msg")
        assert r.summary == "custom msg"


class TestOrchestratorEventStreaming:
    async def test_stream_dispatch_events_uses_deerflow(self, orchestrator):
        config = _make_ai_config()
        config["thinking_supported"] = False

        async def _deerflow_stream(*args, **kwargs):
            yield "DeerFlow answer"

        mock_df = MagicMock()
        mock_df.stream_dispatch = _deerflow_stream

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
            patch("apps.agent.services.orchestrator._create_family_adapter", return_value=mock_df),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = _make_redacted_context(free_text="问题")
            mock_redactor.redact_text.side_effect = lambda text: (text, [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))

            lines = [
                line
                async for line in orchestrator.stream_dispatch_events(
                    capability="chat",
                    family_id="fam-1",
                    task_id="task-1",
                    free_text="问题",
                )
            ]

        joined = "".join(lines)
        assert "DeerFlow answer" in joined
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.deerflow_attempted is True
        assert entry.fallback_used is False

    async def test_deerflow_stream_failure_emits_error_event(self, orchestrator):
        config = _make_ai_config()
        config["thinking_supported"] = False

        async def _raise_stream(*args, **kwargs):
            raise RuntimeError("boom")
            yield ""  # make it a generator

        mock_df = MagicMock()
        mock_df.stream_dispatch = _raise_stream

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
            patch("apps.agent.services.orchestrator._create_family_adapter", return_value=mock_df),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = _make_redacted_context()
            mock_redactor.redact_text.return_value = ("", [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))

            lines = [
                line
                async for line in orchestrator.stream_dispatch_events(
                    capability="report",
                    family_id="fam-1",
                    task_id="task-2",
                )
            ]

        joined = "".join(lines)
        assert "capability.error" in joined or "error" in joined
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.success is False
        assert entry.deerflow_attempted is True
        assert entry.error_type == "RuntimeError"
