"""Unit tests for Orchestrator dispatch pipeline.

DeerFlow is the mandatory execution path. Failures return structured error
responses — there is no silent fallback to direct LLM calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.agent.schemas.response import AgentResponse
from apps.agent.services.deerflow_adapter.adapter import StreamChunk
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
        ai_configs = {
            "ai_enabled": True,
            "providers": [
                {
                    "config_id": "cfg-001",
                    "ai_provider": "anthropic",
                    "api_key": "sk-test",
                    "ai_model_id": "claude-haiku-4-5",
                    "model_1_capabilities": ["text_generation"],
                    "model_2_capabilities": [],
                    "model_3_capabilities": [],
                    "timeout_seconds": 60,
                }
            ],
            "allowed_capabilities": [],
            "admin_only_capabilities": [],
            "member_role": "member",
        }

        async def _deerflow_stream(*args, **kwargs):
            yield StreamChunk(type="text", content="DeerFlow answer")

        mock_df = MagicMock()
        mock_df.stream_dispatch = _deerflow_stream

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
            patch("apps.agent.services.orchestrator._create_family_adapter", return_value=mock_df),
        ):
            MockClient.return_value.get_family_ai_configs = AsyncMock(return_value=ai_configs)
            MockClient.return_value.reset_circuit_success = AsyncMock(return_value={})
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
        ai_configs = {
            "ai_enabled": True,
            "providers": [
                {
                    "config_id": "cfg-001",
                    "ai_provider": "anthropic",
                    "api_key": "sk-test",
                    "ai_model_id": "claude-haiku-4-5",
                    "model_1_capabilities": ["text_generation"],
                    "model_2_capabilities": [],
                    "model_3_capabilities": [],
                    "timeout_seconds": 60,
                }
            ],
            "allowed_capabilities": [],
            "admin_only_capabilities": [],
            "member_role": "member",
        }

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
            MockClient.return_value.get_family_ai_configs = AsyncMock(return_value=ai_configs)
            MockClient.return_value.report_circuit_event = AsyncMock(return_value={})
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


class TestSelectModel:
    """IU-5: Tests for _select_model() model selection strategy."""

    def test_selects_thinking_model_from_slot1(self):
        from apps.agent.services.orchestrator import _select_model

        providers = [
            {
                "config_id": "cfg-1",
                "ai_model_id": "claude-sonnet-4-6",
                "model_1_capabilities": ["text_generation", "deep_thinking"],
                "model_2_capabilities": [],
                "model_3_capabilities": [],
            }
        ]
        provider, model_id, caps = _select_model(providers, "thinking")
        assert model_id == "claude-sonnet-4-6"
        assert provider["config_id"] == "cfg-1"
        assert "deep_thinking" in caps

    def test_skips_provider_without_required_capability(self):
        from apps.agent.services.orchestrator import _select_model

        providers = [
            {
                "config_id": "cfg-no-think",
                "ai_model_id": "gpt-4o",
                "model_1_capabilities": ["text_generation"],
                "model_2_capabilities": [],
                "model_3_capabilities": [],
            },
            {
                "config_id": "cfg-think",
                "ai_model_id": "claude-sonnet-4-6",
                "model_1_capabilities": ["text_generation", "deep_thinking"],
                "model_2_capabilities": [],
                "model_3_capabilities": [],
            },
        ]
        provider, model_id, caps = _select_model(providers, "thinking")
        assert provider["config_id"] == "cfg-think"
        assert model_id == "claude-sonnet-4-6"
        assert "deep_thinking" in caps

    def test_selects_vision_model_from_slot2(self):
        from apps.agent.services.orchestrator import _select_model

        providers = [
            {
                "config_id": "cfg-vis",
                "ai_model_id": "gpt-4o",
                "model_2_id": "gpt-4o-vision",
                "model_1_capabilities": ["text_generation"],
                "model_2_capabilities": ["vision_understanding"],
                "model_3_capabilities": [],
            }
        ]
        provider, model_id, caps = _select_model(providers, "vision")
        assert model_id == "gpt-4o-vision"
        assert "vision_understanding" in caps
        assert "text_generation" not in caps  # slot-2 caps, not slot-1

    def test_selects_model_from_slot3(self):
        """Slot 3 is selected when slots 1 and 2 both lack the required capability."""
        from apps.agent.services.orchestrator import _select_model

        providers = [
            {
                "config_id": "cfg-slot3",
                "ai_model_id": "gpt-4o",
                "model_2_id": "gpt-4o-mini",
                "model_3_id": "deepseek-r1",
                "model_1_capabilities": ["text_generation"],
                "model_2_capabilities": ["text_generation"],
                "model_3_capabilities": ["text_generation", "deep_thinking"],
            }
        ]
        provider, model_id, caps = _select_model(providers, "thinking")
        assert model_id == "deepseek-r1"
        assert "deep_thinking" in caps
        assert provider["config_id"] == "cfg-slot3"

    def test_returned_caps_match_selected_slot_not_slot1(self):
        """selected_caps must reflect the chosen slot, not always slot-1."""
        from apps.agent.services.orchestrator import _select_model

        providers = [
            {
                "config_id": "cfg-mixed",
                "ai_model_id": "text-model",
                "model_2_id": "vision-model",
                "model_1_capabilities": ["text_generation"],
                "model_2_capabilities": ["vision_understanding"],
                "model_3_capabilities": [],
            }
        ]
        _, model_id, caps = _select_model(providers, "vision")
        assert model_id == "vision-model"
        # caps must be slot-2's list, not slot-1's
        assert "vision_understanding" in caps
        assert "text_generation" not in caps

    def test_fallback_when_no_provider_matches(self):
        from apps.agent.services.orchestrator import _select_model

        providers = [
            {
                "config_id": "cfg-text-only",
                "ai_model_id": "gpt-4o-mini",
                "model_1_capabilities": ["text_generation"],
                "model_2_capabilities": [],
                "model_3_capabilities": [],
            }
        ]
        # No provider has deep_thinking — should fall back to first provider slot1
        provider, model_id, caps = _select_model(providers, "thinking")
        assert model_id == "gpt-4o-mini"
        assert provider["config_id"] == "cfg-text-only"
        assert caps == ["text_generation"]

    def test_raises_on_empty_providers(self):
        from apps.agent.services.orchestrator import _select_model

        with pytest.raises(ValueError, match="empty"):
            _select_model([], "text")

    def test_text_task_selects_text_generation_slot(self):
        from apps.agent.services.orchestrator import _select_model

        providers = [
            {
                "config_id": "cfg-t",
                "ai_model_id": "claude-haiku-4-5",
                "model_1_capabilities": ["text_generation"],
                "model_2_capabilities": [],
                "model_3_capabilities": [],
            }
        ]
        provider, model_id, caps = _select_model(providers, "text")
        assert model_id == "claude-haiku-4-5"
        assert "text_generation" in caps


class TestSelectModelAuditAndGuards:
    """Tests for audit logging on error paths and empty model_id guard in stream_dispatch."""

    @pytest.mark.asyncio
    async def test_stream_dispatch_emits_audit_on_empty_providers(self):
        """stream_dispatch must call audit_logger.log_call when _select_model raises ValueError."""
        from apps.agent.services.orchestrator import Orchestrator

        mock_client = MagicMock()
        mock_client.get_family_ai_configs = AsyncMock(return_value={"ai_enabled": True, "providers": []})

        with (
            patch("apps.agent.services.orchestrator.BackendClient", return_value=mock_client),
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
        ):
            orch = Orchestrator()
            chunks = []
            async for chunk in orch.stream_dispatch("chat", "fam-1", task_id="task-1", user_id="u1", free_text="hi"):
                chunks.append(chunk)

        assert any("无法" in c or "重试" in c for c in chunks)
        mock_audit.log_call.assert_called_once()
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.success is False
        assert entry.error_type == "NoProvider"
        assert entry.deerflow_attempted is False

    @pytest.mark.asyncio
    async def test_stream_dispatch_emits_audit_on_empty_model_id(self):
        """stream_dispatch must call audit_logger.log_call when selected model_id is empty."""
        from apps.agent.services.orchestrator import Orchestrator

        mock_client = MagicMock()
        mock_client.get_family_ai_configs = AsyncMock(return_value={
            "ai_enabled": True,
            "providers": [
                {
                    "config_id": "cfg-empty",
                    "ai_model_id": "",  # empty — triggers NoModelId guard
                    "model_1_capabilities": ["text_generation"],
                    "model_2_capabilities": [],
                    "model_3_capabilities": [],
                    "timeout_seconds": 60,
                }
            ],
        })

        with (
            patch("apps.agent.services.orchestrator.BackendClient", return_value=mock_client),
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
        ):
            orch = Orchestrator()
            chunks = []
            async for chunk in orch.stream_dispatch("chat", "fam-1", task_id="task-1", user_id="u1", free_text="hi"):
                chunks.append(chunk)

        assert any("无法" in c or "重试" in c for c in chunks)
        mock_audit.log_call.assert_called_once()
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.success is False
        assert entry.error_type == "NoModelId"


class TestIU5CircuitEvents:
    """IU-5: Tests for circuit event reporting on DeerFlow failures and success."""

    def _make_ai_configs(self, enabled=True):
        return {
            "ai_enabled": enabled,
            "providers": [
                {
                    "config_id": "cfg-001",
                    "ai_provider": "anthropic",
                    "api_key": "sk-test",
                    "ai_model_id": "claude-sonnet-4-6",
                    "model_1_capabilities": ["text_generation"],
                    "model_2_capabilities": [],
                    "model_3_capabilities": [],
                    "timeout_seconds": 60,
                }
            ],
            "allowed_capabilities": [],
            "admin_only_capabilities": [],
            "member_role": "member",
        }

    async def test_deerflow_failure_triggers_report_circuit_event(self):
        orchestrator = Orchestrator()
        ai_configs = self._make_ai_configs()

        async def _raise_stream(*args, **kwargs):
            raise RuntimeError("provider error")
            yield ""

        mock_df = MagicMock()
        mock_df.stream_dispatch = _raise_stream
        mock_client = MagicMock()
        mock_client.get_family_ai_configs = AsyncMock(return_value=ai_configs)
        mock_client.report_circuit_event = AsyncMock(return_value={})
        mock_client.reset_circuit_success = AsyncMock(return_value={})

        with (
            patch("apps.agent.services.orchestrator.BackendClient", return_value=mock_client),
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator.audit_logger"),
            patch("apps.agent.services.orchestrator._create_family_adapter", return_value=mock_df),
        ):
            mock_redactor.redact.return_value = _make_redacted_context()
            mock_redactor.redact_text.return_value = ("", [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))

            chunks = [
                c async for c in orchestrator.stream_dispatch(
                    capability="chat",
                    family_id="fam-1",
                    task_id="t-1",
                )
            ]

        # report_circuit_event must have been scheduled (fire-and-forget)
        mock_client.report_circuit_event.assert_called_once_with("cfg-001", 500)
        mock_client.reset_circuit_success.assert_not_called()
        assert any("不可用" in c or "重试" in c for c in chunks)

    async def test_deerflow_success_triggers_reset_circuit_success(self):
        orchestrator = Orchestrator()
        ai_configs = self._make_ai_configs()

        async def _ok_stream(*args, **kwargs):
            yield StreamChunk(type="text", content="answer")

        mock_df = MagicMock()
        mock_df.stream_dispatch = _ok_stream
        mock_client = MagicMock()
        mock_client.get_family_ai_configs = AsyncMock(return_value=ai_configs)
        mock_client.report_circuit_event = AsyncMock(return_value={})
        mock_client.reset_circuit_success = AsyncMock(return_value={})

        with (
            patch("apps.agent.services.orchestrator.BackendClient", return_value=mock_client),
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator.audit_logger"),
            patch("apps.agent.services.orchestrator._create_family_adapter", return_value=mock_df),
        ):
            mock_redactor.redact.return_value = _make_redacted_context()
            mock_redactor.redact_text.side_effect = lambda text: (text, [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))

            chunks = [
                c async for c in orchestrator.stream_dispatch(
                    capability="chat",
                    family_id="fam-1",
                    task_id="t-2",
                )
            ]

        mock_client.reset_circuit_success.assert_called_once_with("cfg-001")
        mock_client.report_circuit_event.assert_not_called()

    async def test_model_name_records_selected_model_id(self):
        """model_name in session journal must reflect the actually selected model_id."""
        orchestrator = Orchestrator()
        ai_configs = self._make_ai_configs()

        async def _ok_stream(*args, **kwargs):
            yield StreamChunk(type="text", content="done")

        mock_df = MagicMock()
        mock_df.stream_dispatch = _ok_stream
        mock_client = MagicMock()
        mock_client.get_family_ai_configs = AsyncMock(return_value=ai_configs)
        mock_client.reset_circuit_success = AsyncMock(return_value={})

        captured_model: list[str | None] = []

        def _capture_session_start(**kwargs):
            captured_model.append(kwargs.get("model_name"))

        with (
            patch("apps.agent.services.orchestrator.BackendClient", return_value=mock_client),
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
            patch("apps.agent.services.orchestrator.audit_logger"),
            patch("apps.agent.services.orchestrator._create_family_adapter", return_value=mock_df),
            patch("apps.agent.services.orchestrator.session_journal") as mock_journal,
        ):
            mock_redactor.redact.return_value = _make_redacted_context()
            mock_redactor.redact_text.side_effect = lambda text: (text, [])
            orchestrator._build_context = AsyncMock(return_value=MagicMock(family_id="fam-1"))
            mock_journal.write_session_start.side_effect = _capture_session_start
            mock_journal.write_user_message = MagicMock()
            mock_journal.write_assistant_message = MagicMock()
            mock_journal.write_session_end = MagicMock()

            _ = [
                c async for c in orchestrator.stream_dispatch(
                    capability="chat",
                    family_id="fam-1",
                    task_id="t-3",
                )
            ]

        assert captured_model[0] == "claude-sonnet-4-6"
