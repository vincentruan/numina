# Learning OS Deferred Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 4 remaining deferred items from the Learning OS code review — Today Learning card on ChildHomePage, BabyPage→BabyLearningPage navigation, study duration aggregation, and topic graph display.

**Architecture:** One backend task adds a new `/child/learning/today` endpoint and extends the existing `/child/learning/progress` with study-minute aggregation (shared `aggregate_study_minutes` service helper). Four frontend tasks consume those endpoints and fill UI gaps — a `TodayLearningCard` on ChildHomePage, real study-minute display on LearningProgressPage, a learning cell + KeepAlive on BabyPage/MainLayout, and a topic prerequisite/dependent graph section on LearningTopicPage (backend graph endpoint already exists).

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + pytest | Vue 3 + TypeScript + Vant 4 + vue-i18n

**Spec:** [`docs/superpowers/specs/2026-09-23-learning-os-deferred-items-design.md`](../specs/2026-09-23-learning-os-deferred-items-design.md)

## Global Constraints

- All API endpoints respond 200 directly — no 307 redirects. Root-path decorators use `""` not `"/"`.
- All `bigint` IDs serialized as strings in API responses (`SnowflakeBase`).
- All user-facing strings in `.ts`/`.vue` files use i18n keys via `t('key')` — never hardcode Chinese strings.
- Vant 4 components are auto-imported — do not manually import them.
- `<script setup lang="ts">` only — no Options API.
- Snowflake ID fields must be `string` in TypeScript types.
- Service-layer convention: DB aggregation belongs in `progress_service.py`, not inline in routers.
- `ChildProgressOverview` uses `BaseModel` (no IDs) — does NOT need `SnowflakeBase`.
- `TodayLearningResponse` MUST inherit `SnowflakeBase` per spec review [S3].
- `LearningTopic` model has no `sort_order` column — use `centrality DESC` as ordering proxy for recommended topics.
- Incremental formatting — format only files you touch.

## Review Focus

1. **Deterministic ordering for "today" queries**: `current_topic` uses `updated_at DESC`, `pending_assignment` uses `created_at ASC`, `recommended_topic` uses `centrality DESC`. Without ORDER BY, results are non-deterministic. Pin: Task 1 test `test_today_deterministic_ordering` creates multiple learning-state progresses and asserts the most-recently-updated is returned.
2. **`func.sum()` returns `None` for empty sets**: When a child has zero sessions, `func.sum(LearningSession.duration_seconds)` returns `None`, not `0`. Without `or 0`, the response would contain `null` instead of `0`. Pin: Task 1 test `test_today_study_minutes_zero_when_no_sessions`.
3. **`ChildProgressOverview` backward compatibility**: Adding `total_study_minutes` and `today_study_minutes` with `= 0` defaults is backward-compatible — existing consumers ignore unknown fields. Pin: Task 1 test `test_progress_schema_has_study_minutes`.
4. **BabyPage learning cell hidden in "All" tab**: When `selectedChildId === null` (the "全部" tab), the learning cell must not appear — there's no meaningful per-child study minutes to show. Pin: Task 4 visual check — cell only renders with `v-if="selectedChildId"`.
5. **Topic graph fetch failure must not break LearningTopicPage**: The graph API call is supplementary. If it fails, the page must still show the topic detail, mastery bar, and action buttons — just hide the graph section. Pin: Task 5 test — graph fetch wrapped in try/catch with `graphData = null` on error.

---

## Task 1: Backend — Study duration aggregation + Today endpoint (Areas A + E)

**Files:**
- Modify: `server/apps/backend/app/services/learning/progress_service.py` (add `aggregate_study_minutes`)
- Modify: `server/apps/backend/app/schemas/learning.py` (add `TodayLearningResponse`, extend `ChildProgressOverview`)
- Modify: `server/apps/backend/app/routers/learning_child.py` (add `GET /today`, update `GET /progress`)
- Create: `server/tests/backend/test_learning_today_and_duration.py`

**Interfaces:**
- Consumes: `LearningProgress`, `LearningSession`, `LearningAssignment`, `LearningTopic` ORM models; `TopicResponse`, `AssignmentResponse` schemas; `progress_service.get_child_progress_overview`
- Produces: `GET /api/v1/child/learning/today` → `TodayLearningResponse`; `GET /api/v1/child/learning/progress` → extended `ChildProgressOverview` with `total_study_minutes` + `today_study_minutes`

- [ ] **Step 1: Write failing tests**

Create `server/tests/backend/test_learning_today_and_duration.py`:

