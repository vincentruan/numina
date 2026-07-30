"""Shared pytest fixtures for agent test suite.

Provides:
- mock_backend_client: returns canned family data, no real HTTP calls
- mock_deerflow_client: returns a fixed JSON string response
- test_app: FastAPI test application with mocked dependencies
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.agent.golden.fixtures import REDACTED_CONTEXT

# ── Canned backend data ────────────────────────────────────────────────────────

_AI_CONFIG = {
    "ai_enabled": True,
    "ai_provider": "anthropic",
    "api_key": "sk-test-fixture",
    "allowed_capabilities": [],
    "admin_only_capabilities": [],
    "member_role": "member",
}

_DEERFLOW_RESPONSE = json.dumps({
    "summary": "DeerFlow 测试响应",
    "scorecards": [
        {"name": "综合健康", "score": 3.5, "max_score": 5.0, "label": "较好", "color": "green"}
    ],
    "risk_flags": [],
    "recommendations": [],
    "rule_based_findings": [{"source": "rule", "content": "测试规则结论", "confidence": 1.0}],
    "ai_inferences": [{"source": "ai", "content": "测试 AI 推断", "confidence": 0.6}],
    "disclaimers": ["本分析仅供测试"],
})


@pytest.fixture
def mock_backend_client():
    """BackendClient that returns canned data without making HTTP calls."""
    with patch("apps.agent.services.orchestrator.BackendClient") as MockClient:
        instance = MockClient.return_value
        instance.get_family_ai_config = AsyncMock(return_value=_AI_CONFIG)
        instance.get_liabilities = AsyncMock(return_value=REDACTED_CONTEXT.liabilities)
        instance.get_dashboard_overview = AsyncMock(return_value=REDACTED_CONTEXT.dashboard_overview)
        instance.get_dashboard_allocation = AsyncMock(return_value=REDACTED_CONTEXT.dashboard_allocation)
        instance.get_dashboard_trend = AsyncMock(return_value=REDACTED_CONTEXT.dashboard_trend)
        instance.get_dashboard_low_usage = AsyncMock(return_value=REDACTED_CONTEXT.low_usage_assets)
        yield instance


@pytest.fixture
def mock_deerflow_client():
    """DeerFlowAdapter that returns a fixed JSON string without calling DeerFlow."""
    mock = MagicMock()
    mock.dispatch = AsyncMock(return_value=_DEERFLOW_RESPONSE)
    return mock


@pytest.fixture
def test_app():
    """FastAPI test application instance."""
    from apps.agent.app.main import app
    return app
