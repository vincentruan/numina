# Learning OS — OQ Product Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement three confirmed product decisions — on-demand topic translation (OQ-2), failure streak notification (OQ-3), and seed data quality validation (OQ-6).

**Architecture:** Translation uses a lightweight LLM service in the backend (OpenAI SDK → DashScope endpoint) with a new REST endpoint and frontend translate button. Failure streak detection is inline in `progress_service`, dispatching via the existing notification framework. Seed validation adds two new checks to the existing `validate_quality()` function.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + OpenAI SDK (DashScope) | Vue 3 + TypeScript + Vant 4 + vue-i18n

**Spec:** `docs/superpowers/specs/2026-09-24-learning-os-oq-product-decisions.md`

## Global Constraints

- All IDs are Snowflake BigInteger — serialized as `string` in API responses, typed as `string` in TypeScript
- API endpoints respond directly (no 307 redirects) — root-path decorators use `""` not `"/"`
- Response schemas inherit `SnowflakeBase`; request schemas use plain `BaseModel`
- Auth: global learning endpoints require no auth; notification dispatch uses `ensure_reminder()` pattern
- Errors use `AppError(ErrorCode.XXX)` with i18n — add new codes to `errors/codes.py` + locale files
- All user-facing strings use `t('key')` — no hardcoded Chinese in templates
- Models: `from packages.db.session import Base, UTCDateTime` + `from packages.core.snowflake import next_id`
- Tests: SAVEPOINT-isolated `db` fixture, `client` fixture, IDs compared as strings
- Commands from `server/`: `uv run pytest`, `uv run ruff check`, `uv run ruff format`, `uv run alembic`

## Review Focus

1. **LLM config unavailable** — translation endpoint returns a clear error (not 500) when `DASHSCOPE_API_KEY` is missing or the LLM is unreachable. Test: set no env var, call endpoint, expect 503 with `TRANSLATION_SERVICE_UNAVAILABLE`.
2. **Very long topic content exceeds LLM token limit** — `description` can be multi-paragraph text. Truncate or chunk before sending. Test: topic with 3000-word description → translation succeeds without API error.
3. **Streak notification fires exactly once per 3-failure sequence** — 4th consecutive failure must NOT fire a duplicate notification. Test: 4 consecutive `passed=False` → exactly 1 notification created.
4. **Badge dimension validation false positive** — badge model uses `dimension` (ability dimension like `"numerical_reasoning"`), NOT topic subject. A topic with `subject="music"` has no bearing on badge validity. Test: topic with subject `"music"` (no related badges) → validation passes.
5. **Age range null handling** — `age_range_start` and `age_range_end` are both nullable. Validation must skip when either is null, only check when both are non-null. Test: topic with `age_range_start=8, age_range_end=None` → validation passes.

---

### Task 1: Translation Service — LLM Integration

**Files:**
- Modify: `server/apps/backend/app/services/learning/translation.py` (replace placeholder)
- Test: `server/tests/backend/test_learning_translation.py`

**Interfaces:**
- Consumes: LLM config from env (`DASHSCOPE_API_KEY`)
- Produces: `translate_topic(topic: dict) -> dict` returning `{name_zh, description_zh, evidence_zh, assessment_prompt_zh}`
- Consumed by: Task 2 (API endpoint)

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/test_learning_translation.py
import pytest
from unittest.mock import patch, MagicMock

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
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm:
        mock_llm.return_value = mock_llm_response
        result = translate_topic(sample_topic)
    assert result["name_zh"] == "分数基础"
    assert result["description_zh"] == "分数及其性质的介绍。"
    assert len(result["evidence_zh"]) == 2
    assert result["assessment_prompt_zh"] == "让孩子解释什么是分数。"


def test_translate_topic_no_api_key_raises(sample_topic):
    with patch.dict("os.environ", {}, clear=True):
        with patch("apps.backend.app.services.learning.translation._get_api_key", return_value=None):
            with pytest.raises(ValueError, match="LLM API key not configured"):
                translate_topic(sample_topic)


def test_translate_topic_preserves_evidence_count(sample_topic, mock_llm_response):
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm:
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
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm:
        mock_llm.return_value = {
            "name_zh": "测试", "description_zh": "翻译", "evidence_zh": ["e1"], "assessment_prompt_zh": "提示",
        }
        result = translate_topic(topic)
    # Verify the function handled long input without error
    assert result["name_zh"] == "测试"
    # Verify _call_llm received truncated content (under ~4000 chars for description)
    call_args = mock_llm.call_args
    assert len(call_args[0][0]) < 5000  # prompt passed to LLM is bounded
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_translation.py -v`
Expected: FAIL — `_call_llm` and `_get_api_key` don't exist yet

- [ ] **Step 3: Implement translation service**

Replace the placeholder in `server/apps/backend/app/services/learning/translation.py`:

```python
"""On-demand topic translation via LLM (DashScope OpenAI-compatible endpoint)."""

import json
import logging
import os

logger = logging.getLogger(__name__)

# Preserved from original placeholder
ABILITY_DIMENSIONS = [
    "numerical_reasoning", "spatial_reasoning", "verbal_reasoning",
    "scientific_inquiry", "computational_thinking", "social_emotional",
    "creative_thinking", "physical_kinesthetic", "memory_recall", "metacognition",
]

# Max description length sent to LLM (characters) — prevents token limit issues
_MAX_DESCRIPTION_CHARS = 3000
_MAX_EVIDENCE_ITEMS = 10


def _get_api_key() -> str | None:
    """Return DashScope API key from environment, or None."""
    return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")


