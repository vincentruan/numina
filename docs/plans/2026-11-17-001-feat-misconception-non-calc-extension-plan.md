---
title: "feat: Extend misconception detection to fill_blank and multiple_choice"
type: feat
status: completed
date: 2026-11-17
origin: docs/brainstorms/2026-11-17-misconception-non-calc-requirements.md
---

# feat: Extend Misconception Detection to Non-Calculation Question Types

## Overview

Extend the misconception detection engine to support `fill_blank` and `multiple_choice` question types.

**Re-baselined 2026-11-17 (review round 1).** Most of the originally-planned scope has already landed on this branch:

| Commit | Landed |
|--------|--------|
| `fac0ef11` | `text_match` and `option_select` match types added to `misconception_detector.py` |
| `6df4bbfd` | calculation-only gate removed from `misconception_service.py` |
| `478b8c58` | fill_blank and multiple_choice seed misconceptions (sequences 3–6) |
| `6da43895` | seed `wrong_options` correction + test import order |

`text_match` (with `expected_wrong` + `normalize`) covers the fill_blank text case, and `option_select` (with `wrong_options: list[str]`) covers the multiple_choice case. A new `option_key` match type is therefore **not** being added — that would duplicate `option_select`.

What remains is a set of defects that make the landed work non-functional end-to-end. They are the subject of this plan.

---

## Problem Frame

Misconception detection was originally gated to `calculation` questions. That gate is gone, and the match types for non-calc question types exist. But three defects currently prevent the feature from working for real submissions:

1. **Multiple-choice answers never reach matching.** `detect_misconception()` extracts `wrong_answer.get("answer")` then `.get("value")`, returning `None` when both are absent (`misconception_detector.py:110-114`). The child app submits `{ key }` for `multiple_choice` (`PracticeAnswerInput.vue:171-172`), so every real MCQ submission is dropped before the dispatch loop.
2. **Seeded MCQ diagnostic questions have no options.** `seed_misconceptions.py` constructs `Question(...)` without `options_json` (lines 266–277) while the seed data carries an `options` list — the loader silently discards it.
3. **Seed data uses two non-canonical formats.** Seeded fill_blank diagnostic questions use `question_type: "fill_in_blank"`, which `check_answer` does not handle (it handles `fill_blank`), and seeded MCQ `answer` dicts use `{"answer": "B"}` where scoring reads `.get("key")`. Both cause silent grading failure.

(see origin: docs/brainstorms/2026-11-17-misconception-non-calc-requirements.md)

---

## Requirements Trace

- R1. ~~Remove the `question_type != "calculation"` gate~~ — **done** in `6df4bbfd`
- R2. Fill-blank answers reuse `text_match`/`numeric`; answers arrive as `user_answer = {"value": ...}` from the child app, which the detector prelude already extracts
- R3. Multiple-choice matching uses the existing `option_select` match type with `wrong_options: list[str]` (e.g. `["B"]`), matching the scoring contract `user_answer = {"key": "A"}` and `options_json = [{"key": "A", "text": ...}]`
- R4. `_SAFE_MATH_RE` remains a guard on the SymPy path only; text answers reach `text_match`, which never touches SymPy — **done** in `fac0ef11`, no further work
- R5. Seed misconceptions for fill_blank and multiple_choice exist — **done** in `478b8c58`, but the loader and row formats need fixing (U2)

**Origin acceptance examples** (restated against the landed match types):
- AE1 (covers R3): MC user selects wrong option key "B" → `option_select` with `wrong_options: ["B"]` matches
- AE2 (covers R4): fill_blank text answer ("分子" / "denominator") matches via `text_match` without passing through `_SAFE_MATH_RE`
- AE3 (covers R1): numeric fill_blank answer uses existing `numeric` match type
- AE4 (covers R1, R3): multiple_choice question with `{"key": ...}` answer triggers detection end-to-end

---

## Scope Boundaries

- No new match types — `text_match` (fill_blank) and `option_select` (multiple_choice) already exist and are sufficient
- No LLM-based detection — all matching remains rule-based
- No changes to Misconception or MisconceptionDetection models (existing schema supports the new types)
- No frontend changes — the child app already emits the correct payload shapes; the backend is what needs fixing
- No cross-question-type inference
- Pilot limited to existing fraction-addition topic

---

## Context & Research

### Relevant Code and Patterns

