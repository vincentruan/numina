"""Tests for the literacy report generation service."""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.backend.app.models.chore import ChoreInstance
from apps.backend.app.models.coin_transaction import CoinTransaction
from apps.backend.app.models.user import User
from apps.backend.app.services.literacy_report import (
    _aggregate_signals,
    _build_fallback_narrative,
    _build_report_narrative,
    _get_age_group,
    _sunday_of,
    generate_weekly_report,
)
from apps.backend.app.utils.snowflake import next_id

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_family(db):
    from apps.backend.app.models.family import Family

    family = Family(id=next_id(), name="Report Test Family", created_by=next_id())
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


@pytest.fixture
def child_user(db, test_family):
    user = User(
        id=next_id(),
        username="report_child",
        display_name="Report Child",
        password_hash="test_hash",
        family_id=test_family.id,
        role="child",
        birthday=date(2018, 6, 15),  # ~8 years old → "mid"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def week_start():
    """Sunday of the current week."""
    return _sunday_of(date.today())


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestSundayOf:
    def test_sunday_returns_same_day(self):
        # 2026-07-26 is a Sunday
        d = date(2026, 7, 26)
        assert _sunday_of(d) == d

    def test_monday_goes_back_one(self):
        # 2026-07-27 is a Monday → should go back 1 day to Sunday 07-26
        d = date(2026, 7, 27)
        assert _sunday_of(d) == date(2026, 7, 26)

    def test_saturday_goes_back_six(self):
        # 2026-08-01 is a Saturday → go back 6 days to Sunday 07-26
        d = date(2026, 8, 1)
        assert _sunday_of(d) == date(2026, 7, 26)


class TestGetAgeGroup:
    def test_no_birthday_returns_mid(self):
        assert _get_age_group(None) == "mid"

    def test_young_child_returns_low(self):
        birthday = date.today().replace(year=date.today().year - 6)
        assert _get_age_group(birthday) == "low"

    def test_middle_child_returns_mid(self):
        birthday = date.today().replace(year=date.today().year - 9)
        assert _get_age_group(birthday) == "mid"

    def test_older_child_returns_high(self):
        birthday = date.today().replace(year=date.today().year - 12)
        assert _get_age_group(birthday) == "high"


# ---------------------------------------------------------------------------
# Signal aggregation
# ---------------------------------------------------------------------------


class TestAggregateSignals:
    def test_empty_signals(self, db, child_user, week_start):
        signals = _aggregate_signals(db, child_user.id, week_start)
        assert signals["chores_total"] == 0
        assert signals["chores_approved"] == 0
        assert signals["chore_completion_rate"] == 0.0
        assert signals["coin_earned"] == 0
        assert signals["coin_spent"] == 0
        assert signals["scenario_completed"] is False
        assert signals["badges_earned"] == []

    def test_with_approved_chores(self, db, child_user, test_family, week_start):
        # Create 2 chores: 1 approved, 1 available (different template_ids to satisfy uq)
        for i, status in enumerate(["approved", "available"]):
            ci = ChoreInstance(
                id=next_id(),
                template_id=next_id(),
                family_id=test_family.id,
                child_user_id=child_user.id,
                chore_name=f"Test Chore {i}",
                coin_reward=10,
                date_bucket=week_start.isoformat(),
                status=status,
            )
            db.add(ci)
        db.commit()

        signals = _aggregate_signals(db, child_user.id, week_start)
        assert signals["chores_total"] == 2
        assert signals["chores_approved"] == 1
        assert signals["chore_completion_rate"] == 0.5

    def test_with_coin_transactions(self, db, child_user, test_family, week_start):
        # Earn 50, spend 20
        db.add(CoinTransaction(
            id=next_id(), family_id=test_family.id,
            child_user_id=child_user.id, amount=50,
            transaction_type="chore_earn",
        ))
        db.add(CoinTransaction(
            id=next_id(), family_id=test_family.id,
            child_user_id=child_user.id, amount=-20,
            transaction_type="wish_spend",
        ))
        db.commit()

        signals = _aggregate_signals(db, child_user.id, week_start)
        assert signals["coin_earned"] == 50
        assert signals["coin_spent"] == 20


# ---------------------------------------------------------------------------
# Fallback narrative
# ---------------------------------------------------------------------------


class TestFallbackNarrative:
    def test_minimal_signals(self):
        signals = {
            "chores_total": 0,
            "chores_approved": 0,
            "chore_completion_rate": 0.0,
            "coin_earned": 0,
            "coin_spent": 0,
            "scenario_completed": False,
            "badges_earned": [],
        }
        narrative = _build_fallback_narrative(signals)
        assert "暂无家务" in narrative
        assert "下周加油" in narrative

    def test_with_activity(self):
        signals = {
            "chores_total": 3,
            "chores_approved": 2,
            "chore_completion_rate": 0.67,
            "coin_earned": 50,
            "coin_spent": 20,
            "scenario_completed": True,
            "badges_earned": [{"name": "储蓄小能手", "dimension": "saving"}],
        }
        narrative = _build_fallback_narrative(signals)
        assert "2/3" in narrative
        assert "50" in narrative
        assert "20" in narrative
        assert "储蓄小能手" in narrative


# ---------------------------------------------------------------------------
# LLM narrative
# ---------------------------------------------------------------------------


class TestBuildReportNarrative:
    @pytest.mark.asyncio
    async def test_llm_success(self):
        signals = {
            "chores_total": 3, "chores_approved": 2,
            "chore_completion_rate": 0.67,
            "coin_earned": 50, "coin_spent": 20,
            "scenario_completed": True,
            "badges_earned": [],
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": "这是一段温暖的周报告。"}
        mock_resp.raise_for_status = MagicMock()

        with patch("apps.backend.app.services.agent_client.AgentClient") as mock_cls:
            instance = MagicMock()
            instance.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = instance
            result = await _build_report_narrative(1, 2, signals, "mid")

        assert result == "这是一段温暖的周报告。"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_fallback(self):
        signals = {
            "chores_total": 0, "chores_approved": 0,
            "chore_completion_rate": 0.0,
            "coin_earned": 0, "coin_spent": 0,
            "scenario_completed": False,
            "badges_earned": [],
        }
        with patch("apps.backend.app.services.agent_client.AgentClient") as mock_cls:
            instance = MagicMock()
            instance.post = AsyncMock(side_effect=Exception("LLM down"))
            mock_cls.return_value = instance
            result = await _build_report_narrative(1, 2, signals, "mid")

        assert "暂无家务" in result


# ---------------------------------------------------------------------------
# generate_weekly_report
# ---------------------------------------------------------------------------


class TestGenerateWeeklyReport:
    @pytest.mark.asyncio
    async def test_generates_report(self, db, child_user, week_start):
        with patch(
            "packages.domain.literacy.service._build_report_narrative",
            new=AsyncMock(return_value="AI生成的周报内容"),
        ):
            report = await generate_weekly_report(db, child_user, week_start)

        assert report.child_id == child_user.id
        assert report.week_start == week_start
        assert report.narrative == "AI生成的周报内容"
        parsed = json.loads(report.report_json)
        assert "signals" in parsed
        assert "age_group" in parsed

    @pytest.mark.asyncio
    async def test_idempotent(self, db, child_user, week_start):
        with patch(
            "packages.domain.literacy.service._build_report_narrative",
            new=AsyncMock(return_value="first"),
        ):
            r1 = await generate_weekly_report(db, child_user, week_start)
        with patch(
            "packages.domain.literacy.service._build_report_narrative",
            new=AsyncMock(return_value="second"),
        ):
            r2 = await generate_weekly_report(db, child_user, week_start)

        assert r1.id == r2.id
        assert r2.narrative == "first"  # returns existing, not regenerated
