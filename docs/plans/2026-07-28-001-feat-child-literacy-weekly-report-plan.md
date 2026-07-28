---
title: Child Literacy Weekly Report - Plan
date: 2026-07-28
type: feat
topic: child-literacy-weekly-report
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** Introduce financial literacy badges + weekly reports to the child ecosystem. Children play weekly scenario mini-games to demonstrate financial understanding; badges unlock based on their choices combined with passive behavioral signals; parents receive per-child weekly reports connecting gameplay to real-world literacy growth.
- **Product authority:** This plan owns the literacy badge system, weekly report, and scenario mini-game. The broader 儿童财商生态 (4合1) includes progression levels (Lv1-Lv5) and progressive governance as separately plannable areas — not active scope here.
- **Execution:** code

---

## Product Contract

### Summary

A weekly "financial literacy" loop for the child ecosystem: children play one scenario mini-game per week making age-adaptive financial choices; AI-generated badges unlock based on scenario choices + passive behavioral signals (wish prioritization, chore streaks, opportunity-cost peek usage); parents receive per-child weekly reports showing badge progress, behavioral evidence, and suggested family activities. Badges link to the star coin economy for extra motivation.

### Problem Frame

The child app has rich but disconnected gamification: chores earn star coins, wishes teach delayed gratification, opportunity-cost peek reveals trade-offs, celebration animations reward completion. But there is no overarching narrative connecting these activities into a coherent "financial literacy growth" story. Parents see individual transactions (chore approved, wish realized) but cannot see the bigger picture of what their child is learning. The child has no long-term growth trajectory — each activity is an isolated event with no cumulative meaning.

This matters because financial literacy is not taught by single transactions; it develops through repeated exposure and reflection. Without a system that connects activities into a growth narrative, the child app risks being "fun but shallow" in parents' eyes — leading to the exact retention problem the ideation document identifies: "孩子长大就不用了."

### Key Decisions

- **Hybrid signal model.** Badges and weekly reports draw from both passive behavioral signals (wish choices, peek usage, chore completion, star coin patterns) and active scenario game choices. Passive signals are the foundation; the scenario game is the weekly "teaching moment." (session-settled: user-directed — chosen over pure passive analysis and over combo with open-ended reflection questions: lighter child burden while maintaining active expression)
- **Cross-age adaptive delivery.** Scenario presentation and report language adapt to the child's age: low-age (5-7) uses emoji/voice, mid-age (8-10) uses choice questions and short fill-in, high-age (11+) uses open text. Report depth scales accordingly. (session-settled: user-directed — chosen over fixed age range to ensure the system grows with the child)
- **AI-generated scenarios from templates.** Weekly scenarios are AI-generated from expert-seeded templates, personalized based on the child's recent behavior and unlocked badges. Not manually authored per week.
- **Badge progression via replacement.** Badges have levels within dimensions (e.g., "机会成本新手" → "机会成本侦探" → "机会成本大师"). Higher badges replace lower ones in display. New badges always add, never remove — badges do not expire. (session-settled: user-directed — chosen over expiring badges to maintain cumulative motivation)
- **Weekly per-child reports.** One report per child per week. Multi-child families see separate reports. Reports are parent-facing only in the main app; children see a badge wall in the child app. (session-settled: user-approved)
- **Star coin linkage.** Badge unlocks grant bonus star coins (family-configurable amount, opt-in following the B1 education reward pattern). Collecting all levels in one dimension grants an extra bonus. (session-settled: user-approved)
- **Auto unlock + parent notification.** Badge unlock is automatic when AI conditions are met; parent receives notification for review and can adjust. (session-settled: user-directed — chosen over parent-confirmation required: maintains child motivation flow)

### Actors

- **A1. Child (player + expressor).** Plays the weekly scenario game, sees badge wall and progress in the child app. Interacts through age-adaptive UI. Primary motivation: unlock badges, earn coins.
- **A2. Parent (report consumer).** Reads weekly report in the main app, sees badge growth and behavioral evidence. Switches between children in multi-child families. Primary motivation: understand child's financial literacy development.

### Requirements

**Scenario Mini-Game**

- R1. A new scenario is available once per week per child in the child app. Each scenario presents a short story with a financial decision point and 2-4 choices. No choice is "correct" — all choices produce meaningful feedback.
- R2. Scenario presentation adapts to the child's age: low-age (5-7) receives emoji-based choices with short narration, optionally voice-narrated; mid-age (8-10) receives multiple-choice with brief context; high-age (11+) receives scenario with specific numbers and trade-offs. Covers age-adaptive delivery decision.
- R3. Scenarios are generated by AI from a template library, personalized based on the child's recent behavior (e.g., if the child has been comparing wishes, the scenario explores trade-offs). Templates are seeded by financial education domain experts; AI generation runs once per week per child.
- R4. Each week has one scenario. A scenario expires at the start of the next weekly cycle. Unused scenarios do not carry forward.

