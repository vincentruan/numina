"""Tests for literacy MCP tool handlers in MCPSession.call_tool."""
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession


@pytest.fixture
def mock_db():
    return MagicMock()


def _patch_session(mock_db):
    """Return nested patches for SessionLocal and _get_caller_user."""
    sl = patch("apps.backend.app.services.mcp_session.SessionLocal")
    gu = patch("apps.backend.app.services.mcp_session._get_caller_user")
    return sl, gu


# ---------------------------------------------------------------------------
# get_child_literacy_profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_child_literacy_profile_returns_children(mock_db):
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")

    # Mock child user
    child = MagicMock(id=200, display_name="小宝", birthday=date(2018, 5, 1))
    # Mock query chain for User filter
    mock_user_query = MagicMock()
    mock_user_query.filter.return_value = mock_user_query
    mock_user_query.all.return_value = [child]

    # Mock badge query chain
    mock_badge_query = MagicMock()
    mock_badge_query.join.return_value = mock_badge_query
    mock_badge_query.filter.return_value = mock_badge_query
    badge_def = MagicMock(dimension="reading", level=1, name="阅读新手")
    mock_badge_query.all.return_value = [badge_def]

    # Mock scenario count query
    mock_scenario_query = MagicMock()
    mock_scenario_query.filter.return_value = mock_scenario_query
    mock_scenario_query.scalar.return_value = 5

    # Mock latest report query
    mock_report_query = MagicMock()
    mock_report_query.filter.return_value = mock_report_query
    mock_report_query.order_by.return_value = mock_report_query
    mock_report_query.first.return_value = (date(2026, 7, 20),)

    # db.query returns different mocks based on call order
    mock_db.query.side_effect = [
        mock_user_query,       # User query
        mock_badge_query,      # LiteracyBadgeDefinition query
        mock_scenario_query,   # func.count(LiteracyScenario.id) query
        mock_report_query,     # LiteracyWeeklyReport.week_start query
    ]

    sl_patch, gu_patch = _patch_session(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = MagicMock(id="u1", family_id="100")

        with patch(
            "apps.backend.app.services.literacy_report._get_age_group",
            return_value="6-8",
        ):
            result = await session.call_tool("get_child_literacy_profile", {})

    payload = json.loads(result[0].text)
    assert "children" in payload
    assert len(payload["children"]) == 1
    c = payload["children"][0]
    assert c["child_id"] == "200"
    assert c["display_name"] == "小宝"
    assert c["age_group"] == "6-8"
    assert c["total_scenarios_completed"] == 5
    assert c["latest_report_week"] == "2026-07-20"
    assert len(c["current_badges"]) == 1
    assert c["current_badges"][0]["dimension"] == "reading"


@pytest.mark.asyncio
async def test_get_child_literacy_profile_no_children(mock_db):
    """When no children exist, returns empty list."""
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")

    mock_user_query = MagicMock()
    mock_user_query.filter.return_value = mock_user_query
    mock_user_query.all.return_value = []
    mock_db.query.return_value = mock_user_query

    sl_patch, gu_patch = _patch_session(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = MagicMock(id="u1", family_id="100")

        result = await session.call_tool("get_child_literacy_profile", {})

    payload = json.loads(result[0].text)
    assert payload == {"children": []}


# ---------------------------------------------------------------------------
# get_literacy_weekly_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_literacy_weekly_data_returns_signals_and_trend(mock_db):
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")

    current_signals = {
        "chores_total": 10,
        "chores_approved": 8,
        "chore_completion_rate": 0.8,
        "coin_earned": 50,
        "coin_spent": 10,
        "scenario_completed": True,
        "badges_earned": [],
    }
    prev_signals = {
        "chores_total": 6,
        "chores_approved": 4,
        "chore_completion_rate": 0.67,
        "coin_earned": 20,
        "coin_spent": 5,
        "scenario_completed": False,
        "badges_earned": [],
    }

    sl_patch, gu_patch = _patch_session(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = MagicMock(id="u1", family_id="100")

        with patch(
            "apps.backend.app.services.literacy_report._aggregate_signals",
            side_effect=[current_signals, prev_signals],
        ), patch(
            "apps.backend.app.services.literacy_report._sunday_of",
            return_value=date(2026, 7, 26),
        ):
            result = await session.call_tool(
                "get_literacy_weekly_data",
                {"child_id": "200", "week_start": "2026-07-26"},
            )

    payload = json.loads(result[0].text)
    assert payload["child_id"] == "200"
    assert payload["week_start"] == "2026-07-26"
    assert payload["chores_approved"] == 8
    assert payload["coin_earned"] == 50
    assert payload["trend"]["chores_delta"] == 4   # 8 - 4
    assert payload["trend"]["coins_delta"] == 30    # 50 - 20
    assert payload["trend"]["scenario_was_completed_prev"] is False


@pytest.mark.asyncio
async def test_get_literacy_weekly_data_rejects_child_from_other_family(mock_db):
    """get_literacy_weekly_data rejects child_id from a different family."""
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")

    # Mock the child-in-family validation query to return None (child not in family)
    mock_child_query = MagicMock()
    mock_child_query.filter.return_value = mock_child_query
    mock_child_query.first.return_value = None
    mock_db.query.return_value = mock_child_query

    sl_patch, gu_patch = _patch_session(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = MagicMock(id="u1", family_id="100")

        result = await session.call_tool(
            "get_literacy_weekly_data",
            {"child_id": "999", "week_start": "2026-07-26"},
        )

    payload = json.loads(result[0].text)
    assert "error" in payload
    assert payload["error"] == "孩子不属于当前家庭"
    assert payload["child_id"] == "999"
