"""Tests for learning path service — topological sort, rewards, CRUD, coin emission."""

import pytest

from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.schemas.learning import PathCreate
from apps.backend.app.services.learning.path_service import (
    advance_path_item,
    compute_path_rewards,
    get_child_active_paths,
    get_path_progress,
    sort_topics_by_prerequisites,
    try_advance_path_for_topic,
)
from packages.db.models.child_economy.coin_transaction import CoinTransaction
from packages.db.models.learning.path import LearningPath, LearningPathItem
from packages.db.models.learning.topic import LearningDependency, LearningTopic


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


# --- Helpers to seed learning topics and dependencies ---


def _make_topic(db, topic_id: int, name: str, name_zh: str | None = None) -> LearningTopic:
    topic = LearningTopic(
        id=topic_id,
        topic_key=f"test_topic_{topic_id}",
        topic_type="concept",
        subject="math",
        name=name,
        name_zh=name_zh,
    )
    db.add(topic)
    return topic


def _make_dep(db, topic_id: int, prerequisite_id: int) -> LearningDependency:
    dep = LearningDependency(
        topic_id=topic_id,
        prerequisite_id=prerequisite_id,
        strength="hard",
    )
    db.add(dep)
    return dep


def _make_path(
    db, *, path_id: int, family_id: int, child_id: int,
    name: str = "Test Path",
    per_task_score: int = 5,
    bonus_score: int = 10,
    milestone_scores: list | None = None,
) -> LearningPath:
    path = LearningPath(
        id=path_id,
        family_id=family_id,
        child_id=child_id,
        created_by=child_id,
        name=name,
        per_task_score=per_task_score,
        bonus_score=bonus_score,
        milestone_scores_json="[]",
    )
    if milestone_scores:
        path.milestone_scores = milestone_scores
    db.add(path)
    db.flush()
    return path


def _make_path_item(
    db, *, item_id: int, path_id: int, topic_id: int, sort_order: int = 0,
    status: str = "pending",
) -> LearningPathItem:
    item = LearningPathItem(
        id=item_id,
        path_id=path_id,
        topic_id=topic_id,
        sort_order=sort_order,
        status=status,
    )
    db.add(item)
    db.flush()
    return item


# --- Topological Sort Tests ---


class TestTopologicalSort:
    def test_no_dependencies(self, db_session):
        """Topics with no dependencies keep original order."""
        _make_topic(db_session, 10, "A")
        _make_topic(db_session, 20, "B")
        _make_topic(db_session, 30, "C")
        db_session.flush()


        result = sort_topics_by_prerequisites(db_session, [10, 20, 30])
        assert result == [10, 20, 30]

    def test_linear_chain(self, db_session):
        """A -> B -> C should sort as [A, B, C]."""
        _make_topic(db_session, 10, "A")
        _make_topic(db_session, 20, "B")
        _make_topic(db_session, 30, "C")
        # 20 requires 10; 30 requires 20
        _make_dep(db_session, topic_id=20, prerequisite_id=10)
        _make_dep(db_session, topic_id=30, prerequisite_id=20)
        db_session.flush()


        result = sort_topics_by_prerequisites(db_session, [30, 10, 20])
        assert result.index(10) < result.index(20)
        assert result.index(20) < result.index(30)

    def test_partial_subset(self, db_session):
        """Only sort the given topic_ids, ignore others."""
        _make_topic(db_session, 10, "A")
        _make_topic(db_session, 20, "B")
        _make_topic(db_session, 30, "C")
        _make_dep(db_session, topic_id=20, prerequisite_id=10)
        _make_dep(db_session, topic_id=30, prerequisite_id=20)
        db_session.flush()


        result = sort_topics_by_prerequisites(db_session, [30, 10])
        # 10 should come before 30 because of transitive dependency
        assert result.index(10) < result.index(30)

    def test_single_topic(self, db_session):
        """Single topic returns as-is."""

        result = sort_topics_by_prerequisites(db_session, [42])
        assert result == [42]

    def test_empty_list(self, db_session):
        """Empty list returns empty."""

        result = sort_topics_by_prerequisites(db_session, [])
        assert result == []


# --- Compute Path Rewards Tests ---