- `server/apps/backend/app/services/learning/misconception_detector.py` — five match types now exist: `symbolic`, `numeric`, `parametric`, `text_match` (`_match_text`, line 258), `option_select` (`_match_option_select`, line 282). The prelude at lines 110–114 extracts only `answer` and `value`.
- `server/apps/backend/app/services/learning/scoring_service.py` — the authoritative payload contract per question type: `calculation`/`application` read `answer`, `fill_blank`/`true_false` read `value`, `multiple_choice` reads `key` (line 34), `multi_fill_blank` reads `blanks`, `ai_graded` reads `text`
- `server/apps/backend/app/services/learning/misconception_service.py` — `detect_and_record_misconception()`; the calculation gate is already gone
- `server/tests/backend/services/learning/test_misconception_detector.py` — `TestTextMatch`, `TestOptionSelect` classes exist; fixtures pass `{"answer": "B"}` where production sends `{"key": "B"}`
- `server/scripts/seed_misconceptions.py` — `SAMPLE_MISCONCEPTIONS` keyed by `topic_key`; loader at lines 266–277 omits `options_json`
- `server/packages/db/models/learning/question.py` — `options_json: Mapped[str | None]` (line 36), exposed as `options` via `json_text`
- `frontend/apps/child/src/components/learning/PracticeAnswerInput.vue` — emits `{ key }` for `multiple_choice` (line 172), `{ value: raw }` for fill_blank (line 186)

### Institutional Learnings

- The detector's match-type dispatch works well; the landed `text_match`/`option_select` follow the established shape and need no restructuring
- `_PARAMETRIC_HANDLERS` shows the team prefers dict-based dispatch over if/elif chains
- `_SAFE_MATH_RE` is a security gate against SymPy injection. `text_match` and `option_select` correctly never touch SymPy, so the gate never needs to move — the earlier idea of a symbolic-string fallback would have required reordering it and is not being pursued


---

## Key Technical Decisions

- **No new match types.** `text_match` and `option_select` already cover the two question types. Adding `option_key`/`wrong_option_key` would create a second mechanism for the same job, and seeded rows in the new shape would parse successfully then never match — silent failure with no error pointing at the cause. `option_select`'s `wrong_options: list[str]` is also the more expressive of the two: one misconception can cover several distractor keys.
- **Fix the answer-extraction prelude, not the matchers.** The matchers all take `(user_str, pattern)` and cannot see the raw dict. The only place `{"key": ...}` can be recovered is `detect_misconception()`'s prelude. Extending it is a three-line change that makes every existing match type work for MCQ payloads; putting the read inside `_match_option_select` is impossible without changing every matcher's signature.
- **`key` is the only MCQ extraction fallback to add.** `scoring_service.py:34` scores `multiple_choice` on `.get("key")` and the child app emits exactly `{ key }`. `answer`/`value` stay as the first two probes so existing calculation and fill_blank behavior is untouched.
- **Question-type names must be canonical in seed data.** `check_answer` dispatches on exact strings; `fill_in_blank` is not one of them. Seeded rows using it get `logger.warning("Unknown question_type for scoring")` and score `False` unconditionally — the child is marked wrong even when right.
- **`_SAFE_MATH_RE` does not move.** `text_match` and `option_select` never touch SymPy, so the existing per-matcher guards remain exactly where they are. There is no fallback-through-the-regex path to design, because no text-comparison logic lives inside `_match_symbolic`.

---

## Open Questions

### Resolved During Planning

- **Which match type for MC — new `option_key` or existing `option_select`?** — `option_select`. It is already implemented, already seeded, and already tested. `wrong_options: list[str]` subsumes a scalar `wrong_option_key`.
- **Which match type for fill_blank text?** — `text_match` with `expected_wrong` + `normalize`, already implemented at `_match_text` (line 258). It never touches SymPy, so CJK text needs no regex accommodation.
- **Which question type names exist?** — Verified in `scoring_service.py`: `calculation`, `fill_blank`, `multiple_choice`, `true_false`, `application`, `multi_fill_blank`, `ai_graded`. The type is `fill_blank`, not `fill_in_blank`.
- **What does the child app actually send?** — Verified in `PracticeAnswerInput.vue`: `{ key }` for multiple_choice, `{ value }` for fill_blank and true_false, `{ answer }` for calculation, `{ blanks }` for multi_fill_blank, `{ text }` for ai_graded.

### Deferred to Implementation

- **Whether to migrate the already-seeded rows or re-seed.** Sequences 3–6 exist with `fill_in_blank` and `{"answer": ...}` MCQ answers. The seed script upserts by `(topic_id, age_group, sequence)`, so correcting the source data and re-running will update existing rows — but the implementer should confirm the upsert path updates `answer_json` on an existing diagnostic question rather than skipping it. Trade-off to weigh: fixing the loader's question-lookup branch (which reuses an existing question by stem without updating it) may need a separate decision.


---

## Implementation Units

- U1. **Recover `{"key": ...}` from MCQ payloads in the detector prelude**

**Goal:** Make `detect_misconception()` accept the payload shape the child app actually sends for `multiple_choice`, so `option_select` matching can fire.

**Requirements:** R3

**Dependencies:** None

**Files:**
- Modify: `server/apps/backend/app/services/learning/misconception_detector.py`
- Test: `server/tests/backend/services/learning/test_misconception_detector.py`

