---
title: "feat: Misconception Catalog — Adaptive Selection + Smart Tutor Integration"
type: feat
status: completed
date: 2026-11-16
origin: docs/brainstorms/2026-11-16-misconception-catalog-requirements.md
---

# feat: Misconception Catalog — Adaptive Selection + Smart Tutor Integration

## Overview

The misconception detection pipeline already exists (models, detector service, practice router integration, seed data). This plan adds the **two missing pieces** that make misconception detection meaningful:

1. **Adaptive selection boosting** — when a child's recent attempts reveal a specific misconception, the next practice session silently prioritizes diagnostic questions targeting that misconception.
2. **Smart Tutor integration** — the tutor receives misconception context so it can frame corrections as "this is a common mix-up" rather than generic encouragement.

The existing detection pipeline (U1-U4 in the prior plan) is preserved. This plan extends it.

(see origin: `docs/brainstorms/2026-11-16-misconception-catalog-requirements.md`)

---

## Problem Frame

The current implementation detects misconceptions and returns feedback in the API response, but nothing consumes the detection downstream:

- **Adaptive selection** (`select_questions()`) treats all wrong answers equally — it doesn't know which misconceptions were detected, so it can't prioritize diagnostic questions.
- **Smart Tutor** tracks `misconceptions_detected: int` (a count) but doesn't know *which* misconceptions the child holds, so it can't provide targeted emotional framing.

The detection is infrastructure without a consumer. This plan closes the loop.

---

## Requirements Trace