**Literacy Badge System**

- R5. Badges are organized in 4 dimensions: 赚钱 (earning — labor creates value), 选择 (choosing — understanding opportunity cost), 等待 (waiting — delayed gratification), 关心 (caring — family financial participation).
- R6. Each dimension has multiple badge levels (at least 3). Higher-level badges replace lower-level ones in display but lower-level badges remain in history.
- R7. Badge unlock conditions are determined by AI analysis of both passive behavioral signals and active scenario choices. The AI evaluates whether the child's behavior demonstrates understanding in a dimension.
- R8. Badge unlock triggers the existing celebration system (MilestoneCelebration + haptic pulse). Child sees a notification in the child app. Parent sees the unlock noted in the weekly report.
- R9. Badge unlocks grant bonus star coins. The amount is family-configurable and follows the existing education reward opt-in pattern (`education_reward_enabled` on `ChildEconomyConfig`).

**Weekly Report (Parent-Side)**

- R10. One report per child per week. Multi-child families see a child selector to switch between reports. Covers per-child report decision.
- R11. Each report contains: (a) this week's badge status (new unlocks or progress toward next), (b) behavioral evidence from passive signals that contributed to badge progress, (c) the child's scenario game choice and the AI's brief analysis, (d) a suggested family activity or discussion topic related to this week's theme.
- R12. Report language adapts to the child's age — same underlying data, different depth and vocabulary in the narrative.
- R13. Reports are generated weekly by AI aggregation of passive signals and scenario outcomes. Report data covers one calendar week (Sunday 00:00 to Saturday 23:59).

**Child-Side Badge Wall**

- R14. The child app displays a badge wall showing: currently held badge per dimension, lower-level badges in history (marked as "超越"), and progress toward the next unlockable badge in each dimension.
- R15. The badge wall is accessible from the child home page or a dedicated entry point.

### Key Flows

- F1. Weekly scenario game
  - **Trigger:** New weekly cycle begins (Sunday 00:00), system generates a personalized scenario for each child.
  - **Actors:** A1
  - **Steps:** Child opens child app → sees scenario card on home page (or via dedicated entry) → reads/watches the scenario → makes a choice → sees immediate feedback showing how the choice relates to a badge dimension and current progress → scenario card marked as completed.
  - **Covered by:** R1, R2, R3, R4

- F2. Weekly report generation and consumption
  - **Trigger:** Weekly cycle ends (Saturday 23:59).
  - **Actors:** A2
  - **Steps:** System aggregates passive behavioral signals + scenario outcome for the week → AI generates report text → notification sent to parent in main app → parent opens report → reads badge progress, behavioral evidence, scenario analysis, family activity suggestion → in multi-child family, parent can switch between children's reports.
  - **Covered by:** R10, R11, R12, R13

- F3. Badge unlock
  - **Trigger:** AI determines badge unlock conditions met (from scenario choice, passive signals, or combination).
  - **Actors:** A1, A2
  - **Steps:** AI evaluates signals → badge unlocked → celebration animation plays in child app → bonus star coins credited (if family opted in) → child sees updated badge wall → parent notified in next weekly report.
  - **Covered by:** R7, R8, R9

### Scope Boundaries

**In scope:**
- Scenario mini-game (1 per week, age-adaptive, AI-generated from templates)
- 4-dimension badge system with multi-level progression
- Weekly parent report (per child, AI-generated, age-adaptive language)
- Child-side badge wall
- Star coin bonus on badge unlock (family opt-in)

**Deferred for later:**
- Open-ended reflection questions (child voice/text answers beyond scenario choices)
- Progressive financial literacy levels (Lv1-Lv5) — separately plannable
- Progressive governance (graduated financial permissions) — separately plannable
- Badge expiration or time-limited challenges
- Complex star coin economic linkage beyond fixed bonus amounts
- Scenario content in languages beyond zh-CN

**Out of scope:**
- Opportunity-cost peek (already completed, plan `docs/plans/2026-05-24-002-feat-child-cross-wish-bundle-plan.md`)
- Chore gamification enhancements (already completed, plan `docs/plans/2026-05-25-001-feat-child-chore-gamification-plan.md`)
- Changes to existing celebration, blind box, or challenge grant systems (reuse only)

### Acceptance Examples

