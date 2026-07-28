"""Tests for U9 literacy scenario template seeding and AI batch generation."""
from __future__ import annotations

import json

import pytest

from apps.backend.app.services.literacy_scenario_templates import (
    MIN_TEMPLATES_PER_SLOT,
    VALID_AGE_GROUPS,
    VALID_DIMENSIONS,
    _find_gaps,
    _validate_generated_template,
    generate_templates_batch,
    seed_templates,
)
from packages.db.models.literacy_scenario import LiteracyScenarioTemplate


class TestSeedTemplates:
    """Tests for seed_templates()."""

    def test_seed_inserts_12_templates(self, db):
        """First call should insert exactly 12 templates (4 dims x 3 age groups)."""
        count = seed_templates(db)
        assert count == 12

        all_templates = db.query(LiteracyScenarioTemplate).all()
        assert len(all_templates) == 12

    def test_seed_is_idempotent(self, db):
        """Calling seed_templates twice should not create duplicates."""
        first = seed_templates(db)
        assert first == 12

        second = seed_templates(db)
        assert second == 0

        all_templates = db.query(LiteracyScenarioTemplate).all()
        assert len(all_templates) == 12

    def test_seed_covers_all_dimension_age_combinations(self, db):
        """Each of the 12 (dimension, age_group) combinations should be present."""
        seed_templates(db)

        templates = db.query(LiteracyScenarioTemplate).all()
        combos = {(t.dimension, t.age_group) for t in templates}
        expected = {(d, a) for d in VALID_DIMENSIONS for a in VALID_AGE_GROUPS}
        assert combos == expected

    def test_seed_templates_are_active(self, db):
        """All seeded templates should have is_active=True."""
        seed_templates(db)

        templates = db.query(LiteracyScenarioTemplate).filter_by(is_active=True).all()
        assert len(templates) == 12

    def test_seed_choices_json_is_valid(self, db):
        """Every seeded template's choices_json should be parseable with 2-4 choices."""
        seed_templates(db)

        for tmpl in db.query(LiteracyScenarioTemplate).all():
            choices = json.loads(tmpl.choices_json)
            assert isinstance(choices, list)
            assert 2 <= len(choices) <= 4, f"{tmpl.dimension}/{tmpl.age_group} has {len(choices)} choices"
            for choice in choices:
                assert "text" in choice
                assert "feedback" in choice
                assert "dimension_signal" in choice
                assert choice["dimension_signal"] == tmpl.dimension


class TestFindGaps:
    """Tests for _find_gaps()."""

    def test_empty_db_has_all_gaps(self, db):
        """With no templates, all 12 slots should be reported as gaps."""
        gaps = _find_gaps(db)
        assert len(gaps) == 12

    def test_seeded_db_has_no_gaps(self, db):
        """After seeding (1 per slot), each slot still needs 2 more (MIN=3)."""
        seed_templates(db)
        gaps = _find_gaps(db)
        # Each of 12 slots has 1 template, MIN is 3 → all 12 are still gaps
        assert len(gaps) == 12

    def test_slot_with_enough_templates_not_reported(self, db):
        """A slot with >= MIN_TEMPLATES_PER_SLOT templates should not be a gap."""
        seed_templates(db)
        # Add 2 more templates for earning/low to reach MIN_TEMPLATES_PER_SLOT
        for i in range(MIN_TEMPLATES_PER_SLOT - 1):
            db.add(LiteracyScenarioTemplate(
                dimension="earning",
                age_group="low",
                story_template=f"extra template {i}",
                choices_json=json.dumps([
                    {"text": "A", "feedback": "ok", "dimension_signal": "earning"},
                    {"text": "B", "feedback": "ok", "dimension_signal": "earning"},
                ], ensure_ascii=False),
                is_active=True,
            ))
        db.commit()

        gaps = _find_gaps(db)
        assert ("earning", "low") not in gaps
        assert len(gaps) == 11  # 12 - 1 filled slot


