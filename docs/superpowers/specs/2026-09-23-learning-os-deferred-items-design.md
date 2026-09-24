---
date: 2026-09-23
module: learning
problem_type: feature-completion
tags: [learning, ux, frontend, backend, deferred-items]
applies_when: Implementing remaining learning OS features after DeerFlow SSE integration
---

# Learning OS Deferred Items Design

Companion spec to [`2026-09-22-learning-os-design.md`](./2026-09-22-learning-os-design.md) (full Learning OS design). Covers deferred items from the code review ([`2026-09-23-learning-os-code-review.md`](../reviews/2026-09-23-learning-os-code-review.md)) that were not part of the DeerFlow SSE integration.

> **Review note (2026-09-23):** This spec has been reviewed. Findings are annotated inline as `[Review: Sx/Px]` and summarized in the [Review Findings](#review-findings) section at the bottom.

## Scope

Five work items, ordered by priority:

| ID | Item | Review Ref | Type | Status |
|----|------|-----------|------|--------|
| A | ChildHomePage "今日学习" card | OQ-4 | New API + UI component | ✅ Done |
| D | BabyPage → BabyLearningPage navigation | OQ-15, OQ-16 | UI + KeepAlive | Partial — see §D |
| E | Study duration aggregation (child progress) | Duration hardcoded 0 | API extension | Partial — see §E |
| G1 | Global endpoints auth documentation | OQ-13 | Doc comment | ✅ Done |
| G2 | Topic prerequisites/dependents display | OQ-17 | UI enhancement | ✅ Done |

Items explicitly excluded (deferred to Phase 2 or accepted as-is):
- OQ-2: Translation service placeholder (seed data works without it)
- OQ-3: `learning_streak_3_failures` notification (needs product definition)
- OQ-6: Seed quality validation (pre-production task)
- OQ-7: Badge count 27 vs 30 (keep 30, spec update only)
- OQ-10/11: Duplicated TS interfaces and composables (extract on drift)
- OQ-12: Hardcoded Chinese in notification dispatchers (matches existing pattern)
- OQ-14: Error code inconsistency (low-priority cleanup)

## A: ChildHomePage "Today Learning" Card

> **Companion spec context:** See [`2026-09-22-learning-os-design.md`](./2026-09-22-learning-os-design.md) §ChildHomePage for the page layout. This card inserts after the existing `ProgressRing` section.

### Problem
ChildHomePage has no learning section. Children must navigate to `/learning` to see their learning status, missing the daily engagement prompt.

### Current State
**Nothing exists yet.** `ChildHomePage.vue` has sections for chores, challenges, literacy, badges, manifesto, wishes, and calendar — but no learning entry point. No `TodayLearningCard` component, no `/today` endpoint, no `TodayLearningResponse` schema.

### Backend: `GET /child/learning/today`

New endpoint in `learning_child.py` router, protected by `get_current_child_user`.

**Response schema — `TodayLearningResponse`:**

```python
class TodayLearningResponse(SnowflakeBase):   # [Review: S3] inherit SnowflakeBase for ID serialization
    current_topic: TopicResponse | None      # mastery_level == "learning", first by updated_at DESC
    pending_assignment: AssignmentResponse | None  # status == "pending", first by created_at ASC
    recommended_topic: TopicResponse | None  # prereqs met, not started, first by sort_order ASC
    study_minutes_today: int                 # today's session duration sum (0 when no sessions)
```

> **[Review: S3]** `TopicResponse` and `AssignmentResponse` contain snowflake IDs. They already inherit `SnowflakeBase`. `TodayLearningResponse` itself should also inherit `SnowflakeBase` per repo convention — even though it has no top-level `id` field today, this ensures consistency if fields are added later.

**Logic:**

1. Query `LearningProgress` where `child_id == child.id`:  ← **[Review: S4]** standardized to `child` across all sections
   - `current_topic`: first progress with `mastery_level == "learning"`, **ORDER BY `updated_at DESC`** → fetch its topic  ← **[Review: P3]** deterministic ordering
   - `recommended_topic`: first progress with `mastery_level == "locked"` and all hard prereqs met, **ORDER BY `sort_order ASC`** → fetch its topic  ← **[Review: P3]**
2. Query `LearningAssignment` where `child_id == child.id` and `status == "pending"`, **ORDER BY `created_at ASC`** → first match, fetch its topic  ← **[Review: P3]**
3. Aggregate `LearningSession.duration_seconds` where `child_id` matches and `ended_at >= today_start` → `func.sum(...) or 0`, convert to minutes  ← **[Review: P5]** explicit `or 0` for empty-set null → 0

**Priority order for card display:** pending_assignment > current_topic > recommended_topic

### Frontend: `TodayLearningCard` component

Insert after `ProgressRing` in `ChildHomePage.vue`.

**Display logic:**
- If `pending_assignment` exists → "📝 提交作业: {topic_name}" + navigate to `/learning/topic/{topic_id}`
- Else if `current_topic` exists → "📖 继续学习: {topic_name}" + navigate to `/learning/topic/{topic_id}`
- Else if `recommended_topic` exists → "🌟 开始新知识: {topic_name}" + navigate to `/learning/topic/{topic_id}`
- Else → "📚 去学习地图探索" + navigate to `/learning`
- Footer: "今日已学习 {study_minutes_today} 分钟"

**Styling:** Match existing card style on ChildHomePage (rounded, colored background). Use i18n keys for all strings.

## D: BabyPage → BabyLearningPage Navigation

### Problem
`/baby/learning` route exists with a full page (`BabyLearningPage.vue`), but there's no way to reach it from `BabyPage.vue`.

### Current State
**[Review: P2]** Partial implementation already exists:
- ✅ `BabyLearningPage.vue` exists with correct `defineOptions({ name: 'BabyLearning' })` (line 135)
- ✅ Route registered in `router/index.ts:457-459` (`path: 'baby/learning'`, `name: 'BabyLearning'`)
- ❌ `BabyPage.vue` has no learning cell/link — user cannot navigate to BabyLearningPage
- ❌ `'BabyLearning'` not in `cachedTabs` array in `MainLayout.vue:41-48` (currently: `'Dashboard', 'FinanceHub', 'AIHub', 'Baby', 'Family'`)

### Solution

**BabyPage.vue — Add learning cell to summary section:**

Add a cell alongside Balance, Weekly Chores, Active Wishes, etc.:
- Icon: `book-o` (Vant)
- Label: i18n key `baby.learningTab` (zh: "学习管理", en: "Learning")
- Value: child's total study minutes (from `GET /family/learning/children` which already returns `total_study_minutes`)
- Click handler: `router.push('/baby/learning')`

**MainLayout.vue — KeepAlive:**

Add `'BabyLearning'` to the `cachedTabs` array so the page persists across navigation.

> **[Review: P2]** Verify: `BabyLearningPage.vue` already has `defineOptions({ name: 'BabyLearning' })` at line 135 — the KeepAlive `include` string match will work. Deferred item F5 can be resolved: no action needed.

## E: Study Duration Aggregation (Child Progress)

### Problem
`GET /child/learning/progress` returns only mastery-level counts. The child has no visibility into how much time they've spent studying.

### Current State
**[Review: P2]** Partial implementation already exists:
- ✅ Parent-facing `ChildLearningOverview` schema (`schemas/learning.py:149`) already has `total_study_minutes: int`
- ✅ `GET /family/learning/children` already returns `total_study_minutes` per child (used by BabyPage)
- ❌ Child-facing `ChildProgressOverview` schema (`schemas/learning.py:175`) does NOT have `total_study_minutes` or `today_study_minutes`
- ⚠️ `LearningProgressPage.vue:128-131` uses `xp_earned` as a **proxy** for study minutes, with explicit comment: `// Sum xp_earned as a proxy for study time (until backend provides study_minutes)`

> **[Review: P2]** Implementer must: (1) add the two fields to `ChildProgressOverview`, (2) update the router to aggregate from `LearningSession`, (3) update `LearningProgressPage.vue` to use the real values and remove the `xp_earned` proxy workaround.

### Solution

**Schema extension — `ChildProgressOverview`:**

Add two fields:
```python
total_study_minutes: int = 0
today_study_minutes: int = 0
```

**Service layer — `progress_service.py`:** ← **[Review: S1]** aggregation belongs in service, not router

```python
from sqlalchemy import func
from server.packages.db.models.learning.session import LearningSession
from server.packages.core.utils import ensure_utc  # [Review: S2] use repo UTC utility

def aggregate_study_minutes(db: Session, child_id: int) -> dict[str, int]:
    """Return total and today study minutes for a child."""
    # Total study minutes
    total_seconds = db.query(func.sum(LearningSession.duration_seconds)).filter(
        LearningSession.child_id == child_id,
        LearningSession.ended_at.isnot(None),
    ).scalar() or 0  # func.sum() returns None for empty set

    # Today's study minutes
    today_start = ensure_utc(datetime.now(timezone.utc)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_seconds = db.query(func.sum(LearningSession.duration_seconds)).filter(
        LearningSession.child_id == child_id,
        LearningSession.ended_at >= today_start,
        LearningSession.ended_at.isnot(None),
    ).scalar() or 0

    return {
        "total_study_minutes": total_seconds // 60,
        "today_study_minutes": today_seconds // 60,
    }
```

**Router — `GET /child/learning/progress`:**

```python
# In the router, call the service function:
study_minutes = progress_service.aggregate_study_minutes(db, child.id)
return ChildProgressOverview(
    mastered_count=..., learning_count=..., ...,
    **study_minutes,
)
```

**Frontend — `LearningProgressPage.vue`:**

Display both values in a stat row (similar to mastered_count etc.), with i18n labels.

## G1: Global Endpoints Auth Documentation

### ~~Problem~~
> **[Review: P1]** ✅ **Already resolved.** `server/apps/backend/app/routers/learning.py` line 1 already contains:
> ```python
> """Global learning knowledge graph endpoints (no auth required)."""
> ```
> This matches the proposed solution exactly. No action needed. Removed from implementation scope.

### Solution (already applied)

Module-level docstring in `learning.py`:

```python
"""Global learning knowledge graph endpoints (no auth required)."""
```

## G2: Topic Prerequisites/Dependents Display

### Problem
`LearningTopicPage` doesn't show which topics are prerequisites or dependents, making the learning graph opaque.

### Current State
**[Review: P2]** Backend fully exists, frontend entirely missing:
- ✅ `GET /learning/topics/{id}/graph` endpoint exists (`learning.py:57-62`)
- ✅ `TopicGraphResponse` schema exists (`schemas/learning.py:37-41`) with `topic`, `prerequisites`, `dependents`
- ❌ `LearningTopicPage.vue` does NOT display prerequisites or dependents — no graph data fetch, no UI sections
- ❌ Frontend has zero integration with the graph endpoint today

### Solution

**Use existing `GET /learning/topics/{id}/graph` endpoint** which already returns `TopicGraphResponse` with `prerequisites` and `dependents` lists.

**Frontend — `LearningTopicPage.vue`:**

After the topic description section, add a "学习路径" section:

```html
<!-- Prerequisites -->
<div v-if="graphData?.prerequisites?.length" class="section">
  <h4>{{ $t('learning.prerequisites') }}</h4>
  <div class="topic-chips">
    <van-tag v-for="prereq in graphData.prerequisites" :key="prereq.id"
             :type="prereqStatusTag(prereq)" plain size="medium"
             @click="navigateToTopic(prereq.id)">
      {{ prereqStatusIcon(prereq) }} {{ prereq.name }}
    </van-tag>
  </div>
</div>

<!-- Dependents -->
<div v-if="graphData?.dependents?.length" class="section">
  <h4>{{ $t('learning.nextSteps') }}</h4>
  <!-- same pattern -->
</div>
```

**Status icons:** ← **[Review: S5]** use Vant icons instead of raw emoji for consistent rendering + a11y

| Status | Vant Icon | i18n aria-label |
|--------|-----------|-----------------|
| mastered | `<van-icon name="success" />` | `t('learning.status.mastered')` |
| learning / available | `<van-icon name="unlock" />` | `t('learning.status.learning')` |
| locked (prereqs not met) | `<van-icon name="lock" />` | `t('learning.status.locked')` |

**Data loading:** Fetch graph data in the existing `load()` function alongside topic detail. The API already exists, just needs to be called.

## Testing Strategy

<!-- [Review: P4] Expanded from original 2-line version -->

### Backend (pytest)

| Area | Test | Key assertions |
|------|------|----------------|
| A | `test_today_endpoint_all_branches` | 4 response branches: (1) pending_assignment only, (2) current_topic only, (3) recommended_topic only, (4) empty → fallback card. Verify `study_minutes_today == 0` when no sessions. |
| A | `test_today_study_minutes_aggregation` | Multiple sessions on same day → correct sum in minutes. Sessions with `ended_at == None` excluded. |
| A | `test_today_deterministic_ordering` | Multiple topics in `"learning"` state → `current_topic` returns most recently updated, not random. |
| E | `test_progress_schema_extension` | `ChildProgressOverview` returns `total_study_minutes` and `today_study_minutes`. Edge case: child with zero sessions → both fields are `0`, not `null`. |
| E | `test_progress_study_minutes_utc_boundary` | Sessions ending before/after UTC midnight → correct bucketing. |
| G2 | `test_graph_endpoint_returns_prereqs_dependents` | Verify `TopicGraphResponse` returns correct lists for a topic with known dependencies. |

### Frontend (manual verification + component checks)

| Area | Check | Expected |
|------|-------|----------|
| A | TodayLearningCard display states | All 4 priority branches render correctly with i18n strings. Footer shows real `study_minutes_today`. |
| D | BabyPage → BabyLearningPage navigation | Learning cell visible, click navigates to `/baby/learning`. Back button returns to BabyPage. |
| D | KeepAlive caching | Navigate to BabyLearning → switch tab → return. Page state preserved (no re-fetch). |
| E | LearningProgressPage real study minutes | Displays actual minutes from backend, NOT `xp_earned` proxy. Verify proxy code removed. |
| G2 | Prerequisites/dependents sections | Sections appear when graph data has entries. Hidden when empty. Status icons (Vant) render correctly. Click navigates to topic. |
| G2 | Graph loading/error states | Skeleton while fetching. Error toast on failure. |

## Deferred to Planning

Items flagged in doc review (2026-09-23) to be resolved during implementation planning:

- **F2 [P1] TodayLearningCard loading state** — specify skeleton/shimmer pattern consistent with ChildHomePageSkeleton
- **F3 [P1] TodayLearningCard error state** — specify behavior on API failure (hide card vs. static fallback with retry)
- **F4 [P1] BabyPage learning cell: "All" tab behavior** — define behavior when `selectedChildId === null` (hide cell, show aggregate, or placeholder)
- ~~**F5 [P2] KeepAlive component name**~~ — **[Review: P2] Resolved during spec review**: `BabyLearningPage.vue` already has `defineOptions({ name: 'BabyLearning' })` at line 135. No action needed.
- **FYI: TodayLearningCard else-branch** — visual treatment for no-activity state
- **FYI: BabyPage cell position** — insertion order in summary card
- **FYI: UTC midnight timezone** — "today" boundary may misalign with child's local day
- ~~**FYI: G2 emoji icons**~~ — **[Review: S5] Resolved during spec review**: replaced with Vant icons + i18n aria-labels (see §G2 status icons table)
- **FYI: G2 graph section states** — loading/error handling for graph data fetch
- ~~**FYI: Variable name drift**~~ — **[Review: S4] Resolved during spec review**: standardized to `child` across all sections

---

## Review Findings

> **Review date:** 2026-09-23
> **Reviewed against:** codebase state on `feat/learning-tutor-deerflow-sse` branch
> **Standards sources:** root `CLAUDE.md`, `server/apps/backend/CLAUDE.md`, `frontend/apps/child/CLAUDE.md`, `docs/CODING_STANDARDS.md`

### Standards Findings

| ID | Severity | Section | Finding | Resolution |
|----|----------|---------|---------|------------|
| S1 | Judgement | E | Code sample had inline `db.query()` in router — violates service layer convention | Moved aggregation to `progress_service.aggregate_study_minutes()`, router calls service |
| S2 | Judgement | E | Used `datetime.now(timezone.utc)` instead of repo's `ensure_utc()` utility | Updated to use `ensure_utc()` from `packages.core.utils` |
| S3 | Hard | A | `TodayLearningResponse` didn't specify `SnowflakeBase` inheritance | Changed base class to `SnowflakeBase`, added explanatory note |
| S4 | Judgement | A/E | Variable name drift: `current_child` (A) vs `child` (E) | Standardized to `child` across all sections |
| S5 | Judgement | G2 | Raw emoji (✅🔓🔒) as status indicators — fragile rendering, poor a11y | Replaced with Vant icons (`success`/`unlock`/`lock`) + i18n aria-labels |
| S6 | — | All | i18n, Vant patterns, KeepAlive naming correctly referenced | ✅ No issue found |

### Spec Findings

| ID | Severity | Section | Finding | Resolution |
|----|----------|---------|---------|------------|
| P1 | Critical | G1 | G1 already implemented — `learning.py` has the docstring | Marked ✅ done in scope table, section preserved as historical record |
| P2 | Major | D, E, G2 | Spec presented greenfield items that partially exist in codebase | Added "Current State" subsections to each area documenting what exists vs. what's missing |
| P3 | Medium | A | "First match" without ORDER BY is non-deterministic | Added explicit ordering: `updated_at DESC` (current), `created_at ASC` (assignment), `sort_order ASC` (recommended) |
| P4 | Medium | Testing | Testing strategy was 2 lines, missing coverage for D, E, G2 | Expanded to full backend + frontend test matrices |
| P5 | Low | A | `study_minutes_today` zero behavior unspecified | Added explicit `or 0` pattern + note about `func.sum()` returning `None` for empty sets |
| P6 | — | Deferred | Deferred items well-tracked | ✅ No issue found |
| P7 | Low | Header | Companion spec cross-reference lacked links | Added markdown links to companion spec and code review doc |
