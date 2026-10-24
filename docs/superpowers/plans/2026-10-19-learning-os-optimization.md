# Learning OS Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Learning OS from "parent manually drives everything" to "system recommends + AI auto-assesses + parent asynchronously supervises."

**Architecture:** Extend existing `zone_service.py` with breakpoint detection and curriculum gap scoring; add a recommendation API that merges three dimensions (breakpoints, standards, review) into a ranked path. Implement AI dual-track review (auto-pass on score ≥ 0.8, parent override, consecutive-override circuit breaker). Create preset curriculum paths from `curriculum_standards_json`. Restructure `BabyLearningPage` into a modular hub with collapsible sections. Add DNA knowledge graph (2D SVG first, 3D WebGL optional). Update child app with source tags, review-due priority, and rejection feedback.

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy 2.0 / Alembic (backend); Vue 3 + Vant 4 + Pinia + TypeScript (frontend); SVG for 2D graph; WebGL TBD for 3D.

**Spec:** `docs/superpowers/specs/2026-10-18-learning-os-optimization-design.md`

## Global Constraints

- **Mobile-first:** All pages must be fully usable at 375×812 viewport.
- **AI-optional:** When AI is not enabled, all features degrade to pure parent-operation mode — no errors, no blocking.
- **Existing data compatible:** Reuse `os-taxonomy` / `os-taxonomy-beijing` `curriculum_standards_json` mappings. Do not create new data sets.
- **Incremental migration:** Refactor `LearningAssignPage` / `BabyLearningPage` / `ChildLearningMapPage` progressively — no big-bang replacement.
- **URL style:** Router root-path decorators use `""` not `"/"`. `redirect_slashes=False`.
- **Snowflake IDs:** All response schemas with IDs inherit `SnowflakeBase`. Define `id: int`, serializer converts to `str`.
- **No trailing slashes** on API endpoints. Frontend calls must also omit trailing slashes.
- **i18n:** All user-facing strings via `t('key')` in frontend. Backend errors use `AppError` + `ErrorCode`.

## Review Focus

1. **Recommendation correctness with mixed signals** — A topic flagged as both "breakpoint" AND "curriculum required" must merge labels and sort by the higher-priority dimension (breakpoint). Test: create a topic that is both an unmet hard prerequisite AND age-appropriate, verify it gets both labels and sorts as breakpoint.
2. **Auto-pass threshold safety** — `score ≥ 0.8` auto-pass could let low-quality evaluations through. Test: verify `score = 0.79` triggers `parent_review`, `score = 0.8` triggers auto-pass, `score = None` triggers `parent_review`.
3. **Consecutive override circuit breaker** — 5 consecutive parent overrides must pause AI auto-pass. Test: simulate 5 overrides, verify `ai_auto_pass_paused` flag; verify 6th evaluation goes to `parent_review`.
4. **Child selection state across navigation** — `useBabyStore.selectedChildId` set in BabyPage must survive navigation to BabyLearningPage. Test: programmatically set store, navigate, verify BabyLearningPage reads the correct child.
5. **WebGL graceful degradation** — On devices without WebGL, DNA graph must fall back to 2D without errors. Test: mock `WebGLRenderingContext` as unavailable, verify 2D SVG graph renders.

---

## File Structure

### Backend — New files

| File | Responsibility |
|------|---------------|
| `server/apps/backend/app/services/learning/recommendation_service.py` | Composite recommendation logic (merge breakpoints + curriculum + review into ranked path) |
| `server/apps/backend/app/services/learning/preset_path_service.py` | Generate and manage preset curriculum paths from `curriculum_standards_json` |
| `server/apps/backend/app/routers/learning_preset.py` | Preset path list + assign endpoints |
| `server/packages/db/models/learning/preset_path.py` | `PresetLearningPath` SQLAlchemy model |
| `server/tests/backend/services/learning/test_recommendation_service.py` | Tests for breakpoint, curriculum, review detection + composite ranking |
| `server/tests/backend/services/learning/test_review_dual_track.py` | Tests for auto-pass, override, circuit breaker |
| `server/tests/backend/services/learning/test_preset_path_service.py` | Tests for preset path generation + assignment |

### Backend — Modified files

| File | Changes |
|------|---------|
| `server/apps/backend/app/services/learning/zone_service.py` | Add `find_breakpoint_topics()`, `find_curriculum_gap_topics()`, `find_review_due_topics()` |
| `server/apps/backend/app/services/learning/progress_service.py` | Add `check_auto_pass()`, `override_review()`, consecutive-override counter |
| `server/apps/backend/app/services/learning/session_service.py` | Integrate auto-pass into `end_session()` |
| `server/apps/backend/app/routers/learning_family.py` | Add recommendation endpoint + preset path endpoints |
| `server/apps/backend/app/routers/learning_child.py` | Add `review_due` priority to `/today` endpoint |
| `server/apps/backend/app/schemas/learning.py` | Add `RecommendationResponse`, `PresetPathResponse`, `ReviewOverrideRequest` schemas |
| `server/apps/backend/app/main.py` | Register `learning_preset` router |

### Frontend main (parent) — New files

| File | Responsibility |
|------|---------------|
| `frontend/apps/main/src/stores/baby.ts` | `useBabyStore` Pinia store: `selectedChildId`, `selectedChildName`, `activePathId` |
| `frontend/apps/main/src/pages/baby/learning/PresetPathsPage.vue` | Preset curriculum path library (filter by grade/subject) |
| `frontend/apps/main/src/pages/baby/learning/RecommendationsPage.vue` | Smart recommendation detail (drag-sort, remove, replace, confirm) |
| `frontend/apps/main/src/composables/useLearningDnaGraph.ts` | DNA graph data processing + layout composable |
| `frontend/apps/main/src/components/learning/DnaGraph2D.vue` | 2D SVG knowledge graph (spiral layout, mastery colors) |

### Frontend main (parent) — Modified files

| File | Changes |
|------|---------|
| `frontend/apps/main/src/pages/baby/BabyPage.vue` | Create `useBabyStore`, lift child selection into it; boost learning entry cell visual weight |
| `frontend/apps/main/src/pages/baby/learning/BabyLearningPage.vue` | Restructure as modular hub with collapsible sections; add recommendation + preset-paths + review modules |
| `frontend/apps/main/src/pages/baby/learning/ChildLearningMapPage.vue` | Embed 2D DNA graph preview + full-screen mode |
| `frontend/apps/main/src/api/learning.ts` | Add `getRecommendations()`, `getPresetPaths()`, `assignPresetPath()`, `overrideReview()` |
| `frontend/apps/main/src/router/index.ts` | Add routes for PresetPathsPage + RecommendationsPage; remove LearningAssignPage + LearningReviewsPage + LearningPathsPage routes |

### Frontend main (parent) — Deleted files

| File | Reason |
|------|--------|
| `frontend/apps/main/src/pages/baby/learning/LearningAssignPage.vue` | Functionality split to RecommendationsPage / PresetPathsPage / DNA graph |
| `frontend/apps/main/src/pages/baby/learning/LearningReviewsPage.vue` | Merged into BabyLearningPage |
| `frontend/apps/main/src/pages/baby/learning/LearningPathsPage.vue` | Merged into BabyLearningPage |

### Frontend child — Modified files

| File | Changes |
|------|---------|
| `frontend/apps/child/src/components/TodayLearningCard.vue` | Add `review_due` priority + source tag + rejection feedback |
| `frontend/apps/child/src/pages/learning/LearningMapPage.vue` | Add source tags + review-due pulse markers + rejection markers |
| `frontend/apps/child/src/api/learning.ts` | No changes needed (recommendation API is parent-side only) |

### Alembic migration

New migration: add `preset_learning_paths` table.

