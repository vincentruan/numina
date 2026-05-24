---
date: 2026-05-24
id: "2026-05-24-001"
title: "Child Task-Approval Celebration v2 — Game-Feel Choreography"
status: active
origin: docs/brainstorms/2026-05-24-child-celebration-gamefeel-v2-requirements.md
selected-bundle: Gamma
plan-depth: standard
---

# Child Task-Approval Celebration v2 — Implementation Plan

## Overview

Refactor the existing v1 celebration (stars launch upward off-screen) into a Gamma-bundle game-feel choreography: pending-state candle → approval popup → confirm tap → parabolic Bezier star flight from approved task card to balance card → balance scale-pop + glow + tier-cascade count-up → 3-pulse haptic per landing → 60s session-local trail residue → 3s breathing afterglow. Streak-tier escalation (≥7/14/30) layers concurrent particles. Reduced-motion mode short-circuits to a toast + color-invert cue. iOS Safari haptic absence handled silently.

**Zero backend changes.** Reuses existing `ChoreInstance.streak_count`, `streak_bonus`, the `useCelebration` orchestration shell, and the `useBalancePolling` singleton. The substrate (`<FlyToTarget>` + `motionTokens.ts`) is built reuse-ready, but only the celebration call-site is wired in this plan — the other 6 future call-sites in the spec are out of scope.

---

## Requirements Trace

Origin requirements doc grouped components into a core spine, persistence layer, and engineering substrate. This table maps each spec component to its implementation unit. (See origin: `docs/brainstorms/2026-05-24-child-celebration-gamefeel-v2-requirements.md`.)

| Origin component | Description | Unit |
|---|---|---|
| E3 | `motionTokens.ts` shared vocabulary | U1 |
| — | `bezier.ts` quadratic interpolation utility | U1 |
| D5 | `useHaptic()` with iOS Safari fallback | U2 |
| D4 | `useReducedMotion()` matchMedia listener | U2 |
| E1 | `<FlyToTarget>` reusable particle primitive | U3 |
| A1 | `<CandleFlame>` pending-state flame + bloom/gutter transitions | U4 |
| P3 | `<TreasureRevealPopup>` approval-arrival popup | U5 |
| P2 | "锁住宝箱" lock-spin confirm button | U5 (popup) + U10 (sheet) |
| C1 | Balance card scale-pop + glow on first arrival | U6 |
| C2 | Three-tier cascade count-up | U6 |
| A5 | 3-second breathing afterglow | U6 |
| S1, S2 | Bezier star flight + multi-task gathering cloud | U7 |
| M1 | 3-pulse haptic per landing | U7 (consumes useHaptic) |
| S4 | `<TrailResidue>` 60s SVG trail layer | U8 |
| A3 | `<StreakLayer>` streak-tier escalation overlay | U9 |
| — | `useFlightChoreography()` timing-diagram orchestrator | U7 |
| — | `useBalancePolling` `lastChange` reactive ref (C1 trigger) | U6 |
| — | Wire-up in `CelebrationAnimation.vue` + `ChildTasksPage.vue` | U10 |
| — | i18n: 7 new keys × 2 locales | U11 |
| — | All AT-1..AT-10 scenarios pass manual QA | Verification |

Acceptance Examples (origin AT-1..AT-10) cited per-unit under `Test scenarios` and consolidated in the final Verification section.

---

## Output Structure

```
frontend/apps/child/src/
├── components/
│   ├── CelebrationAnimation.vue          [MODIFIED — orchestration shell]
│   ├── coins/CoinDisplay.vue             [MODIFIED — animateAmountChange]
│   └── celebration/                       [NEW directory]
│       ├── FlyToTarget.vue               [NEW — E1 primitive]
│       ├── CandleFlame.vue               [NEW — A1]
│       ├── TreasureRevealPopup.vue       [NEW — P3]
│       ├── TrailResidue.vue              [NEW — S4]
│       └── StreakLayer.vue               [NEW — A3]
├── composables/
│   ├── useCelebration.ts                 [MODIFIED — streak tier resolver]
│   ├── useBalancePolling.ts              [MODIFIED — lastChange ref]
│   ├── useHaptic.ts                      [NEW — D5]
│   ├── useReducedMotion.ts               [NEW — D4]
│   └── useFlightChoreography.ts          [NEW — timing orchestrator]
├── utils/
│   ├── motionTokens.ts                   [NEW — E3]
│   └── bezier.ts                         [NEW — Bezier math]
├── pages/
│   └── ChildTasksPage.vue                [MODIFIED — refs, candle, lock-spin, popup wiring]
└── i18n/locales/
    ├── zh-CN.ts                          [MODIFIED — 7 keys]
    └── en-US.ts                          [MODIFIED — 7 keys]
```

The `celebration/` subdirectory is intentional — it groups game-feel components separately from generic `components/`, keeping `MilestoneCelebration.vue` (out of scope) untouched.

---

## High-Level Technical Design

*This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### Layer architecture

```
ChildTasksPage.vue
  ├── chore-card refs (Map<id, HTMLElement>)
  ├── balance-card ref (HTMLElement)
  ├── <CandleFlame> per pending_approval card
  ├── <CelebrationAnimation>           ← orchestration shell (refactored)
  │     ├── <TreasureRevealPopup>      ← P3 approval popup
  │     ├── <FlyToTarget>              ← S1/S2 star flight
  │     ├── <TrailResidue>             ← S4 session-local trails
  │     ├── <StreakLayer>              ← A3 tier escalation
  │     └── orchestrated via useFlightChoreography()
  └── <CoinDisplay> in .balance-card    ← C2 tier-cascade count-up

useCelebration (existing shell)
  ├── existing: visible / taskCount / starsEarned / taskIds
  ├── new: streakTier (computed from max streak_count across batch)
  └── new: emits to useFlightChoreography for timing

useBalancePolling (existing singleton)
  ├── existing: balance / isLoading / error / start / stop / refresh
  └── new: lastChange ref { from, to, at } — fires when balance value changes

useFlightChoreography (new)
  └── consumes useHaptic + useReducedMotion + bezier
      and emits per-phase events the CelebrationAnimation orchestrates
```

