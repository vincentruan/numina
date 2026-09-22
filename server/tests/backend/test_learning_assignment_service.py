"""Tests for learning assignment service."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.schemas.learning import AssignmentCreate
from apps.backend.app.services.learning.assignment_service import (
    create_assignment,
    get_review_queue,
    list_assignments,
    submit_for_review,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    """Create a learning topic."""
    t = LearningTopic(
        topic_key="mt_assign",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Assignment test topic",
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
            "username": "assignchild",
            "password": "ChildPass1",
            "display_name": "Assign Learner",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child = resp.json()["data"]
    return {"id": int(child["id"])}


@pytest.fixture
def adult_user(db, auth_headers):
    """Return a User-like object with family_id from the auth_headers context."""
    from apps.backend.app.models.user import User

    user = db.query(User).filter(User.username == "testuser").first()
    assert user is not None
    return user


def test_create_assignment(db, adult_user, child_user, topic):
    """Create an assignment for a child."""
    req = AssignmentCreate(
        child_id=child_user["id"],
        topic_id=topic.id,
        assignment_type="parent_assigned",
        priority=1,
    )
    assignment = create_assignment(db, adult_user, req)
    assert assignment.id is not None
    assert assignment.child_id == child_user["id"]
    assert assignment.topic_id == topic.id
    assert assignment.family_id == adult_user.family_id
    assert assignment.status == "pending"
    assert assignment.assignment_type == "parent_assigned"


def test_create_assignment_also_creates_progress(db, adult_user, child_user, topic):
    """Creating an assignment also creates a progress record."""
    req = AssignmentCreate(
        child_id=child_user["id"],
        topic_id=topic.id,
    )
    create_assignment(db, adult_user, req)
    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_user["id"], topic_id=topic.id)
        .first()
    )
    assert progress is not None


def test_create_assignment_topic_not_found(db, adult_user, child_user):
    """Creating an assignment with a nonexistent topic raises an error."""
    req = AssignmentCreate(
        child_id=child_user["id"],
        topic_id=99999,
    )
    with pytest.raises(AppError) as exc_info:
        create_assignment(db, adult_user, req)
    assert "learning_topic_not_found" in str(exc_info.value)


def test_list_assignments(db, adult_user, child_user, topic):
    """List assignments for a child."""
    req = AssignmentCreate(child_id=child_user["id"], topic_id=topic.id)
    create_assignment(db, adult_user, req)
    results = list_assignments(db, child_user["id"])
    assert len(results) == 1
    assert results[0].child_id == child_user["id"]


def test_list_assignments_by_status(db, adult_user, child_user, topic):
    """List assignments filtered by status."""
    req = AssignmentCreate(child_id=child_user["id"], topic_id=topic.id)
    create_assignment(db, adult_user, req)
    results = list_assignments(db, child_user["id"], status="pending")
    assert len(results) == 1
    results = list_assignments(db, child_user["id"], status="completed")
    assert len(results) == 0


def test_submit_for_review(db, adult_user, child_user, topic):
    """Submit an assignment for parent review transitions progress."""
    req = AssignmentCreate(child_id=child_user["id"], topic_id=topic.id)
    assignment = create_assignment(db, adult_user, req)

    # Set progress to 'learning' state
    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_user["id"], topic_id=topic.id)
        .first()
    )
    progress.mastery_level = "learning"
    db.flush()

    result = submit_for_review(db, assignment.id, child_user["id"])
    assert result.mastery_level == "parent_review"


def test_submit_for_review_assignment_not_found(db, child_user):
    """Submit for review with nonexistent assignment raises error."""
    with pytest.raises(AppError) as exc_info:
        submit_for_review(db, 99999, child_user["id"])
    assert "learning_assignment_not_found" in str(exc_info.value)


def test_submit_for_review_invalid_transition(db, adult_user, child_user, topic):
    """Submit for review when progress is not in 'learning' state raises error."""
    req = AssignmentCreate(child_id=child_user["id"], topic_id=topic.id)
    assignment = create_assignment(db, adult_user, req)
    # Progress is 'available', not 'learning'
    with pytest.raises(AppError) as exc_info:
        submit_for_review(db, assignment.id, child_user["id"])
    assert "invalid_state_transition" in str(exc_info.value)


def test_get_review_queue(db, adult_user, child_user, topic):
    """Get review queue returns parent_review progress records."""
    req = AssignmentCreate(child_id=child_user["id"], topic_id=topic.id)
    assignment = create_assignment(db, adult_user, req)

    # Transition to parent_review
    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_user["id"], topic_id=topic.id)
        .first()
    )
    progress.mastery_level = "learning"
    db.flush()
    submit_for_review(db, assignment.id, child_user["id"])

    queue = get_review_queue(db, adult_user.family_id)
    assert len(queue) == 1
    assert queue[0].child_id == child_user["id"]


def test_get_review_queue_empty(db, adult_user):
    """Empty review queue returns empty list."""
    queue = get_review_queue(db, adult_user.family_id)
    assert queue == []
