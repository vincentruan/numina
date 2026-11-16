---
date: 2026-11-16
topic: misconception-catalog
---

# Common Misconception Catalog (常见误解诊断题)

## Problem Frame

Children who answer practice questions incorrectly currently receive only a binary signal: correct or wrong. The system knows *that* they erred but not *why*. Two children who both get `1/3 + 1/4 = 2/7` wrong may have completely different cognitive states — one added numerators and denominators (a known misconception), the other made an arithmetic slip (carelessness). Without distinguishing these, the adaptive engine treats all errors equally and the Smart Tutor can only count misconceptions (`misconceptions_detected: int`) without identifying what specific confusion the child holds.

This feature builds a **misconception catalog** — a structured library of known error patterns per topic — and wires it into the practice loop so the system can detect *which* misconception a child's answer reveals, then silently adapt question selection to address it. The Smart Tutor's existing `misconception_correction` phase gains specific misconception context so it can frame corrections as "this is a common mix-up" rather than generic encouragement.

**Pilot scope:** 3 fraction topics that already have TopicConfusion seed data (Understanding fractions, Fractions of a whole, Equivalent fractions).

---

## Key Flows

- F1. Misconception detection on wrong answer
  - **Trigger:** Child submits a wrong answer in practice
  - **Actors:** scoring_service, misconception_detector (new), PracticeAttempt
  - **Steps:** scoring_service.check_answer returns wrong → misconception_detector.match(topic_id, question_type, user_answer, correct_answer) runs rule-based pattern matching against the topic's catalog entries → if a pattern matches, write `misconception_id` on the PracticeAttempt
  - **Outcome:** The wrong attempt is annotated with which misconception (if any) caused it
  - **Covered by:** R1, R2, R3

- F2. Adaptive question selection with misconception awareness
  - **Trigger:** Next practice session starts or continues
  - **Actors:** adaptive_service, misconception catalog
  - **Steps:** select_questions checks if the child has recent attempts with detected misconceptions → if so, preferentially selects diagnostic questions linked to those misconceptions → child receives targeted practice without seeing any new UI
  - **Outcome:** Questions addressing the child's specific misconception appear earlier in the session
  - **Covered by:** R4, R5

- F3. Smart Tutor misconception-informed dialogue
  - **Trigger:** Smart Tutor session encounters a wrong answer with a detected misconception
  - **Actors:** Smart Tutor LLM, record_tutoring_step, misconception catalog
  - **Steps:** record_tutoring_step receives misconception context (misconception_id, description, category) → SKILL.md prompt instructs tutor to frame correction as "this is a common confusion" and address the specific error pattern → tutor uses gentle persona (already mapped to misconception_correction phase)
  - **Outcome:** Child receives emotionally supportive, misconception-specific guidance
  - **Covered by:** R6, R7

---

## Requirements

**Data model**

- R1. The existing `TopicConfusion` model is extended into a unified `Misconception` model (rename table to `misconceptions`). The base model gains: `error_pattern` (JSON — describes the detectable wrong-answer signature), `category` (enum: `concept_confusion` | `procedural_error` | `carelessness`), `diagnostic_question_id` (nullable FK to a single diagnostic question that targets this misconception). Teach-back-specific fields (`rubric`, `expected_expression`) remain as nullable columns that only teach-back rows populate.
- R2. Each misconception entry is scoped to a `topic_id` + `age_group` (matching the existing TopicConfusion scoping). The `review_status` field (`pending` / `approved`) is retained as the visibility gate.

**Detection engine**

- R3. A new `misconception_detector` service provides `match(topic_id, question_type, user_answer, correct_answer) -> misconception_id | None`. For the pilot, it operates on `calculation` and `multiple_choice` question types by comparing the user's wrong answer against each approved misconception's `error_pattern` for that topic. Pattern matching is deterministic and synchronous — no LLM calls. Returns `None` when no known pattern matches (the error is unclassified, not forced into a misconception).

