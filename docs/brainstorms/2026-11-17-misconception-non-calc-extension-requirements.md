---
date: 2026-11-17
topic: misconception-non-calc-extension
---

# Misconception Detection for Fill-in-Blank and Multiple Choice Questions

## Problem Frame

Misconception detection currently only runs for `calculation` question types. The filter in `misconception_service.py` returns early for any other type, preventing topics that use `fill_in_blank` or `multiple_choice` questions from triggering misconception diagnosis. This limits the adaptive learning system's ability to identify and address common errors across the curriculum.

---

## Requirements

**Answer data formats**
- R1. Fill-in-blank questions use `user_answer = {"answer": "<text or value>"}` — same format as calculation questions.
- R2. Multiple choice questions use `user_answer = {"selected": <int>}` where the integer is the zero-based index into `question.options_json`.

**Filter removal**
- R3. Remove the `question_type != "calculation"` hard-coded filter in `detect_and_record_misconception()` so detection runs for all question types.

**New match type for multiple choice**
- R4. Add a new `match_type: "option_selection"` to the misconception detector's error pattern schema.
- R5. The pattern contains `wrong_option_index: int` — detection triggers when `user_answer["selected"]` equals this index.

**Fill-in-blank answer handling**
- R6. Fill-in-blank answers reuse existing `symbolic` and `numeric` match types.
- R7. The `_SAFE_MATH_RE` safety regex must be bypassed when the answer is clearly non-mathematical text (e.g., contains letters outside variable names, spaces, or non-math symbols). Detection should still run with symbolic matching for text answers.

**Seed data**
- R8. Add at least one seed misconception example for `fill_in_blank` questions.
- R9. Add at least one seed misconception example for `multiple_choice` questions using the new `option_selection` match type.

**Test coverage**
- R10. Tests must verify misconception detection works for `fill_in_blank` questions with symbolic matching.
- R11. Tests must verify misconception detection works for `multiple_choice` questions with option index matching.
- R12. Update or replace the existing `test_non_calculation_question_skips_detection` test — the behavior is changing.

---

## Success Criteria

- Misconception detection runs for `fill_in_blank` and `multiple_choice` questions without errors.
- Wrong answers matching seeded patterns trigger feedback for all three question types.
- All existing tests pass; new tests cover the extended functionality.
- No regression in calculation question detection.

---

## Scope Boundaries

- Parametric matching algorithms remain calculation-specific (fraction operations). No new parametric algorithms for fill_in_blank or multiple_choice in this iteration.
- No changes to the Smart Tutor feedback flow — it already consumes misconception feedback generically.
- No frontend changes — the feedback response schema is unchanged.
- No changes to question generation or selection logic.

---

## Key Decisions

- **Incremental extension over refactor:** Adding `option_selection` as a fourth match type keeps the detector structure intact. A type-specific handler dispatch was considered but rejected as premature abstraction for only three question types.
- **Index-based MCQ matching:** Multiple choice misconceptions map to specific wrong option indices. This is simpler than per-option misconception maps and matches the data model where each option represents a distinct error path.
- **Relaxed safety regex for text answers:** The `_SAFE_MATH_RE` regex was designed to prevent code injection in math expressions. For fill-in-blank text answers, we bypass this check when the answer contains non-math characters, since symbolic matching via SymPy already rejects non-math input.

---

## Dependencies / Assumptions

- The `question.options_json` field stores multiple choice options as a JSON array of strings, indexed from 0.
- Fill-in-blank answers are stored in the same `answer_json` format as calculation questions.
- The existing `symbolic_eq` function can handle simple text comparisons (not just math expressions).

---

## Next Steps

-> `/ce-plan` for structured implementation planning