### Timing diagram (single-task Path B, parent-gated)

| T (ms) | Layer | Event |
|---|---|---|
| 0 | task card | child taps "完成" |
| 0–200 | sheet | "锁住宝箱" tap → lock-spin 360° + spring scale + API |
| 200 | candle | pending → render `<CandleFlame>` flicker (3s loop) |
| X | candle | poll detects `approved` → bloom 200ms → ember 300ms → unmount |
| X+500 | popup | `<TreasureRevealPopup>` mount + 400ms haptic + radial glow |
| F=0 | popup | user tap "太棒了！" → fade-out 300ms |
| F=0..960 | stars | `<FlyToTarget>` quadratic-Bezier flight, 120ms stagger, 3-pulse haptic per landing |
| F=800 | balance | first landing → C1 scale-pop + glow; C2 cascade copper→silver→gold over 1.5s |
| F=2400 | balance | glow fade-out 400ms |
| F=2800 | balance | A5 breathing afterglow 3s |
| F=5800 | balance | static |
| F=60000 | trails | residue removed |

### Reduced-motion path

Single short-circuit at the top of `useFlightChoreography.run()`: when `useReducedMotion()` is true, skip all of the above and instead render a toast (`celebration.reducedMotionToast`) for 2.5s, fire one 400ms color-invert on the balance card, and snap the counter to its new value. No haptic, no popup, no stars.

### Multi-task batch (Path D)

Inserts a "gathering cloud" phase before the unified flight: each visible task card emits 2-3 stars upward to viewport (50%, 40%) over 600ms, stars orbit briefly (~100ms hover), then a single unified Bezier stream from cloud to balance card over 700ms. Cap at 12 stars total; per-task contribution scales as `floor(12/taskCount)`.

---

## Key Technical Decisions

### KTD-1: Polling surface — reactive `lastChange` ref vs. event emitter

The spec said: *"emit `balance-changed` event."* This plan adopts a reactive `Ref<{ from, to, at } | null>` instead.

**Decision:** Add `lastChange: Ref<{ from: number; to: number; at: number } | null>` to the `useBalancePolling` return shape, mutated whenever the polled balance value changes from its previous reading. Initial value `null`.

**Rationale:** Vue 3 idiomatic; consumers `watch(lastChange, ...)` rather than register/unregister listeners; survives the singleton pattern without a separate event bus; testable without DOM.

**Impact:** U6 + U10 watch this ref to trigger C1 + C2.

### KTD-2: Motion vocabulary location — TS constants only

The spec deferred whether tokens land in `motion.css`, `clay.css`, or only TS.

**Decision:** TS-only via `motionTokens.ts`. Components consume durations/easings/scales as inline `style` bindings or template literals. Haptic patterns are TS-only by definition.

**Rationale:** All consumers are TS/Vue components, none CSS-only. Avoids dual-source-of-truth between `clay.css` and TS. CSS variable indirection adds no value when there's exactly one consumer.

### KTD-3: Lock-spin button — inline CSS in `ChildTasksPage.vue`

The call-out asked: extract `<SealButton>` reusable vs. inline. User confirmed inline.

**Decision:** Add a `seal-spin` keyframe and class to `ChildTasksPage.vue`'s scoped CSS. Trigger via a `data-spinning` attribute toggled in `doComplete()`.

**Rationale:** Single call-site; no other "seal" UX in the app today. YAGNI.

### KTD-4: Test depth — pure logic + 1 component smoke

The call-out asked: full component test per `.vue` vs. lighter. User confirmed lighter.

**Decision:**
- Unit tests for `bezier.ts`, `motionTokens.ts` (shape only), `useHaptic.ts`, `useReducedMotion.ts` (exhaustive).
- One mount/unmount smoke test for `<TreasureRevealPopup>` to confirm it renders and emits `confirm`.
- All visual choreography (flight curves, glow, breathing) verified via the 10 manual ATs.

**Rationale:** JSDOM/happy-dom does not run `requestAnimationFrame` realistically; component tests for animated visuals produce false confidence. The 10 ATs in the spec are the real verification.

### KTD-5: Trail residue lifetime — DOM-bound, not state-bound

**Decision:** Each trail `<path>` is a real SVG element appended to the `<TrailResidue>` overlay layer with a single CSS animation `trail-fade 60s linear forwards`. After 60s + 100ms buffer, JS removes the element.

**Rationale:** No reactive state for fade progress; CSS owns the timing; cheap. Page navigation unmounts the layer → trails clear, satisfying D3 "session-local."

### KTD-6: Position resolution timing — at confirm-tap, not popup-mount

**Decision:** `getBoundingClientRect()` calls fire inside the `confirm` handler, not during popup mount.

**Rationale:** Popup mount (with overlay + radial gradient) may shift layout via scroll-lock. Capturing position at confirm-tap aligns the flight origin with what the child sees underneath the dismissing popup.

### KTD-7: Reduced-motion toast surface — Vant `showToast`

**Decision:** Reduced-motion path uses `showToast({ message: t('celebration.reducedMotionToast', {...}), duration: 2500, position: 'top' })`. The color-invert is one CSS class toggle on `.balance-card`.

**Rationale:** Vant toasts are already used app-wide for non-modal notifications; consistent.

---

## Implementation Units

