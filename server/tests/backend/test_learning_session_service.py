"""Tests for learning session service."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.schemas.learning import SessionCreate
from apps.backend.app.services.learning.session_service import (
    create_session,
    end_session,
    start_assessment,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    """Create a learning topic."""
    t = LearningTopic(
        topic_key="mt_session",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Session test topic",
        description="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def child_user(client, auth_headers):
    """Create a child user and return their info."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "sessionchild",
            "password": "ChildPass1",
            "display_name": "Session Learner",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child = resp.json()["data"]
    return {"id": int(child["id"])}


@pytest.fixture
def progress(db, child_user, topic):
    """Create a learning progress record in 'learning' state."""
    p = LearningProgress(
        child_id=child_user["id"],
        topic_id=topic.id,
        mastery_level="learning",
    )
    db.add(p)
    db.flush()
    return p


def test_create_session(db, child_user, topic):
    """Create a learning session."""
    req = SessionCreate(topic_id=topic.id, session_type="tutorial")
    session = create_session(db, child_user["id"], req)
    assert session.id is not None
    assert session.child_id == child_user["id"]
    assert session.topic_id == topic.id
    assert session.session_type == "tutorial"
    assert session.ended_at is None


def test_create_session_with_assignment(db, child_user, topic):
    """Create a session linked to an assignment."""
    req = SessionCreate(topic_id=topic.id, assignment_id=12345, session_type="practice")
    session = create_session(db, child_user["id"], req)
    assert session.assignment_id == 12345
    assert session.session_type == "practice"


def test_end_session(db, child_user, topic):
    """End a session with score and evaluation."""
    req = SessionCreate(topic_id=topic.id)
    session = create_session(db, child_user["id"], req)

    result = end_session(
        db,
        session.id,
        score=0.85,
        ai_evaluation={"feedback": "Good work"},
    )
    assert result.ended_at is not None
    assert result.score == 0.85
    assert result.ai_evaluation == {"feedback": "Good work"}
    assert result.duration_seconds is not None
    assert result.duration_seconds >= 0


def test_end_session_no_score(db, child_user, topic):
    """End a session without a score."""
    req = SessionCreate(topic_id=topic.id)
    session = create_session(db, child_user["id"], req)
    result = end_session(db, session.id)
    assert result.ended_at is not None
    assert result.score is None


def test_end_session_not_found(db):
    """End a nonexistent session raises error."""
    with pytest.raises(AppError) as exc_info:
        end_session(db, 99999)
    assert "learning_session_not_found" in str(exc_info.value)


def test_end_session_already_ended(db, child_user, topic):
    """Ending an already-ended session raises error."""
    req = SessionCreate(topic_id=topic.id)
    session = create_session(db, child_user["id"], req)
    end_session(db, session.id)

    with pytest.raises(AppError) as exc_info:
        end_session(db, session.id)
    assert "learning_session_already_ended" in str(exc_info.value)


def test_start_assessment(db, child_user, topic, progress):
    """Start an assessment transitions progress from learning to assessing."""
    req = SessionCreate(topic_id=topic.id)
    session = create_session(db, child_user["id"], req)

    result = start_assessment(db, session.id, child_user["id"])
    assert result.mastery_level == "assessing"


def test_start_assessment_session_not_found(db, child_user):
    """Start assessment with nonexistent session raises error."""
    with pytest.raises(AppError) as exc_info:
        start_assessment(db, 99999, child_user["id"])
    assert "learning_session_not_found" in str(exc_info.value)


def test_start_assessment_progress_not_found(db, child_user, topic):
    """Start assessment with no progress record raises error."""
    req = SessionCreate(topic_id=topic.id)
    session = create_session(db, child_user["id"], req)
    # No progress record exists for this child+topic
    with pytest.raises(AppError) as exc_info:
        start_assessment(db, session.id, child_user["id"])
    assert "learning_progress_not_found" in str(exc_info.value)


def test_start_assessment_invalid_transition(db, child_user, topic):
    """Start assessment when progress is not 'learning' raises error."""
    # Create progress in 'available' state (not 'learning')
    p = LearningProgress(
        child_id=child_user["id"],
        topic_id=topic.id,
        mastery_level="available",
    )
    db.add(p)
    db.flush()

    req = SessionCreate(topic_id=topic.id)
    session = create_session(db, child_user["id"], req)

    with pytest.raises(AppError) as exc_info:
        start_assessment(db, session.id, child_user["id"])
    assert "invalid_state_transition" in str(exc_info.value)
