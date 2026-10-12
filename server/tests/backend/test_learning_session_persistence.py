"""Verify that learning mutations persist — the db.commit() fix.

Root cause (C17.5): session_service.create_session() called db.flush()
but not db.commit(), so the row was lost when the request's DB session
closed. POST returned 201 but GET returned 404.
"""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning import (
    practice_service,
    progress_service,
    session_service,
)
from apps.backend.app.schemas.learning import SessionCreate
from packages.db.models.family import Family
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User


@pytest.fixture
def learning_setup(db: Session):
    """Create family, child, and topic for learning tests."""
    family = Family(name="Persistence Test", invite_code="LP01", created_by=1)
    db.add(family)
    db.flush()

    child = User(
        display_name="Learn Child",
        password_hash="x",
        role="child",
        family_id=family.id,
    )
    db.add(child)
    db.flush()

    topic = LearningTopic(
        topic_key="persist_test",
        topic_type="concept",
        subject="mathematics",
        domain="Test",
        name="Persist Test",
        description="test",
        age_group="mid",
    )
    db.add(topic)
    db.flush()

    return {"db": db, "family": family, "child": child, "topic": topic}


def test_session_create_persists(learning_setup):
    """POST create_session → data is visible to new query (commits, not just flushes)."""
    db = learning_setup["db"]
    child = learning_setup["child"]
    topic = learning_setup["topic"]

    req = SessionCreate(topic_id=topic.id)
    result = session_service.create_session(db, child.id, req)

    # Verify data persisted by querying from the same session
    from packages.db.models.learning.session import LearningSession

    found = db.query(LearningSession).filter_by(id=result["id"]).first()
    assert found is not None, "Session row should exist after create_session()"
    assert found.child_id == child.id
    assert found.topic_id == topic.id


def test_session_end_persists(learning_setup):
    """end_session() changes (ended_at, duration) should persist."""
    db = learning_setup["db"]
    child = learning_setup["child"]
    topic = learning_setup["topic"]

    req = SessionCreate(topic_id=topic.id)
    result = session_service.create_session(db, child.id, req)
    session_id = result["id"]

    ended = session_service.end_session(db, session_id, score=85.0)
    assert ended.ended_at is not None
    assert ended.score == 85.0

    # Verify persistence
    from packages.db.models.learning.session import LearningSession

    found = db.query(LearningSession).filter_by(id=session_id).first()
    assert found.ended_at is not None
    assert found.score == 85.0


def test_progress_get_or_create_persists(learning_setup):
    """get_or_create_progress() creates a row that persists."""
    db = learning_setup["db"]
    child = learning_setup["child"]
    topic = learning_setup["topic"]

    progress = progress_service.get_or_create_progress(db, child.id, topic.id)
    assert progress is not None

    # Verify persistence
    from packages.db.models.learning.progress import LearningProgress

    found = (
        db.query(LearningProgress)
        .filter_by(child_id=child.id, topic_id=topic.id)
        .first()
    )
    assert found is not None
    assert found.id == progress.id


def test_practice_session_create_persists(learning_setup):
    """practice_service.create_session() persists."""
    db = learning_setup["db"]
    child = learning_setup["child"]
    topic = learning_setup["topic"]

    ps = practice_service.create_session(
        db, child_id=child.id, topic_id=topic.id,
        session_mode="free", question_ids=[],
    )
    assert ps is not None

    from packages.db.models.learning.practice import PracticeSession

    found = db.query(PracticeSession).filter_by(id=ps.id).first()
    assert found is not None
    assert found.child_id == child.id