Units are ordered by dependency. U1–U2 are pure utilities (no UI). U3 depends on U1+U2. U4–U9 are leaf components/composables consuming the substrate. U10 wires everything into the page. U11 is i18n. Each feature-bearing unit lists its test scenarios; pure scaffolding has `Test expectation: none`.

### U1. Motion substrate — tokens + Bezier math

**Goal:** Establish the shared motion vocabulary and the pure-functional Bezier interpolation utility every later unit consumes.

**Requirements:** E3 (motion tokens), prerequisite for S1/S2/C1/A5/M1.

**Dependencies:** none.

**Files:**
- `frontend/apps/child/src/utils/motionTokens.ts` (new)
- `frontend/apps/child/src/utils/bezier.ts` (new)
- `frontend/apps/child/src/utils/bezier.test.ts` (new)
- `frontend/apps/child/src/utils/motionTokens.test.ts` (new)

**Approach:**
- `motionTokens.ts` exports a single `MOTION` const with the four sub-objects from the spec (durations, easings, scales, haptic). Use `as const` for literal-type narrowing.
- `bezier.ts` exports two pure functions: `quadraticBezier(p0, p1, p2, t)` returning `{x, y}`, and `bezierPath(start, end, controlOffset)` returning the SVG path string `M x0 y0 Q cx cy x1 y1`.
- Both files are TS-only, no Vue imports, no DOM imports — fully unit-testable.

**Patterns to follow:** Match style of existing `frontend/apps/child/src/utils/coinTier.ts` (pure functions, named exports, no default export).

**Test scenarios:**
- `bezier.quadraticBezier`: t=0 returns start point exactly; t=1 returns end point exactly; t=0.5 returns midpoint of straight-line interpolation when control is on the line; t=0.5 with elevated control point returns a y-value above the start/end midpoint.
- `bezier.bezierPath`: returns string starting with `M ` and containing ` Q ` token; control point is at `((startX+endX)/2, min(startY,endY) - controlOffset)`.
- `motionTokens.MOTION`: all four sub-keys present; haptic.landing is the 5-element pattern `[50,30,50,30,100]`; durations.medium === 400.

**Verification:** `npm run test:run` passes; `npm run typecheck` clean.

---

### U2. Capability composables — `useHaptic` and `useReducedMotion`

**Goal:** Wrap the two browser capabilities the choreography depends on, with feature-detect so iOS Safari and reduced-motion users degrade gracefully.

**Requirements:** D4 (reduced-motion), D5 (iOS haptic fallback), M1 prerequisite.

**Dependencies:** U1 (consumes `MOTION.haptic`).

**Files:**
- `frontend/apps/child/src/composables/useHaptic.ts` (new)
- `frontend/apps/child/src/composables/useReducedMotion.ts` (new)
- `frontend/apps/child/src/composables/useHaptic.test.ts` (new)
- `frontend/apps/child/src/composables/useReducedMotion.test.ts` (new)

**Approach:**
- `useHaptic()`: returns `{ vibrate(pattern: number | number[]): boolean }`. Internally guards on `typeof navigator === 'undefined'`, `typeof navigator.vibrate !== 'function'`, and a `try/catch` around the call. Returns boolean indicating fired (true) or no-op (false). Exports a `tryVibrate` helper for direct use without the hook.
- `useReducedMotion()`: returns `Readonly<Ref<boolean>>` reactive to `(prefers-reduced-motion: reduce)`. Registers `matchMedia.addEventListener('change', ...)` in setup; cleans up in `onScopeDispose`. Initial value reflects current `matchMedia.matches`.

**Patterns to follow:** Composable style of existing `frontend/apps/child/src/utils/darkMode.ts` (matchMedia listener with proper cleanup).

**Test scenarios:**
- `useHaptic`: with `navigator.vibrate` defined and returning `true`, `vibrate([50])` returns `true` and `navigator.vibrate` was called with `[50]`. With `navigator.vibrate = undefined`, `vibrate([50])` returns `false` and does not throw. With `navigator.vibrate` throwing, `vibrate([50])` returns `false` (caught, no rethrow).
- `useReducedMotion`: initial value matches `matchMedia.matches`; firing a `change` event with `matches=true` updates the ref to `true`; ref is readonly (TS check via `// @ts-expect-error` is forbidden by CLAUDE.md, so verify via runtime `Object.isFrozen` or by wrapping with `readonly()`).

**Verification:** Tests pass; typecheck clean; `useHaptic` imported in U7 without errors.

---

### U3. `<FlyToTarget>` particle primitive

**Goal:** Build the reusable Vue component that animates N particles from one origin to one target along a Bezier path, firing per-landing and final-landed callbacks. This is the substrate for S1/S2 and (out of scope) future call-sites.

**Requirements:** E1, S1 prerequisite.

**Dependencies:** U1 (Bezier + tokens).

**Files:**
- `frontend/apps/child/src/components/celebration/FlyToTarget.vue` (new)

**Approach:**
- `<script setup lang="ts">` with the Props interface from the spec (origin/target accept pixel coords, HTMLElement, or selector string).
- Resolves origin/target to `{x, y}` once on mount via `getBoundingClientRect()`.
- Uses `<Teleport to="body">` with `<div class="fly-overlay">` (`position: fixed; inset: 0; pointer-events: none; z-index: 999`).
- Renders one `<span class="particle">` per `particleCount`, positioned absolutely.
- Drives animation via `requestAnimationFrame`: per-frame, for each particle compute `t` from `(now - launchAt - i*staggerMs) / duration`, clamp to [0,1], call `quadraticBezier`, apply `transform: translate3d(x, y, 0) rotate(rotationDeg*t) scale(...)` and `opacity: 1` once t >= 0.
- When `t === 1` for a particle, fire `props.onLandingPerParticle?.()`.
- When all particles reach `t === 1`, fire `props.onAllLanded?.()` once and stop the rAF loop.
- Particle SVG variants chosen by `particleType` prop: `star` uses existing `@/assets/icons/star-glow.svg`; `coin/sparkle/flame` are inline SVG fallbacks.
- Cleanup: `onUnmounted` cancels rAF and removes any DOM nodes.