---

## Task 1: Recommendation Engine — Zone Service Extensions

**Files:**
- Modify: `server/apps/backend/app/services/learning/zone_service.py`
- Create: `server/apps/backend/app/services/learning/recommendation_service.py`
- Create: `server/tests/backend/services/learning/test_recommendation_service.py`

**Interfaces:**
- Consumes: `LearningProgress` (child_id, topic_id, mastery_level, next_review_at), `LearningTopic` (centrality, age_group, curriculum_standards_json, source_taxonomy), `LearningDependency` (topic_id, prerequisite_id, strength)
- Produces: `find_breakpoint_topics(db, child_id) -> list[BreakpointTopic]`, `find_curriculum_gap_topics(db, child_id) -> list[CurriculumGapTopic]`, `find_review_due_topics(db, child_id) -> list[ReviewDueTopic]`, `generate_recommendation_path(db, child_id) -> RecommendationPath`

- [ ] **Step 1: Write tests for `find_breakpoint_topics`**

```python
# tests/backend/services/learning/test_recommendation_service.py
class TestFindBreakpointTopics:
    def test_returns_hard_prereqs_not_mastered(self, db, child_user, topic_graph):
        """Child mastered A, A --hard--> B (not mastered) => B is breakpoint."""
        from apps.backend.app.services.learning.zone_service import find_breakpoint_topics
        result = find_breakpoint_topics(db, child_user["id"])
        assert len(result) == 1
        assert result[0].topic_id == topic_graph["b_id"]
        assert "知识断点" in result[0].reasons

    def test_excludes_soft_dependency_gaps(self, db, child_user, soft_dep_graph):
        """Soft dependency gaps are NOT breakpoints."""
        result = find_breakpoint_topics(db, child_user["id"])
        assert len(result) == 0

    def test_excludes_already_mastered_prereqs(self, db, child_user, mastered_graph):
        """If child already mastered the dependent topic, no breakpoint."""
        result = find_breakpoint_topics(db, child_user["id"])
        assert len(result) == 0

    def test_empty_when_no_progress(self, db, child_user, topic_graph):
        """No mastered topics => no breakpoints to find."""
        # child has no progress at all
        result = find_breakpoint_topics(db, child_user["id"])
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/services/learning/test_recommendation_service.py::TestFindBreakpointTopics -v`
Expected: FAIL — `find_breakpoint_topics` not defined.

- [ ] **Step 3: Implement `find_breakpoint_topics` in `zone_service.py`**

```python
@dataclass
class BreakpointTopic:
    topic_id: int
    topic_name: str
    reasons: list[str]  # always includes "知识断点"
    centrality: float
    blocking_topic_id: int  # the mastered topic whose hard dep points here

def find_breakpoint_topics(db: Session, child_id: int) -> list[BreakpointTopic]:
    """Find topics that are hard prerequisites of mastered topics but not yet mastered."""
```

Algorithm:
1. Query all `LearningProgress` for child where `mastery_level = "mastered"`, collect `topic_ids`.
2. Query all `LearningDependency` where `prerequisite_id IN mastered_ids` AND `strength = "hard"`.
3. Collect dependent `topic_ids` from those edges.
4. Query child's progress for those dependent topic_ids — exclude any already `mastered`.
5. For each remaining topic, build `BreakpointTopic` with `reasons=["知识断点"]`.
6. Sort by `centrality` descending.

- [ ] **Step 4: Write tests for `find_curriculum_gap_topics`**

```python
class TestFindCurriculumGapTopics:
    def test_returns_age_appropriate_unmastered(self, db, child_user, age_topic):
        """Topic matching child's age_group with curriculum_standards, not mastered => gap."""
        result = find_curriculum_gap_topics(db, child_user["id"])
        assert len(result) >= 1
        assert "课标必会" in result[0].reasons

    def test_excludes_mastered_topics(self, db, child_user, mastered_age_topic):
        """Already-mastered topics are excluded even if curriculum-matching."""
        result = find_curriculum_gap_topics(db, child_user["id"])
        assert all(t.topic_id != mastered_age_topic["id"] for t in result)

    def test_sorted_by_centrality(self, db, child_user, multi_curriculum_topics):
        """Higher centrality topics come first."""
        result = find_curriculum_gap_topics(db, child_user["id"])
        centrality_values = [t.centrality for t in result]
        assert centrality_values == sorted(centrality_values, reverse=True)
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/services/learning/test_recommendation_service.py::TestFindCurriculumGapTopics -v`
Expected: FAIL — `find_curriculum_gap_topics` not defined.

- [ ] **Step 6: Implement `find_curriculum_gap_topics` in `zone_service.py`**

```python
@dataclass
class CurriculumGapTopic:
    topic_id: int
    topic_name: str
    reasons: list[str]  # always includes "课标必会"
    centrality: float

def find_curriculum_gap_topics(db: Session, child_id: int) -> list[CurriculumGapTopic]:
    """Find age-appropriate curriculum topics the child hasn't mastered, sorted by centrality."""
```

Algorithm:
1. Get child's `age_group` via `get_child_age_group()`.
2. Query `LearningTopic` where `age_group = child_age_group` AND `curriculum_standards_json != '[]'` AND `deprecated = False`.
3. Get child's mastered topic_ids.
4. Filter out mastered topics.
5. Sort by `centrality` descending.
6. Return as `CurriculumGapTopic` with `reasons=["课标必会"]`.

- [ ] **Step 7: Write tests for `find_review_due_topics`**

```python
class TestFindReviewDueTopics:
    def test_returns_mastered_past_review_date(self, db, child_user, review_due_progress):
        """Mastered topic with next_review_at <= now => review due."""
        result = find_review_due_topics(db, child_user["id"])
        assert len(result) == 1
        assert "需要复习" in result[0].reasons

    def test_excludes_future_review(self, db, child_user, future_review_progress):
        """Mastered topic with next_review_at > now => not due."""
        result = find_review_due_topics(db, child_user["id"])
        assert len(result) == 0
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/services/learning/test_recommendation_service.py::TestFindReviewDueTopics -v`
Expected: FAIL — `find_review_due_topics` not defined.

- [ ] **Step 9: Implement `find_review_due_topics` in `zone_service.py`**

```python
@dataclass
class ReviewDueTopic:
    topic_id: int
    topic_name: str
    reasons: list[str]  # always includes "需要复习"
    centrality: float
    next_review_at: datetime

def find_review_due_topics(db: Session, child_id: int) -> list[ReviewDueTopic]:
    """Find mastered topics whose SM-2 next_review_at <= now."""
```

Query: `LearningProgress` where `child_id = child_id` AND `mastery_level = "mastered"` AND `next_review_at <= utcnow()`. Join `LearningTopic` for name/centrality.

- [ ] **Step 10: Write tests for `generate_recommendation_path`**

```python
class TestGenerateRecommendationPath:
    def test_breakpoint_sorted_first(self, db, child_user, mixed_graph):
        """Breakpoints appear before curriculum gaps in the merged path."""
        path = generate_recommendation_path(db, child_user["id"])
        reasons = [t.reasons for t in path.topics]
        first_bp = next(i for i, r in enumerate(reasons) if "知识断点" in r)
        first_gap = next((i for i, r in enumerate(reasons) if r == ["课标必会"]), len(reasons))
        assert first_bp < first_gap

    def test_merges_labels_for_same_topic(self, db, child_user, overlap_graph):
        """Topic that is both breakpoint AND curriculum gap gets both labels."""
        path = generate_recommendation_path(db, child_user["id"])
        overlap = [t for t in path.topics if len(t.reasons) > 1]
        assert len(overlap) >= 1
        assert "知识断点" in overlap[0].reasons
        assert "课标必会" in overlap[0].reasons

    def test_empty_for_child_with_no_data(self, db, child_user):
        """Child with no progress and no topics => empty path."""
        path = generate_recommendation_path(db, child_user["id"])
        assert path.topics == []
        assert path.total_count == 0

    def test_prerequisites_met_flag(self, db, child_user, prereq_graph):
        """Topics whose all hard prereqs are mastered have prerequisites_met=True."""
        path = generate_recommendation_path(db, child_user["id"])
        for topic in path.topics:
            if topic.reasons == ["课标必会"]:  # non-breakpoint
                # check: its hard prereqs should be mastered for this flag to be true
                pass  # exact assertion depends on fixture setup
```

