"""Integration test — full learning flow from assignment to mastery."""

import pytest
from sqlalchemy.orm import Session

from packages.db.models.child_economy.coin_transaction import CoinTransaction
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import (
    LearningAssessmentAttempt,
)
from packages.db.models.learning.topic import LearningTopic
from tests.backend.conftest import child_login_two_phase

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "ChildPass1"


# ── helpers ────────────────────────────────────────────────────────────────────

def _create_child(client, headers, username="learnchild"):
    """Create a child via the parent API and return child dict."""
    resp = client.post(
        "/api/v1/family/children",
        headers=headers,
        json={
            "username": username,
            "password": CHILD_PASSWORD,
            "display_name": "Learn Tester",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


def _create_topic(db: Session, topic_key: str = "integ_topic") -> LearningTopic:
    """Insert a LearningTopic directly into the test DB."""
    topic = LearningTopic(
        topic_key=topic_key,
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Integration",
        name="Integration topic",
        name_zh="积分测试知识点",
        description="For integration testing",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()
    return topic


def _parent_headers(client, auth_headers):
    """Return the parent auth_headers (alias for clarity)."""
    return auth_headers


def _child_headers(client, username="learnchild"):
    """Login as child and return Bearer headers dict."""
    token = child_login_two_phase(client, username, CHILD_PASSWORD, PIN)
    return {"Authorization": f"Bearer {token}"}


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def parent_headers(client, auth_headers):
    """Parent auth headers."""
    return auth_headers


@pytest.fixture
def child_data(client, parent_headers):
    """Create a child user; returns child data dict."""
    return _create_child(client, parent_headers)


@pytest.fixture
def topic(db):
    """Create a learning topic."""
    return _create_topic(db)


@pytest.fixture
def child_token_headers(client, child_data):
    """Child auth headers after login."""
    return _child_headers(client, child_data["username"])


# ── happy-path integration test ───────────────────────────────────────────────

def test_full_learning_flow(
    client, db, parent_headers, child_data, child_token_headers, topic
):
    """End-to-end happy path:
    1. Parent creates assignment
    2. Child sees assignment
    3. Child creates session
    4. Child starts assessment
    5. Child submits for review
    6. Parent sees review
    7. Parent approves
    8. Verify: mastery_level=mastered, coin transaction created
    """
    child_id = int(child_data["id"])

    # 1. Parent creates assignment
    resp = client.post(
        "/api/v1/family/learning/assignments",
        headers=parent_headers,
        json={
            "child_id": child_id,
            "topic_id": topic.id,
            "assignment_type": "parent_assigned",
            "priority": 1,
        },
    )
    assert resp.status_code == 201, resp.text
    assignment = resp.json()["data"]
    assignment_id = int(assignment["id"])
    assert assignment["status"] == "pending"

    # 2. Child sees assignment
    resp = client.get(
        "/api/v1/child/learning/assignments",
        headers=child_token_headers,
    )
    assert resp.status_code == 200
    child_assignments = resp.json()["data"]
    assert len(child_assignments) >= 1
    assert any(int(a["id"]) == assignment_id for a in child_assignments)

    # 3. Child creates session (auto-transitions available -> learning)
    resp = client.post(
        "/api/v1/child/learning/sessions",
        headers=child_token_headers,
        json={
            "topic_id": topic.id,
            "assignment_id": assignment_id,
            "session_type": "study",
        },
    )
    assert resp.status_code == 201, resp.text
    session_data = resp.json()["data"]
    session_id = int(session_data["id"])

    # Verify progress auto-transitioned to 'learning'
    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=topic.id)
        .first()
    )
    assert progress is not None
    assert progress.mastery_level == "learning"

    # 4. Child starts assessment (learning -> assessing)
    resp = client.post(
        f"/api/v1/child/learning/sessions/{session_id}/start-assessment",
        headers=child_token_headers,
    )
    assert resp.status_code == 200, resp.text
    progress_data = resp.json()["data"]
    assert progress_data["mastery_level"] == "assessing"

    # 5. Child submits for review — assessing -> review (valid transition),
    # then from 'review' we need to go back to 'learning' to test submit.
    # Realistic flow: use a fresh progress where child goes learning -> parent_review.
    # Reset progress to 'learning' via valid transition: assessing -> review -> learning
    from apps.backend.app.services.learning.progress_service import (
        validate_transition,
    )
    # assessing -> review is valid
    validate_transition(progress.mastery_level, "review")
    progress.mastery_level = "review"
    db.flush()
    # review -> learning is valid
    validate_transition(progress.mastery_level, "learning")
    progress.mastery_level = "learning"
    db.flush()

    resp = client.post(
        f"/api/v1/child/learning/assignments/{assignment_id}/submit",
        headers=child_token_headers,
    )
    assert resp.status_code == 200, resp.text
    progress_data = resp.json()["data"]
    assert progress_data["mastery_level"] == "parent_review"

    # 6. Parent sees review
    resp = client.get(
        "/api/v1/family/learning/reviews",
        headers=parent_headers,
    )
    assert resp.status_code == 200
    reviews = resp.json()["data"]
    assert len(reviews) >= 1
    review_progress_id = int(reviews[0]["progress_id"])

    # 7. Parent approves
    resp = client.post(
        f"/api/v1/family/learning/reviews/{review_progress_id}/approve",
        headers=parent_headers,
    )
    assert resp.status_code == 200, resp.text
    approved = resp.json()["data"]
    assert approved["mastery_level"] == "mastered"

    # 8. Verify coin transaction was created
    txn = (
        db.query(CoinTransaction)
        .filter(
            CoinTransaction.child_user_id == child_id,
            CoinTransaction.transaction_type == "learning_earn",
        )
        .first()
    )
    assert txn is not None
    assert txn.amount == 10

    # Verify assessment attempt was created
    attempt = (
        db.query(LearningAssessmentAttempt)
        .filter_by(child_id=child_id, topic_id=topic.id)
        .first()
    )
    assert attempt is not None
    assert attempt.passed is True
    assert attempt.assessment_type == "parent_approval"


# ── edge-case tests ───────────────────────────────────────────────────────────

def test_child_cannot_start_locked_topic(
    client, db, parent_headers, topic
):
    """A child cannot start learning a topic that is still locked."""
    child_data = _create_child(client, parent_headers, username="lockedchild")
    child_id = int(child_data["id"])

    # Create a topic with a hard prerequisite that is NOT mastered
    prereq_topic = _create_topic(db, topic_key="prereq_topic")
    dependent_topic = _create_topic(db, topic_key="dependent_topic")

    from packages.db.models.learning.topic import LearningDependency

    dep = LearningDependency(
        topic_id=dependent_topic.id,
        prerequisite_id=prereq_topic.id,
        strength="hard",
    )
    db.add(dep)
    db.flush()

    # Assign the dependent topic
    resp = client.post(
        "/api/v1/family/learning/assignments",
        headers=parent_headers,
        json={
            "child_id": child_id,
            "topic_id": dependent_topic.id,
            "assignment_type": "parent_assigned",
        },
    )
    assert resp.status_code == 201

    # Child logs in
    child_headers = _child_headers(client, "lockedchild")

    # Progress should be 'locked'
    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=dependent_topic.id)
        .first()
    )
    assert progress is not None
    assert progress.mastery_level == "locked"

    # Child tries to create a session for the locked topic — should be rejected
    resp = client.post(
        "/api/v1/child/learning/sessions",
        headers=child_headers,
        json={
            "topic_id": dependent_topic.id,
            "session_type": "study",
        },
    )
    assert resp.status_code == 409  # LEARNING_TOPIC_LOCKED
    error_data = resp.json()
    assert "learning_topic_locked" in error_data.get("code", "")


