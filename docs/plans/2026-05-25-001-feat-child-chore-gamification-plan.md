---
status: active
type: feat
origin: ~/.gstack/projects/vincentruan-numina/ceo-plans/2026-05-25-child-chore-gamification.md
created: 2026-05-25
---

# feat: Child Frontend Chore Gamification — Streak Flames, Wish Bump, Haptic Pulse

Add gamification feedback at the chore completion action point: animated streak flames, wish progress bump toast, and haptic pulse patterns. Frontend-only, no backend changes.

## Summary

Transform chore completion from "submit for approval" to a micro-event with visual, tactile, and motivational feedback. Three lightweight enhancements at the action point:

1. **Streak flame animation** — Fire emoji pulses and grows with streak tier (7/14/30), creating "keep fire alive" habit hook
2. **Wish progress bump** — Toast shows "+X ⭐ closer to [wish]" after completion, connecting chore to goal
3. **Haptic pulse** — Double-pulse vibration pattern on completion button tap, tactile reward feeling

**Parity:** Apply to both ChildHomePage and ChildTasksPage for consistent UX.

---

## Problem Frame

Kids complete chores as transactional submissions ("tap → wait approval → get coins"). The action point lacks feedback — the button just disables and shows a badge. No sense of progress, no habit hook, no connection to wishes.

**Goal:** Make the tap feel like an action in a game, not a form submission.

---

## Scope Boundaries

### In Scope
- Streak flame CSS animation on chore cards
- Wish progress bump toast on chore completion
- Haptic pulse pattern on completion button
- Both ChildHomePage and ChildTasksPage parity
- Vitest tests for new behaviors

### NOT in Scope
- Button morph animation (celebration already covers coin flight)
- Challenge progress auto-update (premature before approval)
- Badge unlock at milestones (blocked on icon assets)
- Completion chime sound (blocked on audio assets)
- Achievement overlay style (toast pattern is consistent)

### Deferred to Follow-Up Work
- Mini-badge unlock when badge icon assets are available
- Completion chime when audio assets are sourced

---

## Key Technical Decisions

1. **Streak animation respects reduced motion** — When `useReducedMotion()` returns true, skip pulse animation, show static flame emoji at tier-appropriate size. Follows existing pattern in `useFlightChoreography`.

2. **Haptic pattern reuse** — Use existing `MOTION.haptic.confirm` pattern (`[50]`) for single pulse, or add new `rewardPulse` pattern `[50, 30, 50]` to motionTokens.ts for double-pulse heartbeat feeling.

3. **Toast over overlay** — Wish progress bump uses `showToast()` with duration 2000ms, position 'top'. Consistent with app patterns, no new UI components.

4. **topWish null guard** — Wish bump toast checks `if (!topWish.value)` before showing — avoids crash when no active wish exists.

---

## Implementation Units

### U1. Add haptic pulse pattern to motionTokens

**Goal:** Define a new `rewardPulse` haptic pattern for chore completion — double-pulse feeling like heartbeat.

**Files:**
- `frontend/apps/child/src/utils/motionTokens.ts` — add pattern
- `frontend/apps/child/src/utils/motionTokens.test.ts` — verify value

**Approach:**
Add `rewardPulse: [50, 30, 50]` to the `haptic` object. This is a 3-element pattern: 50ms on, 30ms off, 50ms on — double tap feeling. Distinct from `haptic.landing` (5-step celebration) and `haptic.confirm` (single tap).

**Patterns to follow:**
Existing haptic patterns in motionTokens.ts are arrays of millisecond durations. Tests verify exact array values.

**Test scenarios:**
- `rewardPulse` value is `[50, 30, 50]` — matches expected double-pulse pattern

**Verification:**
motionTokens.test.ts passes with new assertion.

---

### U2. Streak flame animation on chore cards

**Goal:** Add pulsing flame animation to chore card streak badges, scaling by tier (7/14/30).

**Dependencies:** U1 (haptic pattern, but independent — can run parallel)

**Files:**
- `frontend/apps/child/src/pages/ChildHomePage.vue` — chore card template + CSS
- `frontend/apps/child/src/pages/ChildTasksPage.vue` — chore card template + CSS
- `frontend/apps/child/src/composables/useReducedMotion.ts` — check for animation skip

