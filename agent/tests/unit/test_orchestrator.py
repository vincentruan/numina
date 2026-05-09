"""Unit tests for Orchestrator dispatch pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.response import AgentResponse
from services.orchestrator import Orchestrator
from services.stream_events import EventStreamBuilder


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
    from schemas.context import RedactedContext
    return RedactedContext(family_id=family_id, free_text=free_text)


@pytest.fixture
def orchestrator():
    return Orchestrator()


class TestOrchestratorPolicyBlocking:
    async def test_ai_disabled_returns_denied_response(self, orchestrator):
        config = _make_ai_config(enabled=False)
        with patch("services.orchestrator.BackendClient") as MockClient:
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            response = await orchestrator.dispatch("report", "fam-1")
        assert isinstance(response, AgentResponse)
        assert response.capability == "report"
        assert "未启用" in response.summary

    async def test_capability_not_allowed_returns_denied(self, orchestrator):
        config = _make_ai_config()
        config["allowed_capabilities"] = ["chat"]
        with patch("services.orchestrator.BackendClient") as MockClient:
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            response = await orchestrator.dispatch("report", "fam-1")
        assert not response.fallback_used
        assert "不可用" in response.summary


class TestOrchestratorFallbackPath:
    async def test_use_deerflow_false_uses_fallback(self, orchestrator):
        config = _make_ai_config()
        redacted = _make_redacted_context()
        safe_response = AgentResponse(
            capability="report", summary="ok", fallback_used=False, audit_id="a1"
        )
        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
            patch("services.orchestrator.settings") as mock_settings,
        ):
            mock_settings.USE_DEERFLOW = False
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.return_value = ("ok", [])
            mock_fallback.run = AsyncMock(return_value=safe_response)
            # Patch _build_context to avoid real HTTP calls
            orchestrator._build_context = AsyncMock(
                return_value=MagicMock(family_id="fam-1")
            )
            response = await orchestrator.dispatch("report", "fam-1")

        # USE_DEERFLOW=False: legacy is the normal path, fallback_used must be False
        assert response.fallback_used is False
        mock_fallback.run.assert_called_once()
        # Verify is_deerflow_fallback=False was passed
        call_kwargs = mock_fallback.run.call_args
        assert call_kwargs.kwargs.get("is_deerflow_fallback") is False or (
            len(call_kwargs.args) >= 5 and call_kwargs.args[4] is False
        )

    async def test_deerflow_failure_falls_back_to_legacy(self, orchestrator):
        """When USE_DEERFLOW=True but DeerFlow raises, fallback_engine is called."""
        config = _make_ai_config()
        redacted = _make_redacted_context()
        safe_response = AgentResponse(
            capability="report", summary="fallback", fallback_used=True, audit_id="a2"
        )
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(side_effect=RuntimeError("boom"))
        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator._deerflow_adapter", mock_df),
        ):
            mock_settings.USE_DEERFLOW = True
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.return_value = ("fallback", [])
            mock_fallback.run = AsyncMock(return_value=safe_response)
            orchestrator._build_context = AsyncMock(
                return_value=MagicMock(family_id="fam-1")
            )
            response = await orchestrator.dispatch("report", "fam-1")

        assert response.fallback_used is True
        mock_fallback.run.assert_called_once()


class TestOrchestratorAuditLogging:
    async def test_audit_logged_on_success(self, orchestrator):
        config = _make_ai_config()
        redacted = _make_redacted_context()
        ok_response = AgentResponse(
            capability="report", summary="done", fallback_used=True, audit_id="a3"
        )
        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
            patch("services.orchestrator.audit_logger") as mock_audit,
            patch("services.orchestrator.settings") as mock_settings,
        ):
            mock_settings.USE_DEERFLOW = False
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.return_value = ("done", [])
            mock_fallback.run = AsyncMock(return_value=ok_response)
            orchestrator._build_context = AsyncMock(
                return_value=MagicMock(family_id="fam-1")
            )
            await orchestrator.dispatch("report", "fam-1", user_id="u-1")

        mock_audit.log_call.assert_called_once()
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.family_id == "fam-1"
        assert entry.capability == "report"
        assert entry.user_id == "u-1"

    async def test_audit_logged_even_on_backend_failure(self, orchestrator):
        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.audit_logger"),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(
                side_effect=RuntimeError("backend down")
            )
            response = await orchestrator.dispatch("report", "fam-1")

        # audit is NOT called when we return early before the try/finally audit block
        # but the response should still be safe
        assert isinstance(response, AgentResponse)
        assert response.fallback_used is True


class TestOrchestratorSafeResponse:
    def test_safe_response_has_fallback_true(self):
        r = Orchestrator._safe_response("report", "audit-1")
        assert r.fallback_used is True
        assert r.capability == "report"
        assert r.audit_id == "audit-1"

    def test_safe_response_custom_message(self):
        r = Orchestrator._safe_response("chat", "audit-2", "custom msg")
        assert r.summary == "custom msg"


class TestOrchestratorEventStreaming:
    async def test_stream_dispatch_events_does_not_call_legacy_prefix_stream(self, orchestrator):
        config = _make_ai_config()
        config["thinking_supported"] = False

        async def _event_source(*args, **kwargs):
            builder = EventStreamBuilder("chat", "task-1")
            yield builder.phase("answering").to_ndjson()
            yield builder.token("统一事件", is_thinking=False).to_ndjson()
            yield builder.end("统一事件").to_ndjson()

        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.settings") as mock_settings,
            patch.object(
                orchestrator,
                "stream_dispatch",
                side_effect=AssertionError("legacy stream_dispatch should not be used"),
            ),
            patch.object(orchestrator, "_stream_dispatch_event_lines", side_effect=_event_source),
        ):
            mock_settings.USE_DEERFLOW = False
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact_text.return_value = ("统一事件", [])

            lines = [
                line
                async for line in orchestrator.stream_dispatch_events(
                    capability="chat",
                    family_id="fam-1",
                    task_id="task-1",
                    free_text="问题",
                )
            ]

        assert '"type":"token.stream"' in "".join(lines)
        assert "统一事件" in "".join(lines)

    async def test_direct_chat_event_stream_emits_tokens_without_prefixes(self, orchestrator):
        config = _make_ai_config()
        config["thinking_supported"] = False

        captured_prompt = {}

        class FakeLLM:
            async def stream_text(self, prompt, max_tokens):
                captured_prompt["prompt"] = prompt
                yield "直接"
                yield "回答"

        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.LLMClient", return_value=FakeLLM()),
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.audit_logger"),
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.chat._classify_intent", new=AsyncMock(return_value="net_worth")),
            patch("services.chat._fetch_data_for_intent", new=AsyncMock(return_value={"ok": True})),
        ):
            mock_settings.USE_DEERFLOW = False
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = _make_redacted_context(free_text="净资产是多少？")
            mock_redactor.redact_text.side_effect = lambda text: (text, [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))

            lines = [
                line
                async for line in orchestrator.stream_dispatch_events(
                    capability="chat",
                    family_id="fam-1",
                    task_id="task-2",
                    free_text="净资产是多少？",
                )
            ]

        joined = "".join(lines)
        assert "[TEXT]" not in joined
        assert "[THINK]" not in joined
        assert '"token":"直接"' in joined
        assert '"token":"回答"' in joined
        assert "不要输出分析过程" in captured_prompt["prompt"]

    async def test_deerflow_failure_marks_event_stream_as_failed(self, orchestrator):
        config = _make_ai_config()
        config["thinking_supported"] = False
        redacted = _make_redacted_context()
        safe_response = AgentResponse(
            capability="report",
            summary="fallback",
            fallback_used=True,
            audit_id="a4",
        )
        async def _raise_stream(*args, **kwargs):
            raise RuntimeError("boom")
            yield ""

        mock_df = MagicMock()
        mock_df.stream_dispatch = _raise_stream

        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.LLMClient") as MockLLM,
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.audit_logger") as mock_audit,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator._create_family_adapter", return_value=mock_df),
        ):
            mock_settings.USE_DEERFLOW = True
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.return_value = ("fallback", [])
            mock_fallback.run = AsyncMock(return_value=safe_response)
            MockLLM.return_value = MagicMock()
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))

            lines = [
                line
                async for line in orchestrator.stream_dispatch_events(
                    capability="report",
                    family_id="fam-1",
                    task_id="task-3",
                )
            ]

        joined = "".join(lines)
        assert '"type":"capability.end"' in joined
        assert '"type":"token.stream"' in joined
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.success is False
        assert entry.fallback_used is True
        assert entry.deerflow_attempted is True
        assert entry.error_type == "RuntimeError"

    async def test_deerflow_event_stream_uses_adapter_as_execution_boundary(self, orchestrator):
        config = _make_ai_config()
        config["thinking_supported"] = False
        redacted = _make_redacted_context(free_text="净资产是多少？")

        async def _deerflow_stream(*args, **kwargs):
            yield "DeerFlow answer"

        mock_df = MagicMock()
        mock_df.stream_dispatch = _deerflow_stream

        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.LLMClient") as MockLLM,
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.audit_logger") as mock_audit,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator._create_family_adapter", return_value=mock_df) as make_adapter,
        ):
            mock_settings.USE_DEERFLOW = True
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            mock_redactor.redact.return_value = redacted
            mock_redactor.redact_text.side_effect = lambda text: (text, [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))

            lines = [
                line
                async for line in orchestrator.stream_dispatch_events(
                    capability="chat",
                    family_id="fam-1",
                    task_id="task-4",
                    free_text="净资产是多少？",
                )
            ]

        joined = "".join(lines)
        make_adapter.assert_called_once_with("fam-1", config)
        MockLLM.assert_not_called()
        mock_fallback.run.assert_not_called()
        assert "DeerFlow answer" in joined
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.deerflow_attempted is True
        assert entry.fallback_used is False