def test_parent_cannot_approve_non_pending_review(
    client, db, parent_headers, topic
):
    """Parent cannot approve a progress that is not in parent_review state."""
    child_data = _create_child(client, parent_headers, username="nonpendchild")
    child_id = int(child_data["id"])

    # Create assignment and progress
    resp = client.post(
        "/api/v1/family/learning/assignments",
        headers=parent_headers,
        json={
            "child_id": child_id,
            "topic_id": topic.id,
            "assignment_type": "parent_assigned",
        },
    )
    assert resp.status_code == 201

    # Progress is 'available', not 'parent_review'
    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=topic.id)
        .first()
    )
    assert progress is not None

    # Try to approve — should fail
    resp = client.post(
        f"/api/v1/family/learning/reviews/{progress.id}/approve",
        headers=parent_headers,
    )
    assert resp.status_code == 409
    error_data = resp.json()
    assert "invalid_state_transition" in error_data.get("code", "")


def test_state_transition_validation(client, db, parent_headers, topic):
    """Invalid state transitions are rejected."""
    child_data = _create_child(client, parent_headers, username="transchild")
    child_id = int(child_data["id"])

    # Create assignment → progress starts as 'available'
    resp = client.post(
        "/api/v1/family/learning/assignments",
        headers=parent_headers,
        json={
            "child_id": child_id,
            "topic_id": topic.id,
            "assignment_type": "parent_assigned",
        },
    )
    assert resp.status_code == 201

    child_headers = _child_headers(client, "transchild")

    # Try to submit for review directly from 'available' — should fail
    assignment_id = int(resp.json()["data"]["id"])
    resp = client.post(
        f"/api/v1/child/learning/assignments/{assignment_id}/submit",
        headers=child_headers,
    )
    assert resp.status_code == 409
    error_data = resp.json()
    assert "invalid_state_transition" in error_data.get("code", "")