**Approach:**
- Extend the prelude at lines 110–114 with a third probe after `answer` and `value`: `wrong_answer.get("key")`. Order matters — `answer` and `value` must stay first so calculation and fill_blank behavior is byte-identical.
- Update the `wrong_answer` docstring on `detect_misconception()` to name all three shapes and cite `scoring_service.py` as the contract per question type.
- Do **not** add a match type or touch `_match_option_select`. It already receives the extracted string and compares against `wrong_options`.
- Add tests that drive `detect_misconception()` with `{"key": "B"}` (no `answer`/`value`) — the shape production sends. Existing `TestOptionSelect` cases pass `{"answer": "B"}` and so never exercise the prelude path that production uses.

**Patterns to follow:**
- Existing explicit-None sequential probes at `detect_misconception()` lines 110–114 (the comment there explains why `or` is avoided — falsy `0` must not be treated as missing)
- `_match_option_select()` (`misconception_detector.py:282`) — unchanged

**Test scenarios:**
- Happy path: `wrong_answer={"key": "B"}` + `option_select` pattern with `wrong_options: ["B"]` returns the misconception
- Happy path: `wrong_answer={"key": "A"}` with the same pattern returns None
- Edge case: `{"key": None}` mixed with no `answer`/`value` returns None
- Edge case: `{"answer": "B"}` still matches (regression — the existing payload shape keeps working)
- Edge case: `{"answer": "2/7", "key": "B"}` prefers `answer` (probe order preserved)
- Integration: Covers AE1 and AE4 — MCQ submission with `{"key": "B"}` reaches matching end-to-end
- Security regression: `{"key": "__import__('os')"}` does not match any pattern and never reaches SymPy

**Verification:**
- `uv run pytest tests/backend/services/learning/test_misconception_detector.py -v` passes
- `uv run mypy apps/backend/app/services/learning/misconception_detector.py` passes
- `uv run ruff check apps/backend/app/services/learning/misconception_detector.py` passes

---

- U2. **Fix seed loader to persist `options_json` and canonical answer/type shapes**

**Goal:** Make seeded non-calc diagnostic questions actually gradable and renderable — `options_json` populated, `question_type` canonical, MCQ `answer` keyed by `key`.

**Requirements:** R5

**Dependencies:** None (independent of U1 — this is data, not detection)

**Files:**
- Modify: `server/scripts/seed_misconceptions.py`

**Approach:**
- Pass `options_json=json.dumps(diag_data["options"])` on the `Question(...)` construction at lines 266–277 when the diagnostic question carries an `options` key. Today the loader omits it entirely, so `QuestionPublicResponse.options` is `None` and the child sees an MCQ with no choices.
- Correct the seeded rows already on the branch: sequences 3–4 use `question_type: "fill_in_blank"` (lines 135, 161) and sequences 5–6 use `answer: {"answer": "B"}` / `{"answer": "C"}` (lines 196, 226). Change the former to `fill_blank` and the latter to `{"key": "B"}` / `{"key": "C"}`. Note the seeded fill_blank `expected_wrong` values are English ("denominator"/"numerator") while the stems are bilingual — if Chinese answers are to match, the pattern needs `expected_wrong` in the language the child will type, or the `text_match` comparator needs to cover both.
- Verify the upsert path updates an existing diagnostic question matched by stem rather than reusing it untouched — the loader's `existing_q is not None` branch reuses the row without updating `answer_json`/`options_json`, so re-running the script may leave corrected data unapplied. If so, the implementer needs to update that branch or re-seed cleanly.
- Seed options and answer data must contain no correct-answer markers or solution text beyond what the child is meant to see.

**Patterns to follow:**
- Existing `Question(...)` construction and `json.dumps` usage in the same function
- `scoring_service.py` `check_answer` dispatch as the authority on `question_type` strings and answer key names
- Description guidelines in the script header (age 10-12, ~120 chars zh, second person, encouraging)

**Test scenarios:**
- Update `tests/backend/scripts/test_seed_misconceptions.py`: it asserts the seeded count is 3 (two places, both failing today with `assert 7 == 3`) and that every row's `match_type == "parametric"`. Relax both — new total, and a known-match-type set covering `parametric`, `text_match`, and `option_select`.
- New assertion: every seeded `multiple_choice` diagnostic question has non-null `options_json` with ≥2 entries and an `answer` dict containing `key`
- New assertion: no seeded question uses `question_type == "fill_in_blank"`

**Verification:**
- `uv run python scripts/seed_misconceptions.py` runs without errors
- `uv run pytest tests/backend/scripts/test_seed_misconceptions.py -v` passes
- Seeded MCQ questions have non-null `options_json`; DB check: `SELECT COUNT(*) FROM questions WHERE question_type='multiple_choice' AND options_json IS NULL` returns 0 for seeded rows
- No seeded row uses `fill_in_blank`