**Approach:**
1. **Step 0 (ChildHomePage only):** Add streak badge markup to chore card template. Copy pattern from ChildTasksPage.vue: `<span v-if="chore.streak_count > 1" class="streak-badge">🔥{{ chore.streak_count }}</span>`
2. Add `streakTier(count)` helper using existing thresholds (7/14/30). **Tier ranges:** Tier 7 = streaks 7-13 days, tier 14 = 14-29 days, tier 30 = 30+ days.
3. Add dynamic class binding `:class="'flame-tier-' + streakTier(chore.streak_count)"` to streak badge
4. Add CSS keyframes `flame-pulse` with scale animation
5. Add tier-specific CSS classes with font-size and animation-duration
6. Add `.reduced-motion` variant that skips animation (checks `useReducedMotion().value`)

**Technical design (directional):**
```vue
<!-- Template pattern -->
<span
  v-if="chore.streak_count > 1"
  class="streak-badge"
  :class="[
    'flame-tier-' + streakTier(chore.streak_count),
    { 'reduced-motion': reducedMotion }
  ]"
>🔥{{ chore.streak_count }}</span>

<!-- CSS pattern -->
.flame-tier-7 { font-size: 1.05em; animation: flame-pulse 400ms /* durations.medium */ ease-in-out infinite; }
.flame-tier-14 { font-size: 1.10em; animation: flame-pulse 500ms ease-in-out infinite; }
.flame-tier-30 { font-size: 1.15em; animation: flame-pulse 600ms ease-in-out infinite; }
.flame-tier-7.reduced-motion { animation: none; }
```

**Patterns to follow:**
- Use `MOTION.durations.medium` (400ms) for base timing
- Use `MOTION.scales.pulse` (1.03) for scale factor
- Follow existing `useReducedMotion()` pattern from ChildWishesPage.vue (line 226)

**Test scenarios:**
- Streak badge renders static (no animation) when `streak_count` is 2-6 — badge shows 🔥N
- Streak badge absent when `streak_count <= 1`
- Streak badge renders with tier class when `streak_count >= 7`
- Streak badge has `reduced-motion` class when `useReducedMotion()` returns true
- Animation class absent when `streak_count < 7`
- Tier calculation: 7 → '7', 8 → '7' (tier 7 range), 14 → '14', 15 → '14' (tier 14 range), 30 → '30'

**Verification:**
Chore cards in both pages show animated flame when streak >= 7, static flame when reduced motion.

---

### U3. Wish progress bump toast on completion

**Goal:** Show toast "+X ⭐ closer to [wish]" after chore completion, connecting action to goal.

**Dependencies:** U4 (i18n keys must exist)

**Files:**
- `frontend/apps/child/src/pages/ChildHomePage.vue` — complete() handler
- `frontend/apps/child/src/pages/ChildTasksPage.vue` — doComplete() / complete() handlers
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — message string
- `frontend/apps/child/src/i18n/locales/en-US.ts` — message string

**Approach:**
1. In `complete()` handler, after API call succeeds and before state update
2. Check `if (topWish.value)` — null guard
3. Call `showToast(t('chore.wishProgressBump', { stars: chore.coin_reward, wishName: topWish.value.name }))`
4. Duration 2000ms, position 'top'

**Null guards:**
- `topWish.value` — if null, skip toast (no active wish)
- `chore.coin_reward` — default to 0 if undefined

**Patterns to follow:**
- Follow existing `showToast()` pattern with i18n interpolation (e.g., `toast.childGrantedStars`)
- Emoji prefix per CLAUDE.md convention

**Test scenarios:**
- Toast shown when `topWish.value` exists and completion succeeds
- Toast NOT shown when `topWish.value` is null
- Toast message interpolates `{stars}` and `{wishName}` correctly
- Toast duration is 2000ms

**Verification:**
Completing a chore with active wish shows progress bump toast.

---

### U4. Add i18n keys for new messages

**Goal:** Define i18n strings for wish progress bump and days-to-bonus messages.

**Files:**
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — add to `chore` section
- `frontend/apps/child/src/i18n/locales/en-US.ts` — add to `chore` section

**Approach:**
Add keys to existing `chore` object (around line 85-109 in zh-CN.ts):

```ts
// zh-CN.ts
chore: {
  // existing keys...
  wishProgressBump: '✨ +{stars} ⭐ 离「{wishName}」又近一步!',
  daysToBonus: '🔥 还差 {days} 天获得连击奖励!',
}

// en-US.ts
chore: {
  // existing keys...
  wishProgressBump: '✨ +{stars} ⭐ closer to {wishName}!',
  daysToBonus: '🔥 {days} more days to streak bonus!',
}
```

**Patterns to follow:**
- Emoji prefix per CLAUDE.md convention
- Interpolation syntax `{variable}` matches existing patterns

