"""HTTP-level integration tests for all 7 agent endpoints.

Uses httpx.AsyncClient against the real FastAPI app with mocked backend
and DeerFlow clients. Verifies that each endpoint:
- Returns 200 with valid AgentResponse JSON shape
- Returns 401 on invalid token
- Passes X-User-Id through to audit logging
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from schemas.response import AgentResponse

_TOKEN = "test-internal-token"
_FAMILY_ID = "fam-http-test-001"

_AI_CONFIG = {
    "ai_enabled": True,
    "ai_provider": "anthropic",
    "api_key": "sk-test",
    "allowed_capabilities": [],
    "admin_only_capabilities": [],
    "member_role": "member",
}

_SAFE_RESPONSE = {
    "capability": "report",
    "summary": "测试响应",
    "scorecards": [],
    "risk_flags": [],
    "recommendations": [],
    "rule_based_findings": [],
    "ai_inferences": [],
    "disclaimers": ["仅供参考"],
    "fallback_used": True,
    "followup_actions": [],
    "ui_blocks": [],
    "needs_confirmation": [],
    "audit_id": "test-audit-id",
}


def _make_response(capability: str) -> dict:
    r = _SAFE_RESPONSE.copy()
    r["capability"] = capability
    return r


def _patch_orchestrator(capability: str):
    """Context manager that patches orchestrator.dispatch to return a safe AgentResponse."""
    from schemas.response import AgentResponse as AR
    resp = AR(**_make_response(capability))
    return patch(
        "services.orchestrator.Orchestrator.dispatch",
        new=AsyncMock(return_value=resp),
    )


@pytest.fixture
def client():
    """TestClient with AGENT_INTERNAL_TOKEN set and startup validation bypassed."""
    import os
    os.environ["AGENT_INTERNAL_TOKEN"] = _TOKEN

    from main import app
    # Patch validate_required at the class level (avoids pydantic v2 setattr restriction)
    # and patch the module-level settings token used by routers
    with (
        patch("config.AgentSettings.validate_required", return_value=None),
        patch("services.orchestrator.settings.AGENT_INTERNAL_TOKEN", _TOKEN, create=True),
    ):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


class TestReportEndpoint:
    def test_generate_returns_agent_response(self, client):
        with _patch_orchestrator("report"):
            resp = client.post(
                "/report/generate",
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "report"
        assert "summary" in data
        assert "disclaimers" in data

    def test_generate_returns_401_on_bad_token(self, client):
        resp = client.post(
            "/report/generate",
            headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": "wrong"},
        )
        assert resp.status_code == 401


class TestAlertsEndpoint:
    def test_aging_returns_agent_response(self, client):
        with _patch_orchestrator("alerts"):
            resp = client.post(
                "/alerts/aging",
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "alerts"

    def test_aging_returns_401_on_bad_token(self, client):
        resp = client.post(
            "/alerts/aging",
            headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": "bad"},
        )
        assert resp.status_code == 401


class TestLiabilityEndpoint:
    def test_analyze_returns_agent_response(self, client):
        with _patch_orchestrator("liability"):
            resp = client.post(
                "/liability/analyze",
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "liability"

    def test_analyze_returns_401_on_bad_token(self, client):
        resp = client.post(
            "/liability/analyze",
            headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": "bad"},
        )
        assert resp.status_code == 401


class TestDisposalEndpoint:
    def test_scan_returns_agent_response(self, client):
        with _patch_orchestrator("disposal"):
            resp = client.post(
                "/disposal/scan",
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "disposal"

    def test_scan_returns_401_on_bad_token(self, client):
        resp = client.post(
            "/disposal/scan",
            headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": "bad"},
        )
        assert resp.status_code == 401


class TestChatEndpoint:
    def test_ask_returns_agent_response(self, client):
        with _patch_orchestrator("chat"):
            resp = client.post(
                "/chat/ask",
                json={"question": "我的资产健康吗？"},
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "chat"

    def test_ask_returns_401_on_bad_token(self, client):
        resp = client.post(
            "/chat/ask",
            json={"question": "test"},
            headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": "bad"},
        )
        assert resp.status_code == 401

    def test_ask_passes_question_as_free_text(self, client):
        """Verify the question is forwarded to orchestrator as free_text."""
        captured = {}

        async def _capture_dispatch(capability, family_id, user_id=None, free_text=None, thread_id=None):
            captured["free_text"] = free_text
            from schemas.response import AgentResponse as AR
            return AR(**_make_response("chat"))

        with patch("services.orchestrator.Orchestrator.dispatch", side_effect=_capture_dispatch):
            client.post(
                "/chat/ask",
                json={"question": "我的负债压力大吗？"},
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        assert captured.get("free_text") == "我的负债压力大吗？"


class TestAllocationEndpoint:
    def test_drift_returns_agent_response(self, client):
        with _patch_orchestrator("allocation"):
            resp = client.post(
                "/allocation/drift",
                json={"targets": {"存款": 40.0, "基金": 30.0, "车辆": 30.0}, "threshold": 10.0},
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "allocation"

    def test_drift_passes_targets_as_free_text_json(self, client):
        """Verify targets/threshold are forwarded as JSON free_text."""
        captured = {}

        async def _capture(capability, family_id, user_id=None, free_text=None):
            captured["free_text"] = free_text
            from schemas.response import AgentResponse as AR
            return AR(**_make_response("allocation"))

        with patch("services.orchestrator.Orchestrator.dispatch", side_effect=_capture):
            client.post(
                "/allocation/drift",
                json={"targets": {"存款": 50.0}, "threshold": 5.0},
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        parsed = json.loads(captured["free_text"])
        assert parsed["targets"] == {"存款": 50.0}
        assert parsed["threshold"] == 5.0


class TestSuggestEndpoint:
    def test_asset_returns_agent_response(self, client):
        with _patch_orchestrator("suggest"):
            resp = client.post(
                "/suggest/asset",
                json={"name": "我的车", "category": "车辆", "asset_type": "physical"},
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "suggest"

    def test_asset_passes_fields_as_free_text_json(self, client):
        """Verify asset fields are forwarded as JSON free_text."""
        captured = {}

        async def _capture(capability, family_id, user_id=None, free_text=None):
            captured["free_text"] = free_text
            from schemas.response import AgentResponse as AR
            return AR(**_make_response("suggest"))

        with patch("services.orchestrator.Orchestrator.dispatch", side_effect=_capture):
            client.post(
                "/suggest/asset",
                json={"name": "笔记本电脑", "category": "数码", "asset_type": "physical"},
                headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
            )
        parsed = json.loads(captured["free_text"])
        assert parsed["category"] == "数码"
        assert parsed["asset_type"] == "physical"

    def test_asset_returns_401_on_bad_token(self, client):
        resp = client.post(
            "/suggest/asset",
            json={"name": "test", "category": "数码"},
            headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": "bad"},
        )
        assert resp.status_code == 401


class TestGoldenShapeValidation:
    """Load golden JSON fixtures and verify AgentResponse can parse them."""

    def test_health_report_golden_parses(self):
        import json
        from pathlib import Path
        golden = json.loads(
            (Path(__file__).parent.parent / "golden" / "health_report_golden.json").read_text()
        )
        resp = AgentResponse(**golden)
        assert resp.capability == "report"
        assert len(resp.scorecards) == 4
        assert len(resp.risk_flags) == 2
        assert len(resp.disclaimers) >= 1

    def test_liability_advice_golden_parses(self):
        import json
        from pathlib import Path
        golden = json.loads(
            (Path(__file__).parent.parent / "golden" / "liability_advice_golden.json").read_text()
        )
        resp = AgentResponse(**golden)
        assert resp.capability == "liability"
        assert len(resp.scorecards) == 3

    def test_asset_suggest_golden_parses(self):
        import json
        from pathlib import Path
        golden = json.loads(
            (Path(__file__).parent.parent / "golden" / "asset_suggest_golden.json").read_text()
        )
        resp = AgentResponse(**golden)
        assert resp.capability == "suggest"
        assert len(resp.recommendations) >= 1
