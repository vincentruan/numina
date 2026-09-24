# Learning OS Code Review — Deferred Items

> Date: 2026-09-23
> Branch: `feat/learning-os`
> Review scope: Standards + Spec compliance against `docs/superpowers/plans/2026-09-23-learning-os.md`
> Last updated: 2026-09-23 (second review pass)

## Fixed — Session 1 (Initial Review)

### Hard Violations (4)
1. ✅ **Operator precedence bug** — `topic.name_zh or topic.name or "" if topic else ""` → added parens in `learning_family.py` (2 sites) + `learning_child.py` (1 site)
2. ✅ **Hardcoded Chinese narrative** — `narrative="掌握知识点奖励"` → now uses topic name dynamically: `f"掌握知识点：{topic_label}"`
3. ✅ **Inline imports** — `import json` in `end_session()`, `from ... import User` in `get_review_queue()` → moved to module top
4. ✅ **Private function calls** — `_validate_transition` → renamed to public `validate_transition`

### State Machine (Spec)
5. ✅ **State machine aligned to spec** — `mastered → {review, learning}` (was `{review}` only); `review → {learning}` (was `{mastered, learning}`)
6. ✅ **`/child/learning/progress` fixed** — now returns `ChildProgressOverview` with aggregated counts (was returning single `ProgressResponse`)
7. ✅ **`approve_review` extracted to service** — `progress_service.approve_parent_review()` consolidates CAS + stability + coins + attempts

### Code Smells
8. ✅ **Duplicated prerequisite check** — extracted `_all_hard_prereqs_met()` helper in `progress_service.py`
9. ✅ **Duplicated locale resolution** — created `useLocalizedTopic()` composable in both child + main apps, updated 6 pages

### Tests Updated
- `test_review_to_mastered` → `test_review_to_mastered_invalid` (review → mastered now correctly invalid)
- `test_mastered_to_learning_is_invalid` → `test_mastered_to_learning_is_valid` (now correctly valid)
- Integration test: `_validate_transition` → `validate_transition`

---

## Fixed — Session 2 (Second Review Pass)

### P1 — Functional Blocks
10. ✅ **`onSubmitAssignment` stub** (`LearningTopicPage.vue`) — was showing success toast without calling API. Now fetches assignments, finds pending one, calls `submitAssignment()`.
11. ✅ **`onEndSession` stub** (`LearningSessionPage.vue`) — was navigating without ending session. Added backend `POST /child/learning/sessions/{id}/end` with child ownership check, frontend now calls `endSession()`.
12. ✅ **Topic search always empty** (`LearningAssignPage.vue`) — `onSearch()` always returned `[]`. Now calls `GET /learning/topics?search=<q>` with 300ms debounce. Backend `list_topics` gained `search` (ILIKE on name/name_zh/domain) + `limit` params.
13. ✅ **N+1 queries on map pages** (`LearningMapPage.vue`, `ChildLearningMapPage.vue`) — was firing one HTTP request per topic. Added `GET /learning/topics/batch?ids=1,2,3` endpoint + `topic_service.list_topics_by_ids()` + frontend `getTopicsBatch()`. Single request replaces N.
14. ✅ **`study_duration_seconds` hardcoded 0** (`learning_family.py` review_queue) — was `# TODO: aggregate from sessions`. Now aggregates `SUM(duration_seconds)` grouped by `(child_id, topic_id)` from `learning_sessions`.
15. ✅ **i18n key added** — `learning.noPendingAssignment` in zh-CN + en-US for the submit flow.

### P2 — State Machine
16. ✅ **`assessing → parent_review` transition added** — `submit_for_review` requires `parent_review` which was only reachable from `learning`. Once a child started assessment (`learning → assessing`), there was no path to submit. Added `"parent_review"` to `assessing` target set in `VALID_TRANSITIONS`.

---

## Deferred / Open Questions

### OQ-1: MCP Tools are stubs (Task 11)
**Status:** ✅ **Resolved** — All 3 MCP tools (`record_learning_result`, `get_learning_progress`, `evaluate_mastery`) are now implemented and wired into the agent tool registry. Security constraints (input validation, tenant isolation, schema validation) documented in `server/apps/agent/CLAUDE.md` §Security Rules #10.

### OQ-2: Translation service is a placeholder (Task 12)
**Status:** ✅ **Decision confirmed** — On-demand translation via DeerFlow agent, user-triggered, button visible only on language mismatch. See `docs/superpowers/specs/2026-09-24-learning-os-oq-product-decisions.md` §OQ-2.

### OQ-3: `learning_streak_3_failures` notification never fires (Task 21)
**Status:** ✅ **Decision confirmed** — A1+B1+C1: assessment `passed=False`, same topic, inline detection in `progress_service`. See `docs/superpowers/specs/2026-09-24-learning-os-oq-product-decisions.md` §OQ-3.

### OQ-4: "Today learning" card on ChildHomePage (Task 16 Step 5)
**Status:** ✅ **Resolved** — `TodayLearningCard` component integrated at `ChildHomePage.vue:44`, backed by `GET /child/learning/today` endpoint (`learning_child.py:63`). Displays pending assignment > current topic > recommended topic with priority logic. Footer shows today's study minutes. i18n keys at `learning.todayCard.*`.