def _get_base_url() -> str:
    return os.environ.get(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


def _get_model() -> str:
    return os.environ.get("TRANSLATION_MODEL", "qwen-plus")


def _call_llm(prompt: str) -> dict:
    """Call LLM with a translation prompt, return parsed JSON response."""
    from openai import OpenAI

    api_key = _get_api_key()
    if not api_key:
        raise ValueError("LLM API key not configured")

    client = OpenAI(api_key=api_key, base_url=_get_base_url())
    response = client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": _TRANSLATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


_TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional translator specializing in children's education content. "
    "Translate the following English learning topic into Chinese (Simplified). "
    "Preserve technical/mathematical terms in parentheses where helpful. "
    "Return JSON with exactly these keys: name_zh, description_zh, evidence_zh (array), assessment_prompt_zh."
)


def translate_topic(topic: dict) -> dict:
    """Translate a topic's English content to Chinese.

    Args:
        topic: dict with keys: name, description, evidence (list), assessment_prompt

    Returns:
        dict with keys: name_zh, description_zh, evidence_zh, assessment_prompt_zh

    Raises:
        ValueError: if LLM API key is not configured
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("LLM API key not configured")

    # Truncate long content to stay within LLM token limits
    description = topic.get("description", "")
    if len(description) > _MAX_DESCRIPTION_CHARS:
        description = description[:_MAX_DESCRIPTION_CHARS] + "..."

    evidence = topic.get("evidence", [])[:_MAX_EVIDENCE_ITEMS]

    prompt = (
        f"Topic name: {topic.get('name', '')}\n"
        f"Description: {description}\n"
        f"Evidence points: {json.dumps(evidence, ensure_ascii=False)}\n"
        f"Assessment prompt: {topic.get('assessment_prompt', '')}"
    )

    return _call_llm(prompt)


def derive_ability_dimensions(topic: dict) -> list[str]:
    """Derive ability dimensions from topic metadata. Out of scope for OQ-2."""
    return []


def translate_batch(topics: list[dict], batch_size: int = 50) -> list[dict]:
    """Translate a batch of topics. Not used for on-demand translation."""
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/backend/test_learning_translation.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Run linter**

Run: `cd server && uv run ruff check apps/backend/app/services/learning/translation.py tests/backend/test_learning_translation.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/services/learning/translation.py server/tests/backend/test_learning_translation.py
git commit -m "feat(learning): implement LLM translation service (OQ-2)"
```

---

### Task 2: Translation API Endpoint

**Files:**
- Modify: `server/apps/backend/app/routers/learning.py` — add POST endpoint
- Modify: `server/apps/backend/app/errors/codes.py` — add `LEARNING_TRANSLATION_UNAVAILABLE`
- Modify: `server/apps/backend/app/errors/locales/zh-CN.json` — add message
- Modify: `server/apps/backend/app/errors/locales/en-US.json` — add message
- Test: `server/tests/backend/test_learning_translation.py` (append endpoint tests)

**Interfaces:**
- Consumes: `translate_topic()` from Task 1, `LearningTopic` model
- Produces: `POST /api/v1/learning/topics/{topic_id}/translate` endpoint
- Consumed by: Task 7 (frontend)

- [ ] **Step 1: Add error code**

In `server/apps/backend/app/errors/codes.py`, add to the `ErrorCode` enum:

```python
LEARNING_TRANSLATION_UNAVAILABLE = "LEARNING_TRANSLATION_UNAVAILABLE"
```

Add to `ERROR_META`:
```python
ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE: (503, "Translation service unavailable"),
```

Add locale strings in `zh-CN.json`:
```json
"LEARNING_TRANSLATION_UNAVAILABLE": "翻译服务暂不可用，请稍后重试"
```

Add in `en-US.json`:
```json
"LEARNING_TRANSLATION_UNAVAILABLE": "Translation service unavailable, please try again later"
```

- [ ] **Step 2: Write failing endpoint tests (append to test file)**

```python
# Append to server/tests/backend/test_learning_translation.py

from sqlalchemy.orm import Session
from packages.db.models.learning.topic import LearningTopic


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


def test_translate_endpoint_persists_translation(client, db: Session, english_topic):
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm:
        mock_llm.return_value = {
            "name_zh": "分数基础",
            "description_zh": "分数介绍。",
            "evidence_zh": ["能识别二分之一"],
            "assessment_prompt_zh": "问孩子什么是分数。",
        }
        resp = client.post(f"/api/v1/learning/topics/{english_topic.id}/translate")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name_zh"] == "分数基础"

    # Verify persisted in DB
    db.refresh(english_topic)
    assert english_topic.name_zh == "分数基础"
    assert english_topic.description_zh == "分数介绍。"


def test_translate_endpoint_idempotent(client, db: Session, english_topic):
    """Re-translating overwrites with fresh translation."""
    with patch("apps.backend.app.services.learning.translation._call_llm") as mock_llm:
        mock_llm.return_value = {
            "name_zh": "第一版", "description_zh": "第一版描述",
            "evidence_zh": [], "assessment_prompt_zh": "",
        }
        client.post(f"/api/v1/learning/topics/{english_topic.id}/translate")

        mock_llm.return_value = {
            "name_zh": "第二版", "description_zh": "第二版描述",
            "evidence_zh": [], "assessment_prompt_zh": "",
        }
        resp = client.post(f"/api/v1/learning/topics/{english_topic.id}/translate")

    assert resp.json()["data"]["name_zh"] == "第二版"
    db.refresh(english_topic)
    assert english_topic.name_zh == "第二版"


def test_translate_endpoint_topic_not_found(client):
    resp = client.post("/api/v1/learning/topics/999999/translate")
    assert resp.status_code == 404


def test_translate_endpoint_no_api_key(client, db: Session, english_topic):
    with patch("apps.backend.app.services.learning.translation._get_api_key", return_value=None):
        resp = client.post(f"/api/v1/learning/topics/{english_topic.id}/translate")
    assert resp.status_code == 503
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_translation.py -v -k "endpoint"`
Expected: FAIL — endpoint doesn't exist yet

- [ ] **Step 4: Implement the endpoint**

Add to `server/apps/backend/app/routers/learning.py`:

```python
# Add imports at top
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services.learning.translation import translate_topic

# ... existing endpoints ...


@router.post("/topics/{topic_id}/translate")
def translate_topic_endpoint(
    topic_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_adult),  # LLM calls cost money — require auth
):
    """Translate a topic's English content to Chinese on demand."""
    from packages.db.models.learning.topic import LearningTopic

    topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

    topic_dict = {
        "name": topic.name or "",
        "description": topic.description or "",
        "evidence": topic.evidence or [],
        "assessment_prompt": topic.assessment_prompt or "",
    }

    try:
        translated = translate_topic(topic_dict)
    except ValueError:
        raise AppError(ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE)
    except Exception:
        logger.exception("Translation LLM call failed for topic %s", topic_id)
        raise AppError(ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE)

    # Persist translated fields
    topic.name_zh = translated.get("name_zh")
    topic.description_zh = translated.get("description_zh")
    if translated.get("evidence_zh") is not None:
        topic.evidence_zh_json = json.dumps(translated["evidence_zh"], ensure_ascii=False)
    topic.assessment_prompt_zh = translated.get("assessment_prompt_zh")
    db.flush()

    return {
        "name_zh": topic.name_zh,
        "description_zh": topic.description_zh,
        "evidence_zh": topic.evidence_zh,
        "assessment_prompt_zh": topic.assessment_prompt_zh,
    }
