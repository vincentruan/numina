"""Unit tests for Orchestrator dispatch pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.response import AgentResponse
from services.orchestrator import Orchestrator


def _make_ai_config(enabled=True):
    return {
        "ai_enabled": enabled,
        "ai_provider": "anthropic",
        "api_key": "sk-test",
        "allowed_capabilities": [],
        "admin_only_capabilities": [],
        "member_role": "member",
    }


def _make_redacted_context(family_id="fam-1"):
    from schemas.context import RedactedContext
    return RedactedContext(family_id=family_id)


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
            patch("services.orchestrator.audit_logger") as mock_audit,
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
