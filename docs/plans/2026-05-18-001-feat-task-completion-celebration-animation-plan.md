---
title: feat: Task Completion Celebration Animation
plan_type: feat
status: active
created: 2026-05-18
origin: docs/brainstorms/task-completion-celebration-animation-requirements.md
---

# feat: Task Completion Celebration Animation

## Summary

Add a celebration animation that triggers when a child opens the app and discovers newly-approved tasks. Flying SVG stars animate toward the balance display with a random encouraging phrase, creating a tangible reward moment that connects "I did chores" → "I earned stars" → "I feel good."

## Problem

When a child marks a chore complete, the only feedback is a status badge swap (`available` → `pending_approval`). When the parent later approves, the child sees nothing — the task silently appears as "approved" if they check. This makes the reward disconnected and anticlimactic. The MilestoneCelebration component proves overlay-based celebration works; we extend this pattern to per-approval moments.

## Scope

### In Scope

- CelebrationAnimation.vue component with flying stars animation
- Custom SVG star asset with glow effect
- localStorage tracking of celebrated task IDs to prevent repeat celebrations
- Trigger integration on ChildHomePage and ChildTasksPage mount
- Random encouraging phrase from i18n pool
- Merged summary for batch approvals
- CSS @keyframe animations following existing patterns
- i18n additions for phrases and summary text

### Out of Scope

- Swipe-to-complete gesture
- Sound/haptic feedback
- Mystery bonus rewards
- Celebration on immediate task submission (before approval)
- Push notifications

### Deferred to Follow-Up Work

- Sound effects layer (phase 2 of completion experience package)
- Swipe-to-complete gesture (phase 3)
- Mystery bonus rewards (phase 4)