class TestComputePathRewards:
    def test_per_task_only(self):
        class FakePath:
            per_task_score = 5
            bonus_score = 10
            milestone_scores = [{"threshold": 3, "bonus": 10}]


        rewards = compute_path_rewards(FakePath(), completed_count=1, total_count=5)
        assert rewards == {"per_task": 5, "milestone": None, "completion": None}

    def test_milestone_hit(self):
        class FakePath:
            per_task_score = 5
            bonus_score = 10
            milestone_scores = [{"threshold": 3, "bonus": 10}]


        rewards = compute_path_rewards(FakePath(), completed_count=3, total_count=5)
        assert rewards["milestone"] == 10

    def test_completion_bonus(self):
        class FakePath:
            per_task_score = 5
            bonus_score = 10
            milestone_scores = []


        rewards = compute_path_rewards(FakePath(), completed_count=5, total_count=5)
        assert rewards["completion"] == 10

    def test_milestone_and_completion(self):
        class FakePath:
            per_task_score = 5
            bonus_score = 10
            milestone_scores = [{"threshold": 3, "bonus": 15}, {"threshold": 5, "bonus": 20}]


        rewards = compute_path_rewards(FakePath(), completed_count=5, total_count=5)
        assert rewards["milestone"] == 20
        assert rewards["completion"] == 10

    def test_no_milestone_hit(self):
        """completed_count=2 does not hit threshold=3."""
        class FakePath:
            per_task_score = 5
            bonus_score = 10
            milestone_scores = [{"threshold": 3, "bonus": 15}]


        rewards = compute_path_rewards(FakePath(), completed_count=2, total_count=5)
        assert rewards["milestone"] is None
        assert rewards["completion"] is None


# --- Advance Path Item + Coin Emission Tests ---


class TestAdvancePathItem:
    def test_advance_emits_per_task_coins(self, db_session):
        """Completing a pending item emits per_task coins."""

        _make_topic(db_session, 100, "Algebra", "代数")
        _make_path(db_session, path_id=1001, family_id=1, child_id=1)
        _make_path_item(db_session, item_id=2001, path_id=1001, topic_id=100, sort_order=0)
        db_session.commit()

        result = advance_path_item(db_session, 1001, 100, child_user_id=1, family_id=1)

        assert result["item"].status == "completed"
        assert result["rewards"]["per_task"] == 5

        txs = db_session.query(CoinTransaction).filter(
            CoinTransaction.child_user_id == 1,
            CoinTransaction.transaction_type == "path_earn",
        ).all()
        assert len(txs) == 1
        assert txs[0].amount == 5

    def test_advance_is_idempotent(self, db_session):
        """Calling advance twice must not emit coins twice."""

        _make_topic(db_session, 101, "Geometry", "几何")
        _make_path(db_session, path_id=1002, family_id=1, child_id=1)
        _make_path_item(db_session, item_id=2002, path_id=1002, topic_id=101, sort_order=0)
        # Add a second pending item so total_count=2; flush it so the count
        # query inside advance_path_item sees both rows.
        _make_topic(db_session, 1011, "Geometry2", "几何2")
        _make_path_item(db_session, item_id=2022, path_id=1002, topic_id=1011, sort_order=1)
        db_session.commit()

        advance_path_item(db_session, 1002, 101, child_user_id=1, family_id=1)
        result2 = advance_path_item(db_session, 1002, 101, child_user_id=1, family_id=1)

        # Second call returns early, rewards=None (no double emission)
        assert result2["rewards"] is None

        txs = db_session.query(CoinTransaction).filter(
            CoinTransaction.child_user_id == 1,
            CoinTransaction.transaction_type.in_(["path_earn", "path_completion"]),
        ).all()
        # Only 1 per-task coin from the first call
        assert sum(tx.amount for tx in txs) == 5

    def test_path_not_found_raises(self, db_session):
        """Non-existent path raises AppError."""

        with pytest.raises(AppError):
            advance_path_item(db_session, 99999, 100, child_user_id=1, family_id=1)

    def test_topic_not_in_path_returns_none_item(self, db_session):
        """Topic not in path returns item=None."""

        _make_topic(db_session, 102, "Topic", None)
        _make_path(db_session, path_id=1003, family_id=1, child_id=1)
        db_session.commit()

        result = advance_path_item(db_session, 1003, 102, child_user_id=1, family_id=1)
        assert result["item"] is None
        assert result["rewards"] is None

    def test_milestone_combined_with_per_task_no_integrity_error(self, db_session):
        """When milestone is hit, per-task and milestone amounts are combined
        into a SINGLE path_earn transaction to avoid UniqueConstraint violation."""

        # 2-item path; milestone at threshold=2 (hits when second item completed)
        _make_topic(db_session, 105, "T1", "题1")
        _make_topic(db_session, 106, "T2", "题2")
        _make_path(
            db_session, path_id=1005, family_id=1, child_id=1,
            per_task_score=5,
            milestone_scores=[{"threshold": 2, "bonus": 10}],
        )
        _make_path_item(db_session, item_id=2010, path_id=1005, topic_id=105, sort_order=0, status="completed")
        _make_path_item(db_session, item_id=2011, path_id=1005, topic_id=106, sort_order=1)
        db_session.commit()

        # This should NOT raise IntegrityError
        result = advance_path_item(db_session, 1005, 106, child_user_id=1, family_id=1)

        assert result["item"].status == "completed"
        assert result["rewards"]["per_task"] == 5
        assert result["rewards"]["milestone"] == 10

        # Exactly ONE path_earn tx for this item (combined amount = 15)
        earn_txs = db_session.query(CoinTransaction).filter(
            CoinTransaction.child_user_id == 1,
            CoinTransaction.transaction_type == "path_earn",
            CoinTransaction.ref_id == 2011,
        ).all()
        assert len(earn_txs) == 1
        assert earn_txs[0].amount == 15
        # Narrative should mention both components
        assert "+5" in earn_txs[0].narrative
        assert "+10" in earn_txs[0].narrative

    def test_completion_bonus_when_all_done(self, db_session):
        """Completing the last item emits per_task + completion coins."""

        _make_topic(db_session, 103, "T1", None)
        _make_topic(db_session, 104, "T2", None)
        _make_path(db_session, path_id=1004, family_id=1, child_id=1, bonus_score=10)
        _make_path_item(db_session, item_id=2004, path_id=1004, topic_id=103, sort_order=0, status="completed")
        _make_path_item(db_session, item_id=2005, path_id=1004, topic_id=104, sort_order=1)
        db_session.commit()

        result = advance_path_item(db_session, 1004, 104, child_user_id=1, family_id=1)

        assert result["rewards"]["completion"] == 10
        # Check completion coin was emitted (path_completion type)
        completion_tx = db_session.query(CoinTransaction).filter(
            CoinTransaction.transaction_type == "path_completion",
            CoinTransaction.child_user_id == 1,
        ).first()
        assert completion_tx is not None
        assert completion_tx.amount == 10


