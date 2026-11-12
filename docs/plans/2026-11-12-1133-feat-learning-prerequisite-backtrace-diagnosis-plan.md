---
title: Learning Prerequisite Backtrace Diagnosis - Plan
date: 2026-11-12
type: feat
topic: learning-prerequisite-backtrace-diagnosis
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective**: When a child is stuck on a topic (BKT mastery below threshold, ≥3 practice attempts), the system walks the prerequisite graph up to 2 layers backward, identifies weak prerequisites that the child has actually practiced and failed, and surfaces a child-readable, non-blocking inline recommendation on the practice start page — so the child can choose to "go back and fix the foundation" instead of grinding the same failing topic.
- **Means**: Extend `GET /practice/recommend` with a `?diagnosis=true` flag backed by a new depth-2 backtrace service in `adaptive_service`; render an inline diagnostic card on the practice mode-selection screen (KTD6, KTD12).
- **Product authority**: Child-facing practice flow (`frontend/apps/child` practice views + practice router + `adaptive_service`).
- **Execution**: code.
- **Epic position**: Third step of the #206 learning-adaptation epic (`#212 BKT calibration → #213 this plan → #214 misconception diagnosis`). #213 stops at identifying *which* prerequisite is weak; diagnosing *why* it is weak belongs to #214.
- **Execution profile**: Ships as one pull request.
- **Stop conditions**: Stop if the depth-2 backtrace cannot reuse the calibrated estimator's API (`MasteryEstimator.estimate`) or if extending `GET /practice/recommend` cannot preserve the existing `list[RecommendResponse]` response shape for the post-practice caller.

---

## Product Contract

### Summary

A non-blocking diagnostic card on the practice start page that tells the child, in evidence-backed language, which prerequisite they are actually weak at when they are stuck — based on walking the prerequisite graph up to 2 layers and requiring each candidate to have real practice data. The child decides whether to follow the recommendation.

### Problem Frame

Children in the current system who repeatedly fail on a topic keep getting the same topic served at a lower difficulty. The system never looks upstream to find out whether the real cause is a weak prerequisite. The only exits available to a stuck child are to keep grinding in the same spot or to give up entirely. Observation: stuck children give up.

The knowledge graph has 3,221 prerequisite edges that could in principle answer the question "what's actually weak here". The existing `find_weak_prerequisites` service is single-hop only and is called passively from the recommendations endpoint; no multi-hop backtrace diagnosis reaches the practice start page. The existing `PrerequisiteGuidance.vue` and `prereqReview` copy already surface unmet prerequisites on the learning map, but never at the moment the child is about to start practice on a stuck topic.

### Key Decisions

