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
**Status:** All 3 MCP tools in `mcp_tools.py` raise `NotImplementedError`. Not wired into agent tool registry.
**Decision needed:** Implement now or defer to Phase 2? The AI tutor skill (SKILL.md) is ready, but the tools it needs aren't functional.
**Recommendation:** Defer to Phase 2 — AI tutor chat works without MCP tools (uses prompt-only approach). MCP tools add structured data access for more advanced scenarios.

### OQ-2: Translation service is a placeholder (Task 12)
**Status:** `translation.py` returns `None` for all fields. No DashScope/OpenAI integration.
**Decision needed:** When to implement actual LLM-based translation?
**Recommendation:** Defer — seed script works with English-only data. Translation can be batch-run later.

### OQ-3: `learning_streak_3_failures` notification never fires (Task 21)
**Status:** Event registered in notification registry but no dispatcher function or trigger logic exists.
**Decision needed:** What constitutes a "streak of 3 failures"? How should it be detected — in progress_service after failed assessment, or via a scheduled job?
**Recommendation:** Define failure semantics first. Likely needs: (a) assessment failure tracking in session_service, (b) counter in progress_service, (c) dispatcher function. Defer to Phase 2.

### OQ-4: "Today learning" card on ChildHomePage (Task 16 Step 5)
**Status:** Not implemented.
**Decision needed:** Design the card — what data to show, where to place it on ChildHomePage.
**Recommendation:** Low priority. Can be added as a UX enhancement later.

### OQ-5: LearningSessionPage AI chat placeholder (Task 17 Step 2)
**Status:** Chat UI exists but doesn't connect to DeerFlow SSE. TODO comments in place.
**Decision needed:** Should child app extract `useThreadChat` from main app, or build a simplified version?
**Recommendation:** Defer — this is the biggest remaining piece. Needs design decision on shared AI chat composable.

### OQ-6: Seed quality validation + version tracking (Task 13)
**Status:** Seed scripts work but lack orphan edge detection, age range spot checks, and version tracking (`reseed --version <tag>`).
**Decision needed:** How important is data quality validation for initial seed? Version tracking needed before production?
**Recommendation:** Add quality validation before first production seed. Version tracking can wait.

### OQ-7: Badge count discrepancy (Task 14)
**Status:** Spec says 27 badges (8 subjects × 3 + 3). Implementation seeds 30 (9 subjects × 3 + 3, with `learning_to_learn` as 9th subject).
**Decision needed:** Is `learning_to_learn` intentional addition? If so, update spec.
**Recommendation:** Minor — keep the extra subject if it's meaningful. Update spec to match.

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
**Status:** All 4 learning notification functions (`notify_learning_*`) use hardcoded Chinese strings for titles/bodies. However, **all existing notification functions** in `dispatcher.py` follow the same pattern — this is the established convention (errors use i18n `AppError`, notifications use direct Chinese).
**Decision needed:** Migrate all notifications to i18n, or keep current pattern?
**Recommendation:** Keep consistent with existing pattern. A broader notification i18n effort can be done separately if needed.

### OQ-13: No auth on global `/learning/*` endpoints
**Status:** `GET /learning/topics`, `/subjects`, `/clusters` are open (no auth). Intentional — knowledge graph is global/read-only — but undocumented.
**Decision needed:** Add auth or keep open?
**Recommendation:** Keep open — the knowledge graph is shared public data, not family-specific. Add a doc comment on the router explaining the auth decision.

### OQ-14: `ErrorCode.NOT_FOUND` vs learning-specific codes
**Status:** Some endpoints (e.g. `get_child_map`, `create_assignment`) use `ErrorCode.NOT_FOUND` for "child not in family", while others use `LEARNING_TOPIC_NOT_FOUND` etc. Minor inconsistency.
**Recommendation:** Low priority — functional behavior is correct. Standardize in a future cleanup pass.

### OQ-15: No navigation entry to BabyLearningPage
**Status:** `/baby/learning` route exists but no link/button from `BabyPage.vue` or main navigation reaches it.
**Decision needed:** Add entry point from BabyPage (e.g. a "学习管理" card alongside chore/literacy cards)?
**Recommendation:** Add in a follow-up — BabyPage is the parent's main child-management hub and should link to learning.

### OQ-16: BabyLearningPage not in KeepAlive cache
**Status:** Main app's KeepAlive include list doesn't contain `BabyLearning`. `onActivated` hooks won't fire.
**Recommendation:** Add to MainLayout's KeepAlive list when navigation entry is added.

### OQ-17: Prerequisites/dependents not displayed on LearningTopicPage
**Status:** Topic detail page shows topic info but doesn't render prerequisite/dependent topic cards with lock status.
**Recommendation:** Use `GET /learning/topics/{id}/graph` to fetch and display. Defer to UX polish pass.

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