- AE1. 8-year-old's weekly report
  - **Covers R10, R11, R12.** Given: 8-year-old child who compared 3 wishes using opportunity-cost peek twice this week, completed 5/7 chores, and chose "share coins with sibling" in the scenario. When: parent opens weekly report. Then: report shows "选择力 ↑" progress with evidence "本周对比了3个愿望的代价，做出2次跨愿望比较"; scenario analysis reads "你选择分享星币给弟弟——这展示了'关心'维度的理解"; family activity suggestion: "和孩子聊聊：如果只能用一半星币，你会怎么分配？"

- AE2. Badge unlock with upgrade
  - **Covers R6, R8, R9.** Given: child previously held "小帮手" (Lv1 赚钱 badge). When: child completes chores 14 consecutive days + scenario choice demonstrates understanding of labor value. Then: "勤劳小达人" (Lv2) badge unlocks, replacing "小帮手" in current display; celebration animation plays; 50 bonus star coins credited (if family opted in); "小帮手" remains in history as "超越"; parent sees unlock in weekly report.

- AE3. Low-age scenario presentation
  - **Covers R2.** Given: 5-year-old child. When: weekly scenario is delivered. Then: scenario card uses large emoji choices (🍎 vs 🧸), short voice-narrated story ("小明有5颗星币，他想要一个苹果玩具和一个熊熊…"), and tap-to-select interaction. Report to parent uses simpler language.

- AE4. Multi-child family reports
  - **Covers R10.** Given: family with two children (age 8 and age 5). When: weekly cycle ends. Then: two separate reports are generated — one per child with independent data. Parent sees a child selector in the report view; each report reflects the respective child's behavior, badges, and age-adaptive language.

### Dependencies / Assumptions

- Passive behavioral signals already exist: `ChildWishStats.priority_simulation[]`, chore completion with streaks, star coin earn/spend history. No new signal collection needed.
- Child's age from `User.birthday` (`packages/db/models/user.py:78`). Already exists on the User model; no migration needed for the field itself.
- Existing celebration system (`MilestoneCelebration`, `useCelebration`, `motionTokens`) reused without modification.
- Weekly report AI generation reuses existing AI infrastructure (DeerFlow adapter, `finance_coach` skill pattern).
- Scenario template library needs initial seeding — 20-30 base templates covering 4 dimensions × 3 age groups.

### Product Contract preservation

Product Contract unchanged during enrichment. All R/A/F/AE IDs preserved verbatim.

---

## Planning Contract

### Key Technical Decisions

KTD1. **New models in `packages/db/models/` for cross-app access.** `LiteracyBadge`, `LiteracyBadgeDefinition`, `LiteracyScenario`, `LiteracyWeeklyReport` live in `packages/db/models/` because both the child app and main app need to read them, and the agent's weekly report generation service runs in the backend. Badge definitions are stored in a dedicated table (not hard-coded) so new badge tiers can be added without code changes.

KTD2. **Scenario generation via lightweight LLM, not DeerFlow stream.** Weekly scenarios are generated by calling the existing lightweight LLM endpoint (`ai_suggest` pattern in `apps/backend/app/routers/ai_suggest.py`) with a structured prompt that includes the child's recent behavioral signals and a selected template. This is a single-shot generation (no streaming), matching the pattern used for asset field suggestions.

KTD3. **Badge evaluation triggered by events, not weekly batch.** Badge unlock evaluation runs synchronously when a child completes a scenario choice (F3 trigger) and also when a chore is approved. This gives immediate feedback rather than waiting for a weekly batch. The evaluation calls the lightweight LLM with the child's signal bundle and the next badge tier's criteria.

KTD4. **Weekly report generation via scheduler_worker.** Reports are generated by a new task registered in `apps/scheduler_worker/`. The task runs on Sunday 02:00 (after scenario generation at 00:00), aggregates the week's signals, calls the AI for narrative generation, and stores the report. This follows the scheduler pattern (currently zero tasks registered) and keeps heavy AI work out of the request path.

KTD5. **Badge definitions seeded via alembic data migration, not runtime seed.** The initial 4×3=12 badge definitions are inserted in the alembic migration, not in a startup seed script. This ensures they exist before any API call and are version-controlled with the schema.

KTD6. **Child app badge wall as new page + tab entry.** A new `ChildBadgesPage.vue` page with a route `/badges`, linked from the child home page as a card entry. Follows the existing page pattern (ChildTasksPage, ChildTreasuresPage) with the same clay.css theming.

### Assumptions

- `User.birthday` is populated for current child users. If not, the onboarding/settings flow needs updating (Deferred to Planning).
- Scenario templates are initially authored in zh-CN only. English support is deferred.
- Report history is retained indefinitely (no automatic cleanup in v1).
- Parent notification for badge unlock uses the existing notification system.

---

## Implementation Units

### U1. Data Models + Alembic Migration

**Goal:** Create the database schema for the literacy badge system, scenario tracking, weekly reports, and family settings extension.