```

Add `import json` and `import logging` at the top of the router file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/backend/test_learning_translation.py -v`
Expected: All tests PASS (both service tests from Task 1 and endpoint tests)

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/routers/learning.py server/apps/backend/app/errors/
git commit -m "feat(learning): add translation API endpoint (OQ-2)"
```

---

### Task 3: Topic Read Fallback — Prefer Translated Fields

**Files:**
- Modify: `server/apps/backend/app/schemas/learning.py` — add locale-aware response helper
- Modify: `server/apps/backend/app/routers/learning.py` — update topic read endpoints
- Test: `server/tests/backend/test_learning_translation.py` (append fallback tests)

**Interfaces:**
- Consumes: `LearningTopic` model with `_zh` fields populated
- Produces: Topic responses that return Chinese fields when available, English otherwise
- Consumed by: Task 7 (frontend displays returned values directly)

- [ ] **Step 1: Write failing fallback tests**

```python
# Append to server/tests/backend/test_learning_translation.py


def test_topic_response_prefers_translated_fields(client, db: Session, english_topic):
    """When _zh fields are populated, topic GET returns them."""
    english_topic.name_zh = "分数基础"
    english_topic.description_zh = "分数介绍。"
    db.flush()

    resp = client.get(f"/api/v1/learning/topics/{english_topic.id}")
    data = resp.json()["data"]
    assert data["name"] == "分数基础"
    assert data["description"] == "分数介绍。"


def test_topic_response_falls_back_to_english(client, db: Session, english_topic):
    """When _zh fields are None, topic GET returns English originals."""
    resp = client.get(f"/api/v1/learning/topics/{english_topic.id}")
    data = resp.json()["data"]
    assert data["name"] == "Fraction Basics"
    assert data["description"] == "Introduction to fractions."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_translation.py -v -k "fallback or prefers"`
Expected: FAIL — current endpoint returns English fields regardless

- [ ] **Step 3: Implement locale-aware topic response**

Add a helper function in `server/apps/backend/app/routers/learning.py` (or a small utility in `topic_service.py`):

```python
def _topic_to_response(topic: LearningTopic) -> dict:
    """Convert topic to response dict, preferring translated fields when available."""
    return {
        "id": topic.id,
        "topic_key": topic.topic_key,
        "topic_type": topic.topic_type,
        "subject": topic.subject,
        "domain": topic.domain,
        "name": topic.name_zh or topic.name,
        "description": topic.description_zh or topic.description,
        "age_range_start": topic.age_range_start,
        "age_range_end": topic.age_range_end,
        "age_group": topic.age_group,
        "centrality": topic.centrality,
        "evidence": topic.evidence_zh or topic.evidence or [],
        "assessment_prompt": topic.assessment_prompt_zh or topic.assessment_prompt,
        "standards": topic.standards or [],
        "ability_dimensions": topic.ability_dimensions,
        "deprecated": topic.deprecated,
        # Expose raw fields so frontend can detect translation status
        "name_zh": topic.name_zh,
        "description_zh": topic.description_zh,
        "evidence_zh": topic.evidence_zh,
        "assessment_prompt_zh": topic.assessment_prompt_zh,
    }
```

Update the existing `get_topic` and `list_topics` endpoints to use this helper instead of returning the ORM object directly. The response shape stays compatible — `name` and `description` now contain the best-available language, while `_zh` fields let the frontend detect whether translation exists.

**Integration note:** The existing endpoints use `response_model=TopicResponse`. The `TopicResponse` schema already has `name_zh`, `description_zh`, `evidence_zh`, `assessment_prompt_zh` fields, so the helper's extra keys are compatible. Update `get_topic` to call `_topic_to_response(topic)` and return the dict (FastAPI will validate against `response_model`). For `list_topics`, map each ORM object through the helper: `return [_topic_to_response(t) for t in topics]`.

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest tests/backend/test_learning_translation.py -v`
Expected: All PASS

- [ ] **Step 5: Run full learning test suite to verify no regressions**