**Patterns to follow:** Match Teleport+overlay style of `CelebrationAnimation.vue:1-37`. Match scoped-style + dark-theme override conventions of same file.

**Technical design (directional):**

```
onMounted:
  resolvedOrigin = resolve(props.origin)
  resolvedTarget = resolve(props.target)
  controlPoint = midpoint(origin, target) lifted by props.controlPointOffset
  launchAt = performance.now()
  startRAF()

onFrame(now):
  for each particle i:
    elapsed = now - launchAt - i * staggerMs
    if elapsed < 0: continue (not launched yet)
    t = clamp(elapsed / duration, 0, 1)
    {x, y} = quadraticBezier(origin, control, target, t)
    scale = scaleCurve eased on t
    apply transform; mark landed when t === 1
  if all landed: emit('allLanded'); stopRAF
```

**Test scenarios:** none (covered by U10 manual AT-1 step 4 and AT-3 batch). `Test expectation: none — visual choreography asserted via manual ATs per KTD-4.`

**Verification:** Component compiles via `npm run build`; typecheck clean. Manual smoke: import in a one-off scratch route, fire it, observe particles arc.

---

### U4. `<CandleFlame>` pending-state component

**Goal:** Render the candle flicker over `pending_approval` chore cards, with `bloom` (on approved) and `gutter` (on rejected) transitions that the parent controls via prop.

**Requirements:** A1.

**Dependencies:** U1 (durations).

**Files:**
- `frontend/apps/child/src/components/celebration/CandleFlame.vue` (new)

**Approach:**
- Props: `state: 'flickering' | 'bloom' | 'gutter'`, `ariaLabel: string`.
- Renders absolutely-positioned `<span>🕯️</span>` (20×20px) at top-right corner of its parent card. Parent must set `position: relative` (caller responsibility).
- CSS animations driven by `[data-state="..."]` attribute:
  - `flickering` (default): opacity flicker loop (3s) + horizontal jitter (2.5s offset 0.5s).
  - `bloom`: scale 1→1.6 over 200ms, brightness/saturation filter, then opacity fade 300ms. Total 500ms; emits `bloom-end`.
  - `gutter`: opacity 1→0.3→0.05→0 over 600ms; emits `gutter-end`.
- Emits `bloom-end` and `gutter-end` events for parent to remove from DOM.

**Patterns to follow:** Scoped CSS keyframe style from `CelebrationAnimation.vue:186-326`. Dark mode passes through (emoji renders fine).

**Test scenarios:**
- Component test (smoke only): mount with `state="flickering"`, assert `<span>` rendered with `aria-label`. Switch to `state="bloom"`, advance fake timers 500ms, assert `bloom-end` was emitted.

**Verification:** Test passes; manual: visible candle on a pending card, smooth bloom on approval.

---

### U5. `<TreasureRevealPopup>` approval popup

**Goal:** The "treasure unlocked" overlay that appears when an approved task arrives. Shows task emoji + encouraging phrase + "太棒了！" confirm button + 400ms haptic on mount. Auto-dismisses after 6s if user does not tap.

**Requirements:** P3, P2 (visual lock styling for the in-popup confirm button, though the actual lock-spin runs on the sheet button per U10).

**Dependencies:** U1, U2.

**Files:**
- `frontend/apps/child/src/components/celebration/TreasureRevealPopup.vue` (new)
- `frontend/apps/child/src/components/celebration/TreasureRevealPopup.test.ts` (new)

**Approach:**
- Props: `visible: boolean`, `taskCount: number`, `starsEarned: number`, `taskEmoji?: string`.
- Emits: `confirm`, `auto-dismiss` (after 6s), `cancel` (system back-gesture; hooks into `<Teleport>` overlay click).
- `<Teleport to="body">` + `<Transition>` overlay; radial-gradient ochre→peach background (CSS `radial-gradient`).
- On mount: fire `useHaptic().vibrate(MOTION.haptic.arrival)` (single 400ms pulse). Start 6s auto-dismiss timer.
- Phrase from `t('celebration.phrases')` (random pick, matching existing logic at `CelebrationAnimation.vue:62-69`).
- Confirm button: shows `t('celebration.confirmButton')`, fires `emit('confirm')` on tap; cleared timers; emits `dismiss` 300ms later (popup fade-out duration).
- Title: `t('celebration.treasureUnlocked')` for single, falls back to `t('celebration.multipleTasks', {...})` for batch.
- All durations consume `MOTION.durations.*`; easings consume `MOTION.easings.springPop` for phrase pop.

**Patterns to follow:** Teleport + Transition + scoped CSS structure from `CelebrationAnimation.vue:1-37`. Use `aria-modal="true"` and `:aria-label="t('celebration.overlayLabel')"` (existing key).

**Test scenarios:**
- Mounted with `visible=true`: renders title, phrase, confirm button. Emits `confirm` when button clicked. With fake timers, advancing 6000ms emits `auto-dismiss` if no click.
- Mounted with `visible=false`: nothing rendered.

**Verification:** `npm run test:run` passes the new test file; typecheck clean.

---

### U6. Balance reaction — polling lastChange + CoinDisplay cascade + breathing

**Goal:** Wire the balance card to react when stars arrive — scale-pop + glow (C1), tier-cascade count-up (C2), 3-second breathing afterglow on dismiss (A5). Add `lastChange` to the polling singleton.