**Requirements:** R5, R6, R9, R10, R13

**Dependencies:** None (first unit)

**Files:**
- `server/packages/db/models/literacy_badge.py` (new) — `LiteracyBadgeDefinition`, `LiteracyBadge` models
- `server/packages/db/models/literacy_scenario.py` (new) — `LiteracyScenario`, `LiteracyScenarioTemplate` models
- `server/packages/db/models/literacy_report.py` (new) — `LiteracyWeeklyReport` model
- `server/packages/db/models/__init__.py` (modify) — re-export new models
- `server/apps/backend/app/models/child_economy_config.py` (modify) — add `literacy_badge_coin_enabled`, `literacy_badge_coin_amount`
- `server/apps/backend/alembic/versions/YYYYMMDD_add_literacy_badge_system.py` (new) — migration

**Approach:**
1. `LiteracyBadgeDefinition`: `id`, `dimension` (String: earning/choosing/waiting/caring), `level` (Integer), `name` (String), `description` (String), `criteria_summary` (String — short description of unlock criteria for AI context)
2. `LiteracyBadge`: `id`, `child_id` (FK users.id), `definition_id` (FK literacy_badge_definitions.id), `earned_at`, `superseded_at` (nullable — set when a higher-level badge in the same dimension replaces this one), `source` (String: scenario/scenario+passive/passive)
3. `LiteracyScenarioTemplate`: `id`, `dimension`, `age_group` (low/mid/high), `story_template` (Text), `choices_json` (Text — JSON array of 2-4 choices with feedback), `is_active` (Boolean)
4. `LiteracyScenario`: `id`, `child_id` (FK), `week_start` (Date — Sunday of the week), `template_id` (FK), `content_json` (Text — personalized scenario content), `choice_index` (Integer nullable), `feedback_json` (Text nullable), `completed_at` (DateTime nullable), UniqueConstraint(child_id, week_start)
5. `LiteracyWeeklyReport`: `id`, `child_id` (FK), `week_start` (Date), `report_json` (Text — structured report data), `narrative` (Text — AI-generated narrative), `generated_at` (DateTime), UniqueConstraint(child_id, week_start)
6. Extend `ChildEconomyConfig` with `literacy_badge_coin_enabled: Boolean default False` and `literacy_badge_coin_amount: Integer default 50`
7. Alembic migration creates all 5 new tables + alters `child_economy_configs`. Seed 12 badge definitions (4 dimensions × 3 levels) as data migration within the same file.

**Patterns to follow:** `ChildEconomyConfig` model pattern (`server/apps/backend/app/models/child_economy_config.py`), existing alembic migration patterns with `batch_alter_table` for SQLite compatibility.

**Test scenarios:**
- Migration applies cleanly on fresh SQLite DB (all 5 new tables + altered table created)
- Badge definitions seeded: 12 rows in `literacy_badge_definitions` after migration
- `LiteracyBadge.superseded_at` nullable — initially NULL
- `LiteracyScenario` unique constraint prevents duplicate scenarios for same child + week
- `ChildEconomyConfig` new columns have correct defaults (False, 50)

**Verification:** `alembic upgrade head` succeeds on fresh DB. `alembic downgrade -1` succeeds. All new models importable from `packages.db.models`.

---

### U2. Scenario Generation Service

**Goal:** Build the backend service that generates a personalized weekly scenario for each child using the lightweight LLM.