**Test scenarios:**
- Keys exist in both locale files
- Keys interpolate correctly when called via `t()`

**Verification:**
`npm run typecheck` passes, no i18n key errors.

---

### U5. Add haptic vibration to completion handlers

**Goal:** Fire haptic pulse on chore completion button tap — tactile reward feeling.

**Dependencies:** U1 (rewardPulse pattern must exist)

**Files:**
- `frontend/apps/child/src/pages/ChildHomePage.vue` — complete() handler
- `frontend/apps/child/src/pages/ChildTasksPage.vue` — doComplete() handler

**Approach:**
1. Import `tryVibrate` from `@/composables/useHaptic`
2. In completion handler, call `tryVibrate(MOTION.haptic.rewardPulse)` **after API call succeeds** — haptic fires only on successful completion, not on tap intent
3. No-op gracefully on iOS Safari (no vibration API)

**Patterns to follow:**
- Follow existing `tryVibrate()` pattern from `useFlightChoreography.ts` (line 39) and `TreasureRevealPopup.vue` (line 11)
- Use `MOTION.haptic.rewardPulse` from motionTokens

**Test scenarios:**
- `tryVibrate()` called with `[50, 30, 50]` pattern in complete handler
- No error when `navigator.vibrate` absent (iOS Safari mock)

**Verification:**
Android devices feel double-pulse on completion, iOS Safari shows no error.

---

### U6. Days-to-bonus display on chore cards

**Goal:** Show "X more days to streak bonus!" on chore cards when streak is active but below next tier threshold.

**Dependencies:** U4 (daysToBonus i18n key must exist)

**Files:**
- `frontend/apps/child/src/pages/ChildHomePage.vue` — chore card template
- `frontend/apps/child/src/pages/ChildTasksPage.vue` — chore card template

**Approach:**
1. Calculate `daysToBonus = nextTierThreshold - currentStreak` where thresholds are [7, 14, 30]
2. Display only when `streak_count > 1` AND `streak_count < 30` (already at max tier)
3. Use `daysToBonus` i18n key: `t('chore.daysToBonus', { days: daysToBonus })`
4. Position below streak badge, small font (11px), muted color

**Display logic:**
- Streak 2-6: "🔥 还差 {7-streak} 天获得连击奖励!" (showing days to 1.5x bonus)
- Streak 7-13: "🔥 还差 {14-streak} 天获得连击奖励!" (showing days to 2x bonus)
- Streak 14-29: "🔥 还差 {30-streak} 天获得连击奖励!" (showing days to 3x bonus)
- Streak 30+: No message (already at max tier)

**Test scenarios:**
- Days-to-bonus shows when streak_count is 2-6, 7-13, 14-29
- Days-to-bonus hidden when streak_count <= 1 or >= 30
- Days value calculates correctly: streak 5 → "还差 2 天"

**Verification:**
Chore cards show contextual bonus countdown when streak is below next tier.

---

## System-Wide Impact

| Component | Impact |
|-----------|--------|
| ChildHomePage chore cards | New streak animation, streak badge markup, days-to-bonus display, haptic on complete |
| ChildTasksPage chore cards | Same streak animation, days-to-bonus display, haptic on complete |
| useHaptic.ts | No change (pattern in motionTokens) |
| motionTokens.ts | New `rewardPulse` pattern |
| i18n locales | 2 new keys per locale (wishProgressBump, daysToBonus) |
| Vitest tests | 6-7 new test cases |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| CSS animation jank on older devices | Use `will-change: transform` on flame element, test on device |
| Haptic fails silently on iOS | `tryVibrate` already handles missing API gracefully |
| topWish null crash | Explicit null guard before toast |
| Parity drift between pages | Same helper function, same CSS classes in both |

---

## Verification Strategy

1. **Unit tests** — motionTokens value, streak tier calculation, toast interpolation
2. **Component tests** — chore card renders tier class, reduced-motion class
3. **Manual test** — complete chore on Android device, feel haptic pulse, see toast
4. **Typecheck** — `npm run typecheck` passes
5. **Lint** — `npm run lint` passes

---

## Origin Document Reference

This plan derives from CEO review decisions at:
`~/.gstack/projects/vincentruan-numina/ceo-plans/2026-05-25-child-chore-gamification.md`

Accepted scope: D4 (streak flames), D5 (wish bump), D7 (haptic patterns).
Skipped: D3 (button morph), D6 (challenge update), D8 (badges), D9 (chime), D10 (toast style).