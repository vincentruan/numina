"""Tests for learning path service — error codes and coin ref_type mappings."""

import pytest

from apps.backend.app.schemas.learning import PathCreate
from packages.db.models.child_economy.coin_transaction import CoinTransaction


def test_coin_ref_type_includes_path_types():
    """path_earn and path_completion must map to their ref entity types."""
    tx_earn = CoinTransaction(transaction_type="path_earn", ref_id=1)
    assert tx_earn.ref_type == "learning_path_item"

    tx_complete = CoinTransaction(transaction_type="path_completion", ref_id=2)
    assert tx_complete.ref_type == "learning_path"


def test_coin_ref_type_existing_types_still_work():
    """Existing ref_type mappings must not break."""
    tx_chore = CoinTransaction(transaction_type="chore_earn", ref_id=10)
    assert tx_chore.ref_type == "chore_instance"

    tx_wish = CoinTransaction(transaction_type="wish_spend", ref_id=20)
    assert tx_wish.ref_type == "child_wish"

    tx_learning = CoinTransaction(transaction_type="learning_earn", ref_id=30)
    assert tx_learning.ref_type == "learning_assessment_attempt"


def test_coin_ref_type_unknown_returns_none():
    """Unknown transaction types must return None."""
    tx_unknown = CoinTransaction(transaction_type="parent_grant", ref_id=40)
    assert tx_unknown.ref_type is None

    tx_gift = CoinTransaction(transaction_type="gift_sent", ref_id=50)
    assert tx_gift.ref_type is None


# --- PathCreate validation tests (Task 4) ---


class TestPathCreateValidation:
    def test_valid_milestone(self):
        schema = PathCreate(
            child_id=1,
            name="Math Basics",
            topic_ids=[10, 20, 30, 40, 50],
            milestone_scores=[{"threshold": 3, "bonus": 10}, {"threshold": 5, "bonus": 20}],
        )
        assert len(schema.milestone_scores) == 2

    def test_milestone_threshold_out_of_range(self):
        with pytest.raises(ValueError, match="threshold"):
            PathCreate(
                child_id=1,
                name="Math Basics",
                topic_ids=[10, 20, 30],
                milestone_scores=[{"threshold": 5, "bonus": 10}],  # 5 > len(topic_ids)=3
            )

    def test_milestone_negative_bonus(self):
        with pytest.raises(ValueError):
            PathCreate(
                child_id=1,
                name="Math Basics",
                topic_ids=[10, 20, 30],
                milestone_scores=[{"threshold": 2, "bonus": -5}],
            )

    def test_milestone_duplicate_threshold(self):
        with pytest.raises(ValueError, match="duplicate"):
            PathCreate(
                child_id=1,
                name="Math Basics",
                topic_ids=[10, 20, 30, 40],
                milestone_scores=[
                    {"threshold": 2, "bonus": 10},
                    {"threshold": 2, "bonus": 15},
                ],
            )

    def test_milestone_missing_fields(self):
        with pytest.raises(ValueError):
            PathCreate(
                child_id=1,
                name="Math Basics",
                topic_ids=[10, 20, 30],
                milestone_scores=[{"threshold": 2}],  # missing bonus
            )