**Requirements:** R1, R2, R3, R4

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/services/literacy_scenario.py` (new)
- `tests/backend/services/test_literacy_scenario.py` (new)

**Approach:**
1. `generate_weekly_scenario(db, child: User) -> LiteracyScenario`: called once per week per child (triggered by scheduler or on-demand on first app open)
2. Determine child's age group from `User.birthday`: low (5-7), mid (8-10), high (11+)
3. Select a template: pick from `LiteracyScenarioTemplate` where `age_group` matches and `is_active=True`. Exclude templates used in the last 4 weeks for this child (check `LiteracyScenario.template_id` history). Prefer dimensions where the child has no current badge (growth areas).
4. Build LLM prompt: include the template's `story_template`, the child's recent behavioral signals (last 7 days: chore completion count, wish peek interactions, coin earn/spend), and instruction to personalize the scenario content
5. Call lightweight LLM endpoint (following `ai_suggest` pattern). Parse structured response: personalized story + 2-4 choices with per-choice feedback text
6. Store as `LiteracyScenario` with `content_json` containing the personalized content
7. Age-adaptive content formatting: low-age → include emoji hints in the story, mid-age → include brief context per choice, high-age → include specific numbers/trade-offs. The LLM prompt instructs the model to format per age group.

**Patterns to follow:** `ai_suggest.py` lightweight LLM call pattern. Service layer pattern from `services/chores.py`.

**Test scenarios:**
- Scenario generated for 8-year-old uses mid-age template and content format
- Template deduplication: template used last week is not selected again
- LLM failure: service returns a fallback generic scenario (no crash)
- Age group calculation: birthday 6 years ago → low, 9 years ago → mid, 12 years ago → high
- Unique constraint: calling generate twice for same child + week returns the existing scenario (idempotent)

**Verification:** Unit tests pass for age calculation, template selection, LLM mock call, fallback behavior.

---

### U3. Badge Evaluation Service

**Goal:** Build the service that evaluates whether a child should unlock a new badge after a scenario choice or chore approval.

**Requirements:** R5, R6, R7, R8, R9

**Dependencies:** U1, U2

**Files:**
- `server/apps/backend/app/services/literacy_badge.py` (new)
- `tests/backend/services/test_literacy_badge.py` (new)

**Approach:**
1. `evaluate_badge_unlocks(db, child: User, trigger: str) -> list[LiteracyBadge]`: called after scenario choice completion and chore approval
2. For each of the 4 dimensions, find the child's current highest badge (or None if no badge in that dimension)
3. Find the next badge definition in that dimension (current level + 1)
4. If no next badge exists (already at max level), skip
5. Build evaluation context: child's behavioral signals for the relevant dimension over the last 14 days (e.g., for "earning": chore streak data; for "choosing": peek usage data), plus the latest scenario choice if trigger is "scenario"
6. Call lightweight LLM with evaluation prompt: "Given these signals, has the child demonstrated understanding of [dimension concept] at the [next level] tier?"
7. If LLM returns positive: create `LiteracyBadge` record, set `superseded_at` on the previous badge in the same dimension, trigger celebration, credit bonus coins (if family opted in)
8. Return list of newly unlocked badges

**Patterns to follow:** `services/chores.py` for chore data access. `services/dashboard.py:489-530` for education reward aggregation pattern. Coin crediting follows `services/coins.py`.

**Test scenarios:**
- No current badge in dimension → evaluate for Lv1
- Current Lv1 badge → evaluate for Lv2, if positive: Lv1 gets `superseded_at` set, new Lv2 badge created
- Already at max level → no evaluation, no unlock
- LLM returns negative → no badge created
- Family opted out of coin reward (`literacy_badge_coin_enabled=False`) → badge unlocks but no coins credited
- Family opted in with custom amount (75) → 75 coins credited on unlock
- Trigger "chore_approved" → only evaluates 赚钱 dimension
- Trigger "scenario_completed" → evaluates all 4 dimensions

**Verification:** Unit tests for evaluation logic, mock LLM responses for positive/negative cases, coin crediting with opt-in/out.

---

### U4. Backend API — Child Endpoints

**Goal:** Expose scenario and badge endpoints for the child app.

**Requirements:** R1, R2, R4, R14, R15

**Dependencies:** U1, U2, U3

**Files:**
- `server/apps/backend/app/routers/literacy_child.py` (new)
- `server/apps/backend/app/schemas/literacy.py` (new)
- `server/apps/backend/app/main.py` (modify) — register new router
- `tests/backend/routers/test_literacy_child.py` (new)

**Approach:**
1. Router prefix `/api/v1/child/literacy`, adult auth guard with `require_adult` (child token or parent token for child)
2. `GET /scenario` — returns current week's scenario for the calling child. If no scenario exists yet, triggers `generate_weekly_scenario()` on-demand (lazy generation). Response: `ScenarioResponse` with `id`, `story`, `choices[]`, `age_group`, `completed` (boolean)
3. `POST /scenario/choose` — body: `{ choice_index: int }`. Records the child's choice, generates feedback, triggers `evaluate_badge_unlocks()`. Response: `ChoiceFeedbackResponse` with `feedback_text`, `dimension_hint` (which dimension this relates to), `badges_unlocked[]` (list of newly unlocked badge names)
4. `GET /badges` — returns badge wall data. Response: `BadgeWallResponse` with `dimensions[]` each containing: `dimension`, `current_badge` (highest active), `history[]` (superseded badges marked as "超越"), `next_badge` (next unlockable, with progress hint)
5. All response schemas inherit `SnowflakeBase` for ID serialization
6. Register router in `main.py`

**Patterns to follow:** `routers/child_blind_box.py` for child router pattern. `schemas/child_wishes.py` for response schema pattern. `auth/deps.py:599` `require_adult` guard.

**Test scenarios:**
- GET /scenario returns generated scenario for child
- GET /scenario when none exists triggers lazy generation
- POST /scenario/choose with valid choice returns feedback and triggers badge evaluation
- POST /scenario/choose for already-completed scenario returns 409
- GET /badges returns correct structure with current/history/next per dimension
- Non-child user cannot access endpoints (403)
- Cross-family access denied (403)

**Verification:** Router registered, endpoints return correct schemas, auth guards enforced.

---

### U5. Weekly Report Generation + Parent API

**Goal:** Build the weekly report AI generation service and parent-facing API for consuming reports.

**Requirements:** R10, R11, R12, R13

**Dependencies:** U1, U2, U3

**Files:**
- `server/apps/backend/app/services/literacy_report.py` (new)
- `server/apps/backend/app/routers/literacy_parent.py` (new)
- `server/apps/backend/app/schemas/literacy_report.py` (new)
- `server/apps/backend/app/main.py` (modify) — register parent router
- `server/apps/scheduler_worker/tasks/literacy_report.py` (new)
- `tests/backend/services/test_literacy_report.py` (new)
- `tests/backend/routers/test_literacy_parent.py` (new)

**Approach:**
1. `LiteracyReportService.generate_weekly_report(db, child: User, week_start: date) -> LiteracyWeeklyReport`:
   - Aggregate passive signals for the week: chore completion rate, wish peek interactions, coin earn/spend, scenario choice + feedback
   - Aggregate badge changes: any new unlocks, progress toward next tier
   - Build LLM prompt: include all aggregated data, child's age (for language adaptation), and instruction to generate: (a) badge status summary, (b) behavioral evidence highlights, (c) scenario choice analysis, (d) family activity suggestion
   - Parse structured response into `report_json` (structured data) + `narrative` (display text)
   - Store `LiteracyWeeklyReport` record

2. Scheduler worker task: register `generate_literacy_reports` task in `apps/scheduler_worker/tasks/`. Runs weekly on Sunday 02:00. For each child in each active family, calls `generate_weekly_report()`.

3. Parent router `/api/v1/literacy-reports`:
   - `GET /literacy-reports?child_id=X&week_start=Y` — returns report for a specific child and week. If `week_start` omitted, returns latest.
   - `GET /literacy-reports/children` — returns list of children in the family with their latest report week (for the child selector UI)
   - `GET /literacy-reports/history?child_id=X` — returns list of available report weeks for a child
   - Auth: `require_adult` (parent only, not child)
   - Response schemas inherit `SnowflakeBase`

**Patterns to follow:** `routers/dashboard.py` for parent-facing report pattern. `services/dashboard.py:489-530` for signal aggregation. `apps/scheduler_worker/CLAUDE.md` for task registration pattern.

**Test scenarios:**
- Report generation with complete signal data produces structured report
- Report generation with sparse data (new child, no history) produces minimal but valid report
- Age-adaptive language: report for 5-year-old uses simpler vocabulary than for 12-year-old
- GET /literacy-reports returns correct report for given child + week
- GET /literacy-reports without week returns latest
- GET /literacy-reports/children returns all children in family
- Multi-child family: two separate reports with independent data
- Parent-only access: child role returns 403

**Verification:** Scheduler task registers and runs. Report generation tests pass with mock LLM. Parent endpoints return correct data.

---

### U6. Child App — Scenario Game Page

**Goal:** Build the child-facing scenario game UI where children read a story and make financial choices.

**Requirements:** R1, R2, R4

**Dependencies:** U4

**Files:**
- `frontend/apps/child/src/pages/ChildScenarioPage.vue` (new)
- `frontend/apps/child/src/api/literacy.ts` (new) — API client for literacy endpoints
- `frontend/apps/child/src/router/index.ts` (modify) — add `/scenario` route
- `frontend/apps/child/src/components/literacy/ScenarioCard.vue` (new)
- `frontend/apps/child/src/components/literacy/ScenarioFeedback.vue` (new)
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (modify) — add scenario-related i18n keys
- `frontend/apps/child/src/i18n/locales/en-US.ts` (modify) — add scenario-related i18n keys
- `tests/child/pages/ChildScenarioPage.test.ts` (new)

**Approach:**
1. API client `literacy.ts`: `getWeeklyScenario()`, `submitChoice(choiceIndex)`, `getBadges()`. Follow existing API client pattern (`api/childWishes.ts`).
2. `ChildScenarioPage.vue`: fetches current week's scenario on mount. Displays story text, choices as interactive cards. On choice selection, shows feedback overlay. If scenario already completed, shows "已完成" state with previous choice + feedback.
3. Age-adaptive rendering: check `age_group` from API response. Low-age → larger text, emoji-heavy choices, optional TTS for story. Mid-age → standard card layout. High-age → detailed choices with numbers.
4. `ScenarioCard.vue`: renders the scenario story and choices. Props: `story`, `choices[]`, `ageGroup`, `completed`. Emits: `@choose(index)`.
5. `ScenarioFeedback.vue`: shows after choice is made. Displays the feedback text, which dimension it relates to, and any newly unlocked badges (with celebration animation trigger).
6. Route `/scenario` added to child router with KeepAlive (same pattern as other child pages).
7. All strings use i18n keys — no hard-coded Chinese.

**Patterns to follow:** `ChildWishesPage.vue` for page structure + API call pattern. `ChildWishDetailPage.vue` for detail page pattern. Clay.css theming tokens.

**Test scenarios:**
- Page loads and displays scenario from API
- Choice selection triggers API call and shows feedback
- Already-completed scenario shows previous state (no re-choose)
- Low-age rendering: emoji choices, large text
- API error: shows error state, does not crash

**Verification:** Page renders scenario, choices work, feedback shows, age-adaptive rendering correct.

---

### U7. Child App — Badge Wall Page

**Goal:** Build the child-facing badge wall displaying earned badges, history, and progress toward next unlocks.

**Requirements:** R14, R15

**Dependencies:** U4

**Files:**
- `frontend/apps/child/src/pages/ChildBadgesPage.vue` (new)
- `frontend/apps/child/src/components/literacy/BadgeWall.vue` (new)
- `frontend/apps/child/src/components/literacy/BadgeCard.vue` (new)
- `frontend/apps/child/src/components/literacy/BadgeDimension.vue` (new)
- `frontend/apps/child/src/pages/ChildHomePage.vue` (modify) — add badge wall entry card
- `frontend/apps/child/src/router/index.ts` (modify) — add `/badges` route with cache
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (modify) — badge-related keys
- `frontend/apps/child/src/i18n/locales/en-US.ts` (modify) — badge-related keys
- `tests/child/pages/ChildBadgesPage.test.ts` (new)

**Approach:**
1. `ChildBadgesPage.vue`: fetches badge wall data from `GET /child/literacy/badges`. Displays 4 dimension sections.
2. `BadgeDimension.vue`: one per dimension. Shows current badge prominently, progress bar toward next badge, and a collapsed history section showing superseded badges with "超越" label.
3. `BadgeCard.vue`: individual badge display with icon (use iconify skill for badge icons), name, level indicator. Current badges are full-color; superseded badges are dimmed with "超越" overlay; locked/next badges are silhouettes.
4. Home page entry: add a card on `ChildHomePage.vue` linking to `/badges`, showing a summary (e.g., "3 枚徽章, 1 枚待解锁").
5. Route `/badges` added to child router with KeepAlive.

**Patterns to follow:** `ChildTreasuresPage.vue` for collection display pattern. `ChildTasksPage.vue` for page + entry pattern. Celebration system integration for badge unlock animation (`MilestoneCelebration`).

**Test scenarios:**
- Badge wall renders 4 dimensions with correct badge states
- Superseded badge shown with "超越" label
- Empty state: no badges yet → shows all dimensions as locked silhouettes
- Home page card links to /badges and shows correct badge count

**Verification:** Badge wall renders correctly, home page entry works, celebration triggers on new unlock.

---

### U8. Parent App — Weekly Report Page

**Goal:** Build the parent-facing weekly report page in the main app with child selector and report display.

**Requirements:** R10, R11, R12

**Dependencies:** U5

**Files:**
- `frontend/apps/main/src/pages/LiteracyReportPage.vue` (new)
- `frontend/apps/main/src/components/literacy/WeeklyReportCard.vue` (new)
- `frontend/apps/main/src/components/literacy/ReportSection.vue` (new)
- `frontend/apps/main/src/components/literacy/ChildSelector.vue` (new)
- `frontend/apps/main/src/api/literacy.ts` (new)
- `frontend/apps/main/src/router/index.ts` (modify) — add route
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify) — report-related keys
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify) — report-related keys
- `tests/main/pages/LiteracyReportPage.test.ts` (new)

**Approach:**
1. API client `literacy.ts`: `getReport(childId, weekStart?)`, `getReportChildren()`, `getReportHistory(childId)`. Follow main app API client pattern.
2. `LiteracyReportPage.vue`: main page layout. Top: child selector (only visible in multi-child families). Center: current week's report card. Bottom: history navigation.
3. `ChildSelector.vue`: dropdown or tab bar showing children. Only rendered when family has 2+ children. Emits selected child ID.
4. `WeeklyReportCard.vue`: renders the full report with 4 sections: (a) badge status — new unlocks or progress, (b) behavioral evidence — bullet list of signals, (c) scenario analysis — child's choice + AI interpretation, (d) family activity suggestion — highlighted callout.
5. `ReportSection.vue`: reusable section wrapper with title, content slot, and age-adaptive typography.
6. Route: add to main app router. Entry point: link from Dashboard or Finance Hub (add a subtle card on Dashboard).
7. All strings i18n.

**Patterns to follow:** Dashboard page pattern for parent-side layout. `FinanceCoachCard` for narrative card rendering pattern. Vant 4 components for card layout.

**Test scenarios:**
- Report page loads and displays report from API
- Child selector visible only in multi-child family
- Child selector switches report content
- Empty state: no report yet → shows "等待本周报告生成" placeholder
- History navigation loads previous weeks

**Verification:** Report renders all 4 sections, child selector works, history navigation works.

---

### U9. Scenario Template Seed + AI Generation Batch

**Goal:** Create the initial scenario template library (20-30 templates) and the AI batch generation mechanism for populating the template table.

**Requirements:** R3

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/seed/literacy_scenarios.py` (new) — seed script or migration data for initial templates
- `server/apps/backend/app/services/literacy_scenario_templates.py` (new) — AI batch template generation utility
- `tests/backend/services/test_literacy_scenario_templates.py` (new)

