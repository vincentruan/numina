"""Tests for practice API endpoints."""
import json

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_router_test",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Router test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db: Session, topic):
    qs = []
    for i in range(5):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"Q{i}",
            answer_json=json.dumps({"answer": i + 1}),
            difficulty=1,
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        qs.append(q)
    db.flush()
    return qs


def test_create_session_endpoint(client, auth_headers, topic, questions):
    resp = client.post(
        "/api/v1/practice/sessions",
        json={"topic_id": topic.id, "session_mode": "practice", "count": 3},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["session_mode"] == "practice"
    assert len(data["question_ids"]) == 3


def test_submit_answer_endpoint(client, auth_headers, topic, questions):
    # Create session first
    resp = client.post(
        "/api/v1/practice/sessions",
        json={"topic_id": topic.id, "count": 1},
        headers=auth_headers,
    )
    session_id = resp.json()["data"]["id"]

    # Submit answer
    resp = client.post(
        f"/api/v1/practice/sessions/{session_id}/answer",
        json={
            "question_id": questions[0].id,
            "user_answer": {"answer": questions[0].answer["answer"]},
            "time_spent_seconds": 10,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_correct"] is True


def test_finish_session_endpoint(client, auth_headers, topic, questions):
    # Create session
    resp = client.post(
        "/api/v1/practice/sessions",
        json={"topic_id": topic.id, "count": 2},
        headers=auth_headers,
    )
    session_id = resp.json()["data"]["id"]
    q_ids = resp.json()["data"]["question_ids"]

    # Answer 2 questions
    for i, qid in enumerate(q_ids):
        client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": qid,
                "user_answer": {"answer": i + 1},
            },
            headers=auth_headers,
        )

    # Finish
    resp = client.post(
        f"/api/v1/practice/sessions/{session_id}/finish",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_score" in data
    assert data["total_count"] == 2


def test_no_questions_returns_404(client, auth_headers, db):
    """Topic with no approved questions returns error."""
    empty_topic = LearningTopic(
        topic_key="mt_empty_topic",
        topic_type="concept",
        subject="mathematics",
        domain="empty",
        name="Empty",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(empty_topic)
    db.flush()

    resp = client.post(
        "/api/v1/practice/sessions",
        json={"topic_id": int(empty_topic.id), "count": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404
