---
date: 2026-11-17
topic: misconception-non-calc-extension
---

# Misconception Detection: Non-Calculation Question Types

## Problem Frame

Misconception detection currently runs only on `calculation` questions — gated by a hard type check in `misconception_service.py:48`. When a child answers a fill_in_blank or multiple_choice question incorrectly, the system records a generic wrong answer with no misconception annotation. This means two children who pick the same wrong MC option (revealing the same conceptual confusion) are treated identically to a child who made an arithmetic slip — the adaptive engine and Smart Tutor cannot distinguish them.

Extending detection to `fill_in_blank` and `multiple_choice` closes this gap for the question types that already exist in the bank, without requiring new seed data for every topic.

---

## Requirements

**Detection engine**

- R1. Remove the `question_type != "calculation"` gate in `misconception_service.py`. Detection should run for any question type whose answer format is compatible with at least one registered match type.
- R2. Add a `text_match` match type to `misconception_detector.py` for fill_in_blank and text-based answers. Matching compares the user's answer string against `expected_wrong` after normalization (strip whitespace, case-insensitive). The `normalize` flag in the pattern controls whether normalization is applied (default: true).
- R3. Add an `option_select` match type to `misconception_detector.py` for multiple_choice questions. The pattern contains a `wrong_options` list of option keys (e.g., `["B", "C"]`). A match occurs when the user's selected option key is in the list.
- R4. Make the `_SAFE_MATH_RE` input validation conditional. It should only apply to `symbolic`, `numeric`, and `parametric` match types. `text_match` and `option_select` bypass math-expression validation since they operate on plain text and option keys respectively.

**Seed data**

- R5. Add 2 sample fill_in_blank misconceptions and 2 sample multiple_choice misconceptions to `seed_misconceptions.py` for the existing fraction-addition pilot topic (`mt_9KmVWCuh5_`). Each includes a linked diagnostic question of the matching `question_type`.

---

## Acceptance Examples

- AE1. **Covers R3.** Given a multiple_choice question where options B and C both reflect the "add numerators and denominators" misconception, and the child selects option B, `detect_misconception()` returns the matching misconception. The PracticeAttempt is annotated with this `misconception_id`.
- AE2. **Covers R2.** Given a fill_in_blank question where the expected wrong answer is "分子" (numerator), and the child submits "分子 " (with trailing space), the normalized `text_match` comparison succeeds and returns the matching misconception.
- AE3. **Covers R1, R4.** Given a fill_in_blank question where the child submits a numeric answer like "3.14", the existing `numeric` match type is used (not `text_match`). The `_SAFE_MATH_RE` gate passes because the answer is a valid math expression. Detection proceeds normally.
- AE4. **Covers R1.** Given a fill_in_blank question where the child submits "光合作用" (photosynthesis — a Chinese text answer), the `text_match` match type handles it without requiring `_SAFE_MATH_RE` validation. If no misconception pattern matches, detection returns None (unclassified error).

---

## Success Criteria

- A child who picks a wrong MC option linked to a known misconception receives the same adaptive boosting and Smart Tutor context as a child who makes a matching calculation error.
- Fill-in-blank answers with minor formatting differences (trailing spaces, case) still match their intended misconception patterns.
- No regression: existing calculation-type detection remains unchanged. All current seed misconceptions and parametric algorithms continue to work.
- New detection adds <5ms per attempt (deterministic string/option comparison, no I/O).
- The pilot fraction topic has 2 fill_in_blank and 2 multiple_choice misconceptions with working detection rules and linked diagnostic questions.

---

## Scope Boundaries

- **No new match types beyond `text_match` and `option_select`.** Additional types (regex, keyword-contains, fuzzy matching) are deferred until a concrete topic requires them.
- **No LLM-based detection.** All matching remains rule-based and deterministic.
- **No changes to the Misconception or MisconceptionDetection models.** The existing schema (error_pattern_json, wrong_answer_json) already supports the new match types without migration.
- **No frontend changes.** Detection is invisible to the child — it improves adaptive selection and Smart Tutor context only.
- **No cross-question-type inference.** A misconception is still scoped to a single topic. Detection on MC doesn't inform detection on fill_in_blank for the same topic unless the seed data explicitly defines the same misconception for both.
- **Pilot limited to the existing fraction-addition topic.** Expanding seed data to other topics is deferred.

---

## Key Decisions

- **Extend in-place (Approach A):** New match types are added to the existing `misconception_detector.py` alongside `symbolic`/`numeric`/`parametric`. Rationale: the match-type dispatch is already the natural extension point. The file is ~340 lines — small enough to stay unified. Splitting into per-question-type detectors (Approach B) adds a redundant dispatch layer for only 2 new types.
- **Option-key mapping for MC:** Each misconception declares which wrong options indicate it via `wrong_options: ["B", "C"]`. Rationale: simpler than per-option misconception mapping (which requires a bidirectional lookup), and matches the existing pattern where one misconception can be detected by multiple wrong answers.
- **Normalized text matching for fill_in_blank:** Strip whitespace and case-insensitive by default. Rationale: children may add trailing spaces or use inconsistent casing. Exact byte-match would be brittle without value.
- **Existing numeric/symbolic reused for numeric fill_in_blank:** When a fill_in_blank answer is numeric (e.g., "3.14"), the existing `numeric` or `symbolic` match types handle it. No new match type needed for numeric fill-in-blank.

---

## Dependencies / Assumptions

- The `Question.options_json` field stores MC options in a format where option keys (A/B/C/D) are stable and match what the frontend sends in `user_answer`. The detector reads the user's selected key from `user_answer["answer"]` (same path as calculation).
- Fill_in_blank answers arrive as `{"answer": "text string"}` — same dict shape as calculation answers. The existing `wrong_answer.get("answer")` extraction in `detect_misconception()` works without changes.
- The `Misconception.error_pattern_json` column is already a flexible JSON text field. New match types (`text_match`, `option_select`) fit the existing schema without migration.
- The existing `MisconceptionDetection.wrong_answer_json` can store non-math answer dicts without issues — it's already a JSON text column.

---

## Outstanding Questions

### Deferred to Planning

- [Affects R5][Technical] What specific fraction misconceptions are appropriate for fill_in_blank and multiple_choice formats? Need to author pedagogically sound wrong answers for the seed data (e.g., what wrong options make sense for "What is the numerator of 1/2 + 1/3?").
- [Affects R3][Technical] Should the `option_select` pattern also validate that the selected option key actually exists in the question's options list? Or trust that the scoring layer already validated the answer before detection runs?
- [Affects R2][Technical] Should `text_match` support substring or keyword matching in addition to exact normalized match? Deferred until a concrete use case requires it — exact match covers the pilot.

---

## Next Steps

-> `/ce-plan` for structured implementation planning
