"""Tests for Phase 5 practice GET endpoints."""

import json

import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy.orm import Session

from apps.backend.app.models.user import User
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.question import Question
from packages.db.models.learning.practice import PracticeSession, PracticeAttempt


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_p5_router",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Router Test",
        name_zh="路由测试",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def question(db: Session, topic):
    q = Question(
        topic_id=topic.id,
        question_type="calculation",
        stem="1 + 1 = ?",
        answer_json='{"answer": 2}',
        difficulty=1,
        bloom_level="apply",
        source="template",
        review_status="approved",
        age_group="mid",
    )
    db.add(q)
    db.flush()
    return q


def _get_child_id(client, auth_headers) -> int:
    """Extract the authenticated user's ID via /auth/me."""
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    return int(resp.json()["data"]["id"])


@pytest.fixture
def session_with_attempts(db: Session, client, auth_headers, topic, question):
    """Create a completed session with one correct attempt, using real child_id."""
    child_id = _get_child_id(client, auth_headers)

    s = PracticeSession(
        child_id=child_id,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json=json.dumps([question.id]),
        source="adaptive",
        started_at=datetime.now(UTC) - timedelta(hours=1),
        ended_at=datetime.now(UTC),
        total_score=1.0,
        completed_count=1,
    )
    db.add(s)
    db.flush()
    db.add(PracticeAttempt(
        session_id=s.id,
        question_id=question.id,
        child_id=child_id,
        topic_id=topic.id,
        user_answer_json='{"answer": 2}',
        is_correct=True,
        time_spent_seconds=10,
        attempt_number=1,
    ))
    db.flush()
    return s


def test_weak_topics_endpoint(client, auth_headers, topic, session_with_attempts):
    """GET /practice/weak-topics returns weak topic list."""
    resp = client.get(
        "/api/v1/practice/weak-topics",
        params={"limit": 10, "min_attempts": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    w = data[0]
    assert w["topic_id"] == str(topic.id)
    assert w["topic_name"] == "Router Test"
    assert w["accuracy"] == 1.0


def test_list_sessions_endpoint(client, auth_headers, topic, session_with_attempts):
    """GET /practice/sessions returns session history."""
    resp = client.get(
        "/api/v1/practice/sessions",
        params={"limit": 20, "offset": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    s = data[0]
    assert s["id"] == str(session_with_attempts.id)
    assert s["topic_name"] == "Router Test"
    assert s["total_count"] == 1


def test_session_detail_endpoint(client, auth_headers, topic, session_with_attempts):
    """GET /practice/sessions/{id} returns full detail with attempts."""
    resp = client.get(
        f"/api/v1/practice/sessions/{session_with_attempts.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == str(session_with_attempts.id)
    assert data["topic_name"] == "Router Test"
    assert len(data["attempts"]) == 1
    assert data["attempts"][0]["is_correct"] is True
    assert data["attempts"][0]["question_stem"] == "1 + 1 = ?"


def test_session_detail_not_found(client, auth_headers):
    """GET /practice/sessions/{id} returns error for non-existent session."""
    resp = client.get(
        "/api/v1/practice/sessions/999999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_recommend_endpoint_no_topic(client, auth_headers, topic, session_with_attempts):
    """GET /practice/recommend without topic_id returns overall weak topics."""
    resp = client.get(
        "/api/v1/practice/recommend",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    for rec in data:
        assert rec["is_prerequisite"] is False
        assert rec["prerequisite_of_topic_id"] is None


def test_recommend_endpoint_with_topic(client, auth_headers, topic):
    """GET /practice/recommend?topic_id=X returns weak prerequisites."""
    resp = client.get(
        "/api/v1/practice/recommend",
        params={"topic_id": topic.id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    for rec in data:
        assert rec["is_prerequisite"] is True
        assert rec["prerequisite_of_topic_id"] == str(topic.id)