# --- Get Path Progress Tests ---


class TestGetPathProgress:
    def test_returns_items_and_counts(self, db_session):

        _make_topic(db_session, 110, "T1", "题1")
        _make_topic(db_session, 111, "T2", "题2")
        _make_path(db_session, path_id=1100, family_id=1, child_id=1)
        _make_path_item(db_session, item_id=3001, path_id=1100, topic_id=110, sort_order=0, status="completed")
        _make_path_item(db_session, item_id=3002, path_id=1100, topic_id=111, sort_order=1)
        db_session.commit()

        progress = get_path_progress(db_session, 1100, family_id=1)

        assert progress["completed_count"] == 1
        assert progress["total_count"] == 2
        assert len(progress["items"]) == 2
        assert progress["items"][0]["topic_name_zh"] == "题1"

    def test_next_milestone(self, db_session):

        _make_path(
            db_session, path_id=1101, family_id=1, child_id=1,
            milestone_scores=[{"threshold": 3, "bonus": 15}],
        )
        _make_topic(db_session, 112, "T", None)
        _make_path_item(db_session, item_id=3003, path_id=1101, topic_id=112, sort_order=0, status="completed")
        db_session.commit()

        progress = get_path_progress(db_session, 1101, family_id=1)
        assert progress["next_milestone"]["threshold"] == 3
        assert progress["next_milestone"]["progress"] == "1/3"

    def test_path_not_found_raises(self, db_session):

        with pytest.raises(AppError):
            get_path_progress(db_session, 99999, family_id=1)


# --- Get Child Active Paths Tests ---


class TestGetChildActivePaths:
    def test_returns_only_active_paths(self, db_session):

        _make_path(db_session, path_id=1200, family_id=1, child_id=1, name="Active")
        p2 = _make_path(db_session, path_id=1201, family_id=1, child_id=1, name="Done")
        p2.status = "completed"
        db_session.commit()

        paths = get_child_active_paths(db_session, child_id=1, family_id=1)
        assert len(paths) == 1
        assert paths[0].name == "Active"

    def test_tenant_isolation(self, db_session):
        """Paths from other families are not returned."""

        _make_path(db_session, path_id=1202, family_id=1, child_id=1)
        _make_path(db_session, path_id=1203, family_id=999, child_id=1)
        db_session.commit()

        paths = get_child_active_paths(db_session, child_id=1, family_id=1)
        assert all(p.family_id == 1 for p in paths)


# --- Try Advance Path For Topic Tests ---


class TestTryAdvancePathForTopic:
    def test_advances_matching_path(self, db_session):

        _make_topic(db_session, 130, "Topic", None)
        _make_path(db_session, path_id=1300, family_id=1, child_id=1)
        _make_path_item(db_session, item_id=4001, path_id=1300, topic_id=130, sort_order=0)
        db_session.commit()

        result = try_advance_path_for_topic(db_session, child_id=1, family_id=1, topic_id=130)
        assert result is not None
        assert result["item"].status == "completed"

    def test_returns_none_if_topic_not_in_any_path(self, db_session):

        _make_topic(db_session, 131, "Orphan", None)
        db_session.commit()

        result = try_advance_path_for_topic(db_session, child_id=1, family_id=1, topic_id=131)
        assert result is None
