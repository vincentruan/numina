"""Tests for the literacy badge evaluation service (U3)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from apps.backend.app.models.child_economy_config import ChildEconomyConfig
from apps.backend.app.models.coin_transaction import CoinTransaction
from apps.backend.app.models.user import User
from apps.backend.app.services.literacy_badge import (
    _credit_badge_coins,
    _evaluate_with_llm,
    _extract_text,
    _get_current_badge,
    _get_next_definition,
    _parse_unlock,
    evaluate_badge_unlocks,
)
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.literacy_badge import LiteracyBadge, LiteracyBadgeDefinition

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def child(db, test_family):
    user = User(
        id=next_id(),
        username="badge_child",
        display_name="Badge Child",
        password_hash="test_hash",
        family_id=test_family.id,
        role="child",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def definitions(db):
    """Seed 4 dimensions × 3 levels = 12 definitions."""
    defs = []
    for dim in ("earning", "choosing", "waiting", "caring"):
        for level in (1, 2, 3):
            d = LiteracyBadgeDefinition(
                id=next_id(),
                dimension=dim,
                level=level,
                name=f"{dim}-L{level}",
                description=f"Desc {dim} L{level}",
                criteria_summary=f"Criteria for {dim} level {level}",
            )
            db.add(d)
            defs.append(d)
    db.commit()
    for d in defs:
        db.refresh(d)
    return {(d.dimension, d.level): d for d in defs}


@pytest.fixture
def economy_config_opt_in(db, test_family):
    cfg = ChildEconomyConfig(
        id=next_id(),
        family_id=test_family.id,
        literacy_badge_coin_enabled=True,
        literacy_badge_coin_amount=75,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@pytest.fixture
def economy_config_opt_out(db, test_family):
    cfg = ChildEconomyConfig(
        id=next_id(),
        family_id=test_family.id,
        literacy_badge_coin_enabled=False,
        literacy_badge_coin_amount=50,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


# ---------------------------------------------------------------------------
# _get_current_badge
# ---------------------------------------------------------------------------


class TestGetCurrentBadge:
    def test_no_badge_returns_none(self, db, child):
        assert _get_current_badge(db, child.id, "earning") is None

    def test_one_badge_returns_it(self, db, child, definitions):
        defn = definitions[("earning", 1)]
        badge = LiteracyBadge(
            id=next_id(),
            child_id=child.id,
            definition_id=defn.id,
            earned_at=datetime.now(tz=timezone.utc),
            source="scenario",
        )
        db.add(badge)
        db.commit()

        result = _get_current_badge(db, child.id, "earning")
        assert result is not None
        assert result[0].id == badge.id
        assert result[1].id == defn.id

    def test_superseded_badge_returns_next_highest(self, db, child, definitions):
        d1 = definitions[("earning", 1)]
        d2 = definitions[("earning", 2)]
        now = datetime.now(tz=timezone.utc)
        b1 = LiteracyBadge(
            id=next_id(),
            child_id=child.id,
            definition_id=d1.id,
            earned_at=now,
            superseded_at=now,  # superseded
            source="scenario",
        )
        b2 = LiteracyBadge(
            id=next_id(),
            child_id=child.id,
            definition_id=d2.id,
            earned_at=now,
            source="scenario",
        )
        db.add_all([b1, b2])
        db.commit()

        result = _get_current_badge(db, child.id, "earning")
        assert result is not None
        assert result[0].id == b2.id
        assert result[1].level == 2

    def test_all_superseded_returns_none(self, db, child, definitions):
        d1 = definitions[("earning", 1)]
        now = datetime.now(tz=timezone.utc)
        b1 = LiteracyBadge(
            id=next_id(),
            child_id=child.id,
            definition_id=d1.id,
            earned_at=now,
            superseded_at=now,
            source="scenario",
        )
        db.add(b1)
        db.commit()

        assert _get_current_badge(db, child.id, "earning") is None


# ---------------------------------------------------------------------------
# _get_next_definition
# ---------------------------------------------------------------------------


class TestGetNextDefinition:
    def test_level_0_finds_level_1(self, db, definitions):
        result = _get_next_definition(db, 0, "earning")
        assert result is not None
        assert result.level == 1
        assert result.dimension == "earning"

    def test_level_1_finds_level_2(self, db, definitions):
        result = _get_next_definition(db, 1, "choosing")
        assert result is not None
        assert result.level == 2

    def test_level_3_max_returns_none(self, db, definitions):
        assert _get_next_definition(db, 3, "waiting") is None

    def test_level_4_returns_none(self, db, definitions):
        assert _get_next_definition(db, 4, "earning") is None


# ---------------------------------------------------------------------------
# _parse_unlock
# ---------------------------------------------------------------------------


class TestParseUnlock:
    def test_true(self):
        assert _parse_unlock('{"unlock": true, "reason": "good"}') is True

    def test_false(self):
        assert _parse_unlock('{"unlock": false, "reason": "nope"}') is False

    def test_no_json(self):
        assert _parse_unlock("no json here") is False

    def test_empty(self):
        assert _parse_unlock("") is False

    def test_json_embedded_in_text(self):
        text = 'Here is my answer: {"unlock": true, "reason": "yep"} done'
        assert _parse_unlock(text) is True

    def test_malformed_json(self):
        assert _parse_unlock('{"unlock": true') is False


# ---------------------------------------------------------------------------
# evaluate_badge_unlocks
# ---------------------------------------------------------------------------


class TestEvaluateBadgeUnlocks:
    async def test_no_current_badge_evaluates_for_lv1(
        self, db, child, definitions
    ):
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            new=AsyncMock(return_value=True),
        ):
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )
        # Should unlock up to 4 badges (one per dimension, all at Lv1).
        assert len(unlocked) == 4
        for badge in unlocked:
            assert badge.definition_id in {
                d.id for d in definitions.values() if d.level == 1
            }

    async def test_current_lv1_unlocks_lv2_supersedes_lv1(
        self, db, child, definitions
    ):
        # Seed Lv1 earning badge.
        d1 = definitions[("earning", 1)]
        existing = LiteracyBadge(
            id=next_id(),
            child_id=child.id,
            definition_id=d1.id,
            earned_at=datetime.now(tz=timezone.utc),
            source="scenario",
        )
        db.add(existing)
        db.commit()

        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            new=AsyncMock(return_value=True),
        ):
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )

        # Earning should be Lv2 now (Lv1 superseded); the other 3 dims at Lv1.
        assert len(unlocked) == 4
        db.refresh(existing)
        assert existing.superseded_at is not None

        earning_new = [
            b for b in unlocked if b.definition_id == definitions[("earning", 2)].id
        ]
        assert len(earning_new) == 1

    async def test_already_at_max_no_evaluation(self, db, child, definitions):
        # Seed Lv3 for all 4 dimensions.
        for dim in ("earning", "choosing", "waiting", "caring"):
            d3 = definitions[(dim, 3)]
            db.add(
                LiteracyBadge(
                    id=next_id(),
                    child_id=child.id,
                    definition_id=d3.id,
                    earned_at=datetime.now(tz=timezone.utc),
                    source="scenario",
                )
            )
        db.commit()

        eval_mock = AsyncMock(return_value=True)
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            eval_mock,
        ):
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )
        assert unlocked == []
        eval_mock.assert_not_called()

    async def test_llm_negative_no_badge_created(self, db, child, definitions):
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            new=AsyncMock(return_value=False),
        ):
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )
        assert unlocked == []
        assert db.query(LiteracyBadge).count() == 0

    async def test_chore_approved_only_evaluates_earning(
        self, db, child, definitions
    ):
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            new=AsyncMock(return_value=True),
        ) as eval_mock:
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="chore_approved"
            )
        # Only earning should have been evaluated.
        assert len(unlocked) == 1
        assert unlocked[0].definition_id == definitions[("earning", 1)].id

        # The LLM should only have been called once with dimension="earning".
        eval_mock.assert_called_once()
        call_kwargs = eval_mock.call_args.kwargs
        assert call_kwargs["dimension"] == "earning"

    async def test_scenario_completed_evaluates_all_4(
        self, db, child, definitions
    ):
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            new=AsyncMock(return_value=True),
        ) as eval_mock:
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )
        assert len(unlocked) == 4
        dims_evaluated = {call.kwargs["dimension"] for call in eval_mock.call_args_list}
        assert dims_evaluated == {"earning", "choosing", "waiting", "caring"}

    async def test_family_opted_out_no_coins(
        self, db, child, definitions, economy_config_opt_out
    ):
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            new=AsyncMock(return_value=True),
        ):
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )
        assert len(unlocked) == 4
        # No coin transactions written.
        assert (
            db.query(CoinTransaction)
            .filter(CoinTransaction.child_user_id == child.id)
            .count()
            == 0
        )

    async def test_family_opted_in_custom_amount_credits_coins(
        self, db, child, definitions, economy_config_opt_in
    ):
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            new=AsyncMock(return_value=True),
        ):
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )
        assert len(unlocked) == 4
        txs = (
            db.query(CoinTransaction)
            .filter(
                CoinTransaction.child_user_id == child.id,
                CoinTransaction.transaction_type == "badge_earn",
            )
            .all()
        )
        assert len(txs) == 4
        for tx in txs:
            assert tx.amount == 75
            assert tx.family_id == child.family_id

    async def test_idempotent_does_not_duplicate(
        self, db, child, definitions
    ):
        # Pre-seed earning Lv1 AND Lv2 — current is Lv2, so next would be Lv3.
        # But we also pre-seed earning Lv3, so the idempotency guard skips it.
        for level in (1, 2, 3):
            d = definitions[("earning", level)]
            badge = LiteracyBadge(
                id=next_id(),
                child_id=child.id,
                definition_id=d.id,
                earned_at=datetime.now(tz=timezone.utc),
                superseded_at=datetime.now(tz=timezone.utc) if level < 3 else None,
                source="scenario",
            )
            db.add(badge)
        db.commit()

        # LLM always returns True — but earning Lv3 already exists.
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_with_llm",
            new=AsyncMock(return_value=True),
        ):
            unlocked = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )
        # Earning should NOT appear (already at max via existing badges); only 3 new.
        assert len(unlocked) == 3
        earned_def_ids = {b.definition_id for b in unlocked}
        for level in (1, 2, 3):
            assert definitions[("earning", level)].id not in earned_def_ids

    async def test_error_does_not_crash(self, db, child, definitions):
        """Any exception in evaluation returns empty list instead of raising."""
        with patch(
            "apps.backend.app.services.literacy_badge._evaluate_impl",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await evaluate_badge_unlocks(
                db, child, trigger="scenario_completed"
            )
        assert result == []


# ---------------------------------------------------------------------------
# _credit_badge_coins
# ---------------------------------------------------------------------------


class TestCreditBadgeCoins:
    def test_opt_in_creates_transaction(
        self, db, child, definitions, economy_config_opt_in
    ):
        d1 = definitions[("earning", 1)]
        badge = LiteracyBadge(
            id=next_id(),
            child_id=child.id,
            definition_id=d1.id,
            earned_at=datetime.now(tz=timezone.utc),
            source="scenario",
        )
        db.add(badge)
        db.commit()
        db.refresh(badge)

        _credit_badge_coins(db, child, badge, d1)
        db.flush()

        tx = (
            db.query(CoinTransaction)
            .filter(
                CoinTransaction.child_user_id == child.id,
                CoinTransaction.transaction_type == "badge_earn",
            )
            .one()
        )
        assert tx.amount == 75
        assert tx.ref_id == badge.id
        assert tx.narrative_emoji == "🏅"

    def test_opt_out_creates_no_transaction(
        self, db, child, definitions, economy_config_opt_out
    ):
        d1 = definitions[("earning", 1)]
        badge = LiteracyBadge(
            id=next_id(),
            child_id=child.id,
            definition_id=d1.id,
            earned_at=datetime.now(tz=timezone.utc),
            source="scenario",
        )
        db.add(badge)
        db.commit()
        db.refresh(badge)

        _credit_badge_coins(db, child, badge, d1)
        db.flush()

        assert (
            db.query(CoinTransaction)
            .filter(CoinTransaction.child_user_id == child.id)
            .count()
            == 0
        )

    def test_no_config_creates_no_transaction(self, db, child, definitions):
        # No economy config row for this family.
        d1 = definitions[("earning", 1)]
        badge = LiteracyBadge(
            id=next_id(),
            child_id=child.id,
            definition_id=d1.id,
            earned_at=datetime.now(tz=timezone.utc),
            source="scenario",
        )
        db.add(badge)
        db.commit()
        db.refresh(badge)

        _credit_badge_coins(db, child, badge, d1)
        db.flush()

        assert (
            db.query(CoinTransaction)
            .filter(CoinTransaction.child_user_id == child.id)
            .count()
            == 0
        )


# ---------------------------------------------------------------------------
# _evaluate_with_llm
# ---------------------------------------------------------------------------


class TestEvaluateWithLlm:
    async def test_returns_true_on_unlock(self, definitions):
        d2 = definitions[("earning", 2)]
        mock_resp = SimpleNamespace(
            status_code=200,
            json=lambda: {"content": '{"unlock": true, "reason": "good"}'},
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch(
            "apps.backend.app.services.agent_client.AgentClient",
            return_value=mock_client,
        ):
            result = await _evaluate_with_llm(
                family_id=1,
                child_id=1,
                dimension="earning",
                next_def=d2,
                context={"approved_chores_14d": 5},
            )
        assert result is True

    async def test_returns_false_on_negative(self, definitions):
        d2 = definitions[("earning", 2)]
        mock_resp = SimpleNamespace(
            status_code=200,
            json=lambda: {"content": '{"unlock": false}'},
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch(
            "apps.backend.app.services.agent_client.AgentClient",
            return_value=mock_client,
        ):
            result = await _evaluate_with_llm(
                family_id=1,
                child_id=1,
                dimension="earning",
                next_def=d2,
                context={},
            )
        assert result is False

    async def test_returns_false_on_http_error(self, definitions):
        d2 = definitions[("earning", 2)]
        mock_resp = SimpleNamespace(status_code=500, json=lambda: {})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch(
            "apps.backend.app.services.agent_client.AgentClient",
            return_value=mock_client,
        ):
            result = await _evaluate_with_llm(
                family_id=1,
                child_id=1,
                dimension="earning",
                next_def=d2,
                context={},
            )
        assert result is False

    async def test_returns_false_on_exception(self, definitions):
        d2 = definitions[("earning", 2)]
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError("network"))

        with patch(
            "apps.backend.app.services.agent_client.AgentClient",
            return_value=mock_client,
        ):
            result = await _evaluate_with_llm(
                family_id=1,
                child_id=1,
                dimension="earning",
                next_def=d2,
                context={},
            )
        assert result is False


# ---------------------------------------------------------------------------
# _extract_text
# ---------------------------------------------------------------------------


class TestExtractText:
    def test_string_input_returns_as_is(self):
        assert _extract_text("hello") == "hello"

    def test_dict_with_content_key(self):
        assert _extract_text({"content": "result"}) == "result"

    def test_dict_with_text_key(self):
        assert _extract_text({"text": "hello"}) == "hello"

    def test_dict_with_data_key_recurses(self):
        assert _extract_text({"data": {"content": "nested"}}) == "nested"

    def test_dict_with_data_key_string(self):
        assert _extract_text({"data": "direct"}) == "direct"

    def test_non_string_non_dict_falls_back(self):
        result = _extract_text(42)
        assert "42" in result

    def test_dict_no_matching_keys_falls_back(self):
        result = _extract_text({"unknown_key": "val"})
        # No recognized key -> json.dumps fallback
        assert "unknown_key" in result
