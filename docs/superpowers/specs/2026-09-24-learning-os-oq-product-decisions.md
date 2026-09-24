# Learning OS — Product Decision Specs (OQ-2 / OQ-3 / OQ-6)

> Date: 2026-09-24
> Source: Code review `2026-09-23-learning-os-code-review.md` deferred items
> Scope: Requirements and product decisions only — implementation plan is separate
> **Status: All decisions confirmed** ✅

---

## OQ-2 — Topic Translation

### Current State

`translation.py` is a placeholder returning `None` for all fields. The `LearningTopic` model has 4 translated columns (`name_zh`, `description_zh`, `evidence_zh_json`, `assessment_prompt_zh`) that are never populated — seed data is English-only.

### Decision: On-Demand Translation via DeerFlow Agent

**Approach:** User-initiated, not batch. A DeerFlow translation agent translates topics on demand when the user explicitly requests it.

**Requirements:**

1. **Translation trigger** — A "translate" button in the UI, visible **only when the topic's source language differs from the user's interface language** (e.g., English topic + zh-CN user → show button; already-translated topic → hide button).

2. **Translation agent** — A new DeerFlow app (`learning-translate`) that receives a topic's English content and produces translated Chinese fields (`name_zh`, `description_zh`, `evidence_zh`, `assessment_prompt_zh`). The agent uses the user's selected language as the target locale.

3. **Persistence** — Translated fields are written back to the `LearningTopic` record. Subsequent reads use translated fields when available, falling back to English originals.

4. **Idempotency** — Re-translating an already-translated topic overwrites with fresh translation (supports re-translation after content updates).

5. **Scope** — Translation covers the 4 `_zh` fields. `ability_dimensions` (OQ-related) is out of scope for this decision.

6. **Language detection** — Button visibility logic: compare topic's source language (inferred from `name` vs `name_zh` presence, or an explicit `source_lang` field) against the user's `locale` setting. If they match or `name_zh` is already populated, hide the button.

### Out of Scope

- Batch translation of all topics at seed time
- Translation of topics outside the Learning OS module
- `derive_ability_dimensions()` implementation

---

## OQ-3 — Learning Failure Streak Notification

### Current State

`learning_streak_3_failures` is registered in the notification registry (category: `"learning"`, severity: `"warning"`, trigger: `"realtime"`). `LearningAssessmentAttempt` stores `passed: bool` per attempt. However, no code detects consecutive failures or emits the notification.

### Decision Points (choose one per dimension)

#### Dimension A: What constitutes a "failure"?

| Option | Definition | Pros | Cons |
|--------|-----------|------|------|
| **A1** | Assessment `passed=False` (AI judged the child did not demonstrate mastery) | Direct — uses existing `LearningAssessmentAttempt.passed` field | AI assessment reliability is uncertain (see F-04 in design review) |
| **A2** | Session ended with score below threshold (e.g., < 60%) | Quantitative, independent of AI judgment | Requires defining per-topic score thresholds |
| **A3** | Parent rejected the review (child submitted for review, parent said "not yet") | Parent-in-the-loop, high signal | Depends on parent engagement; slow feedback loop |

#### Dimension B: What is the "streak" window?

| Option | Definition | Pros | Cons |
|--------|-----------|------|------|
| **B1** | 3 consecutive failures on the **same topic** | Precise — identifies stuck topics | May rarely trigger if child switches topics |
| **B2** | 3 consecutive failures across **any topics in the same subject** | Broader — identifies subject-level difficulty | Noisier; may frustrate rather than help |
| **B3** | 3 failures within a **rolling time window** (e.g., 7 days), regardless of topic | Time-bounded — avoids stale counters | Needs scheduled cleanup of old failures |

#### Dimension C: How is it detected?

| Option | Definition | Pros | Cons |
|--------|-----------|------|------|
| **C1** | Inline in `progress_service` after each assessment result | Real-time — notification fires immediately after 3rd failure | Adds logic to already-complex service |
| **C2** | In `session_service.end_session()` when score is recorded | Single detection point | Only fires at session end, not per-assessment |
| **C3** | Scheduled job (APScheduler) that scans recent attempts daily | Decoupled from main flow; easy to tune | Not real-time; adds scheduler complexity |