```python
"""Tests for GET /child/learning/today and study duration aggregation (Areas A + E)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic


# ── helpers ──────────────────────────────────────────────────────────────

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "ChildPass1"


def _create_child(client, headers, username="durchild"):
    resp = client.post(
        "/api/v1/family/children",
        headers=headers,
        json={
            "username": username,
            "password": CHILD_PASSWORD,
            "display_name": "Duration Tester",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


def _create_topic(db: Session, topic_key: str = "dur_topic", name: str = "Dur Topic") -> LearningTopic:
    t = LearningTopic(
        topic_key=topic_key,
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name=name,
        description="Test topic",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def _child_login(client, username: str, password: str = CHILD_PASSWORD):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


# ── Area E: study duration aggregation ───────────────────────────────────


def test_progress_schema_has_study_minutes(
    client, db: Session, auth_headers, child_login_two_phase
):
    """ChildProgressOverview returns total_study_minutes and today_study_minutes."""
    child = _create_child(client, auth_headers)
    child_headers = _child_login(client, child["username"])

    resp = client.get("/api/v1/child/learning/progress", headers=child_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_study_minutes" in data
    assert "today_study_minutes" in data
    # No sessions yet → both should be 0
    assert data["total_study_minutes"] == 0
    assert data["today_study_minutes"] == 0


def test_progress_study_minutes_aggregation(
    client, db: Session, auth_headers
):
    """Sessions contribute to total and today study minutes."""
    child = _create_child(client, auth_headers, username="aggchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    topic = _create_topic(db, "agg_topic")

    now = datetime.now(UTC)
    # Two sessions: one today, one yesterday
    s1 = LearningSession(
        child_id=child_id, topic_id=topic.id,
        session_type="tutorial", duration_seconds=600,
        started_at=now - timedelta(hours=2), ended_at=now - timedelta(hours=1),
    )
    s2 = LearningSession(
        child_id=child_id, topic_id=topic.id,
        session_type="tutorial", duration_seconds=300,
        started_at=now - timedelta(days=1, hours=2),
        ended_at=now - timedelta(days=1, hours=1),
    )
    db.add_all([s1, s2])
    db.commit()

    resp = client.get("/api/v1/child/learning/progress", headers=child_headers)
    data = resp.json()["data"]
    assert data["total_study_minutes"] == 15  # (600+300)//60
    assert data["today_study_minutes"] == 10  # 600//60


def test_progress_study_minutes_null_ended_at_excluded(
    client, db: Session, auth_headers
):
    """Sessions with ended_at=None are excluded from aggregation."""
    child = _create_child(client, auth_headers, username="nulchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    topic = _create_topic(db, "null_topic")

    # Active session — no ended_at
    s = LearningSession(
        child_id=child_id, topic_id=topic.id,
        session_type="tutorial", duration_seconds=999,
        started_at=datetime.now(UTC), ended_at=None,
    )
    db.add(s)
    db.commit()

    resp = client.get("/api/v1/child/learning/progress", headers=child_headers)
    data = resp.json()["data"]
    assert data["total_study_minutes"] == 0
    assert data["today_study_minutes"] == 0


# ── Area A: /today endpoint ─────────────────────────────────────────────


def test_today_study_minutes_zero_when_no_sessions(
    client, db: Session, auth_headers
):
    """study_minutes_today is 0 (not null) when child has no sessions."""
    child = _create_child(client, auth_headers, username="zerchild")
    child_headers = _child_login(client, child["username"])

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["study_minutes_today"] == 0
    assert data["current_topic"] is None
    assert data["pending_assignment"] is None
    assert data["recommended_topic"] is None


def test_today_returns_current_topic(
    client, db: Session, auth_headers
):
    """current_topic returns the most recently updated 'learning' progress."""
    child = _create_child(client, auth_headers, username="curchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    t1 = _create_topic(db, "cur_t1", "Topic One")
    t2 = _create_topic(db, "cur_t2", "Topic Two")

    p1 = LearningProgress(child_id=child_id, topic_id=t1.id, mastery_level="learning")
    p2 = LearningProgress(child_id=child_id, topic_id=t2.id, mastery_level="learning")
    db.add_all([p1, p2])
    db.commit()
    # Force p1 to have a later updated_at
    p1.updated_at = datetime.now(UTC)
    db.commit()

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    data = resp.json()["data"]
    assert data["current_topic"] is not None
    assert data["current_topic"]["id"] == str(t1.id)


def test_today_returns_pending_assignment(
    client, db: Session, auth_headers
):
    """pending_assignment takes priority over current_topic."""
    child = _create_child(client, auth_headers, username="pendchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    topic = _create_topic(db, "pend_topic")
    # Create a progress so the child has learning context
    p = LearningProgress(child_id=child_id, topic_id=topic.id, mastery_level="learning")
    db.add(p)

    assignment = LearningAssignment(
        family_id=child["family_id"],
        child_id=child_id,
        topic_id=topic.id,
        created_by=child_id,
        assignment_type="parent_assigned",
        status="pending",
        priority=0,
    )
    db.add(assignment)
    db.commit()

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    data = resp.json()["data"]
    assert data["pending_assignment"] is not None
    assert data["pending_assignment"]["topic"]["id"] == str(topic.id)


def test_today_deterministic_ordering(
    client, db: Session, auth_headers
):
    """Multiple 'learning' progresses → current_topic returns most recently updated."""
    child = _create_child(client, auth_headers, username="detchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    topics = [_create_topic(db, f"det_t{i}", f"Det Topic {i}") for i in range(3)]
    progresses = [
        LearningProgress(child_id=child_id, topic_id=t.id, mastery_level="learning")
        for t in topics
    ]
    db.add_all(progresses)
    db.commit()

    # Set the SECOND topic as most recently updated
    progresses[1].updated_at = datetime.now(UTC) + timedelta(seconds=10)
    db.commit()

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    data = resp.json()["data"]
    assert data["current_topic"]["id"] == str(topics[1].id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_today_and_duration.py -v`