**Requirements:** C1, C2, A5; KTD-1.

**Dependencies:** U1.

**Files:**
- `frontend/apps/child/src/composables/useBalancePolling.ts` (modified)
- `frontend/apps/child/src/composables/useBalancePolling.test.ts` (new — currently no test for polling)
- `frontend/apps/child/src/components/coins/CoinDisplay.vue` (modified)
- `frontend/apps/child/src/components/coins/CoinDisplay.test.ts` (new)

**Approach:**

`useBalancePolling.ts`:
- Add module-level singleton `_lastChangeRef: Ref<{ from: number; to: number; at: number } | null> = ref(null)`.
- Inside `fetchBalance()`, before assigning `_balanceRef.value = bal`, capture `prev = _balanceRef.value`. After assignment, if `prev !== bal`, set `_lastChangeRef.value = { from: prev, to: bal, at: Date.now() }`.
- Same logic in the standalone `refresh()`.
- Append `lastChange: Readonly<Ref<{ from: number; to: number; at: number } | null>>` to the return type and returned object.
- Initial fetch (when `_balanceRef.value === 0` and prev was 0) must NOT fire `lastChange` — guard with a `_hasFetchedOnce` flag at module scope.

`CoinDisplay.vue`:
- Add a new prop `animateChanges?: boolean` (default false — preserves existing call sites).
- When true: watch `props.amount` changes. On change, run a tier-cascade count-up:
  - Compute prev tiers and next tiers via `splitCoinTiers`.
  - Cascade copper (400ms) → silver (500ms, starts +400ms) → gold (600ms, starts +900ms).
  - During each tier's count: drive a local `Ref<number>` per tier from prev→next, eased via `MOTION.easings.standardOut`, displayed instead of the static computed value.
  - Implementation: `requestAnimationFrame` loop; each tier has its own `startedAt` / `duration`.
  - During count-up, the displayed digit briefly bolds (font-weight 700); after settle, returns to 600.
- The `.balance-card` class gets a `[data-reacting="true"]` attribute toggle for scale-pop + glow CSS (added in U10 in the page scope, since `.balance-card` lives there).

**Patterns to follow:** Existing `splitCoinTiers` (`@/utils/coinTier`); rAF-based animation per U3 plan.

**Test scenarios:**
- `useBalancePolling.test.ts`:
  - Mock `getCoinBalance` returning sequence `[100, 100, 150]`. After three fetches: `lastChange.value` is `{ from: 100, to: 150, at: <number> }`.
  - First fetch (0 → 100) does NOT fire `lastChange` (guard via `_hasFetchedOnce`).
  - When balance polls return identical values, `lastChange` is unchanged.
- `CoinDisplay.test.ts` (smoke):
  - Mount with `:amount="0" :animateChanges="true"`. Update prop to `25`. Assert that within 1500ms (+ buffer), the rendered copper count text is `25`.
  - Mount with `:animateChanges="false"` (default), update prop, assert text snaps immediately.

**Verification:** Tests pass. Manual: polling tick that bumps balance triggers visible cascade.

---

### U7. `useFlightChoreography` — timing orchestrator

**Goal:** A single composable that owns the timing diagram from F=0 onward: invokes `<FlyToTarget>`, fires per-landing haptics, triggers balance reaction, schedules glow fade and breathing afterglow. Short-circuits on reduced-motion.

**Requirements:** S1, S2, M1, A5 (timing), D4 short-circuit.

**Dependencies:** U1, U2, U3, U6.

**Files:**
- `frontend/apps/child/src/composables/useFlightChoreography.ts` (new)
- `frontend/apps/child/src/composables/useFlightChoreography.test.ts` (new)

**Approach:**
- Exports `useFlightChoreography()` returning `{ run(opts), cancel() }`.
- `opts`:
  ```
  {
    origins: Array<{x, y} | HTMLElement | string>  // one per task, or single for batch
    target: HTMLElement | string
    starsEarned: number
    taskCount: number
    onPopupDismiss: () => void                  // page hides popup
    onBalanceReact: () => void                  // page toggles data-reacting
    onComplete: () => void                      // celebration done; page calls markCelebrated
    reducedMotionToast: (stars: number) => void // page shows Vant toast
  }
  ```
- Internal state: a `phase: 'idle' | 'flight' | 'glow' | 'breathing' | 'done'` ref.
- `run(opts)`:
  - If `useReducedMotion().value` is true → call `opts.reducedMotionToast(starsEarned)`, fire one `data-reacting="invert"` color-flip on target (300ms), then `onComplete()` after 2500ms.
  - Else: compute control point per Bezier rule from spec. Mount logical `<FlyToTarget>` (via a transient ref or function-based renderer — see directional design below). Per-landing fires `useHaptic().vibrate(MOTION.haptic.landing)`. First landing triggers `onBalanceReact()`. After last landing, schedule glow fade at +1600ms, breathing-afterglow start at +2000ms (3000ms duration), then `onComplete()`.
- `cancel()`: cancels any pending timers + rAF, calls `onComplete()` so state is consistent.
- Multi-task (taskCount > 1): inserts gathering-cloud phase. Origins map to per-task starts; cloud point is `(viewportWidth*0.5, viewportHeight*0.4)`. Two `<FlyToTarget>` invocations sequenced.

**Technical design (directional):**

The orchestrator does not own the `<FlyToTarget>` DOM. Instead, the `CelebrationAnimation.vue` (U10) renders `<FlyToTarget>` declaratively bound to refs the orchestrator mutates. The orchestrator advances `phase`, computes positions, schedules glow/breathing, and emits per-phase signals. This keeps timing logic out of templates.

