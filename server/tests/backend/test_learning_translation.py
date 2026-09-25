from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.translation import (
    _call_llm,
    translate_batch,
    translate_topic,
)
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def sample_topic():
    return {
        "topic_key": "mt_001",
        "name": "Fraction Basics",
        "description": "Introduction to fractions and their properties.",
        "evidence": ["Can identify halves", "Can compare simple fractions"],
        "assessment_prompt": "Ask the child to explain what a fraction is.",
    }


@pytest.fixture
def mock_llm_response():
    return {
        "name_zh": "分数基础",
        "description_zh": "分数及其性质的介绍。",
        "evidence_zh": ["能识别二分之一", "能比较简单分数"],
        "assessment_prompt_zh": "让孩子解释什么是分数。",
    }


def test_translate_topic_returns_all_fields(sample_topic, mock_llm_response):
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm, \
         patch("apps.backend.app.services.learning.translation._get_api_key", return_value="fake-key"):
        mock_llm.return_value = mock_llm_response
        result = translate_topic(sample_topic)
    assert result["name_zh"] == "分数基础"
    assert result["description_zh"] == "分数及其性质的介绍。"
    assert len(result["evidence_zh"]) == 2
    assert result["assessment_prompt_zh"] == "让孩子解释什么是分数。"


def test_translate_topic_no_api_key_raises(sample_topic):
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("apps.backend.app.services.learning.translation._get_api_key", return_value=None),
        pytest.raises(ValueError, match="LLM API key not configured"),
    ):
        translate_topic(sample_topic)


def test_translate_topic_preserves_evidence_count(sample_topic, mock_llm_response):
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm, \
         patch("apps.backend.app.services.learning.translation._get_api_key", return_value="fake-key"):
        mock_llm.return_value = mock_llm_response
        result = translate_topic(sample_topic)
    assert len(result["evidence_zh"]) == len(sample_topic["evidence"])


def test_translate_topic_long_description_truncated():
    topic = {
        "topic_key": "mt_long",
        "name": "Test",
        "description": "word " * 3000,  # ~18000 chars
        "evidence": ["e1"],
        "assessment_prompt": "prompt",
    }
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm, \
         patch("apps.backend.app.services.learning.translation._get_api_key", return_value="fake-key"):
        mock_llm.return_value = {
            "name_zh": "测试", "description_zh": "翻译", "evidence_zh": ["e1"], "assessment_prompt_zh": "提示",
        }
        result = translate_topic(topic)
    # Verify the function handled long input without error
    assert result["name_zh"] == "测试"
    # Verify _call_llm received truncated content (under ~4000 chars for description)
    call_args = mock_llm.call_args
    assert len(call_args[0][0]) < 5000  # prompt passed to LLM is bounded


def test_call_llm_malformed_json_raises():
    """LLM returning invalid JSON should raise a descriptive ValueError."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not valid json {"

    with (
        patch("apps.backend.app.services.learning.translation._get_api_key", return_value="fake-key"),
        patch("openai.OpenAI") as mock_openai,
    ):
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with pytest.raises(ValueError, match="LLM returned malformed translation response"):
            _call_llm("translate this")


def test_call_llm_empty_content_raises():
    """LLM returning None/empty content should raise a descriptive ValueError."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = None

    with (
        patch("apps.backend.app.services.learning.translation._get_api_key", return_value="fake-key"),
        patch("openai.OpenAI") as mock_openai,
    ):
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with pytest.raises(ValueError, match="LLM returned empty response"):
            _call_llm("translate this")


def test_call_llm_missing_keys_raises():
    """LLM returning JSON without required keys should raise a descriptive ValueError."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"name_zh": "测试"}'

    with (
        patch("apps.backend.app.services.learning.translation._get_api_key", return_value="fake-key"),
        patch("openai.OpenAI") as mock_openai,
    ):
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with pytest.raises(ValueError, match="LLM response missing required key"):
            _call_llm("translate this")


def test_translate_batch_raises_not_implemented():
    """translate_batch should fail loudly instead of silently returning empty."""
    with pytest.raises(NotImplementedError, match="Batch translation not supported"):
        translate_batch([{"name": "test"}])


# --- Endpoint tests (OQ-2) ---------------------------------------------------


@pytest.fixture
def english_topic(db: Session):
    topic = LearningTopic(
        topic_key="mt_translate_test",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Fractions",
        name="Fraction Basics",
        description="Introduction to fractions.",
        age_group="mid",
        evidence_json='["Can identify halves"]',
        standards_json="[]",
    )
    db.add(topic)
    db.flush()
    return topic


def test_translate_endpoint_persists_translation(client, db: Session, english_topic, auth_headers):
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm, \
         patch("apps.backend.app.services.learning.translation._get_api_key", return_value="fake-key"):
        mock_llm.return_value = {
            "name_zh": "分数基础",
            "description_zh": "分数介绍。",
            "evidence_zh": ["能识别二分之一"],
            "assessment_prompt_zh": "问孩子什么是分数。",
        }
        resp = client.post(f"/api/v1/learning/topics/{english_topic.id}/translate", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name_zh"] == "分数基础"

    # Verify persisted in DB
    db.refresh(english_topic)
    assert english_topic.name_zh == "分数基础"
    assert english_topic.description_zh == "分数介绍。"


def test_translate_endpoint_idempotent(client, db: Session, english_topic, auth_headers):
    """Re-translating overwrites with fresh translation."""
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm, \
         patch("apps.backend.app.services.learning.translation._get_api_key", return_value="fake-key"):
        mock_llm.return_value = {
            "name_zh": "第一版", "description_zh": "第一版描述",
            "evidence_zh": [], "assessment_prompt_zh": "",
        }
        client.post(f"/api/v1/learning/topics/{english_topic.id}/translate", headers=auth_headers)

        mock_llm.return_value = {
            "name_zh": "第二版", "description_zh": "第二版描述",
            "evidence_zh": [], "assessment_prompt_zh": "",
        }
        resp = client.post(f"/api/v1/learning/topics/{english_topic.id}/translate", headers=auth_headers)

    assert resp.json()["data"]["name_zh"] == "第二版"
    db.refresh(english_topic)
    assert english_topic.name_zh == "第二版"


def test_translate_endpoint_topic_not_found(client, auth_headers):
    resp = client.post("/api/v1/learning/topics/999999/translate", headers=auth_headers)
    assert resp.status_code == 404


def test_translate_endpoint_no_api_key(client, db: Session, english_topic, auth_headers):
    with patch("apps.backend.app.services.learning.translation._get_api_key", return_value=None):
        resp = client.post(f"/api/v1/learning/topics/{english_topic.id}/translate", headers=auth_headers)
    assert resp.status_code == 503