Run: `cd server && uv run pytest tests/backend/ -v -k "learning"`
Expected: All pass — the response shape is backward-compatible (same keys, just better values)

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/routers/learning.py server/tests/backend/test_learning_translation.py
git commit -m "feat(learning): topic responses prefer translated fields with English fallback (OQ-2)"
```

---

### Task 4: Failure Streak Detection Service

**Files:**
- Modify: `server/apps/backend/app/services/learning/progress_service.py` — add `record_failed_assessment` + streak check
- Test: `server/tests/backend/test_learning_streak_detection.py`

**Interfaces:**
- Consumes: `LearningAssessmentAttempt`, `LearningProgress`, `LearningTopic` models
- Produces: `record_failed_assessment(db, child_id, topic_id, session_id, score) -> bool` (returns True if streak notification fired)
- Consumed by: Task 5 (notification dispatch). **Note:** the actual caller that invokes `record_failed_assessment` when `passed=False` must be wired separately — identify the assessment recording path (likely `session_service.py` or the MCP tool handler) and add the call there.

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/test_learning_streak_detection.py
import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningAssessmentAttempt
from apps.backend.app.services.learning.progress_service import (
    get_or_create_progress,
    record_failed_assessment,
    check_consecutive_failures,
)


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_streak", topic_type="CONCEPTUAL", subject="mathematics",
        domain="Test", name="Streak Test", description="Test",
        age_group="mid", evidence_json="[]", standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def child(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "username": "streakchild", "password": "ChildPass1",
        "display_name": "Streak Kid", "avatar_emojis": ["🐱"],
    })
    return resp.json()["data"]


def test_check_consecutive_failures_below_threshold(db, child, topic):
    """1-2 consecutive failures do not trigger."""
    for i in range(2):
        attempt = LearningAssessmentAttempt(
            child_id=int(child["id"]), topic_id=topic.id,
            assessment_type="ai", passed=False, score=0.4,
        )
        db.add(attempt)
    db.flush()

    assert check_consecutive_failures(db, int(child["id"]), topic.id) == 2


def test_check_consecutive_failures_at_threshold(db, child, topic):
    """Exactly 3 consecutive failures triggers."""
    for i in range(3):
        attempt = LearningAssessmentAttempt(
            child_id=int(child["id"]), topic_id=topic.id,
            assessment_type="ai", passed=False, score=0.3,
        )
        db.add(attempt)
    db.flush()

    assert check_consecutive_failures(db, int(child["id"]), topic.id) == 3


def test_check_consecutive_failures_interrupted_by_pass(db, child, topic):
    """A passing attempt breaks the streak."""
    # 2 failures
    for _ in range(2):
        db.add(LearningAssessmentAttempt(
            child_id=int(child["id"]), topic_id=topic.id,
            assessment_type="ai", passed=False, score=0.3,
        ))
    # 1 pass
    db.add(LearningAssessmentAttempt(
        child_id=int(child["id"]), topic_id=topic.id,
        assessment_type="ai", passed=True, score=0.9,
    ))
    # 1 more failure
    db.add(LearningAssessmentAttempt(
        child_id=int(child["id"]), topic_id=topic.id,
        assessment_type="ai", passed=False, score=0.4,
    ))
    db.flush()

    assert check_consecutive_failures(db, int(child["id"]), topic.id) == 1


def test_check_consecutive_failures_different_topics_isolated(db, child, topic):
    """Failures on different topics don't count toward the same streak."""
    topic2 = LearningTopic(
        topic_key="mt_streak2", topic_type="CONCEPTUAL", subject="mathematics",
        domain="Test", name="Other Topic", description="Test",
        age_group="mid", evidence_json="[]", standards_json="[]",
    )
    db.add(topic2)
    db.flush()

    # 2 failures on topic 1
    for _ in range(2):
        db.add(LearningAssessmentAttempt(
            child_id=int(child["id"]), topic_id=topic.id,
            assessment_type="ai", passed=False, score=0.3,
        ))
    # 1 failure on topic 2
    db.add(LearningAssessmentAttempt(
        child_id=int(child["id"]), topic_id=topic2.id,
        assessment_type="ai", passed=False, score=0.3,
    ))
    db.flush()

    assert check_consecutive_failures(db, int(child["id"]), topic.id) == 2
    assert check_consecutive_failures(db, int(child["id"]), topic2.id) == 1


def test_record_failed_assessment_returns_streak_count(db, child, topic):
    get_or_create_progress(db, int(child["id"]), topic.id)

    count1 = record_failed_assessment(db, int(child["id"]), topic.id, None, 0.4)
    assert count1 == 1  # not triggered yet

    count2 = record_failed_assessment(db, int(child["id"]), topic.id, None, 0.3)
    assert count2 == 2

    count3 = record_failed_assessment(db, int(child["id"]), topic.id, None, 0.2)
    assert count3 == 3  # streak! notification should fire
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_streak_detection.py -v`
Expected: FAIL — functions don't exist yet

- [ ] **Step 3: Implement streak detection in progress_service.py**

Add to `server/apps/backend/app/services/learning/progress_service.py`:

```python
from packages.db.models.learning.session import LearningAssessmentAttempt

STREAK_THRESHOLD = 3


def check_consecutive_failures(db: Session, child_id: int, topic_id: int) -> int:
    """Count consecutive failed assessments for a child on a specific topic.

    Walks backward from the most recent attempt. Stops at the first pass
    or beginning of attempts.

    Returns:
        Number of consecutive failures (0 if last attempt passed or no attempts).
    """
    attempts = (
        db.query(LearningAssessmentAttempt)
        .filter_by(child_id=child_id, topic_id=topic_id)
        .order_by(LearningAssessmentAttempt.created_at.desc())
        .all()
    )
    streak = 0
    for attempt in attempts:
        if not attempt.passed:
            streak += 1
        else:
            break
    return streak


def record_failed_assessment(
    db: Session,
    child_id: int,
    topic_id: int,
    session_id: int | None,
    score: float | None,
) -> int:
    """Record a failed assessment attempt and check for streak notification.

    Creates a LearningAssessmentAttempt with passed=False, then checks
    if the consecutive failure count has reached the threshold.

    Returns:
        Current consecutive failure count. Caller should dispatch notification
        if return value == STREAK_THRESHOLD (exactly 3, not > 3 to avoid duplicates).
    """
    attempt = LearningAssessmentAttempt(
        child_id=child_id,
        topic_id=topic_id,
        session_id=session_id,
        assessment_type="ai",
        score=score,
        passed=False,
    )
    db.add(attempt)
    db.flush()

    return check_consecutive_failures(db, child_id, topic_id)
```

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest tests/backend/test_learning_streak_detection.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/progress_service.py server/tests/backend/test_learning_streak_detection.py
git commit -m "feat(learning): failure streak detection service (OQ-3)"
```

---

### Task 5: Failure Streak Notification Dispatch

**Files:**
- Modify: `server/apps/backend/app/services/notification/dispatcher.py` — add `notify_learning_streak_3_failures`
- Modify: `server/apps/backend/app/services/learning/progress_service.py` — wire notification into `record_failed_assessment`
- Test: `server/tests/backend/test_learning_streak_detection.py` (append notification tests)

**Interfaces:**
- Consumes: `record_failed_assessment()` from Task 4, `ensure_reminder()` from dispatcher
- Produces: `notify_learning_streak_3_failures()` dispatch function
- Notification fires exactly once per 3-consecutive-failure sequence

- [ ] **Step 1: Write failing notification tests**

```python
# Append to server/tests/backend/test_learning_streak_detection.py

from apps.backend.app.services.notification.dispatcher import (
    notify_learning_streak_3_failures,
)
from packages.db.models.reminder import Reminder


def test_streak_notification_fires_at_threshold(db, child, topic):
    """Notification fires when streak reaches exactly 3."""
    get_or_create_progress(db, int(child["id"]), topic.id)

    # First 2 failures — no notification
    record_failed_assessment(db, int(child["id"]), topic.id, None, 0.4)
    record_failed_assessment(db, int(child["id"]), topic.id, None, 0.3)

    reminders_before = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).count()

    # 3rd failure — notification should fire
    record_failed_assessment(db, int(child["id"]), topic.id, None, 0.2)

    reminders_after = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).count()

    assert reminders_after == reminders_before + 1


def test_streak_notification_not_duplicated_on_4th_failure(db, child, topic):
    """4th consecutive failure does NOT fire a duplicate notification."""
    get_or_create_progress(db, int(child["id"]), topic.id)

    for i in range(4):
        record_failed_assessment(db, int(child["id"]), topic.id, None, 0.3)

    count = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).count()
    assert count == 1  # exactly 1, not 2


def test_streak_notification_content_includes_child_and_topic(db, child, topic):
    """Notification body includes child name, topic name, and subject."""
    get_or_create_progress(db, int(child["id"]), topic.id)

    for i in range(3):
        record_failed_assessment(db, int(child["id"]), topic.id, None, 0.3)

    reminder = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).first()
    assert reminder is not None
    assert "Streak Kid" in reminder.title or "Streak Kid" in reminder.body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_streak_detection.py -v -k "notification or duplicated or content"`
Expected: FAIL — `notify_learning_streak_3_failures` doesn't exist yet, and `record_failed_assessment` doesn't call it

- [ ] **Step 3: Add notification dispatch function**

Add to `server/apps/backend/app/services/notification/dispatcher.py`:

```python
def notify_learning_streak_3_failures(
    db: Session,
    family_id: int,
    child_name: str,
    topic_name: str,
    subject: str,
) -> None:
    """Notify parent that child has 3 consecutive failures on a topic."""
    # NOTE: Do NOT use ensure_reminder here — its dedup is scoped to
    # (family_id, reminder_type, asset_id=None), which would suppress
    # legitimate streak notifications for different children/topics.
    # Create the Reminder directly with streak-specific dedup.
    from packages.db.models.reminder import Reminder
    from packages.core.snowflake import next_id

    existing = db.query(Reminder).filter_by(
        family_id=family_id,
        reminder_type="learning_streak_3_failures",
        status="active",
    ).filter(
        Reminder.title.contains(child_name),
        Reminder.title.contains(topic_name),
    ).first()
    if existing:
        return  # already notified for this child+topic combo

    reminder = Reminder(
        id=next_id(),
        family_id=family_id,
        reminder_type="learning_streak_3_failures",
        title=f"{child_name} 在 {topic_name} 上连续遇到困难",
        body=f"{child_name} 在「{topic_name}」({subject}) 的评估中连续 3 次未通过。建议一起复习这个知识点，或尝试不同的学习方式。",
        severity="warning",
        template_vars_json=json.dumps({
            "child_name": child_name,
            "topic_name": topic_name,
            "subject": subject,
        }, ensure_ascii=False),
        status="active",
    )
    db.add(reminder)
```

- [ ] **Step 4: Wire notification into `record_failed_assessment`**

Update `record_failed_assessment` in `progress_service.py` to dispatch the notification when streak reaches exactly 3:

```python
def record_failed_assessment(
    db: Session,
    child_id: int,
    topic_id: int,
    session_id: int | None,
    score: float | None,
) -> int:
    """Record a failed assessment and fire streak notification at threshold."""
    attempt = LearningAssessmentAttempt(
        child_id=child_id,
        topic_id=topic_id,
        session_id=session_id,
        assessment_type="ai",
        score=score,
        passed=False,
    )
    db.add(attempt)
    db.flush()

    streak = check_consecutive_failures(db, child_id, topic_id)

    # Fire notification exactly when threshold is reached (not on 4th, 5th, etc.)
    if streak == STREAK_THRESHOLD:
        from apps.backend.app.services.notification.dispatcher import (
            notify_learning_streak_3_failures,
        )
        from packages.db.models.learning.topic import LearningTopic
        from packages.db.models.user import User

        topic = db.query(LearningTopic).get(topic_id)
        # child_id references users.id directly — children are User rows with role="child"
        child_user = db.query(User).get(child_id)
        if child_user and topic:
            notify_learning_streak_3_failures(
                db,
                family_id=child_user.family_id,
                child_name=child_user.display_name or child_user.username,
                topic_name=topic.name_zh or topic.name or topic.topic_key,
                subject=topic.subject,
            )

    return streak