- [ ] **Step 11: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/services/learning/test_recommendation_service.py::TestGenerateRecommendationPath -v`
Expected: FAIL — `generate_recommendation_path` not defined.

- [ ] **Step 12: Implement `generate_recommendation_path` in `recommendation_service.py`**

Create new file `server/apps/backend/app/services/learning/recommendation_service.py`.

```python
@dataclass
class RecommendationTopic:
    topic_id: int
    topic_name: str
    reasons: list[str]
    centrality: float
    prerequisites_met: bool
    suggested_position: int

@dataclass
class RecommendationPath:
    name: str
    topics: list[RecommendationTopic]
    total_count: int

PRIORITY_ORDER = {"知识断点": 0, "课标必会": 1, "高基础度": 2, "需要复习": 3}

def generate_recommendation_path(db: Session, child_id: int) -> RecommendationPath:
    """Merge breakpoint + curriculum + review topics into ranked path."""
```

Algorithm:
1. Call `find_breakpoint_topics()`, `find_curriculum_gap_topics()`, `find_review_due_topics()`.
2. Build a dict keyed by `topic_id`. For each topic, merge `reasons` lists.
3. For topics in both breakpoint and curriculum lists: merge labels → `["知识断点", "课标必会"]`.
4. Sort by: primary key = highest-priority reason (using `PRIORITY_ORDER`), secondary = `centrality` desc.
5. For each topic, compute `prerequisites_met` by checking if all hard prereqs are mastered.
6. Assign `suggested_position` = 1-based index.
7. Return `RecommendationPath(name="建议学习路径", topics=..., total_count=len(topics))`.

- [ ] **Step 13: Run all recommendation tests**

Run: `cd server && uv run pytest tests/backend/services/learning/test_recommendation_service.py -v`
Expected: All PASS.

- [ ] **Step 14: Commit**

```bash
git add server/apps/backend/app/services/learning/zone_service.py \
       server/apps/backend/app/services/learning/recommendation_service.py \
       server/tests/backend/services/learning/test_recommendation_service.py
git commit -m "feat(learning): recommendation engine — breakpoint, curriculum gap, review detection"
```

---

## Task 2: Recommendation API Endpoint

**Files:**
- Modify: `server/apps/backend/app/schemas/learning.py`
- Modify: `server/apps/backend/app/routers/learning_family.py`
- Modify: `server/tests/backend/services/learning/test_recommendation_service.py` (add API test)

**Interfaces:**
- Consumes: `generate_recommendation_path(db, child_id)` from Task 1
- Produces: `GET /api/v1/family/learning/children/{child_id}/recommendations` → `RecommendationPathResponse`

- [ ] **Step 1: Add response schemas to `schemas/learning.py`**

```python
class RecommendedTopicItem(BaseModel):
    topic_id: int
    topic_name: str
    reasons: list[str]
    centrality: float
    prerequisites_met: bool
    suggested_position: int

class RecommendationPathResponse(BaseModel):
    path: RecommendationPathDetail

class RecommendationPathDetail(BaseModel):
    name: str
    topics: list[RecommendedTopicItem]
    total_count: int