**Approach:**
1. Define 4 dimensions × 3 age groups × 2-3 templates per combination = 24-36 templates
2. Template structure: `story_template` (the scenario narrative skeleton with placeholders), `choices_json` (2-4 choices each with: text, feedback text, dimension signal), `dimension`, `age_group`
3. AI batch generation: a one-time script that calls the LLM to generate template content. Input: dimension + age group + seed prompt describing the learning objective. Output: structured template matching the schema.
4. Templates stored in `literacy_scenario_templates` table. Human review step: after generation, templates are inserted with `is_active=False`. Admin enables them after review (can be a simple SQL update or a future admin UI).
5. For v1, seed a minimal set of 12 hand-crafted templates (1 per dimension × age group) directly in the alembic data migration (U1). The AI batch generation is a utility for expanding the library post-launch.

**Patterns to follow:** `seed/categories.py` for seed data pattern.

**Test scenarios:**
- 12 seed templates exist after migration (one per dimension × age group)
- AI batch generation produces templates matching the schema
- Generated template has valid `choices_json` (parseable, 2-4 choices)
- Template selection in scenario generation excludes inactive templates

**Verification:** Seed data present after migration. AI generation utility produces valid templates.

---

## Verification Contract

| Gate | Command | Scope | Pass criteria |
|------|---------|-------|---------------|
| Backend typecheck | `uv run mypy apps/backend/` | U1-U5, U9 | 0 errors |
| Backend lint | `uv run ruff check apps/backend/` | U1-U5, U9 | 0 violations |
| Backend tests | `uv run pytest tests/backend/ -v -k literacy` | U1-U5, U9 | All pass |
| Child typecheck | `cd frontend/apps/child && pnpm typecheck` | U6-U7 | 0 errors |
| Child tests | `cd frontend/apps/child && pnpm test:run` | U6-U7 | All pass |
| Main typecheck | `cd frontend/apps/main && pnpm typecheck` | U8 | 0 errors |
| Main tests | `cd frontend/apps/main && pnpm test:run -t literacy` | U8 | All pass |
| Alembic fresh DB | `cd apps/backend && uv run alembic upgrade head` | U1 | Success, all tables created |