- R1. ~~Unified Misconception model~~ (Existing separate `Misconception` model retained — see Key Technical Decisions)
- R2. Model scoping mirrors TopicConfusion pattern (already implemented)
- R3. Detection service matches wrong answers to known error patterns (already implemented)
- R4. `select_questions` gains misconception-aware boosting — diagnostic questions for recently-detected misconceptions are prioritized
- R5. After each practice attempt is scored, detected misconception IDs flow into the question selection of the next practice session for the same child+topic (cross-session boosting; sessions have fixed question lists)
- R6. `record_tutoring_step` MCP tool accepts optional `misconception_id` field (category resolved from DB, not caller-supplied)
- R7. `misconceptions_detected` on Smart Tutor session responses upgraded from `int` to `list[dict]`
- R8. Smart Tutor SKILL.md updated with misconception-aware feedback instructions per category
- R9. Pilot: 3 fraction topics with 2-3 misconceptions each (already seeded)
- R10. ~~Seed data as JSON file~~ (already implemented via `seed_misconceptions.py`)
- R11. Practice API response includes misconception_feedback (already implemented)
- R12. GET /misconceptions endpoint (already implemented at `practice.py` — returns the child's detections grouped by topic with counts)

**Origin actors:** Child learner (A1), Smart Tutor LLM (A2), Practice adaptive engine (A3)
**Origin flows:** F1 (Misconception detection on wrong answer — already implemented), F2 (Adaptive question selection with misconception awareness), F3 (Smart Tutor misconception-informed dialogue)
**Origin acceptance examples:** AE1 (fraction addition pattern match — already works), AE2 (silent adaptive selection of diagnostic question), AE3 (Smart Tutor names specific misconception in dialogue), AE4 (unclassified wrong answer returns None — already works)

---

## Scope Boundaries

- No LLM-based misconception detection — rule-based only (existing implementation)
- No model unification with TopicConfusion — the existing separate `Misconception` model is retained (see Key Technical Decisions)
- No new frontend UI components — misconception detection is invisible infrastructure that improves question selection and Smart Tutor dialogue only
- No `GET /misconceptions` analytics enhancements — the endpoint already exists; no new parent dashboard built on top of it
- No changes to BKT estimation — misconception detection annotates attempts but does not feed back into mastery parameters
- No cross-topic misconception inference — each misconception is scoped to a single topic
- No changes to teach-back flow — TopicConfusion continues to serve teach-back independently
- Frontend `MisconceptionFeedbackCard` from the prior plan is **not built** — the brainstorm chose silent adaptive selection

---

## Context & Research

### Relevant Code and Patterns

- `server/apps/backend/app/services/learning/adaptive_service.py` — `select_questions()` at line 214 is the integration point for misconception-aware boosting
- `server/apps/backend/app/services/learning/misconception_detector.py` — existing detection service (already implemented, returns `Misconception | None`)
- `server/packages/db/models/learning/misconception.py` — existing `Misconception` and `MisconceptionDetection` models
- `server/apps/backend/app/routers/practice.py` — `submit_practice_answer()` at line 203 already runs detection and builds `MisconceptionFeedbackResponse`
- `server/apps/backend/app/services/mcp_tool_registry.py` — `record_tutoring_step` tool definition at line 508, needs `misconception_id` field added
- `server/apps/backend/app/schemas/learning.py` — `SmartTutorSessionResponse` at line 556 has `misconceptions_detected: int` to upgrade
- `server/apps/agent/skills/builtin/public/learning-smart-tutor/SKILL.md` — Smart Tutor prompt, needs misconception-aware feedback instructions
- `frontend/apps/main/src/api/learning.ts` + `frontend/apps/main/src/pages/BabyLearningPage.vue` — the sole frontend consumers of `misconceptions_detected` (parent-facing Smart Tutor history view; verified by grep — the child app's `useSmartTutor.ts` never reads it)
- `frontend/apps/child/src/components/learning/smart-tutor/SocraticSteps.vue` — displays step phase, may need to handle misconception data

### Institutional Learnings

- Existing Alembic migration naming: `mc001misc0001_*` pattern for misconception tables
- `docs/solutions/database-issues/auto-migrate-string-default-quoting-postgresql.md` — VARCHAR default quoting
- Practice router already uses `is_diagnostic` flag pattern for diagnostic questions outside session membership

---

## Key Technical Decisions

- **Keep separate `Misconception` model (diverges from brainstorm R1).** The brainstorm chose "unified model — extend TopicConfusion." However, the existing implementation already created a separate `Misconception` table with working tests and seed data. Renaming TopicConfusion → Misconception would break the teach-back flow (which references TopicConfusion extensively in `teach_back_service.py`) and require a data migration for existing confusion rows. The existing separate model achieves the same goal — both are per-topic, age-group-scoped, review-gated misconception records. Unification can be revisited as a follow-up refactor when the pilot validates the detection approach.

- **Add `misconception_id` to PracticeAttempt AND keep MisconceptionDetection.** The brainstorm said annotate PracticeAttempt; the existing code uses a separate detection table. Both serve different purposes: `PracticeAttempt.misconception_id` enables fast "what misconception did this attempt reveal?" lookups during question selection (single-table query, no join). `MisconceptionDetection` preserves detection history with the wrong answer payload for future analytics. The practice router sets both. The detection writes are wrapped in a savepoint so a detection failure rolls back only the annotation, never the answer submission.

- **Misconception IDs for selection are always derived from `PracticeAttempt` queries, never held in router memory.** FastAPI handlers are per-request — a handler-local set cannot survive between HTTP requests, and a module-global set would diverge under multi-worker deployment (the backend AGENTS.md explicitly requires Redis for multi-instance, signaling per-process state is unsafe here). At each selection point (next session creation), the router queries `PracticeAttempt.misconception_id` for (child_id, topic_id) over a defined recency window and passes the resulting set to `select_questions()`. Single source of truth, no lifecycle risk, no multi-worker divergence.

- **Smart Tutor receives misconception context via `record_tutoring_step` metadata.** The MCP tool gains an optional `misconception_id` field. The handler validates it belongs to the session's topic (cross-topic/family IDs are rejected), then resolves the description and category from the DB — the caller never supplies the category, so an LLM cannot fabricate or mismatch it. The SKILL.md prompt instructs the tutor to frame corrections using the category-specific tone (`concept_confusion` → "common mix-up", `procedural_error` → "steps got mixed up", `carelessness` → no misconception feedback).

- **`misconceptions_detected` type change is a breaking schema change.** The field changes from `int` to `list[dict]`. The sole frontend consumer is the parent-facing main app (`learning.ts` + `BabyLearningPage.vue`); the child app's `useSmartTutor.ts` never reads it. The count is derived from `len(list)`. The change must land with both main-app updates in the same PR.

---

## Open Questions

### Resolved During Planning

- **How does the practice router accumulate misconception IDs?** It doesn't — no in-memory state. Each selection point (next session creation) queries `PracticeAttempt.misconception_id` for (child_id, topic_id) within the recency window (last 30 attempts or 7 days, whichever covers more history) and passes the resulting set to `select_questions()`. This is multi-worker safe and survives restarts by construction.
- **When does boosting stop?** A misconception drops out of the boost set when the child answers its diagnostic questions correctly twice consecutively (successful resolutions clear the misconception from future lookback by checking the most recent attempts first). This prevents a single old error from indefinitely dominating practice. The recency window (7 days / 30 attempts) is the backstop.
- **Where does the Smart Tutor LLM see misconception data?** The `record_tutoring_step` tool's response includes the misconception description and category. The LLM reads this in the tool result and adjusts its next response accordingly. The SKILL.md instructions tell it how.
- **How does the frontend handle the type change?** In `frontend/apps/main/src/api/learning.ts`, the type changes to `Array<{misconception_id: string, category: string, description: string}>`. In `BabyLearningPage.vue`, `session.misconceptions_detected > 0` becomes `.length > 0` (with an `Array.isArray` guard for transitional safety). No child-app changes needed.

### Deferred to Implementation

- **Exact query for reconstructing misconception IDs after server restart.** The practice router can query `PracticeAttempt.misconception_id` for the session to rebuild the set. The implementer should check whether the session object already loads attempts or needs a separate query.
- **Performance of boosting with large misconception sets.** Expected to be small (<5 misconceptions per session). A simple filter is acceptable. If it grows, the boosting logic can move to a more efficient batch query.
- **Whether teach-back should reference the Misconception model in the future.** Currently teach-back uses TopicConfusion independently. Cross-referencing could share misconception knowledge but is out of scope for this plan.

---

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
Practice Session Flow (with misconception awareness):

  create_session()
    → select_questions(topic_id, count=N)
    → returns questions [q1, q2, ..., qN]

  submit_answer(q1) → WRONG
    → scoring_service.check_answer() → False
    → misconception_detector.detect() → misconception_id=M1
    → PracticeAttempt.misconception_id = M1  (NEW)
    → MisconceptionDetection record created  (existing)
    → response includes misconception_feedback (existing)

  submit_answer(q2) → WRONG
    → detect() → None (unclassified error)
    → PracticeAttempt.misconception_id = null

  Next session (create_session for the same child+topic)
    → query PracticeAttempt.misconception_id (child+topic, recency window)
      → {M1}  (single source of truth — no in-memory state)
    → select_questions(topic_id, misconception_ids={M1})  (NEW parameter)
    → M1's diagnostic question injected as candidate (difficulty bypass)
      and boosted to front
    → child gets targeted practice silently

Smart Tutor Flow (with misconception context):

  record_tutoring_step(
    session_id, question_id, phase="misconception_correction",
    misconception_id=M1,                        (NEW)
    ...
  )
    → tool handler resolves misconception_id → Misconception record
      (validates it belongs to the session's topic; uses the DB's
       category, not a caller-provided value)
    → step record in progress_json includes {description, category}
    → response to LLM includes misconception context
    → SKILL.md instructs category-specific framing
    → SmartTutorSessionResponse.misconceptions_detected
      = derived at serialization from unique misconceptions
        in the session's step records (deduplicated)
      = [{misconception_id, category, description}, ...]
```

The derivation is computed at response-serialization time from the session's step records — `misconceptions_detected` is not a stored session field.

---

## Implementation Units

- U6. **Add `category` column to Misconception + backfill seed data**

**Goal:** The Smart Tutor's category-specific feedback framing (concept_confusion / procedural_error / carelessness) requires a category field that does not exist on the current `Misconception` model. U4 and U5 depend on it.

**Requirements:** R8 (category drives feedback tone)

**Dependencies:** None (independent of U1; can land first)

**Files:**
- Modify: `server/packages/db/models/learning/misconception.py`
- Create: `server/apps/backend/alembic/versions/mc001misc0002_add_misconception_category.py`
- Modify: `server/scripts/seed_misconceptions.py` (backfill categories on seed rows)
- Modify: `server/packages/db/models/learning/misconception.py` (add `ondelete` handling to `MisconceptionDetection.misconception_id` — SET NULL requires making it nullable; folded into the same migration)
- Test: `server/tests/backend/scripts/test_seed_misconceptions.py` (extend)

**Approach:**
- Add nullable `category: Mapped[str | None]` column (String(30)) to `Misconception` with CHECK-style validation in the model, enum values: `concept_confusion`, `procedural_error`, `carelessness`
- Add `ondelete="SET NULL"` and `nullable=True` to `MisconceptionDetection.misconception_id` (currently NOT NULL with no ondelete — topic deletion cascades to misconceptions and would IntegrityError on the detection rows)
- Migration adds both column changes; existing detection rows default to `concept_confusion` via backfill
- Update `seed_misconceptions.py` to write category per entry; re-seed is idempotent
- The category is a property of the misconception, not the error pattern — the same wrong answer can reveal different categories across topics

**Patterns to follow:**
- `server/packages/db/models/learning/misconception.py` — existing column patterns
- Alembic migration naming from `mc001misc0001_add_misconception_tables.py`

**Test scenarios:**
- Happy path: Misconception created with category `concept_confusion` persists correctly
- Happy path: Category is nullable — Misconception without category persists (backward compatible)
- Edge case: Invalid category value rejected (model-level validation)
- Integration: Migration applies cleanly; backfill assigns `concept_confusion` to all existing rows

**Verification:**
- `uv run alembic upgrade head` applies without errors
- `uv run pytest tests/backend/scripts/test_seed_misconceptions.py -v` passes
- Seed data has non-null categories for all pilot misconceptions

---

- U1. **Add `misconception_id` column to PracticeAttempt**

**Goal:** Annotate each practice attempt with the detected misconception (if any), enabling fast queries for adaptive selection.

**Requirements:** R4, R5

**Dependencies:** U6 (category column must exist for the savepoint write path to reference the full misconception state)

**Files:**
- Modify: `server/packages/db/models/learning/practice.py`
- Create: `server/apps/backend/alembic/versions/mc001misc0003_add_practice_attempt_misconception_id.py`
- Test: `server/tests/backend/models/test_practice_attempt_misconception.py`

**Approach:**
- Add nullable `misconception_id: Mapped[int | None]` column to `PracticeAttempt` with FK to `misconceptions.id` (ON DELETE SET NULL)
- Index on `(child_id, topic_id, misconception_id)` for efficient "find recent misconceptions for this child+topic" queries during selection
- Alembic migration adds the column with `nullable=True` (existing rows remain null)
- No backfill needed — old attempts have no misconception data

**Patterns to follow:**
- `server/packages/db/models/learning/practice.py` — existing column patterns
- `server/apps/backend/alembic/versions/mc001misc0001_add_misconception_tables.py` — migration naming

**Test scenarios:**
- Happy path: PracticeAttempt can be created with `misconception_id` set to a valid Misconception
- Happy path: PracticeAttempt can be created with `misconception_id=None` (backward compatible)
- Edge case: Query attempts by `(child_id, topic_id)` where `misconception_id IS NOT NULL` returns only annotated attempts
- Integration: Migration applies cleanly on SQLite and PostgreSQL

**Verification:**
- `uv run alembic upgrade head` applies without errors
- `uv run mypy packages/db` passes
- Existing practice tests still pass

---

- U2. **Wire misconception detection into PracticeAttempt annotation**

**Goal:** Update the practice router to set `PracticeAttempt.misconception_id` when a misconception is detected (in addition to the existing `MisconceptionDetection` recording).

**Requirements:** R5

**Dependencies:** U1

**Files:**
- Modify: `server/apps/backend/app/routers/practice.py`
- Test: `server/tests/backend/routers/test_practice_misconception.py` (extend existing)

**Approach:**
- In `submit_practice_answer()`, after `detect_misconception()` returns a match, set `attempt.misconception_id = misconception.id` before `db.commit()`
- The existing `MisconceptionDetection` recording is preserved (dual-write for different query patterns)
- The existing `misconception_feedback` response building is unchanged

**Patterns to follow:**
- `server/apps/backend/app/routers/practice.py` — existing detection flow at lines 240-285

**Test scenarios:**
- Happy path: Wrong answer matching a misconception → `attempt.misconception_id` is set to the matched misconception's ID
- Happy path: Wrong answer not matching → `attempt.misconception_id` is None
- Happy path: Correct answer → `attempt.misconception_id` is None (detection not run)
- Integration: Both `PracticeAttempt.misconception_id` and `MisconceptionDetection` row are created for the same detection

**Verification:**
- `uv run pytest tests/backend/routers/test_practice_misconception.py -v` passes
- `uv run ruff check apps/backend/app/routers/practice.py` passes

---

- U3. **Adaptive selection boosting for misconception-aware question ordering**

**Goal:** Extend `select_questions()` to accept detected misconception IDs and boost diagnostic questions targeting those misconceptions to the front of the candidate list.

**Requirements:** R4, R5

**Dependencies:** U1

**Files:**
- Modify: `server/apps/backend/app/services/learning/adaptive_service.py`
- Modify: `server/apps/backend/app/routers/practice.py` (pass misconception_ids to select_questions)
- Test: `server/tests/backend/services/learning/test_adaptive_misconception_boost.py`

**Approach:**
- Add optional `misconception_ids: set[int] | None = None` parameter to `select_questions()`
- When `misconception_ids` is provided and non-empty:
  1. Query the `Misconception` table for each misconception's `diagnostic_question_id` (singular FK on the model — one diagnostic question per misconception) where `id IN misconception_ids` AND `diagnostic_question_id IS NOT NULL`
  2. Build a set of diagnostic question IDs to boost
  3. After the existing candidate query (topic + difficulty + review_status filter), partition candidates into `boosted` (in diagnostic set) and `normal` (rest)
  4. Diagnostic questions NOT already in the candidate set are injected as explicit candidates (bypassing the difficulty filter, mirroring the existing `is_diagnostic` bypass pattern in `practice.py`) — a struggling child's mastery-derived difficulty range may otherwise exclude the exact diagnostic question they need
  5. Return order: existing wrong-question prioritization (review mode) → boosted diagnostic questions → remaining candidates (shuffled)
- Boosting happens at session creation only (`create_practice_session`): the practice router queries `PracticeAttempt.misconception_id` for this child+topic within the recency window (last 30 attempts or 7 days) and passes the resulting set to `select_questions()`. Sessions have a fixed question list; there is no mid-session re-selection. R5's "within the session" semantics mean: a misconception detected in session N flows into the question selection of session N+1 (and later questions fetched in N if it resumes after an interruption — no new code path needed).
- Misconception boosting does not override review-mode wrong-question prioritization, but DOES override the difficulty filter via injection (see step 4). A misconception drops out of the boost set after 2 consecutive correct answers on its diagnostic questions, or when it falls outside the recency window.

**Patterns to follow:**
- `server/apps/backend/app/services/learning/adaptive_service.py` — existing review-mode wrong-question prioritization at lines 293-308 (same partition-then-concatenate pattern)
- `select_questions()` already handles exclusion sets and difficulty ranges — boosting is a post-filter reorder plus injection

**Test scenarios:**
- Happy path: `select_questions(misconception_ids={M1})` returns the diagnostic question for M1 before non-diagnostic questions
- Happy path: Without `misconception_ids` parameter, behavior is unchanged (backward compatible)
- Happy path: Diagnostic question whose difficulty is outside the child's mastery-derived range is still injected (difficulty bypass)
- Edge case: `misconception_ids` is empty set → no boosting, same as None
- Edge case: Misconception has `diagnostic_question_id=None` → no questions boosted for it
- Edge case: Diagnostic question is already in the exclusion set (recently answered) → not boosted (exclusion wins)
- Edge case: Multiple misconception_ids → questions for all are boosted, shuffled within the boosted group
- Edge case: Misconception resolved (2 consecutive correct diagnostic answers) → not boosted
- Integration: Practice router at session creation queries recent attempts' misconception IDs and passes them to select_questions

**Verification:**
- `uv run pytest tests/backend/services/learning/test_adaptive_misconception_boost.py -v` passes
- Existing adaptive selection tests still pass: `uv run pytest tests/backend/services/learning/test_adaptive_service.py -v`
- `uv run mypy apps/backend` passes

---

- U4. **Smart Tutor `record_tutoring_step` — add misconception context fields**

**Goal:** Extend the `record_tutoring_step` MCP tool to accept and persist misconception context, and upgrade the `misconceptions_detected` session field from `int` to `list[dict]`.

**Requirements:** R6, R7

**Dependencies:** U1

**Files:**
- Modify: `server/apps/backend/app/services/mcp_tool_registry.py` (tool schema)
- Modify: `server/apps/backend/app/services/mcp_session.py` (tool handler)
- Modify: `server/apps/backend/app/schemas/learning.py` (response schema)
- Modify: `server/apps/backend/app/routers/learning_family.py` (`_parse_smart_tutor_steps` — this function exclusively populates `misconceptions_detected`; change its int count to the deduplicated `list[dict]` derived from step-record misconception fields, update both call sites. The old `quality == "misconception"` count is dead code — `child_response_quality`'s enum has no "misconception" value — and is replaced entirely.)
- Modify: `frontend/apps/main/src/api/learning.ts` (type update — `misconceptions_detected: number` → list type)
- Modify: `frontend/apps/main/src/pages/BabyLearningPage.vue` (comparison update — `> 0` → `.length > 0`, with Array.isArray guard at the usage site)
- Test: `server/tests/backend/services/learning/test_smart_tutor_misconception.py`

Note: `frontend/apps/child/src/composables/useSmartTutor.ts` does NOT read `misconceptions_detected` (verified by grep) — the sole frontend consumer is the parent-facing main app.

**Approach:**
- Add `misconception_id` (integer, optional) to `record_tutoring_step` input_schema. No caller-supplied category — the handler resolves it from the DB.
- In the tool handler: when `misconception_id` is provided, resolve it to the Misconception record and include `description`, `description_zh`, and `category` in the step record persisted to `progress_json`
- Upgrade `SmartTutorSessionResponse.misconceptions_detected` from `int` to `list[dict]` where each dict has `{misconception_id: str, category: str, description: str}`. The list is derived from unique misconceptions in the session's step records. The count is `len(list)`.
- Update `learning.ts` type: `misconceptions_detected: Array<{misconception_id: string, category: string, description: string}>`, and `BabyLearningPage.vue` comparison → `.length > 0`.
- Backward compatibility: if no steps have misconception data, the list is empty (equivalent to old `0`).

**Patterns to follow:**
- `server/apps/backend/app/services/mcp_tool_registry.py` — existing tool schema patterns
- `server/apps/backend/app/services/mcp_session.py` — existing `record_tutoring_step` handler
- `server/packages/db/models/learning/misconception.py` — Misconception model for resolving ID → description

**Test scenarios:**
- Happy path: `record_tutoring_step` with `misconception_id` → step record includes misconception description and category
- Happy path: `record_tutoring_step` without `misconception_id` → step record has no misconception data (backward compatible)
- Happy path: Session with 2 steps referencing the same misconception → `misconceptions_detected` list has 1 entry (deduplicated)
- Happy path: Session with steps referencing different misconceptions → list has multiple entries
- Edge case: `misconception_id` references a non-existent misconception → error or graceful skip (logged warning, step still recorded without misconception data)
- Edge case: `misconception_id` references a misconception from a different topic or family → rejected with a validation error (the tool validates topic membership before resolving; prevents cross-family data leaking into step records)
- Integration: Response schema change from int to list[dict] is correctly serialized

**Verification:**
- `uv run pytest tests/backend/services/learning/test_smart_tutor_misconception.py -v` passes
- `uv run mypy apps/backend` passes
- `pnpm -r typecheck` passes (frontend type update)
- Existing Smart Tutor tests still pass

---

- U5. **Smart Tutor SKILL.md — misconception-aware feedback instructions**

**Goal:** Update the Smart Tutor's SKILL.md prompt so the LLM knows how to respond when misconception context is provided, using category-specific emotional framing.

**Requirements:** R8

**Dependencies:** U4

**Files:**
- Modify: `server/apps/agent/skills/builtin/public/learning-smart-tutor/SKILL.md`

**Approach:**
- Add a new section "Misconception-Aware Feedback" to the SKILL.md body
- When `record_tutoring_step` returns a step with misconception data, the tutor should:
  - `concept_confusion`: "这是一个很常见的混淆" / "This is a very common mix-up — many students confuse X with Y." Name the specific confusion from the description. Emphasize the distinguishing insight.
  - `procedural_error`: "你的思路是对的，但步骤搞混了" / "You had the right idea but the steps got mixed up." Walk through the correct sequence.
  - `carelessness`: No misconception-specific feedback. The error doesn't indicate a conceptual gap. Treat as a normal wrong answer with encouragement to double-check.
- Instruct the tutor to use the `misconception_correction` phase with the "gentle" TeacherAvatar emotion when addressing a detected misconception
- The "你不是笨，是搞混了" framing applies specifically to `concept_confusion` — the tutor should explicitly say "this is not about being wrong, it's about mixing up two similar ideas"

**Patterns to follow:**
- `server/apps/agent/skills/builtin/public/learning-smart-tutor/SKILL.md` — existing phase and persona patterns
- The existing `misconception_correction` phase already maps to "gentle" emotion in `TeacherAvatar.vue`

**Test scenarios:**
- Test expectation: none — SKILL.md is a prompt document, not executable code. Verification is via manual testing in the Smart Tutor session and the numina-sim-test Area 17 test cases.

**Verification:**
- SKILL.md renders correctly (valid markdown, no broken frontmatter)
- The Smart Tutor session correctly receives misconception context via the `record_tutoring_step` tool result (verified in U4 integration tests)

---

## System-Wide Impact

- **Interaction graph:** The practice submit-answer path gains one additional column write (`PracticeAttempt.misconception_id`). The `select_questions()` function gains an optional parameter. The `record_tutoring_step` MCP tool gains optional fields. All changes are additive and backward-compatible.
- **Error propagation:** Misconception detection failures never block the practice flow. The detection writes (`PracticeAttempt.misconception_id` + `MisconceptionDetection`) run inside a savepoint nested in the answer-submission transaction — if the Misconception row vanishes concurrently, only the annotation rolls back and the answer commit survives. `MisconceptionDetection.misconception_id` needs `ondelete` handling (topic deletion cascades to misconceptions; the detection rows currently have no ondelete clause and would raise IntegrityError on cascade) — folded into U1.
- **State lifecycle risks:** No in-memory state. Misconception IDs for selection are always re-derived from `PracticeAttempt` queries, multi-worker safe by construction.
- **API surface parity:** The `SmartTutorSessionResponse.misconceptions_detected` type change from `int` to `list[dict]` is breaking. The sole consumer is the parent-facing main app (`learning.ts` + `BabyLearningPage.vue`); both must be updated in the same deployment. The parent app's regression would otherwise be silent: `[{...}] > 0` evaluates falsy, making the badge disappear without any error.
- **Integration coverage:** The cross-layer scenario (wrong answer → detection → PracticeAttempt annotation → next session question boost → Smart Tutor context) requires end-to-end testing with seeded data.
- **Unchanged invariants:** The existing practice flow, BKT estimation, progress tracking, and teach-back flow are unaffected. The existing `MisconceptionDetection` table and `misconception_feedback` API response continue working as before. The existing `misconception_feedback` response is retained for API consumers and debugging; the child-facing card from the prior iteration is intentionally left unwired — emotional framing lives in the Smart Tutor dialogue (F3), not in practice UI.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `misconceptions_detected` type change breaks frontends | The sole consumer is the parent-facing main app (`learning.ts` type + `BabyLearningPage.vue` comparison → `.length > 0`); update in the same PR. The regression would otherwise be silent (falsy comparison hides the badge). Run a repo-wide grep for `misconceptions_detected` before shipping to catch any other consumers. |
| Misconception ID derivation adds a query per session creation | One indexed query on `(child_id, topic_id, misconception_id)` filtered by recency window. Negligible cost; runs once per session creation, not per answer. |
| Boosting may never fire if diagnostic question difficulty falls outside the child's derived range | Diagnostic questions are injected as explicit candidates bypassing the difficulty filter (mirroring the existing `is_diagnostic` bypass pattern in practice.py) when a misconception is in the boost set. Boosting is not merely a reorder — the misconception's diagnostic question is added to the candidate list even when its difficulty is outside the mastery-derived range. Pilot verification metric: fraction of detections where the diagnostic question actually appeared in the next session. |
| Existing `Misconception` model diverges from brainstorm's unified model decision | Documented as explicit decision. The separate model works. Follow-up trigger: if the pilot validates detection, file an issue for TopicConfusion/Misconception unification in the next quarter; until then, new misconception seeds must not duplicate existing TopicConfusion content for the same topic. |

---

## Sources & References

- **Origin document:** `docs/brainstorms/2026-11-16-misconception-catalog-requirements.md`
- Related code: `server/apps/backend/app/services/learning/adaptive_service.py`, `server/apps/backend/app/services/learning/misconception_detector.py`, `server/apps/backend/app/services/mcp_tool_registry.py`
- Related issue: #214
- Related issues (dependencies): #212 (BKT — merged), #213 (prerequisite diagnosis — merged)