Expected: FAIL — `TodayLearningResponse` not defined, `/today` endpoint doesn't exist, `ChildProgressOverview` missing study fields.

- [ ] **Step 3: Add `aggregate_study_minutes` to `progress_service.py`**

In `server/apps/backend/app/services/learning/progress_service.py`, add at the end of the file:

```python
from packages.db.models.learning.session import LearningSession


def aggregate_study_minutes(db: Session, child_id: int) -> dict[str, int]:
    """Return total and today study minutes for a child.

    Excludes sessions with ended_at=None (still in progress).
    Returns 0 for both fields when no matching sessions exist.
    """
    # Total study minutes (all ended sessions)
    total_seconds = (
        db.query(sa_func.sum(LearningSession.duration_seconds))
        .filter(
            LearningSession.child_id == child_id,
            LearningSession.ended_at.isnot(None),
        )
        .scalar()
        or 0
    )

    # Today's study minutes (UTC midnight boundary)
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_seconds = (
        db.query(sa_func.sum(LearningSession.duration_seconds))
        .filter(
            LearningSession.child_id == child_id,
            LearningSession.ended_at >= today_start,
            LearningSession.ended_at.isnot(None),
        )
        .scalar()
        or 0
    )

    return {
        "total_study_minutes": total_seconds // 60,
        "today_study_minutes": today_seconds // 60,
    }
```

Note: `sa_func` is already imported as `from sqlalchemy import func as sa_func` at line 5. The `LearningSession` import needs to be added (the model is already used indirectly via `LearningAssessmentAttempt` import at line 11 — but add explicit import).

Add this import near the existing imports at line 11:

```python
from packages.db.models.learning.session import LearningAssessmentAttempt, LearningSession
```

- [ ] **Step 4: Add `TodayLearningResponse` schema and extend `ChildProgressOverview`**

In `server/apps/backend/app/schemas/learning.py`:

Add import for `TodayLearningResponse` (after the existing `AssignmentResponse` class, around line 108):

```python
class TodayLearningResponse(SnowflakeBase):
    """Today's learning overview for a child — drives the TodayLearningCard."""

    current_topic: TopicResponse | None = None
    pending_assignment: AssignmentResponse | None = None
    recommended_topic: TopicResponse | None = None
    study_minutes_today: int = 0
```

Extend `ChildProgressOverview` (line 175):

```python
class ChildProgressOverview(BaseModel):
    """Aggregated progress overview for a child."""
    mastered_count: int
    learning_count: int
    available_count: int
    locked_count: int
    review_count: int
    assessing_count: int
    parent_review_count: int
    total_study_minutes: int = 0
    today_study_minutes: int = 0
```

- [ ] **Step 5: Add `GET /today` endpoint and update `GET /progress` in router**

In `server/apps/backend/app/routers/learning_child.py`:

Add `TodayLearningResponse` to the schema imports (line 15-21):

```python
from apps.backend.app.schemas.learning import (
    AssignmentResponse,
    ChildProgressOverview,
    ProgressResponse,
    SessionCreate,
    SessionResponse,
    TodayLearningResponse,
    TopicResponse,
)
```

Add the `/today` endpoint **before** the `/topics/{topic_id}` endpoint (literal path before path-param — per CLAUDE.md FastAPI route ordering rule). Insert after the `/assignments` endpoint (line 65):

```python
@router.get("/today", response_model=TodayLearningResponse)
def today_learning(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Today's learning summary — drives the TodayLearningCard on ChildHomePage."""
    # 1. current_topic: first progress with mastery_level=="learning", ORDER BY updated_at DESC
    current_progress = (
        db.query(LearningProgress)
        .filter(
            LearningProgress.child_id == child.id,
            LearningProgress.mastery_level == "learning",
        )
        .order_by(LearningProgress.updated_at.desc())
        .first()
    )
    current_topic = None
    if current_progress:
        current_topic = (
            db.query(LearningTopic)
            .filter(LearningTopic.id == current_progress.topic_id)
            .first()
        )

    # 2. pending_assignment: first with status=="pending", ORDER BY created_at ASC
    pending_assignment_orm = (
        db.query(LearningAssignment)
        .filter(
            LearningAssignment.child_id == child.id,
            LearningAssignment.status == "pending",
        )
        .order_by(LearningAssignment.created_at.asc())
        .first()
    )
    # Expand topic on the assignment (schema's `topic` field is None by default)
    pending_assignment = None
    if pending_assignment_orm:
        a_topic = (
            db.query(LearningTopic)
            .filter(LearningTopic.id == pending_assignment_orm.topic_id)
            .first()
        )
        pending_assignment = AssignmentResponse.model_validate(pending_assignment_orm)
        pending_assignment.topic = a_topic

    # 3. recommended_topic: locked with all hard prereqs met, stable ordering
    locked_progresses = (
        db.query(LearningProgress)
        .filter(
            LearningProgress.child_id == child.id,
            LearningProgress.mastery_level == "locked",
        )
        .all()
    )
    recommended_topic = None
    for lp in sorted(locked_progresses, key=lambda p: p.topic_id):
        if progress_service._all_hard_prereqs_met(db, child.id, lp.topic_id):
            recommended_topic = (
                db.query(LearningTopic)
                .filter(LearningTopic.id == lp.topic_id)
                .first()
            )
            break

    # 4. study_minutes_today
    study_minutes = progress_service.aggregate_study_minutes(db, child.id)

    return TodayLearningResponse(
        current_topic=current_topic,
        pending_assignment=pending_assignment,
        recommended_topic=recommended_topic,
        study_minutes_today=study_minutes["today_study_minutes"],
    )
```

