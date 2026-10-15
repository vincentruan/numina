"""Tests for practice Pydantic schemas."""
from datetime import UTC, datetime

from apps.backend.app.schemas.practice import QuestionResponse, SessionCreateRequest


def test_question_response_snowflake_serialization():
    q = QuestionResponse(
        id=123456789012345678,
        topic_id=987654321098765432,
        question_type="calculation",
        stem="37 + 58 = ?",
        stem_zh="计算：37 + 58 = ?",
        options=None,
        answer={"answer": 95},
        solution=None,
        difficulty=1,
        bloom_level="apply",
        source="template",
        source_version="v1",
        review_status="approved",
        review_notes=None,
        age_group="mid",
        parameters=None,
        times_used=0,
        correct_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    data = q.model_dump()
    assert isinstance(data["id"], str)
    assert isinstance(data["topic_id"], str)


def test_session_create_request_defaults():
    req = SessionCreateRequest(topic_id=123)
    assert req.session_mode == "practice"
    assert req.count == 5