**Test scenarios:**
- Reduced-motion path: with `useReducedMotion()` mocked to `true`, calling `run({...})` calls `opts.reducedMotionToast` once with `starsEarned`, calls `onComplete()` after 2500ms (fake timers). Does NOT call `onBalanceReact`.
- Normal path: with `useReducedMotion()` mocked to `false`, calling `run({...})` schedules the glow phase at the expected offset (assert via fake-timer advance + state inspection on `phase`).
- `cancel()` mid-flight: clears all timers, leaves `phase === 'done'`.

**Verification:** Tests pass. Integration verified via AT-1, AT-3, AT-4.

---

### U8. `<TrailResidue>` 60s session-local trail layer

**Goal:** Append a faint golden SVG path each time a star lands; fade over 60s; clear on page unmount.

**Requirements:** S4.

**Dependencies:** U1.

**Files:**
- `frontend/apps/child/src/components/celebration/TrailResidue.vue` (new)

**Approach:**
- Component owns a ref to the overlay `<svg>` element. Exposes a method `addPath(d: string)` via `defineExpose`.
- `addPath`: programmatically creates `<path>` element, appends to overlay, sets `class="trail-segment"`. Schedules removal at 60100ms.
- CSS: `.trail-segment { stroke: var(--color-brand-ochre); stroke-width: 1.5; stroke-dasharray: 4 4; stroke-linecap: round; fill: none; opacity: 0.4; animation: trail-fade 60s linear forwards; }`
- `@keyframes trail-fade { from { opacity: 0.4; } to { opacity: 0; } }`
- Overlay container: `position: fixed; inset: 0; pointer-events: none; z-index: 998;` (one less than star overlay).
- On `onBeforeUnmount`, clear all pending removal timers and empty the SVG.

**Patterns to follow:** Inline SVG style of existing coin components (`GoldenCoin.vue`, etc.).

**Test scenarios:** none — `Test expectation: none — pure DOM rendering, asserted via AT-1 manual visual check.`

**Verification:** Manual AT-1 step 8 — trail residue visible ~60s, fading.

---

### U9. `<StreakLayer>` streak-tier overlay

**Goal:** Render the streak-tier-driven extra particles (sparkles at ≥7, flame trail at ≥14, page-edge glow at ≥30). Layered on top of the main flight; consumed by orchestrator.

**Requirements:** A3.

**Dependencies:** U1.

**Files:**
- `frontend/apps/child/src/components/celebration/StreakLayer.vue` (new)

**Approach:**
- Props: `tier: 0 | 7 | 14 | 30`, `active: boolean`.
- For tier 7: 4 small sparkles, similar Bezier to main flight but smaller scale (0.3) and faster duration (500ms). Reuses `<FlyToTarget>` via slot? No — reuses Bezier math directly inside this component to avoid coupling.
- For tier 14: adds a CSS `filter: drop-shadow(0 0 4px var(--color-brand-ochre)) hue-rotate(15deg)` on each main-flight star (page passes a `streakTier` to `<FlyToTarget>` which forwards as a CSS class). Update U3 to accept `cssFilter?: string` prop (cheap addition).
- For tier 30: a single 1.5s `page-edge-glow` keyframe — `box-shadow: inset 0 0 40px var(--color-brand-ochre)` on the body via a `<div class="streak-edge-glow">` overlay (`position: fixed; inset: 0; pointer-events: none; z-index: 1`).
- Resolves the tier ONCE per celebration from `max(streak_count across batch)` — passed in by the orchestrator (D1 from spec).

**Patterns to follow:** Tier resolution logic mirrors approach in `frontend/apps/child/src/utils/coinTier.ts` — pure, testable.

**Test scenarios:** none — `Test expectation: none — visual layer asserted via AT-6 manual check (streak ≥ 7 shows extra sparkles).`

**Verification:** Manual AT-6.

---

### U10. Wire-up — `CelebrationAnimation.vue` refactor + `ChildTasksPage.vue` integration

**Goal:** Replace the v1 in-component star animation with the new orchestrated celebration. Add chore-card refs, balance-card ref, candle rendering, lock-spin, popup wiring.

**Requirements:** Path A/B/C/D/E triggers; KTD-3, KTD-6.

**Dependencies:** U3, U4, U5, U6, U7, U8, U9.

**Files:**
- `frontend/apps/child/src/components/CelebrationAnimation.vue` (modified)
- `frontend/apps/child/src/pages/ChildTasksPage.vue` (modified)
- `frontend/apps/child/src/composables/useCelebration.ts` (modified)

**Approach:**

`useCelebration.ts`:
- Add `celebrationStreakTier: Ref<0 | 7 | 14 | 30>`.
- In `triggerCelebration(tasks)`: compute `max(t.streak_count ?? 0 for t in tasks)`. Map to tier: `>=30 → 30`, `>=14 → 14`, `>=7 → 7`, else 0. Set `celebrationStreakTier.value`.
- Expose `celebrationStreakTier` in the return.

`CelebrationAnimation.vue` (refactor — touches lines 1-326):
- Rewrite template: replace inline `<div class="stars-container">` and inline phrase/summary with `<TreasureRevealPopup>` + `<FlyToTarget>` + `<TrailResidue>` + `<StreakLayer>`.
- Remove `starStyle()`, the inline `@keyframes star-fly` direction-less upward animation, and `starCount`. Keep `randomPhrase` logic but move into `TreasureRevealPopup`.
- New props add: `streakTier: number`, `taskRefs: Map<string, HTMLElement>`, `balanceRef: HTMLElement | null`, `taskIds: string[]`.
- Orchestration: on `props.visible` becomes true, `useFlightChoreography().run({...})` is called with origins resolved from `taskRefs` (filter out missing), target from `balanceRef`, and the four callbacks (popup-dismiss, balance-react, complete, reduced-motion-toast).
- The popup-confirm step: bind `<TreasureRevealPopup @confirm="onPopupConfirm">` where `onPopupConfirm` triggers the flight phase. `@auto-dismiss` does the same.
- Trail residue ref: `<TrailResidue ref="trailRef">`, exposed `addPath` called per landing.
- Streak layer: `<StreakLayer :tier="streakTier" :active="visible">`.
- The dismiss-on-overlay-click behavior in v1 (line 10) is preserved via the popup's own cancel emit, which calls `markCelebrated()` and skips flight (matches Edge Case 1 from spec).