## Definition of Done

- All 9 implementation units implemented and verified
- Verification Contract gates pass
- Acceptance Examples AE1-AE4 pass (manual or automated)
- All user-facing strings use i18n keys (no hard-coded Chinese in .vue or .ts logic)
- All API response schemas inherit `SnowflakeBase`
- All router root-path decorators use `""` not `"/"`
- Alembic migration applies cleanly on fresh DB
- No new dependencies added (all features use existing infrastructure)

---

## Sources & Research

- Requirements source: `docs/plans/2026-07-28-001-feat-child-literacy-weekly-report-plan.md` (ce-brainstorm output)
- Grounding dossier: `/tmp/compound-engineering-501/ce-brainstorm/child-lit-ecosystem/grounding.md`
- Child app patterns: `frontend/apps/child/src/pages/`, `frontend/apps/child/CLAUDE.md`
- Backend child router patterns: `server/apps/backend/app/routers/child_blind_box.py`, `server/apps/backend/app/routers/chores.py`
- Education reward (B1): `server/apps/backend/app/models/child_economy_config.py`, `server/apps/backend/app/routers/dashboard.py:98-104`
- Celebration system: `frontend/apps/child/src/components/CelebrationAnimation.vue`, `frontend/apps/child/src/composables/useCelebration.ts`
- Scheduler worker: `server/apps/scheduler_worker/CLAUDE.md`
- User model with birthday: `server/packages/db/models/user.py:78`
- Opportunity-cost peek (completed): `docs/plans/2026-05-24-002-feat-child-cross-wish-bundle-plan.md`
