"""Tests for the 5 new subject question templates (R13a).

Each template must be registered, generate a valid GeneratedQuestion, and
target a topic key that exists in the os-taxonomy snapshot.
"""

import pytest

import packages.domain.question_templates  # noqa: F401  (triggers @register_template decorators)
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
)

EXPECTED = {
    "history": "history.tutankhamun",
    "personal_social": "personal_social.expressing_feelings",
    "life_skills": "life_skills.buyers_sellers",
    "computing": "computing.ai_daily_life",
    "learning_to_learn": "learning_to_learn.asking_for_help",
}


@pytest.mark.parametrize("subject,template_id", list(EXPECTED.items()))
def test_template_registered(subject: str, template_id: str) -> None:
    assert template_id in TEMPLATE_REGISTRY, f"{subject} template not registered"


@pytest.mark.parametrize("subject,template_id", list(EXPECTED.items()))
def test_template_generates_valid_question(subject: str, template_id: str) -> None:
    q = generate_question(template_id, {})
    assert isinstance(q, GeneratedQuestion)
    assert q.stem
    assert q.answer
    assert q.topic_key.startswith("mt_")
    assert 1 <= q.difficulty <= 5
    assert q.bloom_level


@pytest.mark.parametrize("subject,template_id", list(EXPECTED.items()))
def test_template_targets_expected_topic(subject: str, template_id: str) -> None:
    q = generate_question(template_id, {})
    # Each template's topic_key must match the topic we wired into
    # TOPIC_CHALLENGE_MAP for that subject's signature demo.
    expected_topic_keys = {
        "history": "mt_IR8kIjZn_V",
        "personal_social": "mt_kvrvpQris4",
        "life_skills": "mt_SbEaQnMQoD",
        "computing": "mt_AzTrT5ySCx",
        "learning_to_learn": "mt_mvXufozy2s",
    }
    assert q.topic_key == expected_topic_keys[subject]
