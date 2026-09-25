from unittest.mock import patch

import pytest

from apps.backend.app.services.learning.translation import translate_topic


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