class TestValidateGeneratedTemplate:
    """Tests for _validate_generated_template()."""

    def test_valid_template_passes(self):
        data = {
            "story_template": "小明有5个星币...",
            "choices": [
                {"text": "选项A", "feedback": "好选择", "dimension_signal": "earning"},
                {"text": "选项B", "feedback": "也不错", "dimension_signal": "earning"},
            ],
        }
        assert _validate_generated_template(data, "earning") is True

    def test_missing_story_fails(self):
        data = {
            "choices": [
                {"text": "A", "feedback": "ok", "dimension_signal": "earning"},
                {"text": "B", "feedback": "ok", "dimension_signal": "earning"},
            ],
        }
        assert _validate_generated_template(data, "earning") is False

    def test_too_few_choices_fails(self):
        data = {
            "story_template": "故事",
            "choices": [
                {"text": "A", "feedback": "ok", "dimension_signal": "earning"},
            ],
        }
        assert _validate_generated_template(data, "earning") is False

    def test_too_many_choices_fails(self):
        data = {
            "story_template": "故事",
            "choices": [
                {"text": f"opt{i}", "feedback": "ok", "dimension_signal": "earning"}
                for i in range(5)
            ],
        }
        assert _validate_generated_template(data, "earning") is False

    def test_wrong_dimension_signal_fails(self):
        data = {
            "story_template": "故事",
            "choices": [
                {"text": "A", "feedback": "ok", "dimension_signal": "choosing"},
                {"text": "B", "feedback": "ok", "dimension_signal": "earning"},
            ],
        }
        assert _validate_generated_template(data, "earning") is False

    def test_non_dict_input_fails(self):
        assert _validate_generated_template("not a dict", "earning") is False
        assert _validate_generated_template([], "earning") is False


class TestGenerateTemplatesBatch:
    """Tests for generate_templates_batch() (mocked LLM)."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_gaps(self, db):
        """When all slots have enough templates, should return empty list."""
        # Fill every slot to MIN_TEMPLATES_PER_SLOT
        for dim in VALID_DIMENSIONS:
            for age in VALID_AGE_GROUPS:
                for i in range(MIN_TEMPLATES_PER_SLOT):
                    db.add(LiteracyScenarioTemplate(
                        dimension=dim,
                        age_group=age,
                        story_template=f"template {i}",
                        choices_json=json.dumps([
                            {"text": "A", "feedback": "ok", "dimension_signal": dim},
                            {"text": "B", "feedback": "ok", "dimension_signal": dim},
                        ], ensure_ascii=False),
                        is_active=True,
                    ))
        db.commit()

        result = await generate_templates_batch(db, family_id=1, user_id=1)
        assert result == []

    @pytest.mark.asyncio
    async def test_generated_template_has_valid_choices_json(self, db, monkeypatch):
        """Generated templates should have parseable choices_json with 2-4 entries."""
        from apps.backend.app.services import literacy_scenario_templates as mod

        valid_data = {
            "story_template": "AI生成的故事",
            "choices": [
                {"text": "选择1", "feedback": "反馈1", "dimension_signal": "earning"},
                {"text": "选择2", "feedback": "反馈2", "dimension_signal": "earning"},
                {"text": "选择3", "feedback": "反馈3", "dimension_signal": "earning"},
            ],
        }

        class FakeResp:
            def raise_for_status(self): ...
            def json(self):
                return {"data": valid_data}

        class FakeClient:
            def __init__(self, **kwargs): ...
            async def post(self, endpoint, json=None):
                return FakeResp()

        monkeypatch.setattr(mod, "AgentClient", FakeClient, raising=False)
        # Also patch the deferred import path
        import apps.backend.app.services.agent_client as ac_mod
        monkeypatch.setattr(ac_mod, "AgentClient", FakeClient)

        result = await generate_templates_batch(db, family_id=1, user_id=1)
        # Should have generated at least 1 (there are gaps on a fresh db)
        assert len(result) > 0

        for tmpl in result:
            assert tmpl["dimension"] in VALID_DIMENSIONS
            assert tmpl["age_group"] in VALID_AGE_GROUPS
            choices = json.loads(tmpl["choices_json"])
            assert isinstance(choices, list)
            assert 2 <= len(choices) <= 4

    @pytest.mark.asyncio
    async def test_skips_invalid_llm_response(self, db, monkeypatch):
        """When LLM returns invalid data, that slot should be skipped (not crash)."""
        from apps.backend.app.services import literacy_scenario_templates as mod

        class FakeResp:
            def raise_for_status(self): ...
            def json(self):
                return {"data": "not valid json object"}

        class FakeClient:
            def __init__(self, **kwargs): ...
            async def post(self, endpoint, json=None):
                return FakeResp()

        monkeypatch.setattr(mod, "AgentClient", FakeClient, raising=False)
        import apps.backend.app.services.agent_client as ac_mod
        monkeypatch.setattr(ac_mod, "AgentClient", FakeClient)

        result = await generate_templates_batch(db, family_id=1, user_id=1)
        # All LLM calls return invalid data → nothing generated
        assert result == []