Update the existing `/progress` endpoint (line 161-176) to include study minutes:

```python
@router.get("/progress", response_model=ChildProgressOverview)
def my_overall_progress(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get overall progress overview — aggregated mastery counts + study time."""
    overview = progress_service.get_child_progress_overview(db, child.id)
    study_minutes = progress_service.aggregate_study_minutes(db, child.id)
    return ChildProgressOverview(
        mastered_count=overview["mastered"],
        learning_count=overview["learning"],
        available_count=overview["available"],
        locked_count=overview["locked"],
        review_count=overview["review"],
        assessing_count=overview["assessing"],
        parent_review_count=overview["parent_review"],
        **study_minutes,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/backend/test_learning_today_and_duration.py -v`
Expected: All 7 tests PASS.

Also run existing learning tests to verify no regressions:
Run: `cd server && uv run pytest tests/backend/test_learning_progress_service.py tests/backend/test_learning_integration.py -v`
Expected: All existing tests still PASS.

- [ ] **Step 7: Run lint**

Run: `cd server && uv run ruff check apps/backend/app/services/learning/progress_service.py apps/backend/app/schemas/learning.py apps/backend/app/routers/learning_child.py`
Expected: No errors.

- [ ] **Step 8: Commit**

```bash
git add server/apps/backend/app/services/learning/progress_service.py \
       server/apps/backend/app/schemas/learning.py \
       server/apps/backend/app/routers/learning_child.py \
       server/tests/backend/test_learning_today_and_duration.py
git commit -m "feat(learning): add /today endpoint + study duration aggregation (Areas A+E backend)

- Add aggregate_study_minutes() to progress_service
- Add TodayLearningResponse schema (SnowflakeBase)
- Add GET /child/learning/today endpoint
- Extend ChildProgressOverview with total/today study minutes
- 7 tests covering all branches and edge cases"
```

---

## Task 2: Frontend — TodayLearningCard on ChildHomePage (Area A frontend)

**Files:**
- Modify: `frontend/apps/child/src/api/learning.ts` (add types + API function)
- Create: `frontend/apps/child/src/components/TodayLearningCard.vue`
- Modify: `frontend/apps/child/src/pages/ChildHomePage.vue` (insert card after ProgressRing)
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts` (add i18n keys)
- Modify: `frontend/apps/child/src/i18n/locales/en-US.ts` (add i18n keys)

**Interfaces:**
- Consumes: `GET /api/v1/child/learning/today` → `TodayLearningResponse` (from Task 1)
- Produces: `TodayLearningCard.vue` component inserted after `ProgressRing` in `ChildHomePage.vue`

- [ ] **Step 1: Add TypeScript types and API function**

In `frontend/apps/child/src/api/learning.ts`, add after the existing interfaces (around line 101):

```typescript
export interface TodayLearningResponse {
  current_topic: TopicResponse | null
  pending_assignment: AssignmentResponse | null
  recommended_topic: TopicResponse | null
  study_minutes_today: number
}
```

Add after the existing API functions (around line 160):

```typescript
export async function getTodayLearning(): Promise<TodayLearningResponse> {
  const res = await http.get('/child/learning/today')
  return res.data
}
```

Also update `ChildProgressOverview` interface to include the new fields:

```typescript
export interface ChildProgressOverview {
  mastered_count: number
  learning_count: number
  available_count: number
  locked_count: number
  review_count: number
  assessing_count: number
  parent_review_count: number
  total_study_minutes: number
  today_study_minutes: number
}
```

- [ ] **Step 2: Create `TodayLearningCard.vue`**

Create `frontend/apps/child/src/components/TodayLearningCard.vue`:

```vue
<template>
  <div v-if="displayMode" class="today-learning-card" @click="navigate">
    <div class="today-learning-card__content">
      <span class="today-learning-card__icon">{{ icon }}</span>
      <div class="today-learning-card__text">
        <p class="today-learning-card__label">{{ label }}</p>
        <p class="today-learning-card__topic">{{ topicName }}</p>
      </div>
      <van-icon name="arrow" size="16" color="var(--color-muted-soft)" />
    </div>
    <p class="today-learning-card__footer">
      {{ t('learning.todayCard.footer', { minutes: data.study_minutes_today }) }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { TodayLearningResponse } from '@/api/learning'

const props = defineProps<{
  data: TodayLearningResponse
}>()

const { t } = useI18n()
const router = useRouter()

type DisplayMode = 'assignment' | 'current' | 'recommended' | 'explore'

const displayMode = computed<DisplayMode>(() => {
  if (props.data.pending_assignment) return 'assignment'
  if (props.data.current_topic) return 'current'
  if (props.data.recommended_topic) return 'recommended'
  return 'explore'
})

const icon = computed(() => {
  switch (displayMode.value) {
    case 'assignment': return '📝'
    case 'current': return '📖'
    case 'recommended': return '🌟'
    case 'explore': return '📚'
  }
})

const label = computed(() => t(`learning.todayCard.${displayMode.value}`))

const topicName = computed(() => {
  switch (displayMode.value) {
    case 'assignment': return props.data.pending_assignment?.topic?.name_zh ?? props.data.pending_assignment?.topic?.name ?? ''
    case 'current': return props.data.current_topic?.name_zh ?? props.data.current_topic?.name ?? ''
    case 'recommended': return props.data.recommended_topic?.name_zh ?? props.data.recommended_topic?.name ?? ''
    case 'explore': return t('learning.todayCard.exploreSub')
  }
})

const targetTopicId = computed(() => {
  if (props.data.pending_assignment) return props.data.pending_assignment.topic?.id
  if (props.data.current_topic) return props.data.current_topic.id
  if (props.data.recommended_topic) return props.data.recommended_topic.id
  return null
})

function navigate() {
  if (targetTopicId.value) {
    router.push(`/learning/topic/${targetTopicId.value}`)
  } else {
    router.push('/learning')
  }
}
</script>

<style scoped>
.today-learning-card {
  margin: 12px 0;
  padding: 14px 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: transform 0.1s;
}

.today-learning-card:active {
  transform: scale(0.98);
}

.today-learning-card__content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.today-learning-card__icon {
  font-size: 24px;
  flex-shrink: 0;
}

.today-learning-card__text {
  flex: 1;
  min-width: 0;
}

.today-learning-card__label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
  margin: 0;
}