---

- U3. **Replace the stale calculation-gate test with non-calc integration coverage**

**Goal:** Delete the test that asserts the now-removed gate, and cover the new question types through the practice API.

**Requirements:** R2, R3, R5

**Dependencies:** U1, U2

**Files:**
- Modify: `server/tests/backend/routers/test_practice_misconception.py`

**Approach:**
- Delete `test_non_calculation_question_skips_detection` (line 226). It fails today — detection now runs for `word_problem` and returns feedback — and it encodes behavior the branch deliberately removed.
- Add practice-API integration tests for `fill_blank` (via `text_match`) and `multiple_choice` (via `option_select` with a `{"key": ...}` submission). Build the MCQ question with `options_json` in `[{"key": "A", "text": ...}]` form and `answer_json={"key": "B"}` so both scoring and detection agree.
- Submit answers in the shape `PracticeAnswerInput.vue` emits: `{"value": "..."}` for fill_blank, `{"key": "B"}` for multiple_choice. Not `{"answer": ...}`.
- Keep the existing calculation-type tests untouched as the regression guard.

**Patterns to follow:**
- Existing class `TestMisconceptionDetectionInPracticeAPI` and its topic/question/misconception fixtures
- The session-membership workaround in the deleted test (`session.question_ids_json` append) — adaptive selection may not pick a newly-added question

**Test scenarios:**
- Happy path: fill_blank question + `{"value": "denominator"}` wrong answer triggers `text_match` feedback
- Happy path: multiple_choice question + `{"key": "A"}` wrong option triggers `option_select` feedback
- Regression: calculation question detection unchanged
- Edge case: non-matching fill_blank text returns null feedback
- Edge case: MCQ submission with a `key` that is not in `wrong_options` returns null feedback but still records the attempt

**Verification:**
- `uv run pytest tests/backend/routers/test_practice_misconception.py -v` passes
- `uv run mypy apps/backend/app/services/learning/misconception_detector.py` passes
- All existing tests pass (no regression)

---

## System-Wide Impact

- **Interaction graph:** `practice.py:submit_practice_answer` → `detect_and_record_misconception()` → `detect_misconception()`. The call chain is unchanged. U1 only widens the accepted payload shapes at the detector's entry point.
- **Error propagation:** Detection failure is already isolated (try/except in the router). No new failure modes — the added `key` probe is a dict `.get()` on the same object the existing probes read.
- **State lifecycle risks:** None. `MisconceptionDetection` rows are write-only (no updates/deletes). Widening extraction means more rows may be created for MCQ submissions, using the same row structure.
- **API surface parity:** No API changes. `MisconceptionFeedbackResponse` is unchanged.
- **Grading interaction (U2):** Fixing seeded `question_type` and MCQ `answer` keys changes whether seeded diagnostic questions grade correctly. That is the intent — today they score `False` unconditionally via the `Unknown question_type` warning path and via the `key` vs `answer` mismatch.
- **Unchanged invariants:** `symbolic`, `numeric`, `parametric`, `text_match`, and `option_select` matching logic is unchanged. The `answer`-then-`value` probe order is unchanged, so calculation and fill_blank behavior is byte-identical. `_SAFE_MATH_RE` guards stay exactly where they are. The `Misconception` and `MisconceptionDetection` models are unchanged. `error_pattern_json` is `Text` — no migration needed.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Adding a `key` probe could shift existing behavior | The probe is appended after `answer` and `value`, so any payload that matched before still matches identically. Test scenario covers a payload carrying both. |
| Re-running the seed script may not update already-seeded rows | The loader reuses a diagnostic question matched by stem without updating `answer_json`/`options_json`. U2 requires verifying this branch and either updating it or re-seeding cleanly. |
| Text matching may match too broadly | `text_match` normalizes by strip + lowercase against a short, specific `expected_wrong`. Tighten later if real answers collide. |
| Detection cost grows now that more submissions reach it | Match cost is O(approved misconceptions × per-type work) per wrong submission. `text_match` and `option_select` do no SymPy work, so the added MCQ path is cheap. A per-submission parse cap is a follow-up if load grows — note that the original claim this was bounded by "duplicate-attempt rules" was not verifiable on the practice router path. |
| Seed data quality — pedagogically unsound misconceptions | Keep descriptions aligned with existing guidelines. Review before merging. |

---

## Sources & References

- **Origin document:** `docs/brainstorms/2026-11-17-misconception-non-calc-requirements.md`
- Related code: `server/apps/backend/app/services/learning/misconception_detector.py`
- Related code: `server/apps/backend/app/services/learning/misconception_service.py`
- Related tests: `server/tests/backend/services/learning/test_misconception_detector.py`
- Related seed: `server/scripts/seed_misconceptions.py`
