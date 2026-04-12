"""Integration tests for the Orchestrator pipeline.

These tests exercise the full dispatch pipeline with mocked BackendClient
and mocked LLM/DeerFlow calls, verifying that all 7 capabilities produce
valid AgentResponse objects and that the pipeline components interact correctly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.response import AgentResponse
from services.orchestrator import Orchestrator
from tests.golden.fixtures import REDACTED_CONTEXT, assert_valid_agent_response


def _make_ai_config(enabled=True, provider="anthropic", api_key="sk-test"):
    return {
        "ai_enabled": enabled,
        "ai_provider": provider,
        "api_key": api_key,
        "allowed_capabilities": [],
        "admin_only_capabilities": [],
        "member_role": "member",
    }


def _make_legacy_response(capability: str) -> dict:
    """Minimal legacy service dict for each capability."""
    return {
        "summary": f"{capability} 分析完成（测试）",
        "disclaimers": ["本分析仅供参考"],
    }


@pytest.fixture
def orch():
    return Orchestrator()


@pytest.fixture
def mock_backend():
    """Patch BackendClient to return golden context data."""
    with patch("services.orchestrator.BackendClient") as MockClient:
        instance = MockClient.return_value
        instance.get_family_ai_config = AsyncMock(return_value=_make_ai_config())
        yield instance


class TestOrchestratorAllCapabilities:
    """Verify all 7 capabilities produce valid AgentResponse via fallback path."""

    @pytest.mark.parametrize("capability", [
        "report", "alerts", "disposal", "liability", "allocation", "chat", "suggest"
    ])
    async def test_capability_returns_agent_response(self, orch, mock_backend, capability):
        with (
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
        ):
            mock_settings.USE_DEERFLOW = False
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            mock_fallback.run = AsyncMock(return_value=AgentResponse(
                capability=capability,
                summary=f"{capability} ok",
                disclaimers=["仅供参考"],
                fallback_used=True,
                audit_id="test-audit",
            ))
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)

            response = await orch.dispatch(capability, "fam-golden-001")

        assert isinstance(response, AgentResponse)
        assert response.capability == capability
        assert response.fallback_used is True


class TestOrchestratorPIIRedactionInPipeline:
    """Verify PII redaction runs before fallback/DeerFlow dispatch."""

    async def test_redaction_called_before_fallback(self, orch, mock_backend):
        with (
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
        ):
            mock_settings.USE_DEERFLOW = False
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            mock_redactor.redact.return_value = REDACTED_CONTEXT
            mock_fallback.run = AsyncMock(return_value=AgentResponse(
                capability="report", summary="ok", fallback_used=True, audit_id="a1"
            ))
            orch._build_context = AsyncMock(return_value=MagicMock())

            await orch.dispatch("report", "fam-golden-001")

        mock_redactor.redact.assert_called_once()

    async def test_fallback_receives_redacted_context(self, orch, mock_backend):
        with (
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator.pii_redactor") as mock_redactor,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
        ):
            mock_settings.USE_DEERFLOW = False
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            mock_redactor.redact.return_value = REDACTED_CONTEXT
            mock_fallback.run = AsyncMock(return_value=AgentResponse(
                capability="report", summary="ok", fallback_used=True, audit_id="a1"
            ))
            orch._build_context = AsyncMock(return_value=MagicMock())

            await orch.dispatch("report", "fam-golden-001")

        call_args = mock_fallback.run.call_args
        # Second positional arg is redacted_context
        assert call_args[0][1] is REDACTED_CONTEXT


class TestOrchestratorAuditIntegration:
    """Verify audit entries are written with correct fields for all capabilities."""

    @pytest.mark.parametrize("capability", ["report", "liability", "chat"])
    async def test_audit_entry_has_correct_capability(self, orch, mock_backend, capability):
        with (
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
            patch("services.orchestrator.audit_logger") as mock_audit,
        ):
            mock_settings.USE_DEERFLOW = False
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            mock_fallback.run = AsyncMock(return_value=AgentResponse(
                capability=capability, summary="ok", fallback_used=True, audit_id="a1"
            ))
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)

            await orch.dispatch(capability, "fam-golden-001", user_id="u-test")

        mock_audit.log_call.assert_called_once()
        entry = mock_audit.log_call.call_args[0][0]
        assert entry.capability == capability
        assert entry.family_id == "fam-golden-001"
        assert entry.user_id == "u-test"
        assert entry.duration_ms is not None and entry.duration_ms >= 0

    async def test_audit_entry_records_fallback_true(self, orch, mock_backend):
        with (
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
            patch("services.orchestrator.audit_logger") as mock_audit,
        ):
            mock_settings.USE_DEERFLOW = False
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            mock_fallback.run = AsyncMock(return_value=AgentResponse(
                capability="report", summary="ok", fallback_used=True, audit_id="a1"
            ))
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)

            await orch.dispatch("report", "fam-golden-001")

        entry = mock_audit.log_call.call_args[0][0]
        # USE_DEERFLOW=False: legacy is the normal path — fallback_used must be False
        assert entry.fallback_used is False
        assert entry.deerflow_attempted is False


class TestOrchestratorDeerFlowPath:
    """Verify DeerFlow path produces AgentResponse via output_mapper."""

    async def test_deerflow_output_mapped_to_agent_response(self, orch, mock_backend):
        import json
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

        with (
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator._deerflow_adapter", mock_df),
        ):
            mock_settings.USE_DEERFLOW = True
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)

            response = await orch.dispatch("report", "fam-golden-001")

        assert isinstance(response, AgentResponse)
        assert response.summary == "DeerFlow 分析完成"
        assert response.fallback_used is False

    async def test_deerflow_skill_triggered_recorded_in_audit(self, orch, mock_backend):
        import json
        deerflow_output = json.dumps({
            "summary": "ok", "disclaimers": ["仅供参考"],
        })
        mock_df = MagicMock()
        mock_df.dispatch = AsyncMock(return_value=deerflow_output)

        with (
            patch("services.orchestrator.settings") as mock_settings,
            patch("services.orchestrator._deerflow_adapter", mock_df),
            patch("services.orchestrator.audit_logger") as mock_audit,
        ):
            mock_settings.USE_DEERFLOW = True
            mock_settings.AGENT_INTERNAL_TOKEN = "tok"
            orch._build_context = AsyncMock(return_value=REDACTED_CONTEXT)

            await orch.dispatch("report", "fam-golden-001")

        entry = mock_audit.log_call.call_args[0][0]
        assert entry.skill_triggered == "report"
        assert entry.fallback_used is False


class TestOrchestratorPolicyEnforcement:
    """Verify policy enforcement blocks requests before any LLM call."""

    async def test_ai_disabled_never_calls_fallback(self, orch):
        with (
            patch("services.orchestrator.BackendClient") as MockClient,
            patch("services.orchestrator.fallback_engine") as mock_fallback,
        ):
            MockClient.return_value.get_family_ai_config = AsyncMock(
                return_value=_make_ai_config(enabled=False)
            )
            mock_fallback.run = AsyncMock()

            response = await orch.dispatch("report", "fam-golden-001")

        mock_fallback.run.assert_not_called()
        assert "未启用" in response.summary

    async def test_admin_only_capability_blocked_for_member(self, orch):
        config = _make_ai_config()
        config["admin_only_capabilities"] = ["report"]
        config["member_role"] = "member"

        with patch("services.orchestrator.BackendClient") as MockClient:
            MockClient.return_value.get_family_ai_config = AsyncMock(return_value=config)
            response = await orch.dispatch("report", "fam-golden-001")

        assert "管理员" in response.summary
        assert response.fallback_used is False