```

- [ ] **Step 5: Run tests**

Run: `cd server && uv run pytest tests/backend/test_learning_streak_detection.py -v`
Expected: All tests PASS (both detection tests from Task 4 and notification tests)

- [ ] **Step 6: Run linter**

Run: `cd server && uv run ruff check apps/backend/app/services/learning/progress_service.py apps/backend/app/services/notification/dispatcher.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/services/learning/progress_service.py server/apps/backend/app/services/notification/dispatcher.py server/tests/backend/test_learning_streak_detection.py
git commit -m "feat(learning): wire failure streak notification dispatch (OQ-3)"
```

---

### Task 6: Frontend — Translate Button + Language Detection

**Files:**
- Modify: `frontend/apps/main/src/api/learning.ts` — add `translateTopic()` function
- Modify: `frontend/apps/main/src/pages/ChildLearningMapPage.vue` — add inline translate button on each topic item
- Modify: `frontend/apps/child/src/api/learning.ts` — add `translateTopic()` function
- Modify: `frontend/apps/child/src/pages/learning/LearningTopicPage.vue` — add translate button
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add i18n keys
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts` — add i18n keys
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts` — add i18n keys
- Modify: `frontend/apps/child/src/i18n/locales/en-US.ts` — add i18n keys

**Interfaces:**
- Consumes: `POST /api/v1/learning/topics/{topic_id}/translate` endpoint from Task 2
- Consumes: `name_zh` field in topic response (from Task 3) to detect translation status

- [ ] **Step 1: Add API function to both apps**

In `frontend/apps/main/src/api/learning.ts`:

```typescript
/** Translate a topic's content to Chinese. Returns translated fields. */
export async function translateTopic(topicId: string): Promise<{
  name_zh: string | null
  description_zh: string | null
  evidence_zh: string[] | null
  assessment_prompt_zh: string | null
}> {
  const resp = await http.post(`/learning/topics/${topicId}/translate`)
  return resp.data.data
}
```

Add the same function to `frontend/apps/child/src/api/learning.ts`.

**TypeScript interface update:** Ensure the `TopicResponse` interface in both apps includes `name_zh: string | null` — the translate button visibility check (`!topic.value.name_zh`) depends on this field. If the existing interface omits it, add it.

- [ ] **Step 2: Add i18n keys to all 4 locale files**

Main app `zh-CN.ts`:
```typescript
'learning.translate': '翻译为中文',
'learning.retranslate': '重新翻译',
'learning.translating': '翻译中...',
'learning.translationFailed': '翻译失败，请稍后重试',
'learning.translationComplete': '翻译完成',
```

Main app `en-US.ts`:
```typescript
'learning.translate': 'Translate to Chinese',
'learning.retranslate': 'Re-translate',
'learning.translating': 'Translating...',
'learning.translationFailed': 'Translation failed, please try again',
'learning.translationComplete': 'Translation complete',
```

Child app: add the same keys with child-friendly Chinese translations:
```typescript
// zh-CN.ts
'learning.translate': '翻译成中文',
'learning.translating': '正在翻译...',
'learning.translationFailed': '翻译失败了，再试一次吧',
'learning.translationComplete': '翻译好啦',
```

- [ ] **Step 3: Add translate button to main app ChildLearningMapPage**

In `ChildLearningMapPage.vue`, add a small inline translate button inside each `.topic-item` div (next to the topic mastery indicator). Use `size="small"` and `plain` to keep it compact within the list layout:

```vue
<template>
  <!-- ... existing topic content ... -->

  <!-- Translate button: visible only when locale is zh-CN and topic not yet translated -->
  <van-button
    v-if="showTranslateButton"
    :loading="translating"
    :loading-text="t('learning.translating')"
    size="small"
    type="primary"
    plain
    icon="exchange"
    @click="handleTranslate"
  >
    {{ translateButtonLabel }}
  </van-button>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { translateTopic } from '@/api/learning'

const { t, locale } = useI18n()
const translating = ref(false)

// Show translate button only when user locale is zh-CN and topic lacks translation
// and the source content is not already Chinese
// Show translate/re-translate button when locale is zh-CN and content is not originally Chinese
const showTranslateButton = computed(() => {
  if (locale.value !== 'zh-CN') return false
  if (!topic.value) return false
  // Guard: don't offer translation for originally-Chinese content
  if (topic.value.name && /[一-鿿]/.test(topic.value.name)) return false
  return true
})

// Button label changes based on translation status
const translateButtonLabel = computed(() => {
  return topic.value?.name_zh
    ? t('learning.retranslate')
    : t('learning.translate')
})

async function handleTranslate() {
  if (!topic.value) return
  translating.value = true
  try {
    await translateTopic(topic.value.id)
    showSuccessToast(t('learning.translationComplete'))
    await loadTopic() // refresh topic data from server
  } catch (err: any) {
    if (err?.response?.status === 404) {
      showFailToast(t('learning.topicNotFound'))
    } else if (err?.response?.status === 503) {
      showFailToast(t('learning.translationFailed'))
    } else {
      showFailToast(t('learning.translationFailed'))
    }
  } finally {
    translating.value = false
  }
}
</script>
```

- [ ] **Step 4: Add translate button to child app topic page**

In `LearningTopicPage.vue`, insert the translate button between the description section and the evidence section — near the content it translates. Adjusted for child-app styling (simpler, larger tap targets):

```vue
<van-button
  v-if="showTranslateButton"
  :loading="translating"
  :loading-text="t('learning.translating')"
  size="normal"
  type="primary"
  block
  @click="handleTranslate"
>
  {{ t('learning.translate') }}