`ChildTasksPage.vue` (modified — surgical):
- Add `taskCardRefs = ref(new Map<string, HTMLElement>())` and `balanceCardRef = ref<HTMLElement | null>(null)` to setup.
- Bind in template: `<div class="chore-card" :ref="el => el && taskCardRefs.set(c.id, el as HTMLElement)">`. Remove on unmount via existing v-for key handling (cleanup is implicit since refs are scoped to v-for).
- Bind balance card: `<div class="balance-card" ref="balanceCardRef">`.
- Render `<CandleFlame v-if="c.status === 'pending_approval'" :state="candleStates[c.id] || 'flickering'" :aria-label="t('celebration.candleAriaLabel')">` inside each chore card. On status transition (watch `c.status`), set state to `'bloom'` (approved) or `'gutter'` (rejected); on `bloom-end`/`gutter-end`, delete from `candleStates`.
- Replace existing confirm sheet button text `t('chore.completeConfirm')` with `t('celebration.sealTreasureChest')`.
- Add `[data-spinning]` toggle + scoped `@keyframes seal-spin` (KTD-3): rotate the lock icon 0→360deg over 300ms when `doComplete()` fires.
- Add scoped CSS for `.balance-card[data-reacting="true"] { animation: balance-pop 250ms cubic-bezier(.175,.885,.32,1.275); box-shadow: 0 0 40px var(--color-brand-ochre) ... }` and `.balance-card[data-reacting="invert"] { animation: balance-color-invert 400ms ease-out; }`.
- Pass refs into `<CelebrationAnimation>` as new props.
- `<CoinDisplay>` in `.balance-card` gets `:animate-changes="true"`.
- Watch `useBalancePolling().lastChange` → if it fires while a celebration is active, NOT trigger an extra reaction (the celebration owns the reaction); if it fires outside a celebration (rare, e.g., parent grant), trigger a single C1 pulse without flight.
- For Path E (rejection): existing `c.status === 'rejected'` watch sets `candleStates[c.id] = 'gutter'`.

**Patterns to follow:** Existing watcher patterns in `useCelebration.ts:46-51` and `ChildTasksPage.vue` polling logic.

**Test scenarios:** All 10 manual ATs from origin (AT-1..AT-10). No unit tests — this unit is the integration seam; correctness is observable, not assertable in JSDOM.

**Verification:** Manual run through AT-1, AT-2, AT-4 minimum (covers Paths A, B, reduced-motion). Plus AT-10: `git diff main -- server/` is empty.

---

### U11. i18n keys — 7 new keys × 2 locales

**Goal:** Add the 7 new keys under the `celebration` namespace in zh-CN and add full English translations in en-US.

**Requirements:** Origin §i18n Key Additions.

**Dependencies:** none (parallel-safe with any unit; serves U4, U5, U7, U10).

**Files:**
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (modified)
- `frontend/apps/child/src/i18n/locales/en-US.ts` (modified)

**Approach:**
- Add to existing `celebration: { ... }` namespace (line 307 in zh-CN.ts):
  - `treasureUnlocked: '宝藏解锁！'`
  - `confirmButton: '太棒了！'`
  - `sealTreasureChest: '锁住宝箱！'`
  - `chestLockedAwaiting: '宝箱已锁，等待爸妈开启 ⏳'`
  - `reducedMotionToast: '✨ 任务通过！获得 {stars} ⭐'`
  - `candleAriaLabel: '等待审批中'`
  - `streakBoostNotice: '🔥 连续 {days} 天！奖励翻倍'`
- Mirror in en-US.ts:
  - `treasureUnlocked: 'Treasure Unlocked!'`
  - `confirmButton: 'Awesome!'`
  - `sealTreasureChest: 'Seal the Treasure Chest!'`
  - `chestLockedAwaiting: '🔒 Chest locked — waiting for parents to open ⏳'`
  - `reducedMotionToast: '✨ Task approved! Earned {stars} ⭐'`
  - `candleAriaLabel: 'Awaiting approval'`
  - `streakBoostNotice: '🔥 {days}-day streak! Bonus doubled'`
- Keep existing `chore.completeConfirm` ("确认完成") — do NOT delete (per spec; may be referenced in main app or as a fallback).

**Patterns to follow:** Existing emoji-prefixed convention (root CLAUDE.md §Emoji convention). Existing `{stars}`, `{count}`, `{days}` interpolation style.

**Test scenarios:**
- Quick sync check (manual, not automated): both locale files have identical key sets under `celebration.*`.

**Verification:** `npm run typecheck` clean; `npm run lint` clean; manual locale-toggle smoke (switch language to en-US, run AT-1, popup shows English).

---

## Scope Boundaries

### Deferred to Follow-Up Work (plan-local sequencing)

- **`<SealButton>` extraction** — KTD-3 inlined the lock-spin. If a second seal/lock UX appears, extract then.
- **Dedicated component test per `.vue`** — KTD-4 chose lighter tests. If flakiness in manual ATs becomes a pattern, add visual regression (Chromatic / Percy).
- **Telemetry** — origin doc deferred; no event logging for celebration completion.
- **Audio layer** — origin doc explicitly deferred.

### Outside this plan's identity (origin-deferred)