- KTD1. **MVP = diagnosis + recommendation, no lock.** (session-settled: user-directed — chosen over auto-remedial-session-with-lock: respects the child's agency and avoids a demotivating "you cannot proceed" framing.) Governs R8, R9.
- KTD2. **Trigger is cross-session: when the child opens a topic to practice**, not during an active practice session. (session-settled: user-directed — chosen over within-session interruption: less disruption mid-practice, and the diagnosis has more reliable data to work with.) Governs R2, F1.
- KTD3. **Trigger signal: BKT mastery estimate below a threshold, reusing the #212 calibrated estimator.** (session-settled: user-approved — chosen over raw accuracy threshold and bare attempt count: leverages the already-shipped calibrated machinery and gets time-decay weighting for free.) Governs R2.
- KTD4. **Backtrace depth capped at 2 layers** upstream from the target topic. Governs R1.
- KTD5. **Both the target topic AND each candidate prerequisite must have ≥3 practice attempts before being named "weak".** A prerequisite with fewer attempts is silently excluded and never mentioned in the diagnostic copy. (session-settled: user-directed — chosen over including zero-sample prerequisites: zero samples means "never tried", which is not the same as "weak"; presenting an untaught prerequisite as weak would mislabel it and damage the child's confidence.) Governs R1, R3, F1.
- KTD6. **Presentation: inline card above the main CTA on the practice start page, with the original topic CTA still visible.** (session-settled: user-directed — chosen over modal/bottom-sheet interruption and over CTA replacement: matches the no-lock decision and is the least intrusive shape.) Governs R8, R9. Note: the topic page's existing `difficultyWarning` dialog (a `van-dialog` that fires when a child starts a session on a topic with unmet prerequisites) remains active. The inline card governs the practice start page; the dialog governs session creation. Their copy is deliberately distinct so a child does not read them as the same message twice.
- KTD7. **Ranking among qualified candidates: weakest BKT mastery first; ties broken by greater depth (deeper = more root-cause).** Governs R4.
- KTD8. **Coexistence with `PrerequisiteGuidance.vue`: the diagnostic card does not duplicate any prerequisite already surfaced in the guidance bottom-sheet.** (session-settled: user-approved — chosen after the verification pass revealed that `PrerequisiteGuidance.vue` shows *all* dependency edges including soft prereqs, so the surfaces overlap in practice.) Governs R8, R10, F2. *Conflict call-out (planning research): `PrerequisiteGuidance.vue` renders from the learning map / topic page context, not from `PracticeSessionPage.vue`. Children arriving directly at practice (via `TodayLearningCard` or `LearningProgressPage`) never see the guidance sheet, so for them R10's depth-1 exclusion suppresses the single most obvious recommendation. Proceeding as settled — the decision remains workable and the exclusion keeps the two surfaces non-contradictory — but the owner should weigh whether direct arrivals deserve differentiated copy in a follow-up (see Open Questions).*

### Actors

- A1. **Child** — the child-app user who opens practice topics, sees the diagnostic card, and decides whether to follow it.
- A2. **Backend** — the practice router and `adaptive_service`, which run the diagnosis and return the recommendation result.
- A3. **Parent** — secondary observer, explicitly out of scope for this plan.

### Key Flows

- F1. **Trigger-on-topic-open**
  - **Trigger:** Child navigates to a practice topic and the mode-selection phase is reached (including after a discovery challenge completes; the request is not fired during the discovery phase itself, so an impression is not written for a card the child never reaches).
  - **Actors:** A1, A2.
  - **Steps:**
    1. The practice start page requests the recommendation result for this (topic_id, child_id) with `?diagnosis=true`, unless the arrival URL carries a `fromDiagnosis` referrer marker (R13).
    2. The backend checks whether the target topic has ≥3 attempts AND BKT mastery below threshold; if not, returns an empty diagnosis.
    3. Otherwise walks hard prerequisite edges up to depth 2 (with visited-set tracking), collects each prerequisite's BKT mastery and attempt count, filters to prerequisites with ≥3 attempts, BKT below threshold, and `mastery_level` not `mastered`, excludes direct unmet prerequisites (already surfaced by the prerequisite guidance), ranks by estimator class then by mastery ascending then depth descending, and dedupes by topic id at minimum depth.
    4. The backend writes a diagnosis-impression record (R12) when a qualified candidate is returned.
    5. The frontend receives the list; renders a reserved-height skeleton while loading; if the response contains a candidate, renders the inline diagnostic card naming the top-ranked one (R8 states why only one); otherwise shows no card. The card renders only in the mode-selection phase — a response arriving after the child has started answering is discarded.
    6. Child taps "practice X first" → the page resets its session state and navigates to practice on the recommended prerequisite with a `?fromDiagnosis={sourceTopicId}` referrer marker (suppressing re-diagnosis on arrival). Or taps "continue" → the card is dismissed for this page mount and the mode buttons remain.
  - **Covered by:** R1, R2, R3, R4, R5, R6, R7, R8, R10, R12, R13.
- F2. **Coexistence-with-guidance**
  - **Trigger:** A topic has unmet prerequisites (already surfaced by the prerequisite guidance) AND weak prerequisites detected by the backtrace.
  - **Actors:** A1, A2.
  - **Steps:**
    1. The backend excludes direct unmet prerequisites from the diagnosis response (R10).
    2. The frontend renders the first remaining candidate as the diagnostic card, or shows no card if all candidates were filtered by the backend.
    3. The prerequisite guidance surface (on the learning map) is unaffected.
  - **Covered by:** R8, R10, KTD8.

### Requirements

**Backend — Diagnosis algorithm**

- R1. **Multi-hop backtrace.** When invoked for a `(topic_id, child_id)` pair, the diagnosis walks prerequisite edges upstream up to depth 2 and returns every prerequisite that (a) has ≥3 `PracticeAttempt` rows for this child, (b) whose BKT mastery estimate is below the configured threshold, and (c) whose `mastery_level` is neither `mastered` nor `locked` — where `mastery_level` is the existing `LearningProgress.mastery_level` value from the progress service, not a BKT-derived recomputation; `mastered` is the only guard against recommending a topic the child has already mastered through the learning flow (SC5), and `locked` keeps the card's CTA startable (`create_practice_session` raises `PRACTICE_TOPIC_LOCKED` on locked topics). Only hard-strength edges (`strength == "hard"`) are traversed; soft and deprecated edges are excluded. The backtrace also excludes deprecated topics (`LearningTopic.deprecated`) from candidate results. `LearningDependency` has no deprecated field of its own — deprecation filtering is by topic.
- R2. **Trigger contract.** The diagnosis runs only when the target topic itself has ≥3 practice attempts AND its BKT mastery is below threshold. The target accepts the estimator's rule-based fallback at 3–4 attempts — the same 0.60 threshold applies to both estimator scales, and the target trigger is not restricted to BKT-eligible (5+ attempt) targets. The diagnosis is not run during an active answering session; it is invoked when the practice start page reaches the mode-selection phase (the codeable trigger used in F1 and KTD14). The diagnosis-impression record (see R12) is what SC1/SC2/SC4 denominators are computed from. Note: candidates with 3–4 attempts are scored by the rule-based estimator (which falls back to accuracy), while 5+ attempt candidates are scored by the BKT estimator (which has a hard floor of ~0.346 for every-wrong). R4's ranking must account for this scale difference — do not compare rule-based and BKT scores directly.
- R3. **Zero-sample rule.** A prerequisite with fewer than 3 practice attempts is silently excluded from the diagnosis result. It does not appear in the diagnostic card and is not mentioned in copy. (The existing post-practice result-page card is deliberately unchanged by this plan — it continues to show all unmet direct prerequisites including zero-sample ones; see KTD6 and the Assumptions section.)
- R4. **Ranking.** Among qualified candidates, sort by BKT mastery ascending; ties broken by depth descending (deeper first). When candidates span the estimator boundary (3–4 attempts via rule-based vs. 5+ via BKT), BKT-estimated candidates (5+ attempts, more evidence) sort before rule-based candidates (3–4 attempts, thin evidence); then by mastery ascending within each class. Never compare scores across classes directly.
- R5. **Cycle safety.** The backtrace must terminate cleanly on cyclic `LearningDependency` edges (visited-set tracking); cycles must not produce infinite traversal or duplicate entries. A topic reached through multiple paths is deduped by topic id at its minimum depth.

**API surface**

- R6. **Endpoint contract.** The diagnosis result is exposed through the existing `GET /practice/recommend` endpoint, extended in place with a `?diagnosis=true` query flag. When `diagnosis=true` (the start-page call), the endpoint runs the multi-hop backtrace and returns the diagnosis fields (`depth`, `bkt_mastery`, `sample_size`) alongside the existing fields. When the flag is omitted (the existing result-phase caller, which runs from the session result screen after a low-score session), the endpoint retains its current single-hop weak-prerequisite behavior, unchanged. The response shape remains `list[RecommendResponse]` — the diagnosis fields are optional fields added to the existing schema, so the existing post-practice frontend caller is unaffected. Fields on the diagnosis items: `topic_id`, `topic_name`, `topic_name_zh`, `depth`, `bkt_mastery`, `sample_size`, `accuracy`, `mastery_level`. The existing `accuracy` and `mastery_level` fields are preserved for the post-practice recommendation card, which is a second consumer of this endpoint (rendered on the session result page after a low-score session). The diagnosis-impression record (see R12) is written server-side whenever a `diagnosis=true` response carries a qualified weak-prerequisite candidate.
- R7. **Discriminator.** Each `RecommendResponse` item carries an `is_diagnosis` discriminator (default `false`), set to `true` only on items returned by the `diagnosis=true` backtrace, so the frontend can render diagnosis items with the diagnostic card copy and ordinary recommendations with the existing copy. The existing `is_prerequisite` field continues to distinguish prerequisite recommendations from weak-topic recommendations.

**Frontend — Practice start page**

- R8. **Inline diagnostic card.** On the practice mode-selection screen (`PracticeSessionPage.vue`, route `/learning/practice/:topicId`), when the recommendation response contains at least one qualified weak-prerequisite recommendation, render an inline card above the mode-selection buttons. Exactly one card naming the top-ranked candidate is shown — one call to action, so a 3rd–6th grader is not asked to weigh a list. The card shows the prerequisite name plus one evidence sentence derived from `sample_size` in child language (e.g. "you practised this 5 times and it's not sticking yet"); it never renders `bkt_mastery` as a numeric value or `depth`. The prerequisite name falls back from `topic_name_zh`/`topic_name` to a humanized last resort — never a raw `topic_key` string. The evidence sentence renders only when both the prerequisite name and the target topic name are resolved. Copy frames it as "your foundation may need work on X" rather than "you are weak". The card offers a "practice X first" action and a "continue anyway" action. While the diagnosis request is in flight, a compact skeleton of the final card height reserves the space so the CTA does not shift; on request failure the card is silently omitted (no retry, any error including auth is swallowed). "Continue anyway" performs no persistence — it sets an in-memory dismissal for the current page mount, and the card re-renders on the next topic open if the diagnosis conditions still hold.
- R9. **Non-blocking original CTA.** The original topic's "start practice" CTA must remain visible and functional. The child can bypass the recommendation without friction.
- R10. **Coexistence with guidance.** The backend diagnosis response omits any direct (depth-1) prerequisite of the target topic that is unmet, since these are already surfaced by the prerequisite guidance for the topic. The frontend renders the first remaining candidate from the response, or shows no card if all candidates were filtered.
- R11. **i18n.** Add/extend copy keys in the top-level `practice` namespace (adjacent to the existing `prereqReview` / `prereqReason` keys), with `learning.smart_tutor.broken_link_hint` as the tone precedent for evidence-backed gap wording. Copy must match the project's child-friendly tone in zh-CN and en-US, with keys added to BOTH locale files. The localized name selection follows the `startsWith('zh')` convention (as `PrerequisiteGuidance.vue` does), not exact `locale === 'en-US'` matching. Candidate copy (for owner review):
  - `practice.diagnosis.title`: zh `{{name}} 练得还不太稳` / en `{{name}} needs a little more practice`
  - `practice.diagnosis.evidence`: zh `你练过 {{count}} 次，还没练熟。先巩固一下，{{topic}} 会更容易！` / en `You've tried {{count}} times and it's not quite sticking yet. A quick review will make {{topic}} easier!`
  - `practice.diagnosis.practiceFirst`: zh `先练 {{name}}` / en `Practice {{name}} first`
  - `practice.diagnosis.continue`: zh `继续练 {{topic}}` / en `Keep practicing {{topic}}`
  - The evidence sentence uses `sample_size` only; no mastery percentage or depth is shown to the child.
- R12. **Diagnosis-impression record.** Every `diagnosis=true` response carrying a qualified weak-prerequisite candidate writes a server-side record keyed by `child_id` + `target_topic_id` + `recommended_topic_id` + `timestamp`, including `bkt_mastery`, `sample_size`, and the config/threshold version used. The record is written when the server returns the candidate (not when the child sees the card) — the measurement caveats this creates for SC1/SC2 are recorded in the Assumptions section. The write uses the request's injected db session.
- R13. **Diagnosis-referrer suppression.** When the child navigates to a recommended prerequisite via the diagnostic card's "practice X first" action, the navigation carries a referrer marker (`?fromDiagnosis={sourceTopicId}`) and the page fully resets its session state (phase, session, questions, result, discovery config) for the new topic — the same route is reused with a different param, so without an explicit reset the child would land on the prerequisite still in the previous topic's phase. The marker is added only by the card's navigation, never by back-navigation. The diagnostic card is suppressed on arrivals carrying this marker (a non-numeric or unknown marker value is ignored and does not suppress), so a diagnosis can only be acted on one level per visit.

### Acceptance Examples

- AE1. **Covers R1, R2, R4, R6.**
  - **Given** a child has 8 attempts on "分数加法" (BKT mastery 0.40), a direct prerequisite "通分" that is mastered (excluded by the mastery filter), a depth-2 prerequisite "最小公倍数" with 4 attempts (rule-based estimate 0.30), and a depth-1 prerequisite "约分" with 6 attempts (BKT mastery 0.35, but unmet — excluded by R10 as a direct unmet prerequisite).
  - **When** the child opens "分数加法" practice.
  - **Then** the diagnosis returns only "最小公倍数" (the depth-2 candidate); the diagnostic card names "最小公倍数".
- AE2. **Covers R3, R6.**
  - **Given** a child has 8 attempts on "分数加法" (BKT mastery 0.40), but the direct prerequisite "通分" has 0 practice attempts.
  - **When** the child opens "分数加法" practice.
  - **Then** the diagnosis result does NOT include "通分" (zero-sample). If no other qualified weak prerequisite exists, no diagnostic card appears.
- AE3. **Covers R8, R9.**
  - **Given** the diagnostic card is shown for "最小公倍数" on the "分数加法" practice start page.
  - **When** the child views the page.
  - **Then** they see the diagnostic card naming "最小公倍数" with a "practice 最小公倍数 first" action AND the original "start 分数加法" CTA is still visible; tapping either navigates to the corresponding practice, and the "practice X first" navigation carries `?fromDiagnosis={分数加法 topic id}`.
- AE4. **Covers R10, F2.**
  - **Given** "约分" is both a weak-prerequisite candidate AND a direct unmet prerequisite of "分数加法" (already surfaced by the prerequisite guidance).
  - **When** the child opens the topic.
  - **Then** the backend diagnosis response omits "约分" (excluded as a direct unmet prerequisite). The diagnostic card does not appear for "约分". The prerequisite guidance surface on the learning map is unchanged.
- AE5. **Covers R2.**
  - **Given** a child has 2 attempts on "分数加法" (below the ≥3 min guard).
  - **When** the child opens "分数加法" practice.
  - **Then** the diagnosis is not run; no diagnostic card appears.
- AE6. **Covers R2.**
  - **Given** a child has 5 attempts on "分数加法" (BKT mastery 0.75, above threshold).
  - **When** the child opens "分数加法" practice.
  - **Then** the diagnosis is not run; no diagnostic card appears.
- AE7. **Covers R5.**
  - **Given** the prerequisite graph contains a cycle among topics A → B → A (defensive check), and B satisfies all weak-candidate filters.
  - **When** the diagnosis is invoked for A.
  - **Then** the backtrace terminates without error; B is returned at depth 1; A is not revisited (visited-set); the result contains no duplicates.
- AE8. **Covers R4 (estimator-class ranking).**
  - **Given** the target topic is stuck, and two qualified candidates exist: candidate X with 6 attempts (BKT estimate 0.45) and candidate Y with 4 attempts (rule-based estimate 0.30).
  - **When** the diagnosis runs.
  - **Then** X ranks before Y despite the higher mastery number, because BKT-estimated candidates sort before rule-based candidates.

### Success Criteria

- SC1. At least one real child sees the diagnostic card within 2 weeks of deployment, on a topic where they have sustained practice history.
- SC2. Of children who see the diagnostic card, ≥ 30% follow the "practice X first" link within 4 weeks of deployment.
- SC3. Children who follow the recommendation show a measurable BKT-mastery increase on the original topic within 30 days of completing the prerequisite practice (longitudinal observation; no A/B required).
- SC4. Children who see the diagnostic card and do NOT follow it do NOT show a statistically-significant BKT-mastery decrease on the original topic (the "no harm" check).
- SC5. Zero incidents where the diagnostic card names a prerequisite whose `mastery_level` is `mastered` at the moment the card is rendered.

### Scope Boundaries

**Deferred for later**

- Auto-creation of a `session_mode="remedial"` practice session and the topic-lock-then-unlock flow (original-issue Key Task #4 and part of Key Task #6).
- A/B testing framework (original-issue Key Task #7) — the repo has no experiment infrastructure; longitudinal metrics SC3 and SC4 cover the same question without a framework.
- System-wide "district" model — finding a weak prerequisite that unlocks multiple stuck topics simultaneously, not just the current one.
- Parent-facing diagnostic visibility and parent-dashboard entry point.
- Depth > 2 traversal or adaptive depth (currently fixed at 2).
- Impression semantics refinement for SC1/SC2 measurement (shown-vs-returned distinction, refresh dedupe, "followed" event capture) — see Assumptions.
- A return-to-source affordance on the prerequisite's result page ("continue to {source topic}" when arriving via `fromDiagnosis`) — the natural payoff moment, deferred with the marker retained as pure suppression.

**Outside this product's identity**

- Misconception diagnosis (#214 — the next issue in the epic) — that issue is about *why* a prerequisite is weak, not *whether* it is weak. This plan stops at "you are weak on 通分"; #214 will ask "why".

### Dependencies / Assumptions

- **Depends on #212** — per-skill BKT calibration, shipped 2026-11.
- **Depends on the backward-BFS-with-visited-set pattern** in `server/apps/backend/app/services/learning/path_service.py` (`sort_topics_by_prerequisites`) — the backtrace reuses this adjacency-map + deque + visited-set shape directly in `adaptive_service`, with `mcp_session.py` left untouched.
- **Assumes `LearningDependency` edges are accurate and non-cyclic** (or at least that cycles are rare and finite). R5 requires defensive visited-set tracking regardless.
- **Assumes the causal hypothesis holds for a meaningful fraction of cases** ("failing a topic often means a weak prerequisite is the real cause"). This plan does not validate the hypothesis; it builds a system that will surface data to validate it via SC3 and SC4 metrics.
- **Assumes the existing `PrerequisiteGuidance.vue` bottom-sheet remains the surface for showing unmet prerequisites** (all edges, hard + soft). If that component is reworked later, KTD8 must be revisited.

### Outstanding Questions

**Resolved (code-verified during planning):**

- **Host page** — the diagnostic card renders on the practice mode-selection screen (`PracticeSessionPage.vue`, route `/learning/practice/:topicId`), above the mode buttons. The existing `difficultyWarning` dialog lives on the separate learning flow (`LearningTopicPage.vue`'s "Start Learning" button → `createSession`), so the card and the dialog never appear on the same surface.
- **Endpoint** — extend `GET /practice/recommend` in place with a `?diagnosis=true` query flag; the post-practice result-phase call omits the flag and keeps current behavior, including the unchanged `list[RecommendResponse]` response shape.
- **Topic name on the mode screen** — `PracticeSessionPage.vue` already renders `displayTopicName` (line 176), so the mode screen titles with the topic name; the evidence sentence's `{{topic}}` uses that resolved name.
- **Re-run behavior** — the diagnosis re-runs on the next topic-open (page mount reaching mode phase) if conditions still hold, except arrivals carrying the `?fromDiagnosis=` referrer marker (R13).
- **Estimator class ordering** — BKT-estimated candidates (5+ attempts) rank before rule-based candidates (3–4 attempts); resolved from evidence: a recommendation backed by 5+ attempts is safer to show a child than one backed by thin evidence.

**Remaining decisions:**

- **Settled this session**: BKT trigger threshold = 0.60 as the initial production value. The shipped estimator's floor (~0.346 all-wrong) and rising-with-attempts behavior were weighed; 0.60 is kept as the conservative starting point, to be re-tuned against the observed distribution once the R12 impression records accumulate real data.
- **Settled this session**: card copy drafted in R11 (zh-CN and en-US candidates listed there) — pending a final owner review of the exact wording before implementation locks the i18n keys. Two open wording concerns flagged from the flow analysis: (a) showing the raw count for exactly 3 attempts can read as a reprimand, and for 30+ attempts is demoralizing — the owner may want to cap or soften the count ("练了好几次") without misreporting; (b) "还没练熟" was chosen over "还没完全掌握" because the evidence basis is attempts, not a mastery state.
- **Open (owner decision, from doc review)**: Accessibility facet on the diagnostic card (U4) — the card appears asynchronously above the mode buttons; an aria-live announcement when it renders, keyboard-reachable native buttons, and DOM order matching visual order are proposed but not yet committed. Recommend accepting (project has a11y quality standards).
- **Open (owner decision, from doc review)**: Skeleton timeout — if the diagnosis request does not settle within a short bound (e.g. 8s), silently remove the reserved skeleton rather than leaving an empty block above the CTA. Recommend accepting.
- **Open (owner decision, from doc review)**: Defer the R12 impression table (and U1) out of the MVP, reading SC1/SC2 from server request logs instead — the plan acknowledges the impression denominators are unreliable (AS1). Recommend deferring only if SC measurement can genuinely run from logs; otherwise keep U1.
- **Open (owner, post-ship)**: KTD8's conflict call-out — children arriving directly at the practice page (from `TodayLearningCard` / `LearningProgressPage`) never see `PrerequisiteGuidance.vue`, so for them the depth-1 exclusion suppresses the most obvious recommendation. If real-child data shows this hurts SC2, revisit with differentiated copy rather than removing the exclusion.

---

## Planning Contract

### Key Technical Decisions

- KTD9. **Diagnosis function lives in `adaptive_service.py`.** A new `diagnose_weak_prerequisites(db, topic_id, child_id)` function implements the depth-2 backtrace, reusing the adjacency-map + visited-set BFS shape from `path_service.sort_topics_by_prerequisites`. It does NOT reuse `find_weak_prerequisites` — that function ranks by raw accuracy over unmet prerequisites, which is exactly the metric this plan replaces with the calibrated estimator.
- KTD10. **Threshold as a module constant.** `DIAGNOSIS_MASTERY_THRESHOLD = 0.60` in `adaptive_service.py`, passed into the R12 impression record's config-version field. No existing constant covers this (verified: mastery thresholds live only in `mastery_level` string logic and the 0.3/0.7/0.85 difficulty mapping).
- KTD11. **Estimator usage.** Both target and candidates are scored via `BayesianKnowledgeTracingEstimator.estimate(db, child_id, topic_id)` — its built-in fallback to `RuleBasedMasteryEstimator` below 5 attempts produces the two estimator classes R4 ranks. The estimator class of each candidate is derived from its attempt count (≥5 → BKT, else rule-based), not a second scoring call.
- KTD12. **Response contract.** `GET /practice/recommend` keeps `response_model=list[RecommendResponse]`. New optional fields on `RecommendResponse` (extending `SnowflakeBase`): `is_diagnosis: bool = False`, `depth: int | None = None`, `bkt_mastery: float | None = None`, `sample_size: int | None = None`. A new `DiagnosisImpressionCreate` path (schema + model) does not touch the response list.
- KTD13. **Impression persistence.** New `DiagnosisImpression` ORM model in `server/packages/db/models/learning/` (child_id, target_topic_id, recommended_topic_id, bkt_mastery, sample_size, config_version, created_at; snowflake BigInteger id; index on child_id) + explicit Alembic revision (plain `op.create_table`, following the `u1470x53wpq8_add_skill_registry_table.py` pattern). The write happens in the service layer using the request's injected db session — never a self-opened `SessionLocal()` (test-isolation lesson from the audit-service incident).
- KTD14. **Frontend request lifecycle.** The diagnosis request fires when the page reaches the mode-selection phase (not on raw mount, so discovery-phase children do not generate impressions for cards they never see), carries `?diagnosis=true`, and its result renders only in the mode phase. A per-mount `dismissed` ref suppresses the card after "continue anyway". The `fromDiagnosis` query param suppresses the request entirely on arrival.
- KTD15. **Candidate practiceability.** The backtrace excludes deprecated topics (R1) and — as a follow-on guard so the card's CTA never dead-ends — candidates with zero practiceable questions, using the same question-availability check the practice session creation path applies (`PRACTICE_NO_QUESTIONS_AVAILABLE` guard in `routers/practice.py`).

### Assumptions

Pipeline-run assumptions (unvalidated agent bets, carried to the PR body):

- AS1. **Impression-on-return semantics are accepted for MVP.** R12 records are written when the server returns a candidate, not when the child sees the card. Refreshes can multiply records; network failure after a server write pollutes the SC1/SC2 denominator. Refinement (shown/followed beacons, dedupe) is deferred (Scope Boundaries).
- AS2. **The post-practice result-page card is left semantically inconsistent with the diagnosis.** It continues to show zero-sample unmet prerequisites (which R3 forbids for the diagnostic card) using accuracy-based ranking. Accepted deliberately: changing it is out of scope and its copy is distinct by KTD6.
- AS3 (resolved during doc review). **`createPracticeSession` DOES hard-lock on locked topics** — `routers/practice.py:167` raises `PRACTICE_TOPIC_LOCKED` when the stored `mastery_level` is `locked`, and `get_or_create_progress` sets `locked` whenever any hard prerequisite lacks a mastered row. The diagnosis therefore excludes `locked` candidates (R1c, U2 step 4), keeping the card's CTA reachable without weakening the lock (KTD1).
- AS4. **Rule-based candidates at exactly 3 attempts may render "你练过 3 次".** The copy concern is flagged for owner review in Outstanding Questions; implementation ships the drafted copy unless the owner adjusts it before i18n keys land.

### Sequencing

U1 (model + migration) → U2 (service) → U3 (endpoint) → U4 (frontend card + page wiring). U2–U4 are strictly ordered; U1 is a prerequisite of U2 only because the service writes impressions.

---

## Implementation Units

### U1. DiagnosisImpression model + migration

- **Goal:** Persisted record for every qualified diagnosis response (R12).
- **Requirements:** R12.
- **Dependencies:** none.
- **Files:** `server/packages/db/models/learning/diagnosis_impression.py` (new), `server/packages/db/models/learning/__init__.py` (export), `server/apps/backend/alembic/versions/<generated>_add_diagnosis_impression.py` (new), `server/apps/backend/alembic/env.py` (only if model auto-discovery requires it), `server/tests/backend/test_diagnosis_impression_model.py` (new).
- **Approach:**
  1. Define `DiagnosisImpression` on the shared `Base` with snowflake BigInteger id, child/target/recommended topic ids, `bkt_mastery` float, `sample_size` int, `config_version` string, `created_at`; index on `(child_id, created_at)`.
  2. Generate the Alembic revision from `server/apps/backend/` after checking `alembic heads` (single-chain); plain `op.create_table`, no auto-migrate string defaults.
- **Patterns to follow:** `packages/db/models/learning/practice.py` (PracticeAttempt), migration `u1470x53wpq8_add_skill_registry_table.py`.
- **Test scenarios:**
  - Creating a record persists all fields and round-trips via a fresh query.
  - Two records for the same (child, target, recommended) pair are both stored (no unique constraint — refresh multiplicity is accepted per AS1).
- **Verification:** `uv run pytest tests/backend/test_diagnosis_impression_model.py -v` from `server/`; migration upgrades and downgrades cleanly on a scratch DB.

### U2. Backtrace diagnosis service

- **Goal:** `diagnose_weak_prerequisites` implementing R1–R5 with ranking, exclusion, and dedupe; writes the R12 impression.
- **Requirements:** R1, R2, R3, R4, R5, R10 (exclusion), R12; KTD9–KTD11, KTD13, KTD15.
- **Dependencies:** U1.
- **Files:** `server/apps/backend/app/services/learning/adaptive_service.py` (new function + threshold constant), `server/tests/backend/test_diagnosis_backtrace.py` (new).
- **Approach:**
  1. Add `DIAGNOSIS_MASTERY_THRESHOLD = 0.60` and `diagnose_weak_prerequisites(db, topic_id, child_id) -> list[dict]`.
  2. Load all hard `LearningDependency` edges (the full-load pattern is established at this graph size), build the upstream adjacency map, BFS to depth 2 with a visited set, recording each topic's minimum depth.
  3. Gate on the target (≥3 attempts, estimate below threshold — accepting the rule-based fallback per R2); return empty before any traversal otherwise.
  4. Filter candidates: ≥3 attempts, estimate below threshold, `mastery_level` not in {"mastered", "locked"} from `LearningProgress` (default to non-mastered when no progress row exists), topic not deprecated, has practiceable questions (KTD15), not a direct unmet prerequisite (compute the depth-1 unmet set once via the same logic `get_unmet_prerequisites` uses).
  5. Rank per R4 (BKT-class first, mastery ascending, depth descending) and dedupe by topic id at minimum depth.
  6. Write one `DiagnosisImpression` row per qualified candidate using the injected `db` session.
- **Patterns to follow:** `path_service.sort_topics_by_prerequisites` (BFS + visited set), `find_weak_prerequisites` (dict return shape for the router), test fixture pattern from `test_adaptive_enhanced.py`.
- **Test scenarios:**
  - Covers AE1: direct mastered prereq excluded (mastery filter), direct unmet prereq excluded (R10), depth-2 candidate returned and ranked top.
  - Covers AE2: zero-attempt prerequisite silently absent.
  - Covers AE5 / AE6: target with 2 attempts, and target with mastery above threshold — both return empty, no impression written.
  - Covers AE7: cyclic A→B→A edges terminate; B returned at depth 1; no duplicates.
  - Covers AE8: 6-attempt BKT candidate ranks above 4-attempt rule-based candidate with a lower score.
  - Diamond graph: same prerequisite reachable at depth 1 and 2 appears once, at depth 1.
  - Candidate with `mastery_level == 'mastered'` but recent low BKT is excluded (SC5 guard).
  - Deprecated candidate topic excluded.
  - Candidate with stored `mastery_level == 'locked'` (≥3 attempts, otherwise weak) is not returned — the CTA must not dead-end on `PRACTICE_TOPIC_LOCKED`.
  - Impression row written with correct fields whenever a qualified candidate is returned.
- **Verification:** `uv run pytest tests/backend/test_diagnosis_backtrace.py -v`, `uv run ruff check apps/backend/app/services/learning/adaptive_service.py`, `uv run mypy apps/backend/app/services/learning/adaptive_service.py` from `server/`.

### U3. Endpoint extension

- **Goal:** `GET /practice/recommend?diagnosis=true` returns diagnosis items without changing the existing response shape or the flag-less behavior (R6, R7).
- **Requirements:** R6, R7; KTD12.
- **Dependencies:** U2.
- **Files:** `server/apps/backend/app/routers/practice.py` (extend `get_practice_recommendations`), `server/apps/backend/app/schemas/practice.py` (optional fields on `RecommendResponse`), `server/tests/backend/test_practice_recommend_diagnosis.py` (new).
- **Approach:**
  1. Add `diagnosis: bool = Query(default=False)` to the endpoint (precedent: `min_attempts` on `/weak-topics`).
  2. When `diagnosis=True` and `topic_id` is present, call `diagnose_weak_prerequisites` and map results to `RecommendResponse` items with `is_diagnosis=True`, `is_prerequisite=True`, `prerequisite_of_topic_id=topic_id`, plus the diagnosis fields. When `diagnosis=True` without `topic_id`, return an empty list (diagnosis is topic-scoped).
  3. Flag-less path (both with and without topic_id) byte-identical to current behavior.
- **Patterns to follow:** Existing endpoint body at `routers/practice.py:385`; schema at `schemas/practice.py` (SnowflakeBase).
- **Test scenarios:**
  - `diagnosis=true` with a stuck target returns items with `is_diagnosis`, `depth`, `bkt_mastery`, `sample_size` populated and IDs serialized as strings.
  - `diagnosis=true` without `topic_id` returns `[]`.
  - Omitting the flag with `topic_id` returns the current accuracy-sorted unmet-prereq list with `is_diagnosis` absent/false.
  - Omitting the flag without `topic_id` returns weak topics as today.
  - Existing post-practice consumer contract: response remains a JSON list (envelope-wrapped as today).
- **Verification:** `uv run pytest tests/backend/test_practice_recommend_diagnosis.py tests/backend/test_schemas_practice.py -v` from `server/`.

### U4. Frontend diagnostic card + page wiring

- **Goal:** The child sees the inline diagnostic card on the practice mode screen with both actions, the loading skeleton, suppression, and the reset-on-referral behavior (R8, R9, R13; F1).
- **Requirements:** R8, R9, R11, R13; KTD14.
- **Dependencies:** U3.
- **Files:** `frontend/apps/child/src/components/learning/DiagnosisCard.vue` (new), `frontend/apps/child/src/components/learning/DiagnosisCard.test.ts` (new), `frontend/apps/child/src/pages/learning/PracticeSessionPage.vue` (modify), `frontend/apps/child/src/pages/learning/PracticeSessionPage.test.ts` (new or extend), `frontend/apps/child/src/api/practice.ts` (extend `getPracticeRecommendations` with the flag), `frontend/apps/child/src/i18n/locales/zh-CN.ts`, `frontend/apps/child/src/i18n/locales/en-US.ts` (new `practice.diagnosis.*` keys in both).
- **Approach:**
  1. Extend the API wrapper to pass `diagnosis: true` when requested; widen the `RecommendResponse` TS type with optional `is_diagnosis`, `depth`, `bkt_mastery`, `sample_size` (all `string`/`number` per snowflake rules — ids stay `string`).
  2. Create `DiagnosisCard.vue` (self-gating, Vant 4 cell-group, Clay tokens defined in both `:root` and `[data-theme="dark"]`): localized name via `startsWith('zh')` convention, evidence sentence gated on both names being resolved, "practice X first" and "continue anyway" actions emitting events.
  3. In `PracticeSessionPage.vue`: fetch the target topic via `getTopicDetail(topicId)` when entering the `mode` phase (the existing `displayTopicName` is generic at this phase — it derives from the session, which does not exist yet — and the card's `{{topic}}` needs the resolved name) and pass it into the card; fire the diagnosis request on reaching the `mode` phase (skip when the URL carries a valid `fromDiagnosis`), keep a per-mount `dismissed` ref, render the skeleton at card height while in flight, render the card only in `mode` phase, silently drop failures, and on "practice X first" reset all session state and push the same route with the new topic id + `?fromDiagnosis={sourceTopicId}`.
  4. Add the i18n keys adjacent to `practice.prereqReview` in both locale files; no hardcoded strings.
- **Patterns to follow:** `useDebtWarning` inline-bar precedent for above-CTA placement; `PrerequisiteGuidance.vue` for name localization and test structure; three-state rendering conventions.
- **Execution note:** Add component tests before wiring the page (card rendering, event emission, suppression), then page-level tests for the request lifecycle and route-reuse reset.
- **Test scenarios:**
  - Covers AE3: card names the candidate; both the card action and the original CTA are visible; each navigates correctly; the referral navigation carries `fromDiagnosis`.
  - Card hidden while request in flight → skeleton at reserved height; CTA does not shift.
  - Request failure (including 401) → no card, no retry, no error toast, mode buttons unaffected.
  - "Continue anyway" → card hidden for this mount; re-mount re-fetches.
  - Arrival with valid `fromDiagnosis` → no diagnosis request fired.
  - Arrival with garbage `fromDiagnosis` value → request fires normally.
  - Response arriving after the child started answering → card never renders.
  - Route-reuse reset: from the card's action, the page re-renders in `mode` phase for the new topic with no residual session/result state.
  - i18n: all four keys present in both zh-CN and en-US; evidence sentence interpolates name, count, and topic.
- **Verification:** `pnpm test:run` and `pnpm typecheck` from `frontend/apps/child/` (or workspace root per frontend/AGENTS.md).

---

## Verification Contract

| Scope | Command (from) | Proves |
|---|---|---|
| Backend service + endpoint + model | `uv run pytest tests/backend/ -v` (server/) | U1–U3 scenarios, no regressions in existing learning tests |
| Backend lint/types | `uv run ruff check apps/backend/...` and `uv run mypy apps/backend/...` (server/) | Module conventions |
| Migration | `uv run alembic upgrade head` then `downgrade -1` then `upgrade head` (server/apps/backend/) | Reversible schema change |
| Frontend | `pnpm -r test:run` and `pnpm -r typecheck` (frontend/) | U4 scenarios, TS types, i18n key completeness |

Behavioral gates: AE1–AE8 each map to at least one automated test scenario in U2/U3/U4. SC1–SC5 are post-deployment observations, not automated gates; their measurement caveat is AS1.

## Definition of Done

- All units U1–U4 implemented, and every command in the Verification Contract passes in a clean run.
- The existing post-practice result-phase call and card render exactly as before (regression covered by existing tests plus the U3 contract scenarios).
- No `TODO` placeholders, no skipped tests, no stubbed branches in the diff; abandoned experimental code removed.
- i18n keys exist in both zh-CN and en-US; no hardcoded user-facing strings.
- `git status` clean of stray scratch files; only touched files formatted.
