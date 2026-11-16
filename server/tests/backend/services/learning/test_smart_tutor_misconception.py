"""Tests for Smart Tutor misconception integration (#214 U4)."""

import json

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.misconception import Misconception
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session) -> LearningTopic:
    t = LearningTopic(
        topic_key="mt_tutor_mc_test", topic_type="concept",
        subject="mathematics", domain="arithmetic",
        name="Tutor test", age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def misconception(db: Session, topic: LearningTopic) -> Misconception:
    m = Misconception(
        topic_id=topic.id, sequence=0,
        error_pattern_json=json.dumps(
            {"match_type": "symbolic", "expected_wrong": "2/7"}
        ),
        description="Adding numerators and denominators",
        age_group="mid",
        review_status="approved",
        category="concept_confusion",
    )
    db.add(m)
    db.flush()
    return m


class TestParseSmartTutorStepsMisconception:
    def test_empty_progress_returns_empty_misconceptions(self, db: Session, topic):
        """No steps → empty misconception list."""
        from apps.backend.app.routers.learning_family import (
            _parse_smart_tutor_steps,
        )
        session = LearningSession(
            child_id=1, topic_id=topic.id, session_type="smart_tutor",
            progress_json="[]",
        )
        db.add(session)
        db.flush()
        steps, final_phase, misconceptions = _parse_smart_tutor_steps(session)
        assert steps == []
        assert final_phase is None
        assert misconceptions == []

    def test_deduplicates_misconceptions_across_steps(
        self, db: Session, topic, misconception
    ):
        """Same misconception in multiple steps → one entry."""
        from apps.backend.app.routers.learning_family import (
            _parse_smart_tutor_steps,
        )
        steps = [
            {
                "step": 1, "phase": "DIAGNOSE",
                "quality": "incorrect", "next_phase": "MISCONCEPTION_CORRECTION",
                "misconception": {
                    "id": misconception.id,
                    "category": "concept_confusion",
                    "description": misconception.description,
                },
            },
            {
                "step": 2, "phase": "MISCONCEPTION_CORRECTION",
                "quality": "correct", "next_phase": "VERIFY",
                "misconception": {
                    "id": misconception.id,
                    "category": "concept_confusion",
                    "description": misconception.description,
                },
            },
        ]
        session = LearningSession(
            child_id=1, topic_id=topic.id, session_type="smart_tutor",
            progress_json=json.dumps(steps),
        )
        db.add(session)
        db.flush()
        _, _, misconceptions = _parse_smart_tutor_steps(session)
        assert len(misconceptions) == 1
        assert misconceptions[0]["misconception_id"] == str(misconception.id)
        assert misconceptions[0]["category"] == "concept_confusion"

    def test_multiple_distinct_misconceptions(self, db: Session, topic):
        """Two different misconceptions → two entries."""
        from apps.backend.app.routers.learning_family import (
            _parse_smart_tutor_steps,
        )
        m1 = Misconception(
            topic_id=topic.id, sequence=0,
            error_pattern_json="{}", description="M1",
            age_group="mid", review_status="approved",
            category="concept_confusion",
        )
        m2 = Misconception(
            topic_id=topic.id, sequence=1,
            error_pattern_json="{}", description="M2",
            age_group="mid", review_status="approved",
            category="procedural_error",
        )
        db.add_all([m1, m2])
        db.flush()

        steps = [
            {
                "step": 1, "phase": "DIAGNOSE",
                "misconception": {"id": m1.id, "category": "concept_confusion", "description": "M1"},
            },
            {
                "step": 2, "phase": "DIAGNOSE",
                "misconception": {"id": m2.id, "category": "procedural_error", "description": "M2"},
            },
        ]
        session = LearningSession(
            child_id=1, topic_id=topic.id, session_type="smart_tutor",
            progress_json=json.dumps(steps),
        )
        db.add(session)
        db.flush()
        _, _, misconceptions = _parse_smart_tutor_steps(session)
        assert len(misconceptions) == 2
        ids = {m["misconception_id"] for m in misconceptions}
        assert str(m1.id) in ids
        assert str(m2.id) in ids

    def test_steps_without_misconception_field_ignored(self, db: Session, topic):
        """Steps with no misconception field don't contribute."""
        from apps.backend.app.routers.learning_family import (
            _parse_smart_tutor_steps,
        )
        steps = [
            {"step": 1, "phase": "DIAGNOSE", "quality": "correct"},
            {"step": 2, "phase": "VERIFY", "quality": "correct"},
        ]
        session = LearningSession(
            child_id=1, topic_id=topic.id, session_type="smart_tutor",
            progress_json=json.dumps(steps),
        )
        db.add(session)
        db.flush()
        _, _, misconceptions = _parse_smart_tutor_steps(session)
        assert misconceptions == []