---

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **CSS @keyframes over Vue Transition** | Existing animations (DrawAnimation, MilestoneCelebration) use pure CSS keyframes. Maintains consistency and avoids introducing new patterns. |
| **Task ID set in localStorage** | More precise than timestamp approach — ensures each approval is celebrated exactly once, even across multiple sessions. Prune to 50 IDs to bound growth. |
| **Inline overlay (no Teleport)** | MilestoneCelebration uses fixed-position overlay without Teleport. Simpler implementation, same visual result. |
| **Hardcoded colors in JS** | MilestoneCelebration hardcodes brand colors in JS confetti array. Follow same pattern for star colors — brand-ochre (#e8b94a) as primary. |
| **Trigger on mount, not navigation** | ChildHomePage and ChildTasksPage both need trigger logic. Mount-based trigger catches approvals regardless of entry page. |

---

## Implementation Units

### U1. Create CelebrationAnimation.vue Component

**Goal:** Build the overlay-based celebration animation component with flying stars and encouraging phrase.

**Dependencies:** None (foundation unit)

**Files:**
- `frontend/apps/child/src/components/CelebrationAnimation.vue` (create)
- `frontend/apps/child/src/assets/icons/star-glow.svg` (create)

**Approach:**

Create a modal-style component following MilestoneCelebration.vue patterns:
- Fixed full-screen overlay with semi-transparent background
- Stars animate from bottom-left toward top center via CSS `@keyframes`
- Phrase fades in/out during animation
- Summary card appears if multiple tasks
- Props: `visible`, `taskCount`, `starsEarned`
- Emits: `dismiss` when animation completes

The SVG star uses brand-ochre fill with a soft glow filter (SVG `<filter>` with `<feGaussianBlur>`). The animation choreography follows the requirements doc sequence: overlay fade (0-0.2s) → phrase appear (0.2-0.4s) → stars launch (0.3-1.5s) → balance pulse (1.5-2s) → summary card (1.8-2.5s) → fade out (2.5-3s).

**Patterns to follow:**
- MilestoneCelebration.vue for overlay structure and z-index
- DrawAnimation.vue for `@keyframes` animation pattern (shake, pop)
- ChildWishesPage.vue for shimmer/pulse effect pattern

**Test scenarios:**
- Single task: animation shows phrase + flying stars + "获得 X ⭐！"
- Multiple tasks: shows merged summary "X个任务通过！获得 Y ⭐"
- Animation auto-dismisses after 2-3 seconds
- Stars visible in both light and dark modes
- Overlay prevents interaction with underlying UI during animation

**Verification:** Component renders in isolation with props, animation completes in ≤3s, no console errors.

---

### U2. Add Celebration State Tracking in localStorage

**Goal:** Create a utility module to track celebrated task IDs and detect pending celebrations.

**Dependencies:** U1 (animation component needs the check)

**Files:**
- `frontend/apps/child/src/utils/celebrationState.ts` (create)

**Approach:**

Create a focused utility module with:
- `CELEBRATION_STORAGE_KEY = 'numina-child-celebrated-tasks'`
- `getCelebratedIds(): Set<string>` — read from localStorage, parse JSON
- `markCelebrated(ids: string[])` — add IDs to set, write to localStorage
- `findPendingCelebrations(tasks: ChoreInstance[]): ChoreInstance[]` — filter tasks with `status === 'approved'` that are not in celebrated set
- `pruneCelebratedIds()` — trim set to max 50 IDs ( FIFO: keep most recent)

Follow existing localStorage pattern from `blindBox.ts` and `darkMode.ts` — simple `getItem`/`setItem`, JSON parse/stringify.

**Patterns to follow:**
- `frontend/apps/child/src/stores/blindBox.ts` localStorage access pattern
- `frontend/apps/child/src/utils/darkMode.ts` key naming convention (`numina-child-*`)

**Test scenarios:**
- Empty localStorage returns empty set
- `markCelebrated(['a', 'b'])` persists to localStorage
- `findPendingCelebrations` returns only approved tasks not in set
- Pruning keeps 50 most recent IDs when set exceeds limit
- Invalid JSON in localStorage falls back to empty set (graceful degradation)

**Verification:** Unit tests pass, utility functions work independently of Vue components.

---

### U3. Integrate Celebration Trigger on ChildHomePage

**Goal:** Trigger celebration on ChildHomePage mount when pending celebrations exist.

**Dependencies:** U1, U2

**Files:**
- `frontend/apps/child/src/pages/ChildHomePage.vue` (modify)
- `frontend/apps/child/src/api/chores.ts` (read for ChoreInstance type)

**Approach:**

On `onMounted`, after loading chores:
1. Call `findPendingCelebrations(todayChores)` to get approved-but-not-celebrated tasks
2. If count > 0, set `celebrationVisible = true`, compute `celebrationTaskCount` and `celebrationStarsEarned`
3. Render `<CelebrationAnimation>` component with these props
4. On `@dismiss`, call `markCelebrated(ids)` for the celebrated tasks

Add celebration state refs:
```ts
const celebrationVisible = ref(false)
const celebrationTaskCount = ref(0)
const celebrationStarsEarned = ref(0)
const celebrationTaskIds = ref<string[]>([])
```

**Patterns to follow:**
- Existing `onMounted` async loading pattern in ChildHomePage
- MilestoneCelebration integration pattern for overlay handling

**Test scenarios:**
- Opening page with no approved tasks: no celebration
- Opening page with 1 newly-approved task: celebration triggers with correct count/stars
- Opening page with 3 newly-approved tasks: merged celebration shows "3个任务通过！获得 X ⭐"
- After celebration, IDs are marked celebrated; reopening does not re-trigger
- Network error on chore load: celebration skipped gracefully

**Verification:** Manual test: approve task via parent app, open child app, celebration appears once.

---

### U4. Integrate Celebration Trigger on ChildTasksPage

**Goal:** Trigger celebration on ChildTasksPage mount as alternative entry point.

**Dependencies:** U1, U2, U3

**Files:**
- `frontend/apps/child/src/pages/ChildTasksPage.vue` (modify)

**Approach:**

Same integration pattern as U3:
1. On `onMounted`, after `load()` completes, check `findPendingCelebrations(chores)`
2. If pending, trigger celebration
3. On dismiss, mark IDs as celebrated

Note: ChildTasksPage shows chores for a specific date. Use all approved chores from the loaded list, not just today's.

**Patterns to follow:**
- Same integration approach as U3
- Existing `checkNewMilestones()` pattern for post-load celebration checks

**Test scenarios:**
- Navigating to tasks page with pending approvals: celebration triggers
- After celebration, navigating away then back: no repeat celebration
- Date navigation does not re-trigger celebration for same approvals

**Verification:** Manual navigation test from home to tasks page with pending approvals.

---

### U5. Add i18n Keys for Celebration

**Goal:** Add all celebration strings to i18n locale files.

**Dependencies:** U1 (component needs i18n keys)

**Files:**
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (modify)
- `frontend/apps/child/src/i18n/locales/en-US.ts` (modify)

**Approach:**

Add `celebration` section with:
- `phrases`: array of encouraging phrases (7 strings)
- `singleTask`: format string for single task "获得 {stars} ⭐！"
- `multipleTasks`: format string for batch " {count}个任务通过！获得 {stars} ⭐"
- `overlayLabel`: accessibility label for screen readers

Add English translations with culturally-appropriate equivalents (e.g., "Awesome!", "Great job!").

**Patterns to follow:**
- Existing `milestone` section structure for similar celebration content
- Emoji prefix convention from CLAUDE.md

**Test scenarios:**
- All keys defined in both zh-CN and en-US
- `t('celebration.phrases')` returns array usable for random selection
- Format strings interpolate correctly with `{count}` and `{stars}`

**Verification:** Run `npm run typecheck` in frontend/apps/child — no i18n key errors.

---

## System-Wide Impact

| Area | Impact |
|------|--------|
| **Child UX** | Creates emotional reward moment previously absent |
| **Parent UX** | Approval now creates visible joy for child (indirect benefit) |
| **Performance** | One additional localStorage read/write per app open; negligible |
| **Accessibility** | Overlay needs `aria-modal` and `aria-label`; screen reader support |

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **localStorage corruption** | Low | Graceful fallback: if JSON parse fails, treat as empty set |
| **Animation jank on older devices** | Medium | Keep star count capped at 6-8; use CSS transforms (GPU-accelerated) |
| **Child misses celebration by closing app** | Medium | Mark IDs celebrated before animation starts; summary appears briefly even if interrupted |
| **Dark mode contrast** | Low | brand-ochre visible on dark; test both modes |

---

## Test Scenarios Summary

| Scenario | Page | Expected Behavior |
|----------|------|-------------------|
| No pending approvals | Home/Tasks | No celebration |
| 1 newly-approved | Home | Phrase + stars + "获得 X ⭐！" |
| 3 newly-approved | Home | Merged: "3个任务通过！获得 X ⭐" |
| Already celebrated | Home | No repeat |
| Dark mode | Any | Stars visible, overlay dark-tinted |
| Network error | Home | Celebration skipped, no blocking error |

---

## Verification Checklist

- [ ] CelebrationAnimation renders with correct props
- [ ] Animation completes in ≤3 seconds
- [ ] localStorage correctly tracks celebrated IDs
- [ ] No repeat celebration for same approvals
- [ ] Works in light and dark modes
- [ ] i18n keys present in zh-CN and en-US
- [ ] `npm run typecheck` passes in frontend/apps/child
- [ ] Manual test: approve task, open child app → celebration appears