### Decision (confirmed): A1 + B1 + C1

- **Failure definition (A1):** Assessment `passed=False` (AI judged the child did not demonstrate mastery)
- **Streak window (B1):** 3 consecutive failures on the **same topic**
- **Detection (C1):** Inline in `progress_service` after each assessment result — real-time notification

Rationale:
- A1 uses existing data model (`LearningAssessmentAttempt.passed`)
- B1 is the most actionable — parent can help with the specific stuck topic
- C1 gives immediate feedback — parent gets notified the moment the child struggles

### Notification Content

When triggered, the notification should include:
- Child name
- Topic name (localized if available)
- Subject area
- Suggested action: "Review this topic together" or "Try a different approach"

---

## OQ-6 — Seed Data Quality Validation

### Current State

`seed_learning_topics.py` already has a `validate_quality()` function that checks:
- Total counts (topics, dependencies, clusters)
- Orphan edge detection (dependencies referencing non-existent topics)
- Per-subject topic distribution

Badge seeding is idempotent via upsert but does **not** cross-validate against topic subjects.

### Decision Points (choose minimum quality bar)

#### Dimension A: What validations to enforce?

| Option | Scope | Effort | Value |
|--------|-------|--------|-------|
| **A1 — Minimum viable** | Orphan edge detection (exists) + badge-topic subject cross-check (new) + `age_range_start < age_range_end` constraint (new) | Low | Catches the 3 most likely data errors |
| **A2 — Moderate** | A1 + per-subject minimum topic count (>5) + dependency cycle detection | Medium | Prevents dead-end learning paths |
| **A3 — Strict** | A2 + translated field coverage check + age-range distribution spot check (no age gap > 3 years within a subject) | High | Near-production-grade data quality |

#### Dimension B: When to run validation?

| Option | Timing | Pros | Cons |
|--------|--------|------|------|
| **B1** | Post-seed (current approach) — validate after every `seed` run | Catches issues immediately | Only runs when developer manually seeds |
| **B2** | Post-seed + CI gate — validation also runs in CI against seed data files | Catches issues before merge | Requires seed data files to be in CI |
| **B3** | Post-seed + startup health check — backend verifies data integrity on boot | Catches production data corruption | Slower startup; may mask seed vs runtime issues |

### Decision (confirmed): A1 + B1

- **Validations (A1 — Minimum viable):** Orphan edge detection (already exists) + badge-topic subject cross-check (new) + `age_range_start < age_range_end` constraint (new)
- **Timing (B1):** Post-seed only — validate after every `seed` run

Rationale:
- Orphan edge detection already exists; adding badge-topic cross-check and age_range constraint is low effort
- Post-seed timing is sufficient for a self-hosted app where the developer controls seeding
- CI gate (B2) and startup check (B3) add complexity without proportional value at current scale

### Specific Validations to Add

1. **Badge-topic subject cross-check** — Verify every `subject` in `BADGE_DEFINITIONS` exists in the seeded `LearningTopic.subject` values. Fail seed if any badge subject has 0 topics.

2. **Age range sanity** — Add a check constraint (or post-seed validation): `age_range_start < age_range_end` for all topics and clusters where both are non-null.

3. **Dependency cycle detection** — Verify no circular prerequisites exist in the topic dependency graph. (DFS-based cycle check; O(V+E).)

---

## Summary Table

| OQ | Decision | Key Choices | Status |
|----|----------|-------------|--------|
| OQ-2 | On-demand translation | DeerFlow agent, user-triggered, button visible only on language mismatch | ✅ Confirmed |
| OQ-3 | Failure streak notification | Assessment `passed=False` + same topic + inline detection (A1+B1+C1) | ✅ Confirmed |
| OQ-6 | Seed quality minimum bar | Orphan check + badge cross-check + age constraint, post-seed only (A1+B1) | ✅ Confirmed |