.today-learning-card__topic {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 2px 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.today-learning-card__footer {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
  margin: 8px 0 0;
  padding-top: 8px;
  border-top: 1px solid var(--color-hairline);
}
</style>
```

- [ ] **Step 3: Insert `TodayLearningCard` into `ChildHomePage.vue`**

In `frontend/apps/child/src/pages/ChildHomePage.vue`:

Add import in the `<script setup>` section:

```typescript
import TodayLearningCard from '@/components/TodayLearningCard.vue'
import { getTodayLearning, type TodayLearningResponse } from '@/api/learning'
```

Add reactive state:

```typescript
const todayLearning = ref<TodayLearningResponse | null>(null)
```

Add to the `load()` function (in the `Promise.all` or after existing fetches):

```typescript
try {
  todayLearning.value = await getTodayLearning()
} catch {
  todayLearning.value = null  // non-critical — hide card on failure
}
```

Insert in template after the `ProgressRing` section (after line 41, before the Today's chores section at line 43):

```html
    <!-- Today's learning — drives engagement with learning module -->
    <TodayLearningCard v-if="todayLearning" :data="todayLearning" />
```

- [ ] **Step 4: Add i18n keys**

In `frontend/apps/child/src/i18n/locales/zh-CN.ts`, add inside the `learning` section (around line 500, after `progress`):

```typescript
    todayCard: {
      assignment: '提交作业',
      current: '继续学习',
      recommended: '开始新知识',
      explore: '去学习地图探索',
      exploreSub: '探索知识地图',
      footer: '今日已学习 {minutes} 分钟',
    },
```

In `frontend/apps/child/src/i18n/locales/en-US.ts`, add corresponding keys:

```typescript
    todayCard: {
      assignment: 'Submit Assignment',
      current: 'Continue Learning',
      recommended: 'Start New Topic',
      explore: 'Explore Learning Map',
      exploreSub: 'Explore the knowledge map',
      footer: 'Studied {minutes} min today',
    },
```

- [ ] **Step 5: Verify type check passes**

Run: `cd frontend && pnpm --filter child exec vue-tsc --noEmit`
Expected: No type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/child/src/api/learning.ts \
       frontend/apps/child/src/components/TodayLearningCard.vue \
       frontend/apps/child/src/pages/ChildHomePage.vue \
       frontend/apps/child/src/i18n/locales/zh-CN.ts \
       frontend/apps/child/src/i18n/locales/en-US.ts
git commit -m "feat(learning): add TodayLearningCard to ChildHomePage (Area A frontend)

- TodayLearningCard shows 4 priority states: assignment > current > recommended > explore
- Fetches from GET /child/learning/today
- Graceful degradation: card hidden on API failure
- i18n keys for zh-CN and en-US"
```

---

## Task 3: Frontend — LearningProgressPage real study minutes (Area E frontend)

**Files:**
- Modify: `frontend/apps/child/src/pages/learning/LearningProgressPage.vue` (use real study minutes from API)
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts` (add today study minutes key)
- Modify: `frontend/apps/child/src/i18n/locales/en-US.ts` (add today study minutes key)

**Interfaces:**
- Consumes: `GET /api/v1/child/learning/progress` → `ChildProgressOverview` (now with `total_study_minutes` + `today_study_minutes` from Task 1)
- Produces: `LearningProgressPage.vue` displays real study minutes, `xp_earned` proxy removed

- [ ] **Step 1: Update `LearningProgressPage.vue` to use real study minutes**

In `frontend/apps/child/src/pages/learning/LearningProgressPage.vue`:

Add import for `getMyProgress`:

```typescript
import { getMyLearningMap, getMyProgress, getTopicDetail, type ProgressResponse, type TopicResponse, type ChildProgressOverview } from '@/api/learning'
```

Add reactive state for the overview:

```typescript
const progressOverview = ref<ChildProgressOverview | null>(null)
```

Update the `totalStudyMinutes` computed — **replace lines 128-131** (the `xp_earned` proxy):

```typescript
const totalStudyMinutes = computed(() => {
  return progressOverview.value?.total_study_minutes ?? 0
})

const todayStudyMinutes = computed(() => {
  return progressOverview.value?.today_study_minutes ?? 0
})
```

Update the `load()` function to also fetch the overview:

```typescript
async function load() {
  loading.value = true
  error.value = ''
  try {
    const [progress, overview] = await Promise.all([
      getMyLearningMap(),
      getMyProgress(),
    ])
    progressList.value = progress
    progressOverview.value = overview
    // ... existing topic detail fetch ...
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}
```

Update the template study section (around lines 42-45) to show both total and today:

```html
          <!-- Study time -->
          <div class="study-section">
            <h2 class="section-title">{{ t('learning.progress.studyTime') }}</h2>
            <div class="study-stats">
              <div class="study-stat">
                <span class="study-stat__value">{{ totalStudyMinutes }}</span>
                <span class="study-stat__label">{{ t('learning.progress.totalMinutes') }}</span>
              </div>
              <div class="study-stat">
                <span class="study-stat__value">{{ todayStudyMinutes }}</span>
                <span class="study-stat__label">{{ t('learning.progress.todayMinutes') }}</span>
              </div>
            </div>
          </div>
```

Add CSS for the new study stats layout:

```css
.study-stats {
  display: flex;
  gap: 24px;
}

.study-stat {
  display: flex;
  flex-direction: column;
}

.study-stat__value {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-brand-ochre);
}

.study-stat__label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
  margin-top: 2px;
}
```

Remove the now-unused `.study-value` CSS class (was line 293-298).

- [ ] **Step 2: Add i18n keys**

In `frontend/apps/child/src/i18n/locales/zh-CN.ts`, inside `learning.progress` (around line 499):

```typescript
      totalMinutes: '分钟（总计）',
      todayMinutes: '分钟（今日）',
