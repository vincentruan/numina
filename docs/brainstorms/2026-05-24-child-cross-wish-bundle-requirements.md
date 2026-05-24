---
date: 2026-05-24
topic: child-cross-wish-bundle
seed_ideation: docs/ideation/2026-04-14-children-starcoin-ideation.md (ideas #10 + #11 + #12)
mode: standard
---

# Child Cross-Wish Reachability + Opportunity-Cost Peek Bundle

## Summary

Layer three child-frontend surfaces on top of the existing `ChildWishStats.priority_simulation[]` payload to make multi-wish affordability and trade-offs visible without backend changes: a traffic-light wish constellation grid (overview), a non-committing "what-if" trade telescope (long-press peek of how spending would shift other wishes), and a time-denominated price read on each wish ("≈ N 天"). Tap a grid card to drill into a per-wish full-screen detail. Bundle ships as one v1; the parent main app gets a single "孩子的预估时间会跳变 X 天 → Y 天" warning when a parent edits `star_coin_cost` mid-save, to preserve the system-trust contract that the child UX depends on.

---

## Problem Frame

Numina ships a child-facing wish system today where each wish has its own progress bar, a 25/50/75% star marker overlay, and an estimated `再做约 X 天家务` derived client-side from the recent coin ledger. The backend already returns per-wish affordability data — `star_coin_cost`, `progress`, `covered`, `shortfall_for_high_priority` — through `GET /child/wishes/stats`. Two problems land on top of that already-built data layer:

1. **5–8 year olds cannot mentally compare three independent progress bars.** When `priority_simulation[]` returns three wishes at 67% / 31% / 8% with different costs, the page shows the kid three rectangles stacked vertically and asks them to reason about which is closest, which is reachable today, and which is most worth saving for. None of those questions get a visual answer. GoHenry, Greenlight, and RoosterMoney all have the same gap — every children's banking app silos each savings goal in its own bar. This is the unmet design space the constellation grid fills.

2. **Spending one wish silently delays the others, and that delay is invisible until after the redemption.** The current redeem flow is a silent confirm. A child cannot connect "I just bought the small toy" to "now my big wish is 7 days further away," because nothing in the UI shows that link. Mischel/Kidd 2013 marshmallow research, in its modern revisions, points to this exact gap: delayed-gratification training works through visible cause-and-effect, not willpower. A child who cannot see the trade-off cannot internalize it.

A third problem compounds both: today's progress is shown as a percentage and a coin shortfall. Kindergarteners and early-elementary kids reason fluently in days/sleeps, far before three-digit arithmetic. The "再做约 X 天家务" string is already present on one read site but is not the headline on any wish card.

The constellation grid, what-if peek, and time-denominated price are three lenses on the same `priority_simulation[]` payload. They share a single client-side derivation pipeline (the existing 7-day rolling earn velocity in `ChildWishesPage.vue`), so they ship as one bundle.

---

## Actors

- A1. **Child user (5–10 yo)** — opens the wishes page on a mobile device, can recognize traffic-light colors and emoji icons, may not yet read fluently. Long-press is reachable but not the default gesture.
- A2. **Parent (account owner)** — sets each wish's `star_coin_cost` from the main (adult) app; can edit cost on existing wishes; has visibility into the child's balance and ledger via the parent dashboard.
- A3. **Numina backend** — owns `GET /child/wishes/stats` and `GET /child/coins/ledger`; the source of `priority_simulation[]` and the coin transaction history client uses to derive earn velocity.

---

## Key Flows

- F1. **Child opens wishes page (overview → drill)**
  - **Trigger:** Child taps the wishes tab in `ChildTabBar`.
  - **Actors:** A1, A3.
  - **Steps:**
    1. Page fetches `getChildWishStats()` and `getCoinLedger()` (existing calls).
    2. Top section renders `<WishConstellationGrid>` — 3-column photo grid with one card per active wish. Each card shows the wish photo/emoji, name, traffic-light ring (green/yellow/red/gray), and a status icon.
    3. Headline above the grid reads `你今天可以拿到 K 个 / 共 N 个 心愿` where K = green count, N = active count.
    4. Below the grid, the existing status-grouped sections (active / redemption-pending / realized / rejected) remain as a fallback list view — unchanged.
    5. Child taps a grid card → router navigates to a per-wish detail full-screen view (zoom-in).
  - **Outcome:** Child sees one screen that answers "what can I get today?" without reading numbers.
  - **Covered by:** R1, R2, R3, R7, R10.

- F2. **Child long-presses a wish in the grid (what-if peek)**
  - **Trigger:** Child long-presses any wish card in the constellation grid.
  - **Actors:** A1.
  - **Steps:**
    1. On long-press start (≥350ms hold, threshold matches existing Vant convention), grid card lifts slightly and other wish cards' traffic-light rings dim.
    2. A 1.5-second ghost preview animates: each *other* active wish card shows its progress ring shrinking from current → "what it would be if you spent on this one." Each affected card shows a small `+N 天` floating label.
    3. The pressed wish card shows a `这个就能拿到啦 ✨` confirmation tag (no spend confirmation — peek only).
    4. On long-press release OR after 1.5s timeout, all rings auto-restore to current state with a soft fade.
    5. Nothing is committed. No API call. No state change. No haptic on release.
  - **Outcome:** Child sees, without committing, what spending now would cost the other wishes.
  - **Covered by:** R4, R5, R8, R12.

- F3. **Child redeems a wish (existing flow, unchanged in v1)**
  - **Trigger:** Child taps the redeem button on the per-wish detail view.
  - **Actors:** A1, A3.
  - **Steps:** Existing `requestRedemption()` flow unmodified — confirm dialog, API call, status flips to redemption-pending.
  - **Outcome:** Existing behavior preserved. Trade Telescope on the redeem confirm sheet is explicit v2.
  - **Covered by:** R13.

- F4. **Parent edits an existing wish's `star_coin_cost`**
  - **Trigger:** Parent opens the wish edit dialog in the main app and changes `star_coin_cost` on a wish that already has progress > 0%.
  - **Actors:** A2, A3.
  - **Steps:**
    1. Parent enters new cost.
    2. On confirm, the main app computes the child-visible delta — both the new days-estimate and whether the tint band would change — and surfaces a warning sheet:
       `这个心愿的预估时间会从 ≈ X 天变成 ≈ Y 天，是否确认？`
    3. Parent confirms or cancels.
    4. On confirm, write proceeds; on cancel, no change.
  - **Outcome:** Goalpost-moving is visible to the parent before commit. Kidd 2013 trust contract preserved end-to-end.
  - **Covered by:** R14.

---

## Requirements

**Wish Constellation Grid (overview)**

- R1. The wishes page renders a `<WishConstellationGrid>` component above the existing status-grouped sections, listing all active wishes (status = `active`) as a 3-column photo grid on mobile. Tablet/wide layouts may use 4 columns.
- R2. Each grid card displays: wish photo or emoji, wish name (truncated to one line), traffic-light ring border, and a status icon overlay (`✅` for green, `⏳` for yellow, dim ring with no icon for red, gray dashed ring for placeholder/insufficient-data).
- R3. The headline above the grid reads `你今天可以拿到 K 个 / 共 N 个 心愿` where K is the count of `green` wishes and N is `active_wish_count` from the existing payload. When K = 0 the headline reads `继续加油，离最近的心愿还差 D 天` (D = min days estimate across active wishes).
- R7. Tapping a grid card navigates to a per-wish detail full-screen view via the existing wishes router. The detail view scope is unchanged in v1 — it inherits the current per-wish layout (progress bar, redemption button, description). Future jar-fill animation work (Idea #3 from the seed ideation) lives inside the detail view, not the grid.
- R10. The existing status-grouped sections (active / redemption-pending / realized / rejected) below the grid remain unchanged in layout and content. The grid supplements; it does not replace.

**Reachability tint (shared primitive)**

- R8. A pure function `reachabilityTint(balance, priorSim, daysEstimate) → 'green' | 'yellow' | 'red' | 'gray'` is the single source of truth for tint state. Inputs are: `balance` from `ChildWishStats`, the wish's `priority_simulation` entry (`star_coin_cost`, `progress`, `covered`), and the days-estimate from the existing client-side ledger derivation.
- R9. Tint thresholds in v1 are front-end constants:
  - `green` when `covered === true` (i.e., `balance >= star_coin_cost`)
  - `yellow` when not covered AND `daysEstimate ≤ 14`
  - `red` when not covered AND `daysEstimate > 14`
  - `gray` when the days-estimate is unstable (fewer than 3 distinct earning days in the last 7 days; same threshold as the existing `wishDaysMap` computation in `ChildWishesPage.vue`)
  Family-configurable thresholds are explicit v2.
- R11. Each tint state has a corresponding ARIA label sourced from `t('wishes.tint.{green|yellow|red|gray}.aria')`. Suggested labels: green → `可以兑换啦`; yellow → `快可以兑换了`; red → `还要再等一阵子`; gray → `继续做家务，几天后能更准估计`. Both `zh-CN.ts` and `en-US.ts` must define the keys.

**What-if peek (Trade Telescope v1)**

- R4. Long-pressing a wish card in the constellation grid (≥350ms threshold) triggers a non-committing 1.5-second ghost preview that visually shrinks the *other* active wish cards' progress rings to their hypothetical post-spend value. Each affected wish card displays a small floating `+N 天` label.
- R5. The pressed (origin) wish card displays a `这个就能拿到啦 ✨` confirmation tag during the preview. No commit step. No API call. No haptic. No persistent state change.
- R6. After the 1.5-second timeout OR on long-press release, all visual state restores to the current ground-truth tint and progress with a soft fade. The ground-truth tint is recomputed in case `priority_simulation[]` was refetched during the peek.
- R12. The peek is driven by a pure client function `previewSpend(wishId, balance, priorSim) → { deltas: [{ wish_id, before_progress, after_progress, days_added }] }`. No I/O. The function's `deltas` array drives both the ring animation and the `+N 天` labels. Wishes where the spend would not move the bar (e.g., the wish already covered) get `days_added: 0` and no label.

**Time-denominated wish price**

- R13. Each grid card and the per-wish detail view display a secondary text read `≈ N 天` next to or below the existing star-coin price, where N is the days-estimate from the existing `wishDaysMap` computation. When the days-estimate is unstable (gray tint condition, R9), the secondary read is replaced by placeholder copy: `继续做家务，几天后能更准估计`. The unit in v1 is `天` only; configurable units (`晴天` / `睡觉` / `周末`) are explicit v2.

**Trust-contract path (cross-app)**

- R14. The parent main app's existing wish-edit dialog must, when `star_coin_cost` is changed on a wish where `progress > 0%`, display a confirmation sheet showing the *child's* days-estimate before vs after: `这个心愿的预估时间会从 ≈ X 天变成 ≈ Y 天，是否确认？`. The confirmation sheet is required only when X ≠ Y by ≥1 day OR when the tint band (green/yellow/red) would change. Computation may reuse the same client function as the child app, accepting the parent's cached child balance + ledger or fetching fresh data via existing parent endpoints.

**Accessibility floor**

- R15. The component layer uses `useReducedMotion()`. When reduced motion is active:
  - The 1.5-second ghost preview in F2 is replaced by an instant static overlay showing each affected wish's `before → after` progress and `+N 天` label, dismissed on long-press release or on a 3-second timeout.
  - All other animations on the wishes page that this work introduces (card lift, ring fade, fade-restore) become static state changes.
- R16. Tint state is conveyed by **all three** of: color, status icon (R2), and ARIA label (R11). Color alone is never sufficient.

**i18n & design-system conformance**

- R17. All new user-facing strings live in both `frontend/apps/child/src/i18n/locales/zh-CN.ts` and `en-US.ts`. No string is hard-coded in `.vue` files or `.ts` logic, including template ternaries.
- R18. All new UI uses Clay design tokens from `frontend/apps/child/src/assets/clay.css`. No raw hex colors. Traffic-light ring colors map to existing semantic tokens (`--color-success`, `--color-warning`, `--color-error`) and adapt to `[data-theme="dark"]` automatically. The gray placeholder ring uses `--color-muted-soft`.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3, R8, R9.** Given a child has 3 active wishes — wish A (`star_coin_cost=20`, child balance=25, covered=true), wish B (`star_coin_cost=80`, balance=25, days-estimate=10), wish C (`star_coin_cost=200`, balance=25, days-estimate=30) — when the child opens the wishes page, then the grid renders 3 cards with rings green / yellow / red respectively, and the headline reads `你今天可以拿到 1 个 / 共 3 个 心愿`.

- AE2. **Covers R3.** Given a child has 2 active wishes both not yet covered (days-estimates 5 and 18), when the child opens the wishes page, then K=0 and the headline reads `继续加油，离最近的心愿还差 5 天`.

- AE3. **Covers R4, R5, R6, R12.** Given a child has wishes A (covered), B (`days=8`), C (`days=15`) and a balance of 50, when the child long-presses wish A, then within 1.5s wishes B and C visually shrink their rings to their post-spend progress and show `+3 天` and `+5 天` labels, wish A shows `这个就能拿到啦 ✨`, and on release the rings fade back to current state with no committed change.

- AE4. **Covers R9, R13.** Given a child has fewer than 3 distinct earning days in the last 7 days, when the wishes page renders, then every active wish card shows a gray dashed ring AND the `≈ N 天` secondary read is replaced by `继续做家务，几天后能更准估计`.

- AE5. **Covers R14.** Given a wish has child-side `progress = 60%` and the parent edits `star_coin_cost` from 100 to 150 in the main app, when the parent taps confirm, then the warning sheet shows `这个心愿的预估时间会从 ≈ 6 天变成 ≈ 14 天` (or the actual computed values) and the parent must tap a second confirm to commit.

- AE6. **Covers R14.** Given a wish has child-side `progress = 60%` and the parent edits `star_coin_cost` from 100 to 101, when the parent taps confirm, then the warning sheet does NOT appear (delta < 1 day AND tint band unchanged) and the edit commits directly.

- AE7. **Covers R15.** Given the device has `prefers-reduced-motion: reduce` set, when the child long-presses a wish card, then the ghost preview appears as a static instant-on overlay (not a 1.5s animation), and the overlay dismisses on long-press release or after 3 seconds.

- AE8. **Covers R7, R10.** Given a child taps a wish card in the constellation grid, when navigation completes, then the existing per-wish detail view is shown unmodified, AND the status-grouped sections below the grid on the wishes page remain unchanged when the child returns.

---

## Success Criteria

**Human outcome (child-side)**
- A 6-year-old, given two active wishes with different costs, can answer "which one can I get today?" within 5 seconds of opening the wishes page, by pointing at the green-ring card without reading any numbers.
- A 7-year-old, after long-pressing a wish once during onboarding, can articulate (in any wording) that "if I buy this one, the others get further" — the cause-effect link is internalized.
- Tinted-state recognition holds across at least one color-blind variant (deuteranopia simulation): the status icon + ARIA label are sufficient even when ring color is desaturated.

**Human outcome (parent-side)**
- A parent who edits `star_coin_cost` on an in-progress wish sees the child's days-estimate shift before commit, and reports (in qualitative testing) that this changes their willingness to retroactively reprice. Kidd 2013 trust-contract path is observable, not theoretical.

**Downstream-agent handoff (planner perspective)**
- `/ce-plan` does not need to invent: which surfaces are v1 vs v2, the tint thresholds, the days-estimate fallback behavior, the long-press threshold, the reduced-motion fallback shape, or the cross-app warning trigger condition. All decisions above are stated explicitly.
- `/ce-plan` may decide: the exact component file structure, whether the constellation grid is one component or several, whether the parent warning sheet reuses an existing dialog or a new one, the precise CSS token names for the four ring states, and the test strategy.

---

## Scope Boundaries

**Deferred for later (v2 backlog, ranked by likely demand)**
- Trade Telescope on the redeem confirm sheet, abandon-task hint, parent approval queue, and onboarding tutorial — v1 is the long-press what-if peek only.
- Configurable time units (`晴天` / `睡觉` / `周末`) — v1 is `天` only.
- Family-configurable tint thresholds (e.g., yellow window 7–21 days) — v1 is the constant 14-day boundary.
- Server-side earn-velocity field on `ChildWishStats` — v1 reuses the existing client-side derivation in `ChildWishesPage.vue`.
- Per-wish CSS-fill jar animation (seed Idea #3 from the 04-14 doc) — orthogonal to this bundle; lives in the wish-detail full-screen view if pursued.
- Parent-dashboard mirror of the constellation grid — same payload, parent-side; v2 would add it without backend change.
- Onboarding tutorial that demonstrates trade-off via synthetic wish data — v1 has no onboarding for these features.
- Color-blind palette toggle (e.g., blue/orange/red instead of green/yellow/red) — v1's color + icon + ARIA label is the accessibility floor; explicit alt-palette is v2.

**Explicit non-goals (v1)**
- The grid does not replace or remove the existing status-grouped sections.
- The redeem flow is not changed.
- No new server endpoints, no new server fields, no new SQLAlchemy migrations.
- No native haptic feedback on the long-press peek (would require Capacitor or similar; out of scope).
- No "lock" or "favorite" UI on grid cards — wish priority continues to be parent-set via the existing `priority` field.

---

## Key Decisions

- **Long-press for the what-if peek (not tap or swipe).** Decision: long-press is the secondary gesture; tap navigates to detail. Rationale: tap is already overloaded as the primary navigation; swipe conflicts with horizontal date-nav patterns elsewhere in the child app; long-press has a clear "explore without committing" semantic and is well-supported by Vant. Threshold matches Vant's default (≥350ms) so we don't introduce a new touch-handling primitive.
- **Yellow window = 14 days (not 7).** Decision: wider yellow band. Rationale: low-earning kids would see most wishes flip directly from gray → red without ever experiencing a yellow ("almost!") state. 14 days creates a meaningful "close" zone for typical earn velocities.
- **Constellation grid supplements, does not replace, the status-grouped sections.** Decision: dual-render. Rationale: status grouping serves a different question ("what's pending parental approval?" / "what's already realized?") than reachability. Killing it would lose information without gain.
- **Time unit is `天` only in v1.** Decision: hard-code "天". Rationale: unit selector is genuine UX work (where does it live? family-wide vs per-child? does the child see the same unit the parent set?) — answering it well is a v2 mini-brainstorm. v1 ships the mechanic without the chrome.
- **Parent-edit warning lives in the parent main app, not the child app.** Decision: cross-app addition is in v1 scope. Rationale: the trust contract is incomplete without it. A child seeing their estimated days jump from 6 to 14 because the parent retroactively changed cost is exactly the "moving goalposts" failure mode Kidd 2013 names. The cost is one warning sheet in an existing dialog (~30 LOC), not a new screen.
- **Drill-into wish detail goes to a full-screen view, not an inline expand.** Decision: route navigation. Rationale: matches the "zoom levels" mental model the brainstorm landed on; aligns with existing `ChildWishCreatePage` pattern; avoids cramming a per-wish redemption flow into a grid cell on mobile.

---

## Dependencies / Assumptions

- The existing `GET /child/wishes/stats` endpoint returns `priority_simulation[]` with the documented shape (`wish_id`, `name`, `priority`, `star_coin_cost`, `progress`, `covered`). **Verified** against `server/apps/backend/app/schemas/child_wish.py` and `frontend/apps/child/src/api/childWishes.ts`.
- The existing client-side derivation in `ChildWishesPage.vue` lines 183–217 (`wishDaysMap` computed) computes days-estimate from `getCoinLedger()` with a 3-distinct-day stability gate. **Verified** against the source file. R9's gray-state condition reuses this exact gate.
- Vue 3 `<script setup lang="ts">` and Vant 4 long-press support are already in the codebase (`unplugin-vue-components` auto-imports). Long-press handlers are available without new dependencies. **Assumed; planner should confirm.**
- `expected_price` is excluded from the child-facing wishes payload. **Verified** — `ChildWishResponse` and `ChildWishStatsSimItem` in `server/apps/backend/app/schemas/child_wish.py` contain no `expected_price` field. The opaque cost rule (seed Idea #3) is enforced server-side.
- Pre-existing wish_id type mismatch (server returns int, frontend types as string in `childWishes.ts`) is out of scope for this bundle. Flag for separate cleanup.
- The parent main app has an existing wish-edit dialog where R14's warning can be inserted. **Unverified** — planner should confirm and, if absent, R14 may need to escalate to a small dedicated edit flow.

---

## Outstanding Questions

### Resolve Before Planning

(none — all product decisions resolved during the brainstorm)

### Deferred to Planning

- [Affects R14][Technical] Where does the parent-side wish-edit dialog live (`frontend/apps/main/src/...`)? Does it currently re-fetch the child's balance + ledger before computing the warning, or do we need a thin server endpoint to compute the delta server-side and avoid a parent-side fetch of child data? Planner should locate the dialog and choose the cheaper path.
- [Affects R8, R12][Technical] Should `reachabilityTint` and `previewSpend` live in `frontend/apps/child/src/utils/` or in a new shared package consumed by both child and main apps? R14 needs the same math on the parent side.
- [Affects R4, R6][Needs research] Does Vant 4's `vTouch`/`v-touch` directive support a clean "release before timeout" hook, or do we need a custom long-press composable? If custom, can we reuse anything from `frontend/apps/child/src/composables/`?
- [Affects R15][Technical] The existing `useReducedMotion()` composable's hot-reload behavior on iOS Safari with PWA installation has known quirks (per `docs/solutions/`). Planner should verify the static-overlay fallback in F2 actually triggers cleanly when the OS setting flips during a session.
- [Affects all R][Technical] Performance budget: the constellation grid renders N×wish cards each with their own SVG ring + animation. Low-end Android target: confirm acceptable frame-rate on a 4-wish + 6-wish layout under reduced-motion=off.