</van-button>
```

- [ ] **Step 5: Verify both apps build without errors**

Run: `cd frontend && pnpm --filter main build 2>&1 | tail -5`
Run: `cd frontend && pnpm --filter child build 2>&1 | tail -5`
Expected: Both succeed

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/main/src/api/learning.ts frontend/apps/main/src/pages/ \
  frontend/apps/child/src/api/learning.ts frontend/apps/child/src/pages/learning/ \
  frontend/apps/main/src/i18n/ frontend/apps/child/src/i18n/
git commit -m "feat(learning): add translate button with language detection (OQ-2)"
```

---

### Task 7: Seed Data Validation — Badge Dimensions + Age Range + Dependency Cycles

**Files:**
- Create: `server/apps/backend/app/services/learning/validation.py`
- Modify: `server/scripts/seed_learning_topics.py` — extend `validate_quality()`
- Test: `server/tests/backend/test_learning_seed_validation.py`

**Interfaces:**
- Consumes: `LearningTopic`, `LiteracyBadgeDefinition`, `LearningDependency` models
- Produces: Extended `validate_quality()` with 3 new checks
- Called post-seed via `--skip-validate` CLI flag (existing behavior)

> **Spec→Model note:** The spec says "badge-topic subject cross-check" but `LiteracyBadgeDefinition.dimension` stores ability dimensions (e.g., `"numerical_reasoning"`), NOT topic subjects (e.g., `"mathematics"`). The check validates badge dimensions against the known `ABILITY_DIMENSIONS` constant from `translation.py`.

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/test_learning_seed_validation.py
import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic, LearningDependency
from apps.backend.app.services.learning.validation import (
    validate_badge_dimensions,
    validate_age_ranges,
    validate_no_dependency_cycles,
)


@pytest.fixture
def math_topics(db: Session):
    topics = [
        LearningTopic(
            topic_key=f"mt_{i}", topic_type="CONCEPTUAL", subject="mathematics",
            domain="Test", name=f"Math {i}", description="Test",
            age_range_start=8, age_range_end=10, age_group="mid",
            evidence_json="[]", standards_json="[]",
        )
        for i in range(3)
    ]
    db.add_all(topics)
    db.flush()
    return topics


# --- Badge dimension validity ---

def test_badge_dimensions_all_valid():
    """All recognized ability dimensions pass."""
    valid_dims = {"numerical_reasoning", "spatial_reasoning", "creative_thinking"}
    result = validate_badge_dimensions(valid_dims)
    assert result == []


def test_badge_dimensions_unknown_dimension():
    """An unrecognized dimension fails validation."""
    invalid_dims = {"numerical_reasoning", "astrology"}
    result = validate_badge_dimensions(invalid_dims)
    assert len(result) == 1
    assert "astrology" in result[0]


def test_badge_dimensions_empty_set_ok():
    """No badges defined at all → nothing to validate → passes."""
    result = validate_badge_dimensions(set())
    assert result == []


# --- Age range sanity ---

def test_age_range_valid_passes(db, math_topics):
    """Topics with start < end pass validation."""
    invalid = validate_age_ranges(db)
    assert invalid == []


def test_age_range_invalid_start_gte_end(db):
    """Topic with age_range_start >= age_range_end fails."""
    bad = LearningTopic(
        topic_key="mt_bad_age", topic_type="CONCEPTUAL", subject="mathematics",
        domain="Test", name="Bad Age", description="Test",
        age_range_start=12, age_range_end=8, age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    db.add(bad)
    db.flush()

    invalid = validate_age_ranges(db)
    assert len(invalid) == 1
    assert "mt_bad_age" in invalid[0]


def test_age_range_null_skipped(db):
    """Topics with null age_range values are skipped (not flagged)."""
    nullable = LearningTopic(
        topic_key="mt_null_age", topic_type="CONCEPTUAL", subject="mathematics",
        domain="Test", name="Null Age", description="Test",
        age_range_start=8, age_range_end=None, age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    db.add(nullable)
    db.flush()

    invalid = validate_age_ranges(db)
    assert invalid == []


# --- Dependency cycle detection ---

def test_no_cycles_in_acyclic_graph(db, math_topics):
    """Linear chain A → B → C has no cycles."""
    db.add(LearningDependency(
        topic_id=math_topics[1].id, prerequisite_id=math_topics[0].id,
    ))
    db.add(LearningDependency(
        topic_id=math_topics[2].id, prerequisite_id=math_topics[1].id,
    ))
    db.flush()

    assert validate_no_dependency_cycles(db) == []


def test_cycle_detected(db, math_topics):
    """A → B → A is a cycle."""
    db.add(LearningDependency(
        topic_id=math_topics[1].id, prerequisite_id=math_topics[0].id,
    ))
    db.add(LearningDependency(
        topic_id=math_topics[0].id, prerequisite_id=math_topics[1].id,
    ))
    db.flush()

    cycles = validate_no_dependency_cycles(db)
    assert len(cycles) > 0


def test_self_loop_detected(db, math_topics):
    """A → A is a cycle (self-loop)."""
    db.add(LearningDependency(
        topic_id=math_topics[0].id, prerequisite_id=math_topics[0].id,
    ))
    db.flush()

    cycles = validate_no_dependency_cycles(db)
    assert len(cycles) > 0


def test_no_topics_no_cycles(db):
    """Empty topic table has no cycles."""
    assert validate_no_dependency_cycles(db) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_seed_validation.py -v`
Expected: FAIL — `apps.backend.app.services.learning.validation` module doesn't exist

- [ ] **Step 3: Implement validation functions**

Create `server/apps/backend/app/services/learning/validation.py`:

```python
"""Seed data quality validation for Learning OS."""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic

logger = logging.getLogger(__name__)

# Known ability dimensions — must match translation.py ABILITY_DIMENSIONS
_KNOWN_ABILITY_DIMENSIONS = {
    "numerical_reasoning", "spatial_reasoning", "verbal_reasoning",
    "scientific_inquiry", "computational_thinking", "social_emotional",
    "creative_thinking", "physical_kinesthetic", "memory_recall", "metacognition",
}


def validate_badge_dimensions(badge_dimensions: set[str]) -> list[str]:
    """Verify all badge dimensions are recognized ability dimensions.

    The badge model (LiteracyBadgeDefinition) uses a `dimension` field
    storing ability dimension names (e.g., "numerical_reasoning"), NOT
    topic subjects. This check ensures badge dimensions are valid.

    Returns:
        List of error messages (empty = all good).
    """
    errors = []
    for dim in sorted(badge_dimensions):
        if dim not in _KNOWN_ABILITY_DIMENSIONS:
            errors.append(
                f"Badge dimension '{dim}' is not a recognized ability dimension"
            )
    return errors


def validate_age_ranges(db: Session) -> list[str]:
    """Verify age_range_start < age_range_end for all topics where both are non-null.

    Skips topics where either age_range_start or age_range_end is null.

    Returns:
        List of error messages (empty = all good).
    """
    invalid = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.age_range_start.isnot(None),
            LearningTopic.age_range_end.isnot(None),
            LearningTopic.age_range_start >= LearningTopic.age_range_end,
        )
        .all()
    )
    return [
        f"Topic '{t.topic_key}' has age_range_start={t.age_range_start} >= age_range_end={t.age_range_end}"
        for t in invalid
    ]