**Adaptive selection**

- R4. `select_questions` in `adaptive_service.py` gains an optional `misconception_ids` parameter. When provided, candidate questions whose `id` appears in any matched misconception's `diagnostic_question_ids` are boosted to the front of the candidate list (after existing wrong-question prioritization in review mode, before random shuffle).
- R5. After each practice attempt is scored, the calling code checks for a misconception match and passes detected misconception IDs to the next question selection call within the same session. No separate "diagnostic session" — misconception-targeted questions flow through normal adaptive selection.

**Smart Tutor integration**

- R6. The `record_tutoring_step` MCP tool accepts an optional `misconception_id` field. When present, the tool resolves it to the misconception's `confusion_text` + `category` and includes these in the step record's `progress_json`. The Smart Tutor's SKILL.md is updated with instructions for misconception-aware feedback: frame as common confusion, name the specific mix-up, suggest the distinguishing insight.
- R7. The `misconceptions_detected` field on Smart Tutor session responses is upgraded from `int` to a structured list: `[{misconception_id, category, description}]`. The count is derived from the list length. This is a breaking schema change — the field type changes from `int` to `list[dict]`.

**Emotional framing**

- R8. Each misconception's `category` drives the feedback tone in the Smart Tutor prompt: `concept_confusion` → "This is a very common mix-up — many students confuse X with Y"; `procedural_error` → "You had the right idea but the steps got mixed up"; `carelessness` → no misconception-specific feedback (the error doesn't indicate a conceptual gap). The "你不是笨，是搞混了" framing applies specifically to `concept_confusion` category.

**Seed data**

- R9. For the 3 pilot fraction topics, author 2-3 misconceptions per topic with hand-crafted `error_pattern` rules and link 1-2 existing approved questions per misconception as diagnostic questions. Seed rows are written `review_status = "approved"`. The existing TopicConfusion seed data is migrated to the new schema.

---

## Acceptance Examples

- AE1. **Covers R1, R3.** Given a child answers `1/3 + 1/4 = 2/7` on a fraction addition question, `misconception_detector.match()` returns the "add numerators and denominators separately" misconception (category: `concept_confusion`). The PracticeAttempt is annotated with this `misconception_id`.
- AE2. **Covers R4, R5.** Given the child's last attempt detected a `concept_confusion` misconception, the next question selected for the session is one of the diagnostic questions linked to that misconception. The child sees it as a normal practice question.
- AE3. **Covers R6, R7, R8.** Given a Smart Tutor session where the child's wrong answer matched a `concept_confusion` misconception, the tutor's response includes the misconception description and frames it as "this is a common confusion" using the gentle persona. The session's `misconceptions_detected` field contains `[{misconception_id: "...", category: "concept_confusion", description: "..."}]`.
- AE4. **Covers R3.** Given a child answers `1/3 + 1/4 = 4/12` (a carelessness error — wrong arithmetic, not a conceptual pattern), `misconception_detector.match()` returns `None`. No misconception is recorded. The adaptive engine treats this as a generic wrong answer.

---

## Success Criteria

- A child who makes the same conceptual error twice receives a targeted diagnostic question on the second occurrence, without any new UI or interruption.
- The Smart Tutor names the specific misconception in its dialogue (not generic "try again") when one is detected.
- The `misconceptions_detected` field on session responses identifies *which* misconceptions, not just how many.
- No regression in practice session latency — misconception detection adds <5ms per attempt (deterministic pattern matching, no I/O).
- The 3 pilot fraction topics each have 2-3 hand-authored misconceptions with working detection rules and linked diagnostic questions.

---

## Scope Boundaries