```

In `frontend/apps/child/src/i18n/locales/en-US.ts`:

```typescript
      totalMinutes: 'min (total)',
      todayMinutes: 'min (today)',
```

- [ ] **Step 3: Verify type check passes**

Run: `cd frontend && pnpm --filter child exec vue-tsc --noEmit`
Expected: No type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/child/src/pages/learning/LearningProgressPage.vue \
       frontend/apps/child/src/i18n/locales/zh-CN.ts \
       frontend/apps/child/src/i18n/locales/en-US.ts
git commit -m "feat(learning): use real study minutes from API on progress page (Area E frontend)

- Replace xp_earned proxy with total_study_minutes from backend
- Add today_study_minutes display
- Fetch ChildProgressOverview alongside progress list"
```

---

## Task 4: Frontend — BabyPage → BabyLearningPage navigation (Area D)

**Files:**
- Modify: `frontend/apps/main/src/pages/BabyPage.vue` (add learning cell + data fetch)
- Modify: `frontend/apps/main/src/layouts/MainLayout.vue` (add `'BabyLearning'` to `cachedTabs`)
- Modify: `frontend/apps/main/src/api/learning.ts` (add `TopicGraphResponse` + `getTopicGraph` — deferred from G2, batched here since it's the same API file)
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts` (add `baby.learningTab` key)
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts` (add `baby.learningTab` key)

**Interfaces:**
- Consumes: `getLearningChildren()` from `api/learning.ts` (already exists — returns `ChildLearningOverview[]` with `total_study_minutes`)
- Produces: Learning cell in BabyPage summary card; `'BabyLearning'` in `cachedTabs`

- [ ] **Step 1: Add learning data fetch to BabyPage**

In `frontend/apps/main/src/pages/BabyPage.vue`:

Add import (in the script section):

```typescript
import { getLearningChildren, type ChildLearningOverview } from '@/api/learning'
```

Add reactive state:

```typescript
const learningOverviews = ref<ChildLearningOverview[]>([])
```

Add to `loadData()` — include in the `Promise.all` (around line 1146):

```typescript
    const [balances, stats, wishes, chores, learning] = await Promise.all([
      getAllChildBalances(),
      getChildrenChoreStats(),
      listParentChildWishes(),
      getChildrenChores(today),
      getLearningChildren().catch(() => [] as ChildLearningOverview[]),  // graceful fallback
    ])
    // ... existing assignments ...
    learningOverviews.value = learning
```

Add a computed for the selected child's study minutes:

```typescript
const currentStudyMinutes = computed(() => {
  if (!selectedChildId.value) return 0
  const overview = learningOverviews.value.find(o => o.child_id === selectedChildId.value)
  return overview?.total_study_minutes ?? 0
})
```

- [ ] **Step 2: Add learning cell to BabyPage summary card**

In `BabyPage.vue` template, add the learning cell inside `<van-cell-group inset class="summary-card">`, after the `activeWishes` cell (line 61) and before the `blindBoxGifts` cell (line 62):

```html
          <van-cell
            v-if="selectedChildId"
            :title="t('baby.learningTab')"
            :value="t('learning.studyMinutes', { minutes: currentStudyMinutes })"
            is-link
            @click="$router.push('/baby/learning')"
          />
```

The `v-if="selectedChildId"` hides this cell when the "全部" (All) tab is selected — per spec deferred item F4.

- [ ] **Step 3: Add `'BabyLearning'` to `cachedTabs`**

In `frontend/apps/main/src/layouts/MainLayout.vue`, update the `cachedTabs` array (line 41-48):

```typescript
const cachedTabs = ref<string[]>([
  'Dashboard',
  'FinanceHub',
  'AIHub',
  'Baby',
  'BabyLearning',
  'Family',
  // 'Settings' removed to force remount on navigation (fixes stale data)
])
```

- [ ] **Step 4: Add i18n keys**

In `frontend/apps/main/src/i18n/locales/zh-CN.ts`, inside the `baby` section (around line 1633, after `activeWishes`):

```typescript
    learningTab: '学习管理',
```

In `frontend/apps/main/src/i18n/locales/en-US.ts`, inside the `baby` section:

```typescript
    learningTab: 'Learning',
```

Also check if `learning.studyMinutes` key exists in the main app. If not, add to the `learning` section:

```typescript
    studyMinutes: '{minutes} 分钟',
```

(From my reading, `learning.studyMinutes` already exists at line 1774 of the main zh-CN: `studyMinutes: '{minutes} 分钟'`. Verify en-US has the equivalent.)

- [ ] **Step 5: Verify type check passes**

Run: `cd frontend && pnpm --filter main exec vue-tsc --noEmit`
Expected: No type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/main/src/pages/BabyPage.vue \
       frontend/apps/main/src/layouts/MainLayout.vue \
       frontend/apps/main/src/i18n/locales/zh-CN.ts \
       frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(learning): add BabyPage→BabyLearningPage navigation + KeepAlive (Area D)

- Learning cell in BabyPage summary card (hidden in 'All' tab)
- Shows child's total study minutes from existing API
- Add BabyLearning to cachedTabs for KeepAlive persistence"
```

---

## Task 5: Frontend — Topic prerequisites/dependents display (Area G2)

**Files:**
- Modify: `frontend/apps/child/src/api/learning.ts` (add `TopicGraphResponse` type + `getTopicGraph` function)
- Modify: `frontend/apps/child/src/pages/learning/LearningTopicPage.vue` (add graph section)
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts` (add graph i18n keys)
- Modify: `frontend/apps/child/src/i18n/locales/en-US.ts` (add graph i18n keys)

**Interfaces:**
- Consumes: `GET /learning/topics/{id}/graph` → `TopicGraphResponse` (endpoint already exists at `learning.py:57-62`)
- Produces: Prerequisites and dependents sections on `LearningTopicPage.vue` with Vant status icons

- [ ] **Step 1: Add TypeScript types and API function**

In `frontend/apps/child/src/api/learning.ts`, add after the existing interfaces:

```typescript
export interface TopicGraphResponse {
  topic: TopicResponse
  prerequisites: TopicResponse[]
  dependents: TopicResponse[]
}
```

Add API function:

```typescript
export async function getTopicGraph(topicId: string): Promise<TopicGraphResponse> {
  const res = await http.get(`/learning/topics/${topicId}/graph`)
  return res.data
}
```

- [ ] **Step 2: Add graph data fetch and UI to `LearningTopicPage.vue`**

In `frontend/apps/child/src/pages/learning/LearningTopicPage.vue`:

Add `getTopicGraph` to the import (line 78-87):

```typescript
import {
  getTopicDetail,
  getTopicGraph,
  getMyLearningMap,
  getMyAssignments,
  createSession,
  submitAssignment,
  type TopicResponse,
  type ProgressResponse,
  type AssignmentResponse,
  type TopicGraphResponse,
} from '@/api/learning'
```

Add reactive state (near line 104):

```typescript
const graphData = ref<TopicGraphResponse | null>(null)
```

Add helper functions for status display:

```typescript
function getProgressLevel(topicId: string): string {
  const prog = allProgress.value.find(p => p.topic_id === topicId)
  return prog?.mastery_level ?? 'available'
}

function prereqStatusIconName(topicId: string): string {
  const level = getProgressLevel(topicId)
  if (level === 'mastered') return 'success'
  if (level === 'locked') return 'lock'
  return 'unlock'
}

function prereqStatusTagType(topic: TopicResponse): string {
  const level = getProgressLevel(topic.id)
  if (level === 'mastered') return 'success'
  if (level === 'locked') return 'default'
  return 'primary'
}

function navigateToTopic(topicId: string) {
  router.push(`/learning/topic/${topicId}`)
}
```

Update the `load()` function to also fetch graph data (in the `Promise.all`):

```typescript
async function load() {
  loading.value = true
  error.value = ''
  try {
    const [topicDetail, progressList, graph] = await Promise.all([
      getTopicDetail(topicId.value),
      getMyLearningMap(),
      getTopicGraph(topicId.value).catch(() => null),  // non-critical
    ])
    topic.value = topicDetail
    allProgress.value = progressList
    graphData.value = graph
    // ... existing progress lookup ...
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}
```

Insert in the template after the evidence section (after line 48) and before the action buttons (line 50):

```html
      <!-- Learning path: prerequisites + dependents -->
      <div v-if="graphData?.prerequisites?.length" class="graph-section">
        <h3 class="section-title">{{ t('learning.prerequisites') }}</h3>
        <div class="topic-chips">
          <van-tag
            v-for="prereq in graphData.prerequisites"
            :key="prereq.id"
            :type="prereqStatusTagType(prereq)"
            plain
            size="medium"
            class="topic-chip"
            @click="navigateToTopic(prereq.id)"
          >
            <van-icon
              :name="prereqStatusIconName(prereq.id)"
              size="12"
              :aria-label="t(`learning.status.${getProgressLevel(prereq.id)}`)"
            />
            {{ prereq.name_zh || prereq.name }}
          </van-tag>
        </div>
      </div>

      <div v-if="graphData?.dependents?.length" class="graph-section">
        <h3 class="section-title">{{ t('learning.nextSteps') }}</h3>
        <div class="topic-chips">
          <van-tag
            v-for="dep in graphData.dependents"
            :key="dep.id"
            :type="prereqStatusTagType(dep)"
            plain
            size="medium"
            class="topic-chip"
            @click="navigateToTopic(dep.id)"
          >
            <van-icon
              :name="prereqStatusIconName(dep.id)"
              size="12"
              :aria-label="t(`learning.status.${getProgressLevel(dep.id)}`)"
            />
            {{ dep.name_zh || dep.name }}
          </van-tag>
        </div>
      </div>
```

Add CSS for the graph sections:

```css
/* Graph section */
.graph-section {
  margin-bottom: 16px;
}

.topic-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-chip {
  cursor: pointer;
  padding: 6px 12px;
}

.topic-chip:active {
  opacity: 0.7;
}
```

- [ ] **Step 3: Add i18n keys**

In `frontend/apps/child/src/i18n/locales/zh-CN.ts`, inside the `learning` section:

```typescript
    prerequisites: '前置知识',
    nextSteps: '后续学习',
```

In `frontend/apps/child/src/i18n/locales/en-US.ts`:

```typescript
    prerequisites: 'Prerequisites',
    nextSteps: 'Next Steps',
```

- [ ] **Step 4: Verify type check passes**

Run: `cd frontend && pnpm --filter child exec vue-tsc --noEmit`
Expected: No type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/child/src/api/learning.ts \
       frontend/apps/child/src/pages/learning/LearningTopicPage.vue \
       frontend/apps/child/src/i18n/locales/zh-CN.ts \
       frontend/apps/child/src/i18n/locales/en-US.ts
git commit -m "feat(learning): show topic prerequisites/dependents on topic page (Area G2)

- Fetch from existing GET /learning/topics/{id}/graph endpoint
- Status icons via Vant (success/lock/unlock) with i18n aria-labels
- Graceful: graph section hidden on fetch failure
- Click navigates to prerequisite/dependent topic"
```

---

## Task 6: Final verification + branch review

- [ ] **Step 1: Run all backend learning tests**

```bash
cd server && uv run pytest tests/backend/test_learning_*.py tests/backend/integration/test_learning_*.py -v
```

Expected: All tests pass.

- [ ] **Step 2: Run frontend type check for both apps**

```bash
cd frontend && pnpm --filter child exec vue-tsc --noEmit
cd frontend && pnpm --filter main exec vue-tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 3: Run backend lint**

```bash
cd server && uv run ruff check apps/backend/app/services/learning/ apps/backend/app/schemas/learning.py apps/backend/app/routers/learning_child.py
```

Expected: No errors.

- [ ] **Step 4: Manual E2E verification checklist**

| Check | Expected |
|-------|----------|
| ChildHomePage shows TodayLearningCard | Card visible with correct priority state |
| TodayLearningCard → click navigates | Navigates to correct topic or /learning |
| TodayLearningCard footer | Shows real study_minutes_today |
| LearningProgressPage study time | Shows real minutes, not xp_earned |
| BabyPage learning cell | Visible when child selected, hidden in "All" tab |
| BabyPage learning cell → click | Navigates to /baby/learning |
| BabyLearning KeepAlive | Navigate away → return → page state preserved |
| LearningTopicPage graph | Prerequisites/dependents shown when they exist |
| LearningTopicPage graph icons | Vant icons render (success/unlock/lock) |
| LearningTopicPage graph → click tag | Navigates to the topic |

- [ ] **Step 5: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "fix(learning): final cleanup from deferred items implementation"
```