def validate_no_dependency_cycles(db: Session) -> list[str]:
    """Detect circular prerequisites in the topic dependency graph (DFS-based, O(V+E)).

    Returns:
        List of error messages (empty = no cycles found).
    """
    from packages.db.models.learning.topic import LearningTopic, LearningDependency

    edges = db.query(
        LearningDependency.topic_id, LearningDependency.prerequisite_id
    ).all()

    graph: dict[int, list[int]] = defaultdict(list)
    all_nodes: set[int] = set()
    for topic_id, prereq_id in edges:
        graph[prereq_id].append(topic_id)  # prerequisite → dependent
        all_nodes.add(topic_id)
        all_nodes.add(prereq_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[int, int] = {n: WHITE for n in all_nodes}
    cycles: list[str] = []

    def dfs(node: int) -> None:
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color[neighbor] == GRAY:
                cycles.append(f"Cycle detected: {node} → {neighbor}")
            elif color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for node in all_nodes:
        if color[node] == WHITE:
            dfs(node)

    return cycles
```

- [ ] **Step 4: Wire into `validate_quality()` in seed script**

Update `server/scripts/seed_learning_topics.py` — extend `validate_quality()`:

```python
def validate_quality(session):
    """Run all quality validations after seeding."""
    # ... existing checks (counts, orphan edges, per-subject stats) ...

    from apps.backend.app.services.learning.validation import (
        validate_badge_dimensions,
        validate_age_ranges,
        validate_no_dependency_cycles,
    )

    # NEW: Badge dimension validity check
    from packages.db.models.literacy_badge import LiteracyBadgeDefinition
    badge_dims = set(
        r[0] for r in session.query(LiteracyBadgeDefinition.dimension).distinct().all()
    )
    dim_errors = validate_badge_dimensions(badge_dims)
    if dim_errors:
        for err in dim_errors:
            logger.error("BADGE DIMENSION: %s", err)
        raise ValueError(f"Badge dimension validation failed: {dim_errors}")

    # NEW: Age range sanity
    age_errors = validate_age_ranges(session)
    if age_errors:
        for err in age_errors:
            logger.error("AGE RANGE: %s", err)
        raise ValueError(f"Age range validation failed: {len(age_errors)} topics")

    # NEW: Dependency cycle detection
    cycle_errors = validate_no_dependency_cycles(session)
    if cycle_errors:
        for err in cycle_errors:
            logger.error("DEPENDENCY CYCLE: %s", err)
        raise ValueError(f"Dependency cycle detection failed: {len(cycle_errors)} cycles")

    logger.info("All quality validations passed ✅")
```

- [ ] **Step 5: Run tests**

Run: `cd server && uv run pytest tests/backend/test_learning_seed_validation.py -v`
Expected: All 10 tests PASS

- [ ] **Step 6: Run linter**

Run: `cd server && uv run ruff check apps/backend/app/services/learning/validation.py scripts/seed_learning_topics.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/services/learning/validation.py server/scripts/seed_learning_topics.py server/tests/backend/test_learning_seed_validation.py
git commit -m "feat(learning): add badge dimension + age range + cycle validation to seed (OQ-6)"
```

---

## Task Dependency Graph

```
Task 1 (translation service) → Task 2 (translation endpoint) → Task 3 (topic fallback)
                                                                   ↓
Task 4 (streak detection) → Task 5 (streak notification)     Task 6 (frontend translate button)

Task 7 (seed validation) — independent, no dependencies
```

**Recommended execution order:**
1. Task 7 (seed validation) — standalone, no dependencies, quick win
2. Tasks 1 → 2 → 3 (translation pipeline) — sequential, each builds on previous
3. Tasks 4 → 5 (failure streak) — sequential, can run parallel with translation
4. Task 6 (frontend) — after Task 2 (needs the API endpoint)

---

## Deferred / Open Questions

### From 2026-09-24 doc review

- ~~**Main app translate button placement (P0):**~~ ✅ **Resolved:** Inline on `ChildLearningMapPage.vue` topic items.
- ~~**Child app translate button position (P1):**~~ ✅ **Resolved:** Between description and evidence sections in `LearningTopicPage.vue`.
- ~~**Re-translation UX (P2):**~~ ✅ **Resolved:** Keep button visible after translation, change label to "Re-translate" (`learning.retranslate` i18n key added).
