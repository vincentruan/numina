"""Tests for the misconception seed script (issue #214)."""

import json

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.misconception import Misconception
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def fraction_topic(db: Session):
    """Create the pilot topic keyed mt_9KmVWCuh5_ for seeding."""
    t = LearningTopic(
        topic_key="mt_9KmVWCuh5_",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Understanding fractions",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


class TestSeedMisconceptions:
    def test_seed_creates_misconceptions_with_diagnostic_questions(
        self, db, fraction_topic, monkeypatch
    ):
        """Seeding creates all 3 misconceptions, each with an approved diagnostic question."""
        from scripts import seed_misconceptions as seed_mod

        # Point SessionLocal at the test DB so the script writes where we can verify.
        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)

        seed_mod.seed_misconceptions()

        misconceptions = (
            db.query(Misconception)
            .filter_by(topic_id=fraction_topic.id)
            .order_by(Misconception.sequence)
            .all()
        )
        assert len(misconceptions) == 3
        for m in misconceptions:
            assert m.review_status == "approved"
            assert m.age_group == "mid"
            assert m.diagnostic_question_id is not None
            # Diagnostic question exists and is approved.
            diag_q = db.query(Question).filter_by(id=m.diagnostic_question_id).first()
            assert diag_q is not None
            assert diag_q.review_status == "approved"
            # Error pattern is valid JSON with a match_type.
            pattern = m.error_pattern
            assert pattern is not None
            assert "match_type" in pattern
            assert pattern["match_type"] == "parametric"

    def test_seed_is_idempotent(self, db, fraction_topic, monkeypatch):
        """Re-running the seed keeps the same count (delete + insert)."""
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)

        seed_mod.seed_misconceptions()
        count_1 = db.query(Misconception).filter_by(topic_id=fraction_topic.id).count()

        seed_mod.seed_misconceptions()
        count_2 = db.query(Misconception).filter_by(topic_id=fraction_topic.id).count()

        assert count_1 == count_2 == 3

    def test_missing_topic_skipped_with_warning(self, db, monkeypatch, capsys):
        """A missing topic_key is skipped with a warning; others still seeded."""
        from scripts import seed_misconceptions as seed_mod

        # No topic with that key exists in the test DB.
        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)

        seed_mod.seed_misconceptions()

        output = capsys.readouterr().out
        assert "not found, skipping" in output
        # No misconceptions were seeded (the only topic key is missing).
        assert db.query(Misconception).count() == 0

    def test_seeded_misconceptions_are_detectable(self, db, fraction_topic, monkeypatch):
        """The seeded fraction_add_numerators misconception actually detects 2/7."""
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)
        seed_mod.seed_misconceptions()

        from apps.backend.app.services.learning.misconception_detector import (
            detect_misconception,
        )

        q = Question(
            topic_id=fraction_topic.id,
            question_type="calculation",
            stem="What is 1/3 + 1/4?",
            answer_json=json.dumps({"answer": "7/12", "fractions": [[1, 3], [1, 4]]}),
            difficulty=2,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(q)
        db.flush()

        result = detect_misconception(db, fraction_topic.id, {"answer": "2/7"}, q)
        assert result is not None
        assert result.sequence == 0  # fraction_add_numerators is the first

        # The whole-numbers variant also detected.
        result2 = detect_misconception(db, fraction_topic.id, {"answer": "2"}, q)
        assert result2 is not None
        assert result2.sequence == 1
