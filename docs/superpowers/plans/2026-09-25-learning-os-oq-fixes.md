# Learning OS OQ Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 code-review findings from the Learning OS OQ audit: migrate translation to agent module (multi-provider LLM), fix notification dedup re-trigger, fix badge validation target mismatch.

**Architecture:** Translation moves from backend direct-LLM to agent-module proxy (following `ai_suggest` pattern: backend `AgentClient.post()` → agent router → `LLMClient.complete_json()`). Notification dedup adds `child_id`/`topic_id` structured columns to `Reminder` and auto-resolves active streak reminders when a pass breaks the streak. Badge validation checks against actual `LearningTopic.subject` values instead of a mismatched ability-dimension set.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, `LLMClient` (agent `core/llm.py`), `AgentClient` (backend), Pydantic v2

**Spec:** Code review findings (OQ-2 #2, OQ-2 #3, OQ-2 #6, OQ-3, OQ-6 #1, OQ-6 cycle detection)

## Global Constraints

- Import direction: `apps/` → `packages/` only; agent must NOT import from `apps/backend`
- URL style: no trailing slashes, `@router.post("")` not `@router.post("/")`
- All `bigint` IDs serialized as strings in API responses (SnowflakeBase)
- Agent auth: `X-Agent-Token` via `verify_service_token`; backend uses `AgentClient` (never raw httpx)
- Agent LLM: lightweight single-call paths use `core/llm.py` directly (exempt from DeerFlow dispatch per agent/CLAUDE.md §Key Invariants #4)

## Deliberate Deviations (No Code Change)

| Finding | Decision | Rationale |
|---------|----------|-----------|
| OQ-2 #3: No server-side fallback on reads | **Keep current** — client-side `useLocalizedTopic` handles locale selection | Deliberate design choice (commit `1395bbc1`): return raw English + `_zh` fields, let frontend pick. Simpler, no coupling. |
| OQ-2 #6: Re-translate button shows when `name_zh` filled | **Keep current** — shows "Re-translate" instead of hiding | Better UX than spec. Uses `hasChineseChars(name)` since `source_lang` field doesn't exist. |
| OQ-6: `validate_no_dependency_cycles()` scope creep | **No action** — function does not exist in codebase | Verified via exhaustive search. Only orphan-edge detection exists in `validate_quality()`. |

## Review Focus

1. **Translation proxy error path** — when agent service is down or family has no AI provider, backend must return `LEARNING_TRANSLATION_UNAVAILABLE` (503), not a raw 500. Test: mock `AgentClient.post` raising `httpx.ConnectError`.
2. **Notification re-trigger after pass** — after 3 failures → active reminder → pass → 3 more failures, a second reminder must fire. Test: full sequence in one test.
3. **Badge validation matches seed data** — `BADGE_DEFINITIONS` dimensions (`mathematics`, `science`, …) must pass `validate_badge_subjects()`. Test: feed actual seed dimensions.
4. **Reminder migration backfill** — existing `learning_streak_3_failures` reminders get `child_id`/`topic_id` populated. Test: migration up + data check.
5. **LLMClient provider mapping** — family AI config `ai_provider` values (`openai`, `anthropic`, `openai_compatible`) must map to `LLMClient(provider=...)` correctly. Test: each provider variant.

---

### Task 1: Create agent translation service

**Files:**
- Create: `server/apps/agent/services/topic_translate.py`
- Test: `server/tests/agent/test_topic_translate.py`

**Interfaces:**
- Consumes: `LLMClient` from `apps.agent.core.llm` (constructor: `LLMClient(provider, api_key, model_id, base_url=None, timeout=60.0)`; method: `async complete_json(prompt, max_tokens, system) -> str`)
- Produces: `async translate_topic(topic: dict, ai_config: dict) -> dict` — takes a topic dict and a provider config dict, returns `{name_zh, description_zh, evidence_zh, assessment_prompt_zh}`

- [ ] **Step 1: Write the failing test**

Create `server/tests/agent/test_topic_translate.py`:

```python
"""Tests for agent-side topic translation service."""

import json

import pytest

from apps.agent.services.topic_translate import (
    TRANSLATION_SYSTEM_PROMPT,
    translate_topic,
)


def _make_ai_config(
    provider: str = "openai_compatible",
    model: str = "qwen-plus",
    api_key: str = "test-key",
    base_url: str = "https://example.com/v1",
) -> dict:
    return {
        "ai_provider": provider,
        "ai_model_id": model,
        "api_key": api_key,
        "ai_base_url": base_url,
    }


@pytest.mark.asyncio
async def test_translate_topic_returns_all_keys(monkeypatch):
    """translate_topic returns all four _zh keys from LLM JSON response."""
    expected = {
        "name_zh": "加法",
        "description_zh": "学习基本加法运算",
        "evidence_zh": ["能正确计算", "理解进位概念"],
        "assessment_prompt_zh": "请计算以下题目",
    }

    async def mock_complete_json(self, prompt, max_tokens=4000, system=None):
        return json.dumps(expected, ensure_ascii=False)

    from apps.agent.core.llm import LLMClient

    monkeypatch.setattr(LLMClient, "complete_json", mock_complete_json)

    topic = {
        "name": "Addition",
        "description": "Learn basic addition",
        "evidence": ["Can compute correctly", "Understands carrying"],
        "assessment_prompt": "Calculate the following",
    }
    result = await translate_topic(topic, _make_ai_config())
    assert result == expected


@pytest.mark.asyncio
async def test_translate_topic_truncates_long_description(monkeypatch):
    """Description is truncated to _MAX_DESCRIPTION_CHARS before sending to LLM."""
    captured_prompt = {}

    async def mock_complete_json(self, prompt, max_tokens=4000, system=None):
        captured_prompt["value"] = prompt
        return json.dumps({
            "name_zh": "X", "description_zh": "Y",
            "evidence_zh": [], "assessment_prompt_zh": "Z",
        })

    from apps.agent.core.llm import LLMClient

    monkeypatch.setattr(LLMClient, "complete_json", mock_complete_json)

    topic = {
        "name": "Test",
        "description": "A" * 5000,
        "evidence": [],
        "assessment_prompt": "",
    }
    await translate_topic(topic, _make_ai_config())
    # The prompt should NOT contain the full 5000-char description
    assert len(captured_prompt["value"]) < 5000


@pytest.mark.asyncio
async def test_translate_topic_missing_key_raises():
    """LLM response missing a required key raises ValueError."""
    from unittest.mock import AsyncMock, patch

    from apps.agent.core.llm import LLMClient

    with patch.object(
        LLMClient, "complete_json",
        new_callable=AsyncMock,
        return_value=json.dumps({"name_zh": "X"}),  # missing other keys
    ):
        with pytest.raises(ValueError, match="missing required key"):
            await translate_topic(
                {"name": "T", "description": "D", "evidence": [], "assessment_prompt": ""},
                _make_ai_config(),
            )


@pytest.mark.asyncio
async def test_translate_topic_malformed_json_raises():
    """Non-JSON LLM response raises ValueError."""
    from unittest.mock import AsyncMock, patch

    from apps.agent.core.llm import LLMClient

    with patch.object(
        LLMClient, "complete_json",
        new_callable=AsyncMock,
        return_value="not json at all",
    ):
        with pytest.raises(ValueError, match="malformed|JSON|json"):
            await translate_topic(
                {"name": "T", "description": "D", "evidence": [], "assessment_prompt": ""},
                _make_ai_config(),
            )


@pytest.mark.asyncio
async def test_translate_topic_empty_provider_fallback():
    """Missing api_key in ai_config raises ValueError."""
    with pytest.raises(ValueError, match="API key|api_key"):
        await translate_topic(
            {"name": "T", "description": "D", "evidence": [], "assessment_prompt": ""},
            {"ai_provider": "openai", "ai_model_id": "gpt-4", "api_key": ""},
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/agent/test_topic_translate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.agent.services.topic_translate'`

- [ ] **Step 3: Create the translation service**

Create `server/apps/agent/services/topic_translate.py`:

```python
"""On-demand topic translation via LLM — agent module.

Replaces the old backend-side ``translation.py`` that called DashScope directly.
Now uses ``LLMClient.complete_json()`` so translation honours the family's
configured AI provider (multi-provider, circuit-breaker-aware via router layer).
"""

import json
import logging

from apps.agent.core.llm import LLMClient

logger = logging.getLogger(__name__)

_MAX_DESCRIPTION_CHARS = 3000
_MAX_EVIDENCE_ITEMS = 10

TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional translator specializing in children's education content. "
    "Translate the following English learning topic into Chinese (Simplified). "
    "Preserve technical/mathematical terms in parentheses where helpful. "
    "Return JSON with exactly these keys: name_zh, description_zh, evidence_zh (array), assessment_prompt_zh."
)

_REQUIRED_KEYS = ("name_zh", "description_zh", "evidence_zh", "assessment_prompt_zh")


async def translate_topic(topic: dict, ai_config: dict) -> dict:
    """Translate a topic's English content to Chinese.

    Args:
        topic: dict with keys: name, description, evidence (list), assessment_prompt
        ai_config: provider config dict with keys: ai_provider, ai_model_id,
                   api_key, ai_base_url (or base_url)

    Returns:
        dict with keys: name_zh, description_zh, evidence_zh, assessment_prompt_zh

    Raises:
        ValueError: if api_key is missing or LLM returns malformed/incomplete JSON
    """
    api_key = ai_config.get("api_key")
    if not api_key:
        raise ValueError("LLM API key not configured")

    provider = (ai_config.get("ai_provider") or "openai").lower()
    model = ai_config.get("ai_model_id") or "gpt-4o-mini"
    base_url = ai_config.get("ai_base_url") or ai_config.get("base_url")

    client = LLMClient(
        provider=provider,
        api_key=api_key,
        model_id=model,
        base_url=base_url,
        timeout=60.0,
    )

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

    raw = await client.complete_json(
        prompt=prompt,
        max_tokens=4000,
        system=TRANSLATION_SYSTEM_PROMPT,
    )

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned malformed translation response: {e}") from e

    for key in _REQUIRED_KEYS:
        if key not in result:
            raise ValueError(f"LLM response missing required key: {key}")

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/agent/test_topic_translate.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/agent/services/topic_translate.py server/tests/agent/test_topic_translate.py
git commit -m "feat(learning): add agent-side topic translation service using LLMClient

Replaces backend direct-LLM call with agent-module service that honours
the family's configured AI provider via LLMClient.complete_json().

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Create agent translate router

**Files:**
- Create: `server/apps/agent/routers/translate.py`
- Modify: `server/apps/agent/app/main.py` (add import + include_router)
- Test: `server/tests/agent/test_translate_router.py`

**Interfaces:**
- Consumes: `translate_topic()` from Task 1; `BackendClient.get_family_ai_config()`; `_select_stream_run_provider()` from orchestrator
- Produces: `POST /translate/topic` endpoint accepting `{name, description, evidence, assessment_prompt}`, returning `{name_zh, description_zh, evidence_zh, assessment_prompt_zh}`

- [ ] **Step 1: Write the failing test**

Create `server/tests/agent/test_translate_router.py`:

```python
"""Tests for the agent translate router."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from apps.agent.app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_translate_endpoint_no_token_rejecteded():
    """Request without X-Agent-Token returns 401/403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/translate/topic", json={"name": "Test"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_translate_endpoint_no_provider_returns_503(monkeypatch):
    """When no AI provider is configured, return 503."""
    from apps.agent.core.backend_client import BackendClient

    async def mock_get_config(self):
        return {"providers": []}

    monkeypatch.setattr(BackendClient, "get_family_ai_config", mock_get_config)

    # Mock the service token verification
    from packages.security.service_auth import agent_token_verify

    monkeypatch.setattr(
        agent_token_verify, "verify_service_token",
        lambda: "test-family-id",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/translate/topic",
            json={"name": "Test", "description": "D", "evidence": [], "assessment_prompt": ""},
            headers={"X-Agent-Token": "test", "X-Family-Id": "123"},
        )
    assert resp.status_code == 503
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/agent/test_translate_router.py -v`
Expected: FAIL — endpoint does not exist (404)

- [ ] **Step 3: Create the translate router**

Create `server/apps/agent/routers/translate.py`:

```python
"""Learning topic translation endpoint (called by backend proxy).

Follows the ``ai_suggest`` pattern: backend proxies via ``AgentClient``,
this router selects a provider from the family's AI config (circuit-breaker-
aware) and delegates to ``topic_translate.translate_topic()``.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from apps.agent.core.backend_client import BackendClient
from apps.agent.services.topic_translate import translate_topic
from packages.security.service_auth.agent_token_verify import verify_service_token

router = APIRouter(prefix="/translate", tags=["translate"])
logger = logging.getLogger(__name__)


class TranslateTopicRequest(BaseModel):
    name: str
    description: str = ""
    evidence: list[str] = []
    assessment_prompt: str = ""


@router.post("/topic")
async def translate_topic_endpoint(
    body: TranslateTopicRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    _token_family: str = Depends(verify_service_token),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """Translate a learning topic to Chinese using the family's AI provider."""
    client = BackendClient(family_id=x_family_id)
    ai_config = await client.get_family_ai_config()
    providers = ai_config.get("providers", [])
    if not providers:
        raise HTTPException(status_code=503, detail="No AI provider configured")

    # Circuit-state aware selection
    from apps.agent.services.orchestrator import _select_stream_run_provider

    selected = _select_stream_run_provider(providers)
    if selected is None:
        raise HTTPException(status_code=503, detail="All AI providers unavailable")

    topic_dict = body.model_dump()
    try:
        return await translate_topic(topic_dict, selected)
    except ValueError as e:
        logger.warning("Translation failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception:
        logger.exception("Translation LLM call failed")
        raise HTTPException(status_code=503, detail="Translation service unavailable")
```

- [ ] **Step 4: Register the router in agent main.py**

In `server/apps/agent/app/main.py`, add the import at the top with other router imports (around line 18-26):

```python
from apps.agent.routers import translate as translate_router
```

And add `app.include_router()` in the router registration block (around line 300-307):

```python
app.include_router(translate_router.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/agent/test_translate_router.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run linter**

Run: `cd server && uv run ruff check apps/agent/routers/translate.py apps/agent/services/topic_translate.py`
Fix any issues.

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/routers/translate.py server/apps/agent/app/main.py server/tests/agent/test_translate_router.py
git commit -m "feat(learning): add agent translate router with circuit-breaker-aware provider selection

Backend will proxy POST /learning/topics/{id}/translate to this endpoint.
Uses _select_stream_run_provider() for circuit-state-aware provider selection.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Switch backend translate endpoint to AgentClient proxy

**Files:**
- Modify: `server/apps/backend/app/routers/learning.py` (lines 121-160)
- Delete: `server/apps/backend/app/services/learning/translation.py` (166 lines)
- Test: `server/tests/backend/test_learning_translation_proxy.py`

**Interfaces:**
- Consumes: `AgentClient` from `apps.backend.app.services.agent_client`
- Produces: Same API contract — `POST /api/v1/learning/topics/{topic_id}/translate` returns `{name_zh, description_zh, evidence_zh, assessment_prompt_zh}`

- [ ] **Step 1: Write the failing test**

Create `server/tests/backend/test_learning_translation_proxy.py`:

```python
"""Tests for the backend translate endpoint proxying to agent."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.backend.app.main import app
from apps.backend.app.errors import ErrorCode


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_auth(monkeypatch):
    """Bypass auth for testing."""
    from apps.backend.app.auth import deps
    from apps.backend.app.models.user import User

    fake_user = User(id=1, family_id=1, username="test", role="adult")
    monkeypatch.setattr(deps, "require_adult", lambda: fake_user)


def test_translate_proxies_to_agent(client, mock_auth, db, monkeypatch):
    """Translate endpoint proxies to agent and persists translated fields."""
    from packages.db.models.learning.topic import LearningTopic

    topic = LearningTopic(
        topic_key="test_translate",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Addition",
        description="Basic addition",
        age_group="mid",
        evidence_json='["can add"]',
        standards_json="[]",
    )
    db.add(topic)
    db.flush()
    topic_id = topic.id

    agent_response = {
        "name_zh": "加法",
        "description_zh": "基本加法",
        "evidence_zh": ["会加法"],
        "assessment_prompt_zh": "请计算",
    }

    mock_resp = httpx.Response(
        200,
        json=agent_response,
        request=httpx.Request("POST", "http://test/translate/topic"),
    )

    with patch(
        "apps.backend.app.services.agent_client.AgentClient.post",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        resp = client.post(f"/api/v1/learning/topics/{topic_id}/translate")

    assert resp.status_code == 200
    data = resp.json()
    assert data["name_zh"] == "加法"
    assert data["description_zh"] == "基本加法"

    # Verify DB persistence
    db.expire_all()
    updated = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
    assert updated.name_zh == "加法"


def test_translate_agent_timeout_returns_503(client, mock_auth, db, monkeypatch):
    """When agent service times out, return LEARNING_TRANSLATION_UNAVAILABLE."""
    from packages.db.models.learning.topic import LearningTopic

    topic = LearningTopic(
        topic_key="test_timeout",
        topic_type="CONCEPTUAL",
        subject="science",
        domain="Test",
        name="Photosynthesis",
        description="Plant process",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()

    with patch(
        "apps.backend.app.services.agent_client.AgentClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timeout"),
    ):
        resp = client.post(f"/api/v1/learning/topics/{topic.id}/translate")

    assert resp.status_code == 503
    assert resp.json()["code"] == ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE.value


def test_translate_agent_error_returns_503(client, mock_auth, db, monkeypatch):
    """When agent returns an error, return LEARNING_TRANSLATION_UNAVAILABLE."""
    from packages.db.models.learning.topic import LearningTopic

    topic = LearningTopic(
        topic_key="test_error",
        topic_type="CONCEPTUAL",
        subject="english",
        domain="Test",
        name="Grammar",
        description="Rules",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()

    mock_resp = httpx.Response(
        503,
        json={"detail": "No AI provider configured"},
        request=httpx.Request("POST", "http://test/translate/topic"),
    )

    with patch(
        "apps.backend.app.services.agent_client.AgentClient.post",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        resp = client.post(f"/api/v1/learning/topics/{topic.id}/translate")

    assert resp.status_code == 503
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_translation_proxy.py -v`
Expected: FAIL — current endpoint calls `translate_topic()` directly, not via `AgentClient`

- [ ] **Step 3: Rewrite the backend translate endpoint**

Replace the endpoint in `server/apps/backend/app/routers/learning.py` lines 121-160.

Old code to remove (the entire `translate_topic_endpoint` function):

```python
@router.post("/topics/{topic_id}/translate")
def translate_topic_endpoint(
    topic_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_adult),
):
    """Translate a topic's English content to Chinese on demand."""
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
        raise AppError(ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE) from None
    except Exception:
        logger.exception("Translation LLM call failed for topic %s", topic_id)
        raise AppError(ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE) from None

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

New code (async, proxies to agent):

```python
@router.post("/topics/{topic_id}/translate")
async def translate_topic_endpoint(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    """Translate a topic's English content to Chinese on demand.

    Proxies to the agent module which uses the family's configured AI provider
    via ``LLMClient.complete_json()`` (multi-provider, circuit-breaker-aware).
    """
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
        agent_client = AgentClient(
            current_user.family_id, current_user.id, timeout=60.0,
        )
        resp = await agent_client.post("/translate/topic", json=topic_dict)
        resp.raise_for_status()
        translated = resp.json()
    except httpx.TimeoutException:
        raise AppError(ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE) from None
    except Exception:
        logger.exception("Translation proxy call failed for topic %s", topic_id)
        raise AppError(ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE) from None

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

Also update imports at the top of `learning.py`:
- Remove: `from apps.backend.app.services.learning.translation import translate_topic`
- Add: `import httpx` (if not already present)
- Add: `from apps.backend.app.services.agent_client import AgentClient` (if not already present)

- [ ] **Step 4: Delete the old translation.py**

```bash
git rm server/apps/backend/app/services/learning/translation.py
```

This removes 166 lines including the dead circuit breaker code, the hardcoded DashScope env-var config, and the sync OpenAI client.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/backend/test_learning_translation_proxy.py -v`
Expected: All 3 tests PASS

Also verify existing learning tests still pass:

Run: `cd server && uv run pytest tests/backend/test_learning_seed_validation.py -v`

- [ ] **Step 6: Run linter and verify no broken imports**

Run: `cd server && uv run ruff check apps/backend/app/routers/learning.py`
Run: `cd server && grep -r "from.*translation import" apps/backend/` — should return no results

- [ ] **Step 7: Commit**

```bash
git add -A server/apps/backend/
git commit -m "feat(learning): proxy translate endpoint to agent module

Backend translate endpoint now uses AgentClient to proxy to the agent
module's /translate/topic endpoint, which uses LLMClient.complete_json()
with the family's configured AI provider.

Deletes the old backend translation.py (166 lines) that called DashScope
directly with a dead circuit breaker.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Fix badge validation to check subject slugs

**Files:**
- Modify: `server/apps/backend/app/services/learning/validation.py`
- Modify: `server/tests/backend/test_learning_seed_validation.py`

**Interfaces:**
- Consumes: `LearningTopic` model for querying distinct subjects from DB
- Produces: `validate_badge_subjects(badge_subjects: set[str], db: Session) -> list[str]` — replaces `validate_badge_dimensions()`

- [ ] **Step 1: Write the failing test**

Update `server/tests/backend/test_learning_seed_validation.py` — replace the three badge dimension tests with subject-based tests:

```python
# --- Badge subject validity (replaces badge dimension tests) ---


def test_badge_subjects_all_valid(db, math_topics):
    """Subjects that exist in LearningTopic pass validation."""
    # math_topics fixture creates topics with subject="mathematics"
    valid_subjects = {"mathematics"}
    result = validate_badge_subjects(valid_subjects, db)
    assert result == []


def test_badge_subjects_unknown_subject(db, math_topics):
    """A subject not in any LearningTopic fails validation."""
    invalid_subjects = {"mathematics", "astrology"}
    result = validate_badge_subjects(invalid_subjects, db)
    assert len(result) == 1
    assert "astrology" in result[0]


def test_badge_subjects_empty_set_ok(db):
    """No badges defined -> nothing to validate -> passes."""
    result = validate_badge_subjects(set(), db)
    assert result == []


def test_badge_subjects_actual_seed_data(db):
    """All BADGE_DEFINITIONS dimensions must be valid LearningTopic subjects.

    This test catches the original mismatch where validate_badge_dimensions()
    checked against _KNOWN_ABILITY_DIMENSIONS (cognitive abilities) instead
    of LearningTopic.subject values (mathematics, science, etc.).
    """
    from scripts.seed_learning_badges import BADGE_DEFINITIONS

    badge_subjects = {dim for dim, *_ in BADGE_DEFINITIONS}
    # Seed some topics with all subjects so the DB has them
    for subj in badge_subjects:
        db.add(LearningTopic(
            topic_key=f"seed_check_{subj}",
            topic_type="CONCEPTUAL",
            subject=subj,
            domain="Check",
            name=f"Check {subj}",
            description="Validation check",
            age_group="mid",
            evidence_json="[]",
            standards_json="[]",
        ))
    db.flush()

    result = validate_badge_subjects(badge_subjects, db)
    assert result == [], f"Seed badge subjects failed validation: {result}"
```

Update the import at the top of the test file:

```python
from apps.backend.app.services.learning.validation import (
    validate_age_ranges,
    validate_badge_subjects,  # was: validate_badge_dimensions
)
```

Remove the old `test_badge_dimensions_*` tests (3 tests).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_seed_validation.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_badge_subjects'`

- [ ] **Step 3: Fix the validation function**

Replace `validate_badge_dimensions()` in `server/apps/backend/app/services/learning/validation.py` with `validate_badge_subjects()`:

```python
def validate_badge_subjects(badge_subjects: set[str], db: Session) -> list[str]:
    """Verify all badge subjects exist as LearningTopic.subject values.

    The badge model (LiteracyBadgeDefinition) uses a `dimension` field
    storing subject slugs (e.g., "mathematics", "science") that must match
    actual LearningTopic.subject values in the seed data.

    Returns:
        List of error messages (empty = all good).
    """
    existing_subjects = {
        row[0]
        for row in db.query(LearningTopic.subject).distinct().all()
        if row[0]
    }
    errors = []
    for subj in sorted(badge_subjects):
        if subj not in existing_subjects:
            errors.append(
                f"Badge subject '{subj}' does not match any LearningTopic.subject"
            )
    return errors
```

Remove the `_KNOWN_ABILITY_DIMENSIONS` constant (lines 14-25) — it is no longer referenced.

- [ ] **Step 4: Update the seed script to call the renamed function**

In `server/scripts/seed_learning_topics.py`, find the call to `validate_badge_dimensions()` inside `validate_quality()` (around lines 229-238) and update:

```python
# Old:
from apps.backend.app.services.learning.validation import (
    validate_age_ranges,
    validate_badge_dimensions,
)
# ...
badge_dims = {dim for dim, *_ in BADGE_DEFINITIONS}
errors = validate_badge_dimensions(badge_dims)

# New:
from apps.backend.app.services.learning.validation import (
    validate_age_ranges,
    validate_badge_subjects,
)
# ...
badge_subjects = {dim for dim, *_ in BADGE_DEFINITIONS}
errors = validate_badge_subjects(badge_subjects, db)
```

Note: `validate_badge_subjects` now requires `db` as a second argument. The `validate_quality()` function already receives `db` as a parameter.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/backend/test_learning_seed_validation.py -v`
Expected: All tests PASS (6 tests: 3 badge subject + 3 age range)

- [ ] **Step 6: Run linter**

Run: `cd server && uv run ruff check apps/backend/app/services/learning/validation.py scripts/seed_learning_topics.py`

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/services/learning/validation.py server/scripts/seed_learning_topics.py server/tests/backend/test_learning_seed_validation.py
git commit -m "fix(learning): validate badge subjects against LearningTopic.subject, not ability dimensions

The old validate_badge_dimensions() checked badge dimension names against
_KNOWN_ABILITY_DIMENSIONS (cognitive abilities like 'numerical_reasoning'),
but BADGE_DEFINITIONS actually uses LearningTopic.subject slugs (mathematics,
science, etc.). Renamed to validate_badge_subjects() and queries the DB
for distinct subject values.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Add child_id/topic_id to Reminder + auto-resolve streak on pass

**Files:**
- Modify: `server/packages/db/models/reminder.py` (add columns)
- Create: `server/apps/backend/alembic/versions/<timestamp>_add_reminder_child_topic.py`
- Modify: `server/apps/backend/app/services/notification/dispatcher.py` (structured dedup + auto-resolve)
- Modify: `server/apps/backend/app/services/mcp_session.py` (wire pass-resolution + streak detection)
- Modify: `server/apps/backend/app/services/learning/progress_service.py` (add `resolve_streak_reminder_on_pass`)
- Test: `server/tests/backend/test_learning_streak_dedup.py`

**Interfaces:**
- Consumes: `Reminder` model, `LearningAssessmentAttempt` model
- Produces: `resolve_streak_reminder_on_pass(db, child_id, topic_id) -> int` — returns count of resolved reminders

- [ ] **Step 1: Write the failing test**

Create `server/tests/backend/test_learning_streak_dedup.py`:

```python
"""Tests for notification dedup fix — structured child_id/topic_id + auto-resolve on pass."""

import pytest
from datetime import UTC, datetime

from apps.backend.app.services.learning.progress_service import (
    STREAK_THRESHOLD,
    check_consecutive_failures,
    resolve_streak_reminder_on_pass,
)
from apps.backend.app.services.notification.dispatcher import (
    notify_learning_streak_3_failures,
)
from packages.db.models.learning.session import LearningAssessmentAttempt
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.reminder import Reminder
from packages.db.models.user import User


@pytest.fixture
def child(db):
    user = User(
        id=100, family_id=1, username="child1",
        display_name="Alice", role="child",
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def topic(db):
    t = LearningTopic(
        topic_key="dedup_test",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Subtraction",
        description="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def _make_attempt(db, child_id, topic_id, passed, n):
    """Helper to create ordered attempts."""
    attempt = LearningAssessmentAttempt(
        child_id=child_id, topic_id=topic_id,
        session_id=None, assessment_type="ai",
        score=0.0 if not passed else 1.0,
        passed=passed,
    )
    db.add(attempt)
    db.flush()
    return attempt


def test_structured_dedup_uses_child_topic_ids(db, child, topic):
    """notify_learning_streak_3_failures stores child_id and topic_id on Reminder."""
    # Create 3 failures
    for i in range(3):
        _make_attempt(db, child.id, topic.id, passed=False, n=i)

    notify_learning_streak_3_failures(db, child_id=child.id, topic_id=topic.id)
    db.flush()

    reminder = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
    ).first()
    assert reminder is not None
    assert reminder.child_id == child.id
    assert reminder.topic_id == topic.id


def test_pass_resolves_active_streak_reminder(db, child, topic):
    """When a child passes, active streak reminders for that child+topic are resolved."""
    # Create an active streak reminder
    reminder = Reminder(
        id=999,
        family_id=child.family_id,
        reminder_type="learning_streak_3_failures",
        title="Test",
        body="Test",
        severity="warning",
        status="active",
        child_id=child.id,
        topic_id=topic.id,
    )
    db.add(reminder)
    db.flush()

    # Pass should resolve it
    count = resolve_streak_reminder_on_pass(db, child.id, topic.id)
    assert count == 1

    db.expire_all()
    resolved = db.query(Reminder).filter(Reminder.id == 999).first()
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None


def test_full_retrigger_sequence(db, child, topic):
    """3 fails → notification → pass resolves → 3 more fails → new notification."""
    # Phase 1: 3 failures → notification
    for i in range(3):
        _make_attempt(db, child.id, topic.id, passed=False, n=i)

    notify_learning_streak_3_failures(db, child_id=child.id, topic_id=topic.id)
    db.flush()

    reminders_1 = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
        status="active",
        child_id=child.id,
        topic_id=topic.id,
    ).all()
    assert len(reminders_1) == 1

    # Phase 2: pass → auto-resolve
    _make_attempt(db, child.id, topic.id, passed=True, n=3)
    resolve_streak_reminder_on_pass(db, child.id, topic.id)
    db.flush()

    active_after_pass = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
        status="active",
        child_id=child.id,
        topic_id=topic.id,
    ).all()
    assert len(active_after_pass) == 0

    # Phase 3: 3 more failures → new notification
    for i in range(3):
        _make_attempt(db, child.id, topic.id, passed=False, n=4 + i)

    streak = check_consecutive_failures(db, child.id, topic.id)
    assert streak == STREAK_THRESHOLD

    notify_learning_streak_3_failures(db, child_id=child.id, topic_id=topic.id)
    db.flush()

    reminders_2 = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
        status="active",
        child_id=child.id,
        topic_id=topic.id,
    ).all()
    assert len(reminders_2) == 1
    assert reminders_2[0].id != reminders_1[0].id  # different reminder
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_streak_dedup.py -v`
Expected: FAIL — `Reminder` has no `child_id`/`topic_id` columns; `resolve_streak_reminder_on_pass` doesn't exist

- [ ] **Step 3: Add child_id and topic_id columns to Reminder model**

In `server/packages/db/models/reminder.py`, add two nullable columns after `asset_id`:

```python
    child_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )
```

Note: `topic_id` is not a FK to `learning_topics` because that table lives in the same DB but the Reminder model is in `packages/db` which should not depend on learning-specific tables. The column is a plain `BigInteger` with an index.

- [ ] **Step 4: Create Alembic migration**

```bash
cd server/apps/backend
uv run alembic revision --autogenerate -m "add child_id and topic_id to reminders"
```

Review the generated migration. It should add two nullable `BigInteger` columns with indexes. If there are existing `learning_streak_3_failures` reminders, add a data migration to backfill their `child_id` and `topic_id` from the title string (parse `child_name` and `topic_name`, look up IDs). For simplicity, the initial migration can leave them NULL for old rows — the structured dedup only applies to new reminders going forward.

- [ ] **Step 5: Update dispatcher to use structured dedup**

In `server/apps/backend/app/services/notification/dispatcher.py`, modify `notify_learning_streak_3_failures()`:

Replace the old dedup query (lines 322-336):

```python
    # Old: string containment dedup
    existing = (
        db.query(Reminder)
        .filter_by(
            family_id=family_id,
            reminder_type="learning_streak_3_failures",
            status="active",
        )
        .filter(
            Reminder.title.contains(child_name),
            Reminder.title.contains(topic_name),
        )
        .first()
    )
    if existing:
        return
```

With structured dedup:

```python
    # Structured dedup by child_id + topic_id (replaces fragile string containment)
    existing = (
        db.query(Reminder)
        .filter_by(
            family_id=family_id,
            reminder_type="learning_streak_3_failures",
            status="active",
            child_id=child_id,
            topic_id=topic_id,
        )
        .first()
    )
    if existing:
        return  # already notified for this child+topic combo
```

And add `child_id`/`topic_id` to the Reminder creation (around line 338):

```python
    reminder = Reminder(
        id=next_id(),
        family_id=family_id,
        reminder_type="learning_streak_3_failures",
        title=f"{child_name} 在 {topic_name} 上连续遇到困难",
        body=(
            f"{child_name} 在「{topic_name}」({subject}) 的评估中连续 3 次未通过。"
            "建议一起复习这个知识点，或尝试不同的学习方式。"
        ),
        severity="warning",
        status="active",
        child_id=child_id,      # NEW
        topic_id=topic_id,      # NEW
    )
```

- [ ] **Step 6: Add resolve_streak_reminder_on_pass to progress_service.py**

In `server/apps/backend/app/services/learning/progress_service.py`, add after `check_consecutive_failures()`:

```python
def resolve_streak_reminder_on_pass(
    db: Session, child_id: int, topic_id: int,
) -> int:
    """Resolve active streak reminders when a pass breaks the failure streak.

    This allows future failure streaks to trigger new notifications
    instead of being suppressed by the old active reminder.

    Returns:
        Number of reminders resolved.
    """
    from packages.db.models.reminder import Reminder

    now = datetime.now(UTC)
    updated = (
        db.query(Reminder)
        .filter_by(
            reminder_type="learning_streak_3_failures",
            status="active",
            child_id=child_id,
            topic_id=topic_id,
        )
        .update({
            Reminder.status: "resolved",
            Reminder.resolved_at: now,
        })
    )
    if updated:
        db.flush()
    return updated
```

- [ ] **Step 7: Wire pass-resolution into mcp_session.py**

In `server/apps/backend/app/services/mcp_session.py`, find the `record_learning_result` handler where `LearningAssessmentAttempt` is created (around line 782-794). After the attempt is created and flushed, add streak logic:

```python
    # After: db.add(attempt); db.flush()

    # Streak detection and notification
    from apps.backend.app.services.learning import progress_service

    if attempt.passed:
        # Pass breaks any active streak — resolve old reminders so
        # future failure streaks can re-trigger notifications
        progress_service.resolve_streak_reminder_on_pass(
            db, child.id, session.topic_id,
        )
    else:
        streak = progress_service.check_consecutive_failures(
            db, child.id, session.topic_id,
        )
        if streak == progress_service.STREAK_THRESHOLD:
            from apps.backend.app.services.notification.dispatcher import (
                notify_learning_streak_3_failures,
            )
            notify_learning_streak_3_failures(
                db, child_id=child.id, topic_id=session.topic_id,
            )
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/backend/test_learning_streak_dedup.py -v`
Expected: All 3 tests PASS

Also run existing streak tests:

Run: `cd server && uv run pytest tests/backend/test_learning_streak_detection.py -v`

- [ ] **Step 9: Run full learning test suite + linter**

Run: `cd server && uv run pytest tests/backend/ -k learning -v`
Run: `cd server && uv run ruff check apps/backend/app/services/notification/dispatcher.py apps/backend/app/services/learning/progress_service.py apps/backend/app/services/mcp_session.py packages/db/models/reminder.py`

- [ ] **Step 10: Commit**

```bash
git add -A server/
git commit -m "fix(learning): structured reminder dedup + auto-resolve streak on pass

Add child_id/topic_id columns to Reminder for structured dedup
(replaces fragile string containment in title). When a child passes
an assessment, active streak reminders are auto-resolved so future
failure streaks can re-trigger notifications.

Also wires streak detection into the production mcp_session.py
assessment flow (was previously only in record_failed_assessment
which was never called from production code).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Verify full suite + integration smoke

- [ ] **Step 1: Run all backend tests**

Run: `cd server && uv run pytest tests/backend/ -v --timeout=60`
Expected: All tests pass

- [ ] **Step 2: Run all agent tests**

Run: `cd server && uv run pytest tests/agent/ -v --timeout=60`
Expected: All tests pass

- [ ] **Step 3: Run linter on all changed files**

Run: `cd server && uv run ruff check apps/agent/services/topic_translate.py apps/agent/routers/translate.py apps/backend/app/routers/learning.py apps/backend/app/services/learning/validation.py apps/backend/app/services/notification/dispatcher.py apps/backend/app/services/learning/progress_service.py apps/backend/app/services/mcp_session.py packages/db/models/reminder.py`

- [ ] **Step 4: Verify no dangling imports**

Run: `cd server && grep -r "from.*learning.translation" apps/ scripts/` — should return empty
Run: `cd server && grep -r "validate_badge_dimensions" apps/ scripts/ tests/` — should return empty (all references renamed)
Run: `cd server && grep -r "_KNOWN_ABILITY_DIMENSIONS" apps/` — should return empty

- [ ] **Step 5: Run type check**

Run: `cd server && uv run mypy apps/agent/services/topic_translate.py apps/agent/routers/translate.py`

- [ ] **Step 6: Final commit (if any cleanup needed)**

Only if previous steps found issues to fix.
