"""API tests for the topic hook question endpoint."""

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.hook import TopicHookQuestion
from packages.db.models.learning.topic import LearningTopic
from tests.backend.conftest import child_login_two_phase

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "HookPass123"


def _create_child(client, headers, username="hookchild"):
    resp = client.post(
        "/api/v1/family/children",
        headers=headers,
        json={
            "username": username,
            "password": CHILD_PASSWORD,
            "display_name": "Hook Tester",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


def _create_topic(db: Session, topic_key: str = "hook_topic") -> LearningTopic:
    topic = LearningTopic(
        topic_key=topic_key,
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Hook",
        name="Hook topic",
        description="For hook testing",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
        source_taxonomy="os-taxonomy",
    )
    db.add(topic)
    db.flush()
    return topic


@pytest.fixture
def topic(db):
    return _create_topic(db)


@pytest.fixture
def child_headers(client, auth_headers):
    child = _create_child(client, auth_headers)
    token = child_login_two_phase(client, child["username"], CHILD_PASSWORD, PIN)
    return {"Authorization": f"Bearer {token}"}


def test_hook_returns_null_when_not_seeded(client, child_headers, topic):
    """A topic without a seeded hook returns null — the page then hides the card."""
    resp = client.get(
        f"/api/v1/child/learning/topics/{topic.id}/hook", headers=child_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"] is None


def test_hook_returns_age_matched_question(client, db, child_headers, topic):
    """The endpoint returns the question matching the child's age group."""
    db.add_all(
        [
            TopicHookQuestion(
                topic_id=topic.id,
                review_status="approved",
                question_text="Can you share a cake fairly?",
                question_text_zh="你能公平地分蛋糕吗？",
                age_group="low",
                difficulty="easy",
            ),
            TopicHookQuestion(
                topic_id=topic.id,
                review_status="approved",
                question_text="Why do fractions need a common denominator?",
                question_text_zh="为什么分数需要通分？",
                age_group="mid",
                difficulty="medium",
            ),
            TopicHookQuestion(
                topic_id=topic.id,
                review_status="approved",
                question_text="What does 'common' really mean in common denominator?",
                question_text_zh="公分母里的「公」到底是什么意思？",
                age_group="high",
                difficulty="medium",
            ),
        ]
    )
    db.flush()

    resp = client.get(
        f"/api/v1/child/learning/topics/{topic.id}/hook", headers=child_headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data is not None
    # Child created without a birthday → age group defaults to "mid"
    assert data["age_group"] == "mid"
    assert "common denominator" in data["question_text"]
    # Snowflake ID serialized as string
    assert isinstance(data["id"], str)
    assert isinstance(data["topic_id"], str)


def test_hook_requires_child_auth(client, topic):
    """Adults / unauthenticated callers can't hit the child endpoint."""
    resp = client.get(f"/api/v1/child/learning/topics/{topic.id}/hook")
    assert resp.status_code in (401, 403)