These are NOT in this plan and NOT in any plan-local follow-up. From origin §Out of Scope:

- Swipe-to-complete gesture
- Mystery bonus (~20% golden flash)
- Star-pet creature balance (A2)
- Home page star-sky archive (A4)
- Parent-stamp avatar (P4)
- Red envelope reveal (P1)
- Swipe-to-bank dismissal (P5)
- Tier-crossing explosion (C3)
- Backend changes — `git diff main -- server/` must remain empty (AT-10)
- Other 6 future call-sites of `<FlyToTarget>` (wish-jar, gift-transfer, blind-box, milestone confetti replacement, treasure-collection, daily-login)

---

## System-Wide Impact

| Surface | Impact |
|---|---|
| Child app — Tasks page | Significant: new components, refs, candle rendering, lock-spin, popup wiring |
| Child app — Home page | Indirect: `<CoinDisplay>` adds `animateChanges` prop (default false → no behavior change for existing callers in Home/Ledger/Wishes) |
| Child app — Wishes / Treasures / Ledger | None — `useCelebration` only fires on Tasks page; cold-arrival celebration (Path C) is gated to that mount |
| Main app | None |
| Backend | None (AT-10 enforces) |
| Polling singleton | Additive: new `lastChange` ref. Existing consumers unaffected (don't use it) |
| i18n | 7 new keys × 2 locales; no removals |
| CSS / design tokens | Additive: motion vocabulary as TS only (KTD-2). No `clay.css` changes |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `requestAnimationFrame` choreography janks on low-end Android | Medium | Medium | Bezier math is cheap; particle count capped at 8/12; no heavy filters in tier-7. Fallback (Edge Case in spec) is opacity fade |
| `getBoundingClientRect()` returns zeroed rect when chore card is in a virtualized/transitioning state | Low | Medium | KTD-6 captures at confirm-tap (after sheet close); plus the Edge Case fallback to viewport-anchored origin |
| `useBalancePolling.lastChange` fires during cold-load (initial 0 → real value) | Medium | Medium | `_hasFetchedOnce` guard in U6; explicit unit test |
| Refactoring `CelebrationAnimation.vue` breaks the existing `CelebrationAnimation.test.ts` | High | Low | Existing test asserts inline-template structure; rewrite test to assert orchestration shell (popup mount, fly-target invocation count) |
| Multi-celebration queue collision (Edge Case row 11 — second tap during flight) | Low | Medium | `useFlightChoreography.cancel()` exposed; second trigger calls `cancel()` on first then runs; or queue with 400ms gap (spec D, Path D) |
| iOS Safari Vant toast position-top covered by status bar | Low | Low | Vant `showToast` has `position: 'top'` already accounts for safe-area; verify in AT-5 |

---

## Verification Plan

### Automated (CI gate)

Run from `frontend/apps/child/`:
- `npm run typecheck` — must pass clean.
- `npm run lint` — must pass clean.
- `npm run test:run` — must pass; new tests added in U1, U2, U5, U6 must all pass.

### Manual (acceptance test pass)

Run all 10 ATs from origin §Acceptance Test Scenarios. Minimum required for "ready to merge":

- **AT-1** Path A immediate-approval — flight, popup, glow, cascade, breathing all visible.
- **AT-2** Path B parent-gated — candle visible in pending; bloom on approval.
- **AT-3** Path D batch — gathering cloud phase visible.
- **AT-4** Reduced motion — DevTools toggle; no flight; toast + invert only.
- **AT-7** Rejection — candle gutters; no popup.
- **AT-10** `git diff main -- server/` returns empty.

Optional but recommended:
- AT-5 iOS Safari (or `navigator.vibrate = undefined` in console) — no JS errors.
- AT-6 streak-7 — visible extra sparkles.
- AT-8 scrolled-off — fallback origin used.
- AT-9 network failure — error toast, no celebration.

### Verifier Evidence

Per CLAUDE.md §Verify Before Claiming Done — capture:
- Output of `npm run typecheck` (clean).
- Output of `npm run test:run` (all green).
- One short screen recording of AT-1 + AT-2 + AT-4 (the three different paths) before opening PR.

---

## Dependencies / Assumptions

- **`ChoreInstance.streak_count`** present on every chore — verified `frontend/apps/child/src/api/chores.ts:66`.
- **Vue 3 reactivity + happy-dom** sufficient for unit tests — verified `frontend/apps/child/vitest.config.ts`.
- **Clay tokens** `--color-brand-ochre`, `--color-coin-{gold,silver,copper}-text` exist in both light and dark mode — verified `frontend/apps/child/src/assets/clay.css:11-32, 121-127`.
- **Vant `showToast`** auto-imported — verified by existing usages.
- **Existing `useCelebration` shell** — verified `frontend/apps/child/src/composables/useCelebration.ts:11-60`; this plan extends it, does not replace it.
- **No backend changes** — explicit constraint (AT-10).

---

## Sequencing Summary

```
U1 (tokens + bezier)   ┐
                       ├─→ U3 (FlyToTarget) ─┐
U2 (haptic + reduced)  ┘                     ├─→ U7 (orchestrator) ─┐
                                              │                      │
U4 (CandleFlame) ─────────────────────────────┤                      │
U5 (TreasureRevealPopup) ─────────────────────┤                      ├─→ U10 (wire-up) ─→ Verification
U6 (polling.lastChange + CoinDisplay) ────────┤                      │
U8 (TrailResidue) ────────────────────────────┤                      │
U9 (StreakLayer) ─────────────────────────────┘                      │
                                                                      │
U11 (i18n) ──────────────────────────────────────────────────────────┘
```

U1–U2 and U11 are parallelizable starting points. U3 unblocks U7. U10 is the convergence seam and runs last.
