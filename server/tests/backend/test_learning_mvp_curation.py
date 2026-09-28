"""Tests for MVP topic curation."""

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningDependency, LearningTopic


@pytest.fixture
def mvp_topics(db: Session):
    """Create a set of test topics across 3 subjects with dependencies."""
    topics = []
    for subject in ["mathematics", "science", "english"]:
        for i in range(25):
            t = LearningTopic(
                topic_key=f"mvp_{subject}_{i}",
                topic_type="CONCEPTUAL",
                subject=subject,
                domain=f"Test {subject}",
                name=f"{subject} topic {i}",
                description=f"Test topic for {subject}",
                age_group="mid",
                centrality=100.0 - i,  # Higher centrality for lower i
                evidence_json="[]",
                standards_json="[]",
            )
            db.add(t)
            topics.append(t)
    db.flush()

    # Add chain dependencies: each topic depends on the previous
    for subject in ["mathematics", "science", "english"]:
        subject_topics = [t for t in topics if t.subject == subject]
        for i in range(1, len(subject_topics)):
            dep = LearningDependency(
                topic_id=subject_topics[i].id,
                prerequisite_id=subject_topics[i - 1].id,
                strength="hard",
            )
            db.add(dep)
    db.flush()
    return topics


class TestSelectMVPTopics:
    def test_selects_from_three_subjects(self, db: Session, mvp_topics):
        from scripts.seed_learning_topics import select_mvp_topics

        ids = select_mvp_topics(db)
        selected = db.query(LearningTopic).filter(LearningTopic.id.in_(ids)).all()
        subjects = {t.subject for t in selected}
        assert subjects == {"mathematics", "science", "english"}

    def test_selects_correct_count(self, db: Session, mvp_topics):
        from scripts.seed_learning_topics import select_mvp_topics

        ids = select_mvp_topics(db)
        # Should select 25 per subject = 75 total (within 60-90 range)
        assert 60 <= len(ids) <= 90

    def test_prefers_high_centrality(self, db: Session, mvp_topics):
        from scripts.seed_learning_topics import select_mvp_topics

        ids = set(select_mvp_topics(db))
        # Topic with centrality=100 (i=0) should be included
        top_topics = [t for t in mvp_topics if t.centrality == 100.0]
        for t in top_topics:
            assert t.id in ids


class TestValidateMVPCuration:
    def test_valid_curation_passes(self, db: Session, mvp_topics):
        from scripts.seed_learning_topics import select_mvp_topics, validate_mvp_curation

        ids = select_mvp_topics(db)
        errors = validate_mvp_curation(db, ids)
        assert errors == []

    def test_too_few_topics_fails(self, db: Session):
        from scripts.seed_learning_topics import validate_mvp_curation

        # Create only 5 topics total
        topics = []
        for i in range(5):
            t = LearningTopic(
                topic_key=f"few_{i}",
                topic_type="CONCEPTUAL",
                subject="mathematics",
                description="Test",
                age_group="mid",
                evidence_json="[]",
                standards_json="[]",
            )
            db.add(t)
            topics.append(t)
        db.flush()

        errors = validate_mvp_curation(db, [t.id for t in topics])
        assert any("Too few" in e for e in errors)

    def test_subject_imbalance_detected(self, db: Session, mvp_topics):
        from scripts.seed_learning_topics import validate_mvp_curation

        # Select only math topics (simulating imbalance)
        math_ids = [t.id for t in mvp_topics if t.subject == "mathematics"]
        errors = validate_mvp_curation(db, math_ids)
        assert any("science" in e.lower() or "Too few" in e for e in errors)
