"""Tests for content_hash backfill and Beijing topic fix."""
import pytest

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic
from apps.backend.app.services.learning.question_seeder import _compute_content_hash


class TestContentHashBackfill:
    """content_hash backfill produces correct hashes."""

    def test_backfill_sets_hash_on_all_questions(self, db_session):
        """After backfill, every question has a content_hash."""
        from apps.backend.scripts.backfill_content_hash import backfill

        q1 = Question(
            topic_id=1, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="approved",
            age_group="lower",
        )
        q2 = Question(
            topic_id=1, question_type="fill_blank",
            stem="Capital of China", answer_json='{"value": "北京"}',
            difficulty=1, source="template", review_status="approved",
            age_group="lower",
        )
        db_session.add_all([q1, q2])
        db_session.flush()

        result = backfill(db_session)

        db_session.refresh(q1)
        db_session.refresh(q2)
        assert q1.content_hash is not None
        assert q2.content_hash is not None
        assert q1.content_hash != q2.content_hash
        assert result["backfilled"] == 2

    def test_backfill_hash_matches_compute_function(self, db_session):
        """Backfilled hash matches _compute_content_hash output."""
        from apps.backend.scripts.backfill_content_hash import backfill

        q = Question(
            topic_id=1, question_type="calculation",
            stem="2+2=?", answer_json='{"answer": 4}',
            difficulty=1, source="template", review_status="approved",
            age_group="lower",
        )
        db_session.add(q)
        db_session.flush()

        backfill(db_session)
        db_session.refresh(q)

        expected = _compute_content_hash("2+2=?", {"answer": 4})
        assert q.content_hash == expected

    def test_backfill_is_idempotent(self, db_session):
        """Running backfill twice doesn't change existing hashes."""
        from apps.backend.scripts.backfill_content_hash import backfill

        q = Question(
            topic_id=1, question_type="calculation",
            stem="3+3=?", answer_json='{"answer": 6}',
            difficulty=1, source="template", review_status="approved",
            age_group="lower",
        )
        db_session.add(q)
        db_session.flush()

        backfill(db_session)
        db_session.refresh(q)
        first_hash = q.content_hash

        result = backfill(db_session)
        db_session.refresh(q)
        assert q.content_hash == first_hash
        assert result["skipped"] == 1


class TestBeijingTopicFix:
    """Beijing topics get subject/age_group from upstream data.

    Note: The production bug (NULL subject/age_group) cannot be reproduced
    in SQLite because the column has a NOT NULL constraint. We test the
    function's logic with the "already fixed" (skipped) path and verify
    the upstream index builder works correctly.
    """

    def test_fix_skips_already_complete_topics(self, db_session):
        """Beijing topics with subject+age_group already set are skipped."""
        from apps.backend.scripts.fix_beijing_topics import fix_beijing_topics

        upstream = LearningTopic(
            topic_key="math.number.addition", subject="mathematics",
            domain="number", name="Addition", age_group="lower",
            source_taxonomy="upstream", deprecated=False,
            topic_type="knowledge",
        )
        beijing = LearningTopic(
            topic_key="bj-math.number.addition", subject="mathematics",
            domain="number", name="北京版-加法", age_group="lower",
            source_taxonomy="beijing", deprecated=False,
            topic_type="knowledge",
        )
        db_session.add_all([upstream, beijing])
        db_session.flush()

        result = fix_beijing_topics(db_session)
        assert result["skipped"] == 1
        assert result["fixed"] == 0

    def test_upstream_index_builder(self, db_session):
        """_build_upstream_index creates domain → topic mapping."""
        from apps.backend.scripts.fix_beijing_topics import _build_upstream_index

        t = LearningTopic(
            topic_key="math.number.add", subject="mathematics",
            domain="number", name="Add", age_group="lower",
            source_taxonomy="upstream", deprecated=False,
            topic_type="knowledge",
        )
        db_session.add(t)
        db_session.flush()

        index = _build_upstream_index(db_session)
        assert "number" in index
        assert index["number"].subject == "mathematics"