### OQ-5: LearningSessionPage AI chat placeholder (Task 17 Step 2)
**Status:** ✅ **Resolved** — `LearningSessionPage.vue` is now connected to the DeerFlow SSE stream via the learning-tutor app. Chat UI supports real-time AI tutoring with Redis bridge event delivery. See commits `feat(learning): implement LearningSessionPage chat UI with SSE streaming` and `feat(learning): add assessment stream endpoint with Redis bridge subscribe`.

### OQ-6: Seed quality validation + version tracking (Task 13)
**Status:** ✅ **Decision confirmed** — A1+B1: orphan check + badge-topic cross-validation + age_range constraint, post-seed timing. See `docs/superpowers/specs/2026-09-24-learning-os-oq-product-decisions.md` §OQ-6.

### OQ-7: Badge count discrepancy (Task 14)
**Status:** ✅ **Resolved** — Spec updated to reflect 9 subjects (added `learning_to_learn`). 30 badges = 9 × 3 + 3. Implementation is correct; spec was outdated.

### ~~OQ-8: N+1 query pattern in frontend~~ ✅ Fixed (Session 2, #13)
Added `GET /learning/topics/batch` endpoint. Both map pages now use `getTopicsBatch()` — single request instead of N+1.

### ~~OQ-9: TODO stubs in frontend~~ ✅ Fixed (Session 2, #10-12)
`onSubmitAssignment` now calls actual API. `onEndSession` now calls backend endpoint. Topic search in `LearningAssignPage` now fetches from backend.

### OQ-10: Duplicated TypeScript interfaces across apps
**Status:** `TopicResponse`, `ProgressResponse`, `AssignmentResponse`, `SessionResponse` etc. are defined identically in `apps/child/src/api/learning.ts` and `apps/main/src/api/learning.ts`.
**Decision needed:** Extract to `@numina/types/learning` shared package, or keep duplicated?
**Recommendation:** Keep duplicated for now — type definitions are small, drift risk is low at current pace. Both files have a comment noting the duplication. Extract to shared package if drift becomes painful.

### OQ-11: Duplicated `useLocalizedTopic` composable
**Status:** Identical composable in `apps/child/src/composables/useLocalizedTopic.ts` and `apps/main/src/composables/useLocalizedTopic.ts`.
**Decision needed:** Extract to `@numina/composables` or keep duplicated?
**Recommendation:** Same as OQ-10 — keep for now, extract together when types are moved.

### OQ-12: Hardcoded Chinese in notification dispatcher
**Status:** ✅ **Resolved (by design)** — All 4 learning notification functions (`notify_learning_*`) use hardcoded Chinese strings. This **matches the established convention** across all dispatcher functions (errors use i18n `AppError`, notifications use direct Chinese). Added comment documenting this is intentional.

### OQ-13: No auth on global `/learning/*` endpoints
**Status:** ✅ **Resolved** — Added module docstring to `learning.py` explaining the auth decision: knowledge graph is shared/read-only data (same for all families), no family-specific data is served. Write endpoints and family-scoped progress endpoints live behind `require_adult` / `get_current_child_user` in `learning_family.py` and `learning_child.py`.

### OQ-14: `ErrorCode.NOT_FOUND` vs learning-specific codes
**Status:** ✅ **Resolved** — All `ErrorCode.NOT_FOUND` usages in `learning_family.py` were for "child not found" checks. Standardized to `ErrorCode.AUTH_CHILD_NOT_FOUND` which is the correct semantic error code.

### OQ-15: No navigation entry to BabyLearningPage
**Status:** ✅ **Resolved** — `BabyPage.vue` already contains a `van-cell` entry at line 64-67 with `@click="$router.push('/baby/learning')"` linking to the learning page.

### OQ-16: BabyLearningPage not in KeepAlive cache
**Status:** ✅ **Resolved** — `MainLayout.vue` already includes `'BabyLearning'` in `cachedTabs` (line 46).

### OQ-17: Prerequisites/dependents not displayed on LearningTopicPage
**Status:** ✅ **Resolved** — `LearningTopicPage.vue` renders prerequisites (line 51) and dependents/next-steps (line 73) sections using `GET /learning/topics/{id}/graph` endpoint. Uses Vant tags with status icons (success/unlock/lock). i18n keys `learning.prerequisites` and `learning.nextSteps` in both locales.

---

## Verification Summary

| Check | Result |
|-------|--------|
| Backend lint (`ruff check`) | ✅ All pass |
| Backend tests (59 learning tests) | ✅ All pass |
| Notification tests (11 tests) | ✅ All pass |
| Frontend typecheck (child) | ✅ No errors |
| Frontend typecheck (main) | ✅ No errors |

---

## Change Summary (Session 2)

### New Backend Endpoints
- `GET /api/v1/learning/topics/batch?ids=1,2,3` — batch topic fetch
- `POST /api/v1/child/learning/sessions/{id}/end` — end a learning session

### Enhanced Backend Endpoints
- `GET /api/v1/learning/topics` — added `search` (ILIKE) + `limit` params

### State Machine Update
- `assessing → {mastered, review, parent_review}` (added `parent_review`)

### Files Changed (Session 2)
28 files, +531/-258 lines across backend services/routers, frontend pages/API layers, i18n locales.
