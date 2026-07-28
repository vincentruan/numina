"""Tests for the literacy scenario generation service (U2)."""
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.backend.app.services import literacy_scenario as svc
from apps.backend.app.services.literacy_scenario import (
    _build_fallback_content,
    _get_age_group,
    _growth_dimensions,
    _select_template,
    _sunday_of,
    generate_weekly_scenario,
)
from packages.db.models.literacy_badge import LiteracyBadge, LiteracyBadgeDefinition
from packages.db.models.literacy_scenario import (
    LiteracyScenario,
    LiteracyScenarioTemplate,
)

# ---------------------------------------------------------------------------
# Helpers: factories that build model instances without needing the DB fixture
# (used for pure-logic tests). Model instances are not persisted here.
# ---------------------------------------------------------------------------

def _make_template(**overrides):
    defaults = dict(
        id=1,
        dimension="saving",
        age_group="mid",
        story_template="小兔子想存钱买胡萝卜……",
        choices_json=json.dumps(
            [{"label": "每天存一点", "feedback": "很好！"}, {"label": "全部花掉", "feedback": "要注意预算哦"}],
            ensure_ascii=False,
        ),
        is_active=True,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_child(*, child_id=100, family_id=10, birthday=None):
    return SimpleNamespace(id=child_id, family_id=family_id, birthday=birthday)


# ---------------------------------------------------------------------------
# _sunday_of
# ---------------------------------------------------------------------------


class TestSundayOf:
    def test_sunday_returns_same_day(self):
        # 2026-07-26 is a Sunday
        assert _sunday_of(date(2026, 7, 26)) == date(2026, 7, 26)

    def test_monday_returns_previous_sunday(self):
        assert _sunday_of(date(2026, 7, 27)) == date(2026, 7, 26)

    def test_saturday_returns_previous_sunday(self):
        # 2026-08-01 is a Saturday
        assert _sunday_of(date(2026, 8, 1)) == date(2026, 7, 26)


# ---------------------------------------------------------------------------
# _get_age_group
# ---------------------------------------------------------------------------


class TestGetAgeGroup:
    def test_unknown_birthday_defaults_to_mid(self):
        assert _get_age_group(None, reference=date(2026, 7, 28)) == "mid"

    def test_age_6_is_low(self):
        birthday = date(2020, 1, 1)  # 6 years old on 2026-07-28
        assert _get_age_group(birthday, reference=date(2026, 7, 28)) == "low"

    def test_age_7_is_low(self):
        birthday = date(2019, 1, 1)  # 7
        assert _get_age_group(birthday, reference=date(2026, 7, 28)) == "low"

    def test_age_8_is_mid(self):
        birthday = date(2018, 1, 1)
        assert _get_age_group(birthday, reference=date(2026, 7, 28)) == "mid"

    def test_age_10_is_mid(self):
        birthday = date(2016, 1, 1)
        assert _get_age_group(birthday, reference=date(2026, 7, 28)) == "mid"

    def test_age_11_is_high(self):
        birthday = date(2015, 1, 1)
        assert _get_age_group(birthday, reference=date(2026, 7, 28)) == "high"

    def test_birthday_not_yet_passed_this_year(self):
        # Reference date before birthday in the calendar year → age is one less.
        birthday = date(2018, 12, 1)  # would be 8, but on 2026-07-28 still 7
        assert _get_age_group(birthday, reference=date(2026, 7, 28)) == "low"


# ---------------------------------------------------------------------------
# _select_template / _growth_dimensions (DB-backed)
# ---------------------------------------------------------------------------


@pytest.fixture
def template_low_saving(db):
    t = LiteracyScenarioTemplate(
        id=1001,
        dimension="saving",
        age_group="low",
        story_template="故事A",
        choices_json="[]",
        is_active=True,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def template_low_earning(db):
    t = LiteracyScenarioTemplate(
        id=1002,
        dimension="earning",
        age_group="low",
        story_template="故事B",
        choices_json="[]",
        is_active=True,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def template_low_inactive(db):
    t = LiteracyScenarioTemplate(
        id=1003,
        dimension="investing",
        age_group="low",
        story_template="故事C",
        choices_json="[]",
        is_active=False,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


class TestSelectTemplate:
    def test_returns_none_when_no_active_templates(self, db, test_family):
        assert _select_template(db, child_id=9999, age_group="low") is None

    def test_excludes_inactive_templates(self, db, template_low_inactive):
        assert _select_template(db, child_id=9999, age_group="low") is None

    def test_returns_active_template(self, db, template_low_saving):
        result = _select_template(db, child_id=9999, age_group="low")
        assert result is not None
        assert result.id == template_low_saving.id

    def test_excludes_recently_used_templates(self, db, template_low_saving, template_low_earning, test_family):
        # Mark saving as used last week → should be excluded.
        used_scenario = LiteracyScenario(
            id=1,
            child_id=9999,
            week_start=date(2026, 7, 19),  # last week (Sunday)
            template_id=template_low_saving.id,
            content_json="{}",
        )
        db.add(used_scenario)
        db.commit()

        result = _select_template(db, child_id=9999, age_group="low", reference=date(2026, 7, 28))
        assert result is not None
        assert result.id == template_low_earning.id

    def test_prefers_growth_dimensions(self, db, template_low_saving, template_low_earning):
        result = _select_template(
            db,
            child_id=9999,
            age_group="low",
            growth_dimensions=["earning"],
            reference=date(2026, 7, 28),
        )
        assert result is not None
        assert result.id == template_low_earning.id


class TestGrowthDimensions:
    def test_all_dimensions_when_no_badges(self, db):
        dims = _growth_dimensions(db, child_id=9999)
        assert set(dims) == {"earning", "saving", "investing", "giving"}

    def test_excludes_earned_dimension(self, db):
        defn = LiteracyBadgeDefinition(
            id=2001, dimension="saving", level=1, name="小存钱家", description="d", criteria_summary="c"
        )
        badge = LiteracyBadge(
            id=3001, child_id=9999, definition_id=defn.id, source="scenario"
        )
        db.add_all([defn, badge])
        db.commit()

        dims = _growth_dimensions(db, child_id=9999)
        assert "saving" not in dims
        assert "earning" in dims


# ---------------------------------------------------------------------------
# generate_weekly_scenario
# ---------------------------------------------------------------------------


@pytest.fixture
def child_user(db, test_family):
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    user = User(
        id=next_id(),
        username="lit_child",
        display_name="Lit Child",
        password_hash="x",
        family_id=test_family.id,
        birthday=date(2019, 5, 1),  # 7 years old on 2026-07-28 → low
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def active_template(db):
    t = LiteracyScenarioTemplate(
        id=4001,
        dimension="saving",
        age_group="low",
        story_template="原始故事模板",
        choices_json=json.dumps([{"label": "选择1", "feedback": "反馈1"}], ensure_ascii=False),
        is_active=True,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


class TestGenerateWeeklyScenario:
    @pytest.mark.asyncio
    async def test_idempotent_returns_existing(self, db, child_user, active_template):
        ref = date(2026, 7, 28)
        # First call creates.
        first = await generate_weekly_scenario(db, child_user, reference=ref)
        assert first.child_id == child_user.id

        # Second call returns the same row.
        second = await generate_weekly_scenario(db, child_user, reference=ref)
        assert second.id == first.id

    @pytest.mark.asyncio
    async def test_llm_success_personalises_content(self, db, child_user, active_template):
        ref = date(2026, 7, 28)
        llm_response = {"story": "个性化故事", "choices": [{"label": "A", "feedback": "好"}]}

        with patch(
            "apps.backend.app.services.literacy_scenario._enrich_with_llm",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            scenario = await generate_weekly_scenario(db, child_user, reference=ref)

        content = json.loads(scenario.content_json)
        assert content["story"] == "个性化故事"
        assert scenario.template_id == active_template.id

    @pytest.mark.asyncio
    async def test_llm_failure_uses_template_verbatim(self, db, child_user, active_template):
        ref = date(2026, 7, 28)

        with patch(
            "apps.backend.app.services.literacy_scenario._enrich_with_llm",
            new_callable=AsyncMock,
            return_value=None,
        ):
            scenario = await generate_weekly_scenario(db, child_user, reference=ref)

        content = json.loads(scenario.content_json)
        assert content["story"] == active_template.story_template
        assert scenario.template_id == active_template.id

    @pytest.mark.asyncio
    async def test_no_template_returns_fallback(self, db, child_user):
        ref = date(2026, 7, 28)
        scenario = await generate_weekly_scenario(db, child_user, reference=ref)

        content = json.loads(scenario.content_json)
        assert content["story"] == _build_fallback_content()["story"]
        assert scenario.template_id == 0

    @pytest.mark.asyncio
    async def test_week_start_is_sunday(self, db, child_user, active_template):
        ref = date(2026, 7, 28)  # Tuesday
        scenario = await generate_weekly_scenario(db, child_user, reference=ref)
        assert scenario.week_start == date(2026, 7, 26)  # Sunday


# ---------------------------------------------------------------------------
# _enrich_with_llm
# ---------------------------------------------------------------------------


class TestEnrichWithLlm:
    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        template = _make_template()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("boom")

        with patch(
            "apps.backend.app.services.agent_client.AgentClient",
        ) as mock_cls:
            instance = MagicMock()
            instance.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = instance
            result = await svc._enrich_with_llm(family_id=1, child_id=2, template=template)

        assert result is None

    @pytest.mark.asyncio
    async def test_parses_envelope(self):
        template = _make_template()
        llm_payload = {"data": {"story": " enriched", "choices": [{"label": "x", "feedback": "y"}]}}

        with patch(
            "apps.backend.app.services.agent_client.AgentClient",
        ) as mock_cls:
            instance = MagicMock()
            resp = MagicMock()
            resp.json.return_value = llm_payload
            resp.raise_for_status.return_value = None
            instance.post = AsyncMock(return_value=resp)
            mock_cls.return_value = instance
            result = await svc._enrich_with_llm(family_id=1, child_id=2, template=template)

        assert result is not None
        assert result["story"] == " enriched"

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_shape(self):
        template = _make_template()
        llm_payload = {"data": {"choices": []}}  # missing story, empty choices

        with patch(
            "apps.backend.app.services.agent_client.AgentClient",
        ) as mock_cls:
            instance = MagicMock()
            resp = MagicMock()
            resp.json.return_value = llm_payload
            resp.raise_for_status.return_value = None
            instance.post = AsyncMock(return_value=resp)
            mock_cls.return_value = instance
            result = await svc._enrich_with_llm(family_id=1, child_id=2, template=template)

        assert result is None