- **No LLM-based misconception detection in V1.** Detection is rule-based only. LLM classification for question types where rules can't capture patterns (e.g., application word problems) is deferred.
- **No new frontend components.** Misconception detection is invisible to the child — it improves question selection and Smart Tutor dialogue only. No "misconception detected" cards, badges, or parent-facing dashboards.
- **No misconception authoring UI.** Seed data is hand-authored in migration files. A parent/admin tool for authoring misconceptions is out of scope.
- **No cross-topic misconception inference.** Each misconception is scoped to a single topic. Detecting that a child's error on topic B stems from a misconception in prerequisite topic A is deferred (the existing prerequisite backtrace diagnosis from #213 handles that path separately).
- **No changes to BKT estimation.** Misconception detection annotates attempts but does not feed back into BKT parameter estimation. The mastery model remains independent.
- **Pilot limited to 3 fraction topics.** Expanding the catalog to other subjects/topics is deferred until the pilot validates the detection accuracy and seed data quality.

---

## Key Decisions

- **Unified model (not separate catalog):** TopicConfusion is extended into a Misconception model rather than building a parallel table. Rationale: both represent per-topic known misunderstandings; teach-back and practice detection share the same misconception knowledge. Teach-back-specific fields become nullable extensions.
- **Rule-based detection (not LLM):** Deterministic pattern matching for V1. Rationale: zero latency overhead, no cost per wrong answer, fully deterministic (same input → same detection), testable without mocking LLM responses. LLM fallback can be added later for unclassifiable errors.
- **Silent adaptive selection (not intervention cards):** Misconception-targeted questions flow through normal adaptive selection. Rationale: no new UI surface, no interruption to practice flow, child doesn't need to know they're being "diagnosed" — it just feels like smarter question ordering.
- **Smart Tutor prompt enhancement (not backend feedback messages):** Emotional framing is handled by the Smart Tutor LLM via enhanced prompt instructions. Rationale: the `misconception_correction` phase with "gentle" persona already exists; adding misconception context to its input is minimal new surface. Avoids duplicating emotional intelligence in backend templates.
- **Fraction pilot (not all topics):** Start with 3 topics that have existing TopicConfusion data. Rationale: proves the full pipeline end-to-end with minimal new seed data, validates detection accuracy before scaling.

---

## Dependencies / Assumptions

- The existing TopicConfusion seed data for the 3 fraction topics can be migrated to the new Misconception schema without data loss. The existing `confusion_text` maps to the misconception description, and `rubric`/`expected_expression` are retained as teach-back extensions.
- There are existing approved questions for the 3 fraction topics that can serve as diagnostic questions (linked via `diagnostic_question_ids`). If not, new questions need to be authored as part of R9.
- The `PracticeAttempt` model can accept a nullable `misconception_id` column via migration without affecting existing attempts (they remain `null`).
- The Smart Tutor's `record_tutoring_step` MCP tool can accept an optional `misconception_id` parameter without breaking existing callers.

---

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Technical] How to handle the table rename from `topic_confusions` to `misconceptions` in Alembic — is a rename cleaner than creating a new table + data migration? The teach-back flow references `TopicConfusion` by class name extensively.
- [Affects R3][Technical] What is the `error_pattern` JSON schema for `calculation` question types? Need to define the pattern language (e.g., `{type: "fraction_add", rule: "numerator_sum/denominator_sum"}`) that the detector can evaluate against `user_answer` and `correct_answer`.
- [Affects R3][Technical] What is the `error_pattern` JSON schema for `multiple_choice` question types? Likely maps wrong option keys to misconception IDs (e.g., `{wrong_key: "B" -> misconception_id}`).
- [Affects R5][Technical] How does the practice session router pass detected misconception IDs to the next `select_questions` call? Is it an in-memory accumulation within the session, or re-queried from recent PracticeAttempt rows?
- [Affects R7][Needs research] What frontend code reads `misconceptions_detected: int`? The type change to `list[dict]` is breaking — need to assess the blast radius in the child frontend (`useSmartTutor.ts`, `SocraticSteps.vue`, parent dashboard).

---

## Next Steps

-> `/ce-plan` for structured implementation planning