```

Note: IDs are `int` in schema; `SnowflakeBase` auto-converts to `str` in JSON.

- [ ] **Step 2: Write API test**

```python
class TestRecommendationEndpoint:
    def test_returns_recommendations_for_child(self, client, auth_headers, db, child_user, mixed_graph):
        resp = client.get(
            f"/api/v1/family/learning/children/{child_user['id']}/recommendations",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data
        assert data["path"]["total_count"] >= 1
        assert len(data["path"]["topics"]) >= 1

    def test_topic_ids_serialized_as_strings(self, client, auth_headers, db, child_user, mixed_graph):
        """Snowflake IDs must be strings in JSON response."""
        resp = client.get(
            f"/api/v1/family/learning/children/{child_user['id']}/recommendations",
            headers=auth_headers,
        )
        data = resp.json()
        for topic in data["path"]["topics"]:
            assert isinstance(topic["topic_id"], str)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/services/learning/test_recommendation_service.py::TestRecommendationEndpoint -v`
Expected: FAIL — endpoint returns 404.

- [ ] **Step 4: Add endpoint to `learning_family.py`**

```python
from apps.backend.app.services.learning.recommendation_service import generate_recommendation_path
from apps.backend.app.schemas.learning import RecommendationPathResponse, RecommendationPathDetail, RecommendedTopicItem

@router.get(
    "/children/{child_id}/recommendations",
    response_model=RecommendationPathResponse,
)
def get_recommendations(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    path = generate_recommendation_path(db, child_id)
    topics = [
        RecommendedTopicItem(
            topic_id=t.topic_id,
            topic_name=t.topic_name,
            reasons=t.reasons,
            centrality=t.centrality,
            prerequisites_met=t.prerequisites_met,
            suggested_position=t.suggested_position,
        )
        for t in path.topics
    ]
    return RecommendationPathResponse(
        path=RecommendationPathDetail(
            name=path.name,
            topics=topics,
            total_count=path.total_count,
        )
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/services/learning/test_recommendation_service.py::TestRecommendationEndpoint -v`
Expected: PASS.

- [ ] **Step 6: Run lint + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/routers/learning_family.py apps/backend/app/schemas/learning.py && uv run mypy apps/backend/app/routers/learning_family.py`
Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/routers/learning_family.py \
       server/apps/backend/app/schemas/learning.py \
       server/tests/backend/services/learning/test_recommendation_service.py
git commit -m "feat(learning): add recommendation API endpoint"
```

---

## Task 3: Review Dual-Track Backend

**Files:**
- Modify: `server/apps/backend/app/services/learning/progress_service.py`
- Modify: `server/apps/backend/app/services/learning/session_service.py`
- Modify: `server/apps/backend/app/routers/learning_child.py`
- Modify: `server/apps/backend/app/routers/learning_family.py`
- Modify: `server/apps/backend/app/schemas/learning.py`
- Create: `server/tests/backend/services/learning/test_review_dual_track.py`

**Interfaces:**
- Consumes: `LearningProgress` (mastery_level, mastery_score, completed_via), `LearningSession` (ai_evaluation_json), `LearningAssessmentAttempt`
- Produces: `check_auto_pass(db, score, child_id) -> AutoPassResult`, `override_review(db, progress_id, parent_id, new_decision, reason) -> LearningProgress`

- [ ] **Step 1: Write tests for `check_auto_pass`**

```python
# tests/backend/services/learning/test_review_dual_track.py
class TestCheckAutoPass:
    def test_score_above_threshold_returns_auto_pass(self, db, child_user, topic):
        result = check_auto_pass(db, score=0.85, child_id=child_user["id"])
        assert result.should_auto_pass is True
        assert result.reason == "score_above_threshold"

    def test_score_at_threshold_returns_auto_pass(self, db, child_user, topic):
        result = check_auto_pass(db, score=0.8, child_id=child_user["id"])
        assert result.should_auto_pass is True

    def test_score_below_threshold_returns_parent_review(self, db, child_user, topic):
        result = check_auto_pass(db, score=0.79, child_id=child_user["id"])
        assert result.should_auto_pass is False

    def test_none_score_returns_parent_review(self, db, child_user, topic):
        result = check_auto_pass(db, score=None, child_id=child_user["id"])
        assert result.should_auto_pass is False

    def test_paused_auto_pass_returns_parent_review(self, db, child_user, topic):
        """When ai_auto_pass_paused flag is set, even high scores go to parent_review."""
        # Set the pause flag (e.g. via cache or DB field)
        result = check_auto_pass(db, score=0.9, child_id=child_user["id"], ai_paused=True)
        assert result.should_auto_pass is False

    def test_short_session_flagged_as_needs_attention(self, db, child_user, topic):
        """Sessions < 3 minutes are flagged even if score passes."""
        result = check_auto_pass(db, score=0.85, child_id=child_user["id"], duration_seconds=120)
        assert result.should_auto_pass is True
        assert result.needs_attention is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/services/learning/test_review_dual_track.py::TestCheckAutoPass -v`
Expected: FAIL — `check_auto_pass` not defined.

- [ ] **Step 3: Implement `check_auto_pass` and `AutoPassResult` in `progress_service.py`**

```python
AUTO_PASS_THRESHOLD = 0.8
CONSECUTIVE_OVERRIDE_LIMIT = 5
SHORT_SESSION_SECONDS = 180  # 3 minutes

@dataclass
class AutoPassResult:
    should_auto_pass: bool
    reason: str  # "score_above_threshold", "score_below_threshold", "ai_paused", "no_score"
    needs_attention: bool = False  # True for short sessions

def check_auto_pass(
    db: Session,
    score: float | None,
    child_id: int,
    ai_paused: bool = False,
    duration_seconds: int | None = None,
) -> AutoPassResult:
    if score is None:
        return AutoPassResult(should_auto_pass=False, reason="no_score")
    if ai_paused:
        return AutoPassResult(should_auto_pass=False, reason="ai_paused")
    if score >= AUTO_PASS_THRESHOLD:
        needs_attention = (
            duration_seconds is not None and duration_seconds < SHORT_SESSION_SECONDS
        )
        return AutoPassResult(
            should_auto_pass=True,
            reason="score_above_threshold",
            needs_attention=needs_attention,
        )
    return AutoPassResult(should_auto_pass=False, reason="score_below_threshold")
```

- [ ] **Step 4: Write tests for parent override**

```python
class TestOverrideReview:
    def test_parent_can_override_ai_pass_to_reject(self, db, child_user, ai_passed_progress):
        result = override_review(
            db,
            progress_id=ai_passed_progress.id,
            parent_id=child_user["parent_id"],
            new_decision="learning",  # downgrade to relearn
            reason="孩子实际上没有掌握",
        )
        assert result.mastery_level == "learning"
        assert result.overridden_by == child_user["parent_id"]

    def test_parent_can_override_reject_to_pass(self, db, child_user, rejected_progress):
        result = override_review(
            db,
            progress_id=rejected_progress.id,
            parent_id=child_user["parent_id"],
            new_decision="mastered",
            reason="其实孩子已经掌握了",
        )
        assert result.mastery_level == "mastered"

    def test_override_records_metadata(self, db, child_user, ai_passed_progress):
        result = override_review(
            db,
            progress_id=ai_passed_progress.id,
            parent_id=child_user["parent_id"],
            new_decision="learning",
            reason="test reason",
        )
        assert result.overridden_by == child_user["parent_id"]
        assert result.overridden_at is not None
        assert result.override_reason == "test reason"
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/services/learning/test_review_dual_track.py::TestOverrideReview -v`
Expected: FAIL.

- [ ] **Step 6: Add override fields to `LearningProgress` model + `override_review` function**

Add to `LearningProgress` model in `server/packages/db/models/learning/progress.py`:
```python
overridden_by = Column(BigInteger, nullable=True)       # parent user_id
overridden_at = Column(UTCDateTime, nullable=True)       # timestamp
override_reason = Column(Text, nullable=True)            # optional text
```

Implement `override_review()` in `progress_service.py`:
```python
def override_review(
    db: Session,
    progress_id: int,
    parent_id: int,
    new_decision: str,  # "mastered" | "learning"
    reason: str | None = None,
) -> LearningProgress:
    """Parent overrides AI assessment. new_decision is the final mastery_level."""
    validate_transition(...)  # ensure valid transition
    progress.mastery_level = new_decision
    progress.overridden_by = parent_id
    progress.overridden_at = datetime.utcnow()
    progress.override_reason = reason
    if new_decision == "mastered":
        progress.completed_via = "parent_override"
    db.flush()
    _increment_consecutive_override_counter(db, progress.child_id)
    return progress
```

- [ ] **Step 7: Write tests for consecutive override circuit breaker**

```python
class TestConsecutiveOverrideCircuitBreaker:
    def test_five_overrides_pauses_auto_pass(self, db, child_user, ai_passed_progresses):
        """After 5 consecutive overrides, auto-pass should be paused."""
        for p in ai_passed_progresses[:5]:
            override_review(db, p.id, child_user["parent_id"], "learning", "reason")
        assert is_ai_auto_pass_paused(db, child_user["id"]) is True

    def test_counter_resets_on_non_override_approval(self, db, child_user, pending_progress):
        """A normal parent approval (not override) resets the counter."""
        approve_parent_review(db, pending_progress, child_user["family_id"])
        assert get_consecutive_override_count(db, child_user["id"]) == 0
```

- [ ] **Step 8: Implement circuit breaker**

Add a counter mechanism (in-memory cache or DB field on `LearningStats`):
```python
def _increment_consecutive_override_counter(db: Session, child_id: int) -> None:
    stats = get_or_create_stats(db, child_id)
    stats.consecutive_ai_overrides = (stats.consecutive_ai_overrides or 0) + 1
    db.flush()

def is_ai_auto_pass_paused(db: Session, child_id: int) -> bool:
    stats = get_or_create_stats(db, child_id)
    return (stats.consecutive_ai_overrides or 0) >= CONSECUTIVE_OVERRIDE_LIMIT

def get_consecutive_override_count(db: Session, child_id: int) -> int:
    stats = get_or_create_stats(db, child_id)
    return stats.consecutive_ai_overrides or 0
```

Add `consecutive_ai_overrides: Mapped[int]` field to `LearningStats` model (default 0).

- [ ] **Step 9: Integrate auto-pass into `end_session`**

Modify `session_service.py` `end_session()`:
```python
def end_session(db, session_id, score=None, ai_evaluation=None):
    # ... existing logic ...
    if score is not None and progress.mastery_level == "assessing":
        # Check if AI is available for this family
        ai_available = _check_ai_available(db, session.child_id)
        if ai_available:
            auto_result = check_auto_pass(
                db, score, session.child_id,
                ai_paused=is_ai_auto_pass_paused(db, session.child_id),
                duration_seconds=session.duration_seconds,
            )
            if auto_result.should_auto_pass:
                transition_to_mastered(db, progress, score, completed_via="ai_assessment")
            else:
                progress.mastery_level = "parent_review"
                progress.mastery_score = score
        else:
            # AI not available — degrade to parent review
            progress.mastery_level = "parent_review"
            progress.mastery_score = score
    # ... rest of existing logic ...
```

- [ ] **Step 10: Add `review_due` priority to `/today` endpoint**

In `learning_child.py` `today_learning()`, add `review_due` check between `pending_assignment` and `current_topic`:

```python
# Priority: pending_assignment > review_due > current_topic > recommended_topic > fallback
review_due_progress = db.query(LearningProgress).filter(
    LearningProgress.child_id == child_id,
    LearningProgress.mastery_level == "mastered",
    LearningProgress.next_review_at <= datetime.utcnow(),
).first()
if review_due_progress:
    # Include in response as review_due topic
```

Add test:
```python
class TestTodayLearningReviewDue:
    def test_review_due_before_current_topic(self, client, child_headers, db, review_due_progress, current_progress):
        resp = client.get("/api/v1/child/learning/today", headers=child_headers)
        data = resp.json()
        assert data.get("review_due_topic") is not None
```

- [ ] **Step 11: Add override + pause endpoints to `learning_family.py`**

```python
class ReviewOverrideRequest(BaseModel):
    new_decision: str  # "mastered" | "learning"
    reason: str | None = None

@router.post("/reviews/{progress_id}/override")
def override_review_endpoint(
    progress_id: int,
    req: ReviewOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    result = override_review(db, progress_id, current_user.id, req.new_decision, req.reason)
    return result

@router.get("/children/{child_id}/ai-review-status")
def get_ai_review_status(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    paused = is_ai_auto_pass_paused(db, child_id)
    count = get_consecutive_override_count(db, child_id)
    return {"ai_auto_pass_paused": paused, "consecutive_overrides": count}

@router.post("/children/{child_id}/ai-review-resume")
def resume_ai_review(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    stats = get_or_create_stats(db, child_id)
    stats.consecutive_ai_overrides = 0
    db.flush()
    return {"ai_auto_pass_paused": False}
```

- [ ] **Step 12: Run all dual-track tests**

Run: `cd server && uv run pytest tests/backend/services/learning/test_review_dual_track.py -v`
Expected: All PASS.

- [ ] **Step 13: Run lint + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/services/learning/progress_service.py apps/backend/app/services/learning/session_service.py apps/backend/app/routers/learning_family.py apps/backend/app/routers/learning_child.py && uv run mypy apps/backend/app/services/learning/progress_service.py`

- [ ] **Step 14: Alembic migration for new columns**

```bash
cd server/apps/backend
uv run alembic revision --autogenerate -m "add override fields and consecutive_ai_overrides"
```

Verify the migration includes: `overridden_by`, `overridden_at`, `override_reason` on `learning_progress`, `consecutive_ai_overrides` on `learning_stats`.

- [ ] **Step 15: Commit**

```bash
git add server/apps/backend/app/services/learning/progress_service.py \
       server/apps/backend/app/services/learning/session_service.py \
       server/apps/backend/app/routers/learning_family.py \
       server/apps/backend/app/routers/learning_child.py \
       server/apps/backend/app/schemas/learning.py \
       server/packages/db/models/learning/progress.py \
       server/packages/db/models/learning/stats.py \
       server/apps/backend/alembic/versions/xxx_add_override_fields.py \
       server/tests/backend/services/learning/test_review_dual_track.py
git commit -m "feat(learning): dual-track review — AI auto-pass + parent override + circuit breaker"
```

---

## Task 4: Preset Learning Paths Backend

**Files:**
- Create: `server/packages/db/models/learning/preset_path.py`
- Create: `server/apps/backend/app/services/learning/preset_path_service.py`
- Create: `server/apps/backend/app/routers/learning_preset.py`
- Create: `server/tests/backend/services/learning/test_preset_path_service.py`
- Modify: `server/apps/backend/app/schemas/learning.py`
- Modify: `server/apps/backend/app/main.py`

**Interfaces:**
- Consumes: `LearningTopic` (curriculum_standards_json, age_group, subject), `LearningDependency` (for ordering), `LearningPath` + `LearningPathItem` (for assignment)
- Produces: `GET /api/v1/family/learning/preset-paths` → `list[PresetPathResponse]`, `POST /api/v1/family/learning/preset-paths/{preset_id}/assign` → `PathResponse`

- [ ] **Step 1: Create `PresetLearningPath` model**

```python
# server/packages/db/models/learning/preset_path.py
class PresetLearningPath(Base):
    __tablename__ = "preset_learning_paths"

    id = Column(BigInteger, primary_key=True)
    grade: Mapped[int]                      # 1-6
    semester: Mapped[str]                   # "fall" | "spring"
    subject: Mapped[str]                    # "mathematics" | "chinese" | "english" | ...
    name: Mapped[str]                       # "三年级上 · 数学 · 分数单元"
    name_zh: Mapped[str]
    description: Mapped[str | None]
    topic_ids_json: Mapped[str]             # JSON array of topic_ids in order
    topic_count: Mapped[int]
    age_group: Mapped[str]                  # "low" | "mid" | "high"
    source_taxonomy: Mapped[str]            # "os-taxonomy" | "beijing"
    is_active: Mapped[bool]                 # default True
    created_at = Column(UTCDateTime, default=datetime.utcnow)
```

Register in `server/packages/db/models/learning/__init__.py`.

- [ ] **Step 2: Write tests for preset path service**

```python
# tests/backend/services/learning/test_preset_path_service.py
class TestGeneratePresetPaths:
    def test_generates_paths_from_curriculum_standards(self, db):
        """Seed script generates preset paths from topics with curriculum_standards_json."""
        paths = generate_preset_paths(db)
        assert len(paths) > 0
        for p in paths:
            assert p.topic_count > 0
            assert p.grade in range(1, 7)
            assert p.semester in ("fall", "spring")

    def test_topics_ordered_by_prerequisites(self, db, topic_chain):
        """Within a preset path, topics are topologically sorted by hard dependencies."""
        paths = generate_preset_paths(db)
        for p in paths:
            topic_ids = json.loads(p.topic_ids_json)
            # verify no topic appears before its hard prereqs
            for i, tid in enumerate(topic_ids):
                prior = set(topic_ids[:i])
                hard_prereqs = get_hard_prereqs(db, tid)
                assert hard_prereqs.issubset(prior | set(topic_ids[:i]))

class TestAssignPresetPath:
    def test_creates_learning_path_for_child(self, db, child_user, preset_path):
        path = assign_preset_path(db, preset_path.id, child_user["id"], child_user["parent_id"])
        assert path.child_id == child_user["id"]
        assert path.status == "active"

    def test_creates_path_items_for_each_topic(self, db, child_user, preset_path):
        path = assign_preset_path(db, preset_path.id, child_user["id"], child_user["parent_id"])
        items = db.query(LearningPathItem).filter_by(path_id=path.id).all()
        assert len(items) == preset_path.topic_count

    def test_assigning_same_preset_twice_creates_new_path(self, db, child_user, preset_path):
        path1 = assign_preset_path(db, preset_path.id, child_user["id"], child_user["parent_id"])
        path2 = assign_preset_path(db, preset_path.id, child_user["id"], child_user["parent_id"])
        assert path1.id != path2.id
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/services/learning/test_preset_path_service.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement `preset_path_service.py`**

```python
def generate_preset_paths(db: Session) -> list[PresetLearningPath]:
    """Generate preset paths from curriculum_standards_json.
    Group topics by (age_group mapped to grade, subject), sort by dependencies."""

def assign_preset_path(db: Session, preset_id: int, child_id: int, parent_id: int) -> LearningPath:
    """Create a LearningPath + LearningPathItems from a preset."""

def list_preset_paths(db: Session, grade: int | None, semester: str | None, subject: str | None) -> list[PresetLearningPath]:
    """List preset paths with optional filters."""
```

- [ ] **Step 5: Add response schemas**

```python
class PresetPathResponse(SnowflakeBase):
    id: int
    grade: int
    semester: str
    subject: str
    name: str
    name_zh: str
    description: str | None
    topic_count: int
    topic_ids: list[int]  # deserialized from JSON
    is_active: bool
```

- [ ] **Step 6: Create `learning_preset.py` router**

```python
router = APIRouter(prefix="/family/learning", tags=["learning-preset"])

@router.get("/preset-paths", response_model=list[PresetPathResponse])
def list_preset_paths_endpoint(
    grade: int | None = Query(None),
    semester: str | None = Query(None),
    subject: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
): ...

@router.post("/preset-paths/{preset_id}/assign", response_model=PathResponse, status_code=201)
def assign_preset_path_endpoint(
    preset_id: int,
    req: AssignPresetRequest,  # { child_id: int }
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
): ...
```

- [ ] **Step 7: Register router in `main.py`**

```python
from apps.backend.app.routers import learning_preset as learning_preset_router
app.include_router(learning_preset_router.router, prefix="/api/v1")
```

- [ ] **Step 8: Run all preset path tests**

Run: `cd server && uv run pytest tests/backend/services/learning/test_preset_path_service.py -v`
Expected: All PASS.

- [ ] **Step 9: Alembic migration for `preset_learning_paths` table**

```bash
cd server/apps/backend
uv run alembic revision --autogenerate -m "add preset_learning_paths table"
```

- [ ] **Step 10: Commit**

```bash
git add server/packages/db/models/learning/preset_path.py \
       server/packages/db/models/learning/__init__.py \
       server/apps/backend/app/services/learning/preset_path_service.py \
       server/apps/backend/app/routers/learning_preset.py \
       server/apps/backend/app/schemas/learning.py \
       server/apps/backend/app/main.py \
       server/apps/backend/alembic/versions/xxx_add_preset_learning_paths.py \
       server/tests/backend/services/learning/test_preset_path_service.py
git commit -m "feat(learning): preset curriculum paths — model, service, API"
```

---

## Task 5: Frontend — `useBabyStore` + BabyLearningPage Hub

**Files:**
- Create: `frontend/apps/main/src/stores/baby.ts`
- Modify: `frontend/apps/main/src/pages/baby/BabyPage.vue`
- Modify: `frontend/apps/main/src/pages/baby/learning/BabyLearningPage.vue`
- Modify: `frontend/apps/main/src/api/learning.ts`
- Modify: `frontend/apps/main/src/router/index.ts`

**Interfaces:**
- Consumes: `getRecommendations(childId)` API (Task 2), `getReviews()` API (existing), `getPaths(childId)` API (existing), `getPresetPaths()` API (Task 4)
- Produces: `useBabyStore` with `selectedChildId`, `selectedChildName`, `activePathId`; restructured `BabyLearningPage` with 5 modules

- [ ] **Step 1: Create `useBabyStore`**

```typescript
// frontend/apps/main/src/stores/baby.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBabyStore = defineStore('baby', () => {
  const selectedChildId = ref<string | null>(null)
  const selectedChildName = ref<string | null>(null)
  const activePathId = ref<string | null>(null)

  function selectChild(id: string | null, name: string | null = null) {
    selectedChildId.value = id
    selectedChildName.value = name
  }

  function setActivePath(pathId: string | null) {
    activePathId.value = pathId
  }

  return { selectedChildId, selectedChildName, activePathId, selectChild, setActivePath }
})
```

- [ ] **Step 2: Lift child selection in BabyPage.vue into `useBabyStore`**

In `BabyPage.vue`, replace local `ref()` for child selection with `useBabyStore()`:
- `onMounted`: read existing child list, set `store.selectChild(firstChild.id, firstChild.name)`
- Tab click: `store.selectChild(child.id, child.name)`
- Navigation to learning: `router.push('/baby/learning')` (store carries the child context)

- [ ] **Step 3: Add API functions to `learning.ts`**

```typescript
// Add to frontend/apps/main/src/api/learning.ts
export function getRecommendations(childId: string) {
  return http.get<RecommendationPathResponse>(
    `/family/learning/children/${childId}/recommendations`
  )
}

export function getPresetPaths(params?: { grade?: number; semester?: string; subject?: string }) {
  return http.get<PresetPathResponse[]>('/family/learning/preset-paths', { params })
}

export function assignPresetPath(presetId: string, childId: string) {
  return http.post<PathResponse>(`/family/learning/preset-paths/${presetId}/assign`, { child_id: childId })
}

export function overrideReview(progressId: string, newDecision: string, reason?: string) {
  return http.post<ProgressResponse>(`/family/learning/reviews/${progressId}/override`, {
    new_decision: newDecision,
    reason,
  })
}
```

- [ ] **Step 4: Restructure BabyLearningPage.vue**

Replace current monolithic layout with 5 collapsible modules. Key structure:

```vue
<template>
  <div class="baby-learning-page">
    <!-- Header with child switcher -->
    <van-nav-bar :title="t('baby.learningManagement')">
      <template #right>
        <ChildSwitcher v-model="currentChildId" :children="children" />
      </template>
    </van-nav-bar>

    <!-- Module 1: Smart Recommendations (default expanded) -->
    <RecommendationModule :child-id="currentChildId" />

    <!-- Module 2: Review Queue (default expanded, 🔒 parent-only marker) -->
    <ReviewModule :child-id="currentChildId" />

    <!-- Module 3: Preset Paths (default collapsed) -->
    <van-collapse v-model="expandedModules">
      <PresetPathsSummary :child-id="currentChildId" />
      <ActivePathsSummary :child-id="currentChildId" />
      <DnaGraphPreview :child-id="currentChildId" />
    </van-collapse>
  </div>
</template>
```

Each module loads independently with skeleton screens. On child switch, each module re-fetches data independently.

- [ ] **Step 5: Build RecommendationModule (inline in BabyLearningPage)**

```vue
<!-- Recommendation section -->
<div class="module-card">
  <div class="module-header" @click="toggleExpand('recommendations')">
    <span>🌟 {{ t('learning.smartRecommendations') }}</span>
    <van-icon :name="expanded ? 'arrow-up' : 'arrow-down'" />
  </div>
  <div v-if="expanded" v-show="expanded">
    <van-skeleton v-if="loading" :rows="3" />
    <div v-else-if="recommendations.length === 0" class="empty-state">
      <EmptyState :description="t('learning.noRecommendations')" />
    </div>
    <div v-else>
      <div class="summary-line">
        {{ t('learning.recommendationSummary', { count: recommendations.length }) }}
      </div>
      <div class="topic-tags">
        <van-tag v-for="topic in recommendations.slice(0, 5)" :key="topic.topic_id"
          :type="reasonToTagType(topic.reasons)" round>
          {{ getReasonEmoji(topic.reasons) }} {{ topic.topic_name }}
        </van-tag>
      </div>
      <div class="actions">
        <van-button size="small" type="primary" @click="confirmAssign">
          {{ t('learning.confirmAssign') }}
        </van-button>
        <van-button size="small" @click="$router.push('/baby/learning/recommendations')">
          {{ t('learning.fineTunePath') }}
        </van-button>
        <van-button size="small" plain @click="refreshRecommendations">
          {{ t('learning.refreshBatch') }}
        </van-button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 6: Build ReviewModule (inline in BabyLearningPage)**

Show top 3 pending reviews. Each item shows: child name, topic name, study duration. "Expand evidence" opens bottom sheet with AI evaluation details + [通过] [要求重学] [覆盖] buttons.

```vue
<van-popup v-model:show="showEvidencePopup" position="bottom" round :style="{ height: '60%' }">
  <ReviewEvidencePanel :session="selectedSession" @approve="handleApprove" @reject="handleReject" @override="handleOverride" />
</van-popup>
```

- [ ] **Step 7: Add routes for new pages**

In `router/index.ts`:
```typescript
// Add
{ path: '/baby/learning/preset-paths', name: 'PresetPaths', component: () => import('@/pages/baby/learning/PresetPathsPage.vue') },
{ path: '/baby/learning/recommendations', name: 'Recommendations', component: () => import('@/pages/baby/learning/RecommendationsPage.vue') },
// Remove
// /baby/learning/assign → delete
// /baby/learning/reviews → delete (merged into BabyLearningPage)
// /baby/learning/paths → delete (merged into BabyLearningPage)
```

- [ ] **Step 8: Run frontend lint + typecheck**

Run: `cd frontend && pnpm -r lint && pnpm -r typecheck`
Expected: No errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/apps/main/src/stores/baby.ts \
       frontend/apps/main/src/pages/baby/BabyPage.vue \
       frontend/apps/main/src/pages/baby/learning/BabyLearningPage.vue \
       frontend/apps/main/src/api/learning.ts \
       frontend/apps/main/src/router/index.ts
git commit -m "feat(learning): useBabyStore + BabyLearningPage hub restructure"
```

---

## Task 6: PresetPathsPage + RecommendationsPage

**Files:**
- Create: `frontend/apps/main/src/pages/baby/learning/PresetPathsPage.vue`
- Create: `frontend/apps/main/src/pages/baby/learning/RecommendationsPage.vue`

**Interfaces:**
- Consumes: `getPresetPaths()`, `assignPresetPath()` (Task 5), `getRecommendations()` (Task 2), `createAssignment()` (existing)
- Produces: Two new route pages

- [ ] **Step 1: Build PresetPathsPage**

Layout:
- Top: horizontal chips for grade → semester → subject (step-by-step filter)
- Center: path cards (subject icon + name + topic count + mastery progress)
- Click card: expand topic list + [一键派发] button
- Empty: "该年级暂无预设路径"
- On assign: toast success + navigate to BabyLearningPage

```vue
<template>
  <div class="preset-paths-page">
    <van-nav-bar :title="t('learning.presetPaths')" left-arrow @click-left="$router.back()" />
    <!-- Filter chips -->
    <div class="filter-chips">
      <van-tabs v-model:active="filterStep" shrink>
        <van-tab :title="t('learning.grade')"><!-- grade chips 1-6 --></van-tab>
        <van-tab :title="t('learning.semester')"><!-- fall/spring --></van-tab>
        <van-tab :title="t('learning.subject')"><!-- math/chinese/english/science --></van-tab>
      </van-tabs>
    </div>
    <!-- Path cards -->
    <div class="path-list">
      <van-skeleton v-if="loading" :rows="3" />
      <EmptyState v-else-if="paths.length === 0" :description="t('learning.noPresetPaths')" />
      <PresetPathCard v-for="path in filteredPaths" :key="path.id" :path="path"
        @assign="handleAssign(path)" @preview="handlePreview(path)" />
    </div>
  </div>
</template>
```

- [ ] **Step 2: Build RecommendationsPage**

Layout:
- List of recommended topics as draggable cards
- Each card shows: reason emoji + topic name + centrality bar
- Interactions: long-press to drag-reorder, swipe-left to remove, tap to see alternatives
- Bottom bar: [从知识图谱添加] button
- Top bar: [确认派发] to create assignments for all topics in order

```vue
<template>
  <div class="recommendations-page">
    <van-nav-bar :title="t('learning.fineTunePath')" left-arrow @click-left="$router.back()">
      <template #right>
        <van-button size="small" type="primary" @click="confirmPath">{{ t('learning.confirmAssign') }}</van-button>
      </template>
    </van-nav-bar>
    <div class="topic-list">
      <div v-for="(topic, index) in orderedTopics" :key="topic.topic_id"
        class="topic-card" @click="showAlternatives(topic)">
        <span class="reason-emoji">{{ getReasonEmoji(topic.reasons) }}</span>
        <span class="topic-name">{{ topic.topic_name }}</span>
        <van-swipe-cell>
          <van-button slot="right" type="danger" size="small" @click="removeTopic(topic)">
            {{ t('common.remove') }}
          </van-button>
        </van-swipe-cell>
      </div>
    </div>
    <van-button block plain @click="$router.push(`/baby/learning/${childId}/map`)">
      {{ t('learning.addFromGraph') }}
    </van-button>
  </div>
</template>
```

- [ ] **Step 3: Run lint + typecheck**

Run: `cd frontend && pnpm -r lint && pnpm -r typecheck`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/baby/learning/PresetPathsPage.vue \
       frontend/apps/main/src/pages/baby/learning/RecommendationsPage.vue
git commit -m "feat(learning): PresetPathsPage + RecommendationsPage"
```

---

## Task 7: DNA 2D Knowledge Graph

**Files:**
- Create: `frontend/apps/main/src/composables/useLearningDnaGraph.ts`
- Create: `frontend/apps/main/src/components/learning/DnaGraph2D.vue`
- Modify: `frontend/apps/main/src/pages/baby/learning/ChildLearningMapPage.vue`

**Interfaces:**
- Consumes: `getChildMap(childId)` API (existing), `getTopicsBatch(ids)` API (existing)
- Produces: `useLearningDnaGraph(items)` composable for layout calculation; `DnaGraph2D` component for SVG rendering

- [ ] **Step 1: Create `useLearningDnaGraph` composable**

```typescript
// frontend/apps/main/src/composables/useLearningDnaGraph.ts
interface GraphNode {
  topicId: string
  name: string
  subject: string
  masteryLevel: string  // locked | available | learning | assessing | mastered | review | parent_review
  centrality: number
  ageGroup: string
  x: number
  y: number
}

interface GraphEdge {
  from: string
  to: string
  strength: 'hard' | 'soft'
}

export function useLearningDnaGraph(items: ProgressWithTopic[]) {
  const nodes = computed<GraphNode[]>(() => layoutSpiral(items))
  const edges = computed<GraphEdge[]>(() => extractEdges(items))
  const selectedNode = ref<GraphNode | null>(null)

  function layoutSpiral(items: ProgressWithTopic[]): GraphNode[] {
    // Spiral layout: angle = f(age_group), radius = f(centrality)
    // Color by subject, opacity/pulse by mastery_level
  }

  function getMasteryStyle(level: string) {
    // mastered: bright solid + glow
    // learning: pulse animation
    // available: semi-transparent
    // locked: dark, faded
    // review: yellow blink
  }

  return { nodes, edges, selectedNode, getMasteryStyle }
}
```

- [ ] **Step 2: Create `DnaGraph2D.vue` component**

SVG-based 2D knowledge graph. Renders nodes as circles on a spiral layout, edges as lines.

```vue
<template>
  <div class="dna-graph-2d" ref="containerRef">
    <van-skeleton v-if="loading" :rows="5" />
    <EmptyState v-else-if="nodes.length === 0" :description="t('learning.noGraphData')" />
    <svg v-else :viewBox="viewBox" class="graph-svg" @click="handleSvgClick">
      <!-- Edges -->
      <line v-for="edge in edges" :key="`${edge.from}-${edge.to}`"
        :x1="getNode(edge.from).x" :y1="getNode(edge.from).y"
        :x2="getNode(edge.to).x" :y2="getNode(edge.to).y"
        :class="['edge', edge.strength]" />
      <!-- Nodes -->
      <circle v-for="node in nodes" :key="node.topicId"
        :cx="node.x" :cy="node.y" :r="nodeRadius"
        :class="['node', getMasteryStyle(node.masteryLevel)]"
        :fill="getSubjectColor(node.subject)"
        @click.stop="selectNode(node)" />
    </svg>
    <!-- Legend -->
    <div class="legend" v-if="showLegend">
      <span v-for="style in masteryLegend" :key="style.key" class="legend-item">
        <span class="dot" :class="style.cssClass" /> {{ style.label }}
      </span>
    </div>
    <!-- Bottom sheet on node click -->
    <van-popup v-model:show="showNodeSheet" position="bottom" round>
      <NodeDetailPanel v-if="selectedNode" :node="selectedNode"
        @add-to-path="addToPath" @assign="directAssign" @view-prereqs="highlightPrereqs" />
    </van-popup>
  </div>
</template>
```

Key styles per mastery level:
- `mastered`: `opacity: 1`, `filter: drop-shadow(glow)`
- `learning`: CSS `@keyframes pulse` animation
- `available`: `opacity: 0.5`
- `locked`: `opacity: 0.2`, `fill: gray`
- `review`: CSS `@keyframes blink` animation, yellow tint

Subject colors: mathematics → blue, chinese → red, english → green, science → purple, etc.

- [ ] **Step 3: Integrate into ChildLearningMapPage**

Replace the current `TopicGrid` list with `DnaGraph2D`. Add:
- Subject filter chips at top
- [全屏] button → navigate to full-screen mode at `/baby/learning/:childId/map`
- Embedded preview mode (~200px height) in BabyLearningPage

- [ ] **Step 4: Run lint + typecheck**

Run: `cd frontend && pnpm -r lint && pnpm -r typecheck`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/composables/useLearningDnaGraph.ts \
       frontend/apps/main/src/components/learning/DnaGraph2D.vue \
       frontend/apps/main/src/pages/baby/learning/ChildLearningMapPage.vue
git commit -m "feat(learning): DNA 2D knowledge graph — SVG spiral layout with mastery visualization"
```

---

## Task 8: Child App — Source Tags, Review-Due, Rejection Feedback

**Files:**
- Modify: `frontend/apps/child/src/components/TodayLearningCard.vue`
- Modify: `frontend/apps/child/src/pages/learning/LearningMapPage.vue`

**Interfaces:**
- Consumes: `TodayLearningResponse` (new `review_due_topic` field from Task 3), `ProgressResponse` (assignment_type field for source tag)
- Produces: Updated visual indicators across child app

- [ ] **Step 1: Add `review_due` priority to TodayLearningCard**

In `displayMode` computed:
```typescript
const displayMode = computed<'assignment' | 'review_due' | 'current' | 'recommended' | 'explore'>(() => {
  if (props.data.pending_assignment) return 'assignment'
  if (props.data.review_due_topic) return 'review_due'  // NEW
  if (props.data.current_topic) return 'current'
  if (props.data.recommended_topic) return 'recommended'
  return 'explore'
})
```

Add icon mapping: `review_due` → `🔄`

- [ ] **Step 2: Add source tag to TodayLearningCard**

```vue
<van-tag v-if="sourceTag" :type="sourceTagType" size="medium" class="source-tag">
  {{ sourceTag }}
</van-tag>
```

```typescript
const sourceTag = computed(() => {
  const assignmentType = currentAssignment?.assignment_type
  if (assignmentType === 'self_selected') return '🔍 自己探索'
  if (currentAssignment?.path?.name?.includes('智能推荐')) return '🌟 系统推荐'
  if (assignmentType === 'parent_assigned') return '📝 爸妈布置'
  return null
})
```

- [ ] **Step 3: Add rejection feedback display to TodayLearningCard**

When a topic has been rejected (mastery_level is `parent_review` or `learning` after assessment failure):
```vue
<div v-if="rejectionFeedback" class="rejection-banner">
  <span>❌ {{ t('learning.needsRereview') }}</span>
  <span class="weakness">{{ rejectionFeedback.weakness }}</span>
  <van-button size="mini" @click="relearn">{{ t('learning.relearn') }}</van-button>
  <van-button size="mini" plain @click="goPractice">{{ t('learning.goPractice') }}</van-button>
</div>
```

- [ ] **Step 4: Add review-due pulse + rejection markers to LearningMapPage**

In `TopicGrid` node rendering:
```vue
<!-- Review due: yellow pulse -->
<div v-if="item.mastery_level === 'mastered' && isReviewDue(item)" class="review-pulse" />

<!-- Rejection: red dashed border + exclamation -->
<div v-if="isRejected(item)" class="rejected-marker">
  <van-icon name="warning-o" />
</div>

<!-- Source tag: small corner badge -->
<div v-if="getSourceBadge(item)" class="source-badge">
  {{ getSourceBadge(item) }}
</div>
```

- [ ] **Step 5: Run lint + typecheck**

Run: `cd frontend && pnpm -r lint && pnpm -r typecheck`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/child/src/components/TodayLearningCard.vue \
       frontend/apps/child/src/pages/learning/LearningMapPage.vue
git commit -m "feat(child): source tags + review-due priority + rejection feedback"
```

---

## Task 9: Route Cleanup + Delete Deprecated Pages

**Files:**
- Delete: `frontend/apps/main/src/pages/baby/learning/LearningAssignPage.vue`
- Delete: `frontend/apps/main/src/pages/baby/learning/LearningReviewsPage.vue`
- Delete: `frontend/apps/main/src/pages/baby/learning/LearningPathsPage.vue`
- Modify: `frontend/apps/main/src/router/index.ts`

**Interfaces:**
- Consumes: Routes from Tasks 5-6
- Produces: Clean router with no dead routes

- [ ] **Step 1: Remove deprecated route entries from `router/index.ts`**

Remove:
```typescript
{ path: '/baby/learning/assign', ... }      // → replaced by RecommendationsPage / PresetPathsPage
{ path: '/baby/learning/reviews', ... }     // → merged into BabyLearningPage
{ path: '/baby/learning/paths', ... }       // → merged into BabyLearningPage
```

- [ ] **Step 2: Delete deprecated page files**

```bash
rm frontend/apps/main/src/pages/baby/learning/LearningAssignPage.vue
rm frontend/apps/main/src/pages/baby/learning/LearningReviewsPage.vue
rm frontend/apps/main/src/pages/baby/learning/LearningPathsPage.vue
```

- [ ] **Step 3: Remove unused imports**

Search for any remaining imports of deleted pages (e.g., in lazy-loading route definitions, navigation guards). Fix or remove.

- [ ] **Step 4: Boost learning entry cell in BabyPage.vue**

Increase visual weight of the learning entry `van-cell`:
- Add icon: `<van-icon name="chart-trending-o" slot="icon" />` (or a learning-specific icon)
- Add subtitle: show recommendation count or active path summary
- Use `van-cell-group` with inset style to make it stand out

- [ ] **Step 5: Run full frontend quality check**

Run: `cd frontend && pnpm -r lint && pnpm -r typecheck`
Expected: No errors. No broken imports.

- [ ] **Step 6: Run full backend quality check**

Run: `cd server && uv run ruff check apps/backend/ && uv run pytest tests/backend/ -v`
Expected: All tests pass, no lint errors.

- [ ] **Step 7: Commit**

```bash
git add -A frontend/apps/main/src/pages/baby/learning/ \
       frontend/apps/main/src/router/index.ts \
       frontend/apps/main/src/pages/baby/BabyPage.vue
git commit -m "refactor(learning): remove deprecated pages + boost learning entry"
```

---

## Post-Implementation Checklist

After all 9 tasks are complete:

1. Run `cd server && uv run alembic upgrade head` — verify both migrations apply cleanly.
2. Run `cd server && uv run pytest tests/backend/ -v` — all backend tests pass.
3. Run `cd frontend && pnpm -r lint && pnpm -r typecheck` — no frontend errors.
4. Verify BabyLearningPage loads with all 5 modules at `http://localhost:5173/baby/learning`.
5. Verify recommendation API returns correct data: `curl http://localhost:8000/api/v1/family/learning/children/{id}/recommendations`.
6. Verify child app TodayLearningCard shows `review_due` and source tags.
7. Verify DNA 2D graph renders in ChildLearningMapPage.
