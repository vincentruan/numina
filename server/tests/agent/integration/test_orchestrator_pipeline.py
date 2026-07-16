"""Integration tests for the Orchestrator pipeline.

These tests exercise the full dispatch pipeline with mocked BackendClient
and mocked DeerFlow calls, verifying that all capabilities produce valid
AgentResponse objects and that the pipeline components interact correctly.

DeerFlow is the mandatory execution path. There is no fallback to direct LLM.
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.agent.schemas.response import AgentResponse
from apps.agent.services.orchestrator import Orchestrator
from tests.agent.golden.fixtures import REDACTED_CONTEXT, assert_valid_agent_response


def _make_ai_config(enabled=True, provider="anthropic", api_key="sk-test"):
    return {
        "ai_enabled": enabled,
        "ai_provider": provider,
        "api_key": api_key,
        "providers": [
            {
                "ai_provider": provider,
                "api_key": api_key,
                "ai_model_id": "claude-3-5-sonnet-20241022",
                "is_active": True,
            }
        ],
        "allowed_capabilities": [],
        "admin_only_capabilities": [],
        "member_role": "member",
    }


def _make_deerflow_output(capability: str) -> str:
    return json.dumps({
        "summary": f"{capability} 分析完成（测试）",
        "disclaimers": ["本分析仅供参考"],
    })


@pytest.fixture
def orch():
    return Orchestrator()


@pytest.fixture
def mock_backend():
    """Patch BackendClient to return golden context data."""
    with patch("apps.agent.services.orchestrator.BackendClient") as MockClient:
        instance = MockClient.return_value
        instance.get_family_ai_config = AsyncMock(return_value=_make_ai_config())
        yield instance


class TestOrchestratorAllCapabilities:
    """Verify all capabilities produce valid AgentResponse via DeerFlow path."""

    @pytest.mark.parametrize("capability", [
        "report", "alerts", "disposal", "liability", "allocation", "chat", "suggest"
    ])
    async def test_capability_returns_agent_response(self, orch, mock_backend, capability):
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output(capability))

        with patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df):
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)
            response = await orch.dispatch(capability, "fam-golden-001")

        assert isinstance(response, AgentResponse)
        assert response.capability == capability
        assert response.fallback_used is False


class TestOrchestratorPIIRedactionInPipeline:
    """Verify PII redaction runs before DeerFlow dispatch."""

    async def test_redaction_called_before_dispatch(self, orch, mock_backend):
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output("report"))

        with (
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
        ):
            mock_redactor.redact.return_value = REDACTED_CONTEXT
            mock_redactor.redact_text.return_value = ("ok", [])
            orch._build_context = AsyncMock(return_value=MagicMock())

            await orch.dispatch("report", "fam-golden-001")

        mock_redactor.redact.assert_called_once()

    async def test_deerflow_receives_redacted_context(self, orch, mock_backend):
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output("report"))

        with (
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
            patch("apps.agent.services.orchestrator.pii_redactor") as mock_redactor,
        ):
            mock_redactor.redact.return_value = REDACTED_CONTEXT
            mock_redactor.redact_text.return_value = ("ok", [])
            orch._build_context = AsyncMock(return_value=MagicMock())

            await orch.dispatch("report", "fam-golden-001")

        call_kwargs = mock_df.dispatch.call_args[1]
        assert call_kwargs["context"] is REDACTED_CONTEXT


class TestOrchestratorAuditIntegration:
    """Verify audit entries are written with correct fields for all capabilities."""

    @pytest.mark.parametrize("capability", ["report", "liability", "chat"])
    async def test_audit_entry_has_correct_capability(self, orch, mock_backend, capability):
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output(capability))

        with (
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
        ):
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)
            await orch.dispatch(capability, "fam-golden-001", user_id="u-test")

        mock_audit.log_call.assert_called_once()
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.capability == capability
        assert entry.family_id == "fam-golden-001"
        assert entry.user_id == "u-test"
        assert entry.duration_ms is not None and entry.duration_ms >= 0

    async def test_audit_entry_records_deerflow_attempted(self, orch, mock_backend):
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output("report"))

        with (
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
        ):
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)
            await orch.dispatch("report", "fam-golden-001")

        entry = mock_audit.log_call.call_args[0][0]
        assert entry.fallback_used is False
        assert entry.deerflow_attempted is True


class TestOrchestratorDeerFlowPath:
    """Verify DeerFlow path produces AgentResponse via output_mapper."""

    async def test_deerflow_output_mapped_to_agent_response(self, orch, mock_backend):
        deerflow_output = json.dumps({
            "summary": "DeerFlow 分析完成",
            "disclaimers": ["仅供参考"],
            "risk_flags": [],
            "recommendations": [],
            "rule_based_findings": [],
            "ai_inferences": [],
        })
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=deerflow_output)

        with patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df):
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)
            response = await orch.dispatch("report", "fam-golden-001")

        assert isinstance(response, AgentResponse)
        assert response.summary == "DeerFlow 分析完成"
        assert response.fallback_used is False

    async def test_deerflow_skill_triggered_recorded_in_audit(self, orch, mock_backend):
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=_make_deerflow_output("report"))

        with (
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
            patch("apps.agent.services.orchestrator.audit_logger") as mock_audit,
        ):
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)
            await orch.dispatch("report", "fam-golden-001")

        entry = mock_audit.log_call.call_args[0][0]
        assert entry.skill_triggered == "report"
        assert entry.fallback_used is False

    async def test_deerflow_failure_returns_error_response(self, orch, mock_backend):
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(side_effect=RuntimeError("harness timeout"))

        with patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df):
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)
            response = await orch.dispatch("report", "fam-golden-001")

        assert isinstance(response, AgentResponse)
        assert "不可用" in response.summary or "重试" in response.summary
        assert response.fallback_used is True  # Error response IS a fallback


class TestOrchestratorPolicyEnforcement:
    """Verify policy enforcement blocks requests before any LLM call."""

    async def test_ai_disabled_never_calls_deerflow(self, orch):
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock()

        with (
            patch("apps.agent.services.orchestrator.BackendClient") as MockClient,
            patch("apps.agent.services.orchestrator._deerflow_adapter", mock_df),
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(
                return_value=_make_ai_config(enabled=False)
            )
            response = await orch.dispatch("report", "fam-golden-001")

        mock_df.dispatch.assert_not_called()
        assert "未启用" in response.summary

    async def test_admin_only_capability_blocked_for_member(self, orch):
        config = _make_ai_config()
        config["admin_only_capabilities"] = ["report"]
        config["member_role"] = "member"

        with patch("apps.agent.services.orchestrator.BackendClient") as MockClient:
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            response = await orch.dispatch("report", "fam-golden-001")

        assert "管理员" in response.summary
        assert response.fallback_used is False
