---
date: 2026-05-24
status: ready-for-planning
upstream-ideation: docs/ideation/child-ui-interaction-ideas.md, docs/ideation/2026-04-14-children-starcoin-ideation.md
supersedes: none — v1 lives in docs/brainstorms/task-completion-celebration-animation-requirements.md (still valid as baseline); this is the v2 deepening
selected-bundle: Gamma (Alpha core + A1 candle + A3 streak tier + S4 trail residue + A5 breathing balance)
scope-tier: standard / feature
---

# Child Task-Approval Celebration v2 — Game-Feel Choreography

## Summary

Deepen the v1 celebration (stars launch upward off-screen on app-open after parent approval) into a moment that *feels like a game*: an approval-arrival popup → child confirms → stars arc from the approved task card to the balance card on a parabolic Bezier path → balance card pops and glows → gold/silver/copper tiers cascade-count-up → 3-pulse haptic signature accompanies each landing. Ambient layer adds a candle that flickers while pending, streak-tier-driven visual escalation, faint star trails that linger 60s, and a 3-second breathing afterglow on the balance card.

## Problem

The current celebration (`CelebrationAnimation.vue`) is anticlimactic in five specific ways:

1. **Direction-less flight** — stars launch upward off-screen (`translate(calc(-65vh))`) instead of toward the balance card. The reward visually *disappears* rather than *arriving*.
2. **Silent counter** — `CoinDisplay` updates instantly on `amount` prop change with no animation; `useBalancePolling` refreshes silently every 60s. The balance has no reaction to receiving stars.
3. **Flat pending state** — between "completed" and "approved", the card shows a static `pending_approval` badge for up to 10 minutes. Dead air.
4. **No multi-sensory signal** — zero haptic, zero audio. Visual-only feedback in a context where children's reward processing is strongly multi-sensory.
5. **No persistence beyond 2.8s** — once celebration dismisses, the page returns to a static list. The reward has no afterlife and the page feels dead between approvals.

The v1 ideation (`docs/ideation/child-ui-interaction-ideas.md`) selected the "Completion Experience Package" bundle (celebration + swipe + sound/haptic + mystery bonus). This v2 brainstorm fully specifies the celebration component, intentionally deferring swipe-to-complete and mystery bonus to separate brainstorms.

## User Story

**As a 5-8 year old child**, when I tap "完成" on a chore and my parent later approves it, I want the moment of approval to feel like opening a treasure chest: I see something arrive, I tap to claim it, stars fly into my star jar, my jar pops and grows, and I feel a buzz in my hand confirming the reward is real and mine.

**As a parent**, I want the celebration to be brief enough not to derail my child's focus, but rich enough that my child wants to come back tomorrow.

## Scope

### In Scope (Gamma bundle)

**Core spine (Alpha):**
- `P2` "锁住宝箱" confirm-button with lock-spin + spring scale
- `P3` Treasure-reveal popup on `approved` arrival (radial gradient, task emoji, encouraging phrase)
- `S1` Parabolic Bezier star flight from task card → balance card
- `S2` Multi-task batch: gathering cloud → unified burst
- `C1` Balance card scale-pop + glow-pulse on first star arrival
- `C2` Three-tier cascade count-up (copper → silver → gold)
- `M1` 3-pulse haptic signature per star landing

**Persistence layer (Gamma additions):**
- `A1` Candle flame while `pending_approval` → bloom on `approved` arrival
- `A3` Streak-tier visual escalation (day 1 base / day 7 sparkle / day 14 flame / day 30 page-glow)
- `S4` Faint golden SVG trail path persisting 60s session-local
- `A5` Balance card 3-second breathing afterglow on dismiss

**Engineering substrate:**
- `E1` `<FlyToTarget>` Vue primitive (reusable for future gift-transfer, wish-jar-fill, blind-box-drop)
- `E3` `motionTokens.ts` shared easing/duration/scale vocabulary

### Out of Scope (deferred to separate brainstorms)

- **Swipe-to-complete gesture** — replacing the tap interaction with horizontal swipe on the task card
- **Audio layer** — pop on tap, coin-clink on earn, jingle on complete (no audio in this iteration)
- **Mystery bonus** — ~20% chance of golden flash + extra reward
- **Star-pet creature balance** (A2) — replaces balance card with chipmunk/fox/bear
- **Home page star-sky memory archive** (A4) — localStorage celebration history rendered on home page
- **Parent-stamp avatar visualization** (P4) — parent's avatar walks across screen to stamp task
- **Red envelope reveal popup** (P1) — coin amount hidden until tap-to-tear
- **Swipe-to-bank dismissal gesture** (P5) — popup requires upward swipe to clear
- **Tier-crossing explosion** (C3) — coins scatter and recompose when crossing tier boundary
- **Backend changes** — uses existing `ChoreInstance.streak_count`, `streak_bonus`; no new endpoints

## Trigger Conditions

| Trigger | Path | Behavior |
|---|---|---|
| Child taps `btn-complete` on an `available` task | Path A: immediate-approval (no parent gate) | Sheet shows → confirm with lock-spin → API returns `approved` directly → popup appears → celebration runs |
| Child taps `btn-complete`, status → `pending_approval` | Path B: parent-gate | Card shows pending badge + candle flicker → polling detects `approved` → popup appears at next polling tick → celebration runs |
| Child opens app and finds previously-approved tasks not yet celebrated (v1 path) | Path C: cold-arrival | `useCelebration.checkAndTriggerCelebration()` fires after data load → batch celebration via gathering-cloud → balance reacts |
| Multiple tasks approved while child active | Path D: batch | Each new approval enqueues; celebrations run sequentially with 400ms gap, or merge if arrival is within 800ms window |
| Parent rejects a pending task | Path E: rejection | Candle gutters out (flicker-to-dark over 600ms) → no popup → status badge swaps to `rejected` |

## Choreography Specification

### Timing Diagram (single task, Path A or B)

```
T=0ms      User taps "完成" → bottom sheet opens
T=0-200ms  User taps "锁住宝箱" button → lock-icon rotates 0→360deg (300ms ease-out) +
           button scale-pulse 1.0→0.95→1.05→1.0 (spring, 250ms) → API call fires
T=200ms    Submit complete; sheet closes; if response = approved go directly to T=2000ms
           if response = pending_approval → render candle flame on card

[Path B only, pending → approved transition]
T=Xms      Polling tick detects status === 'approved' (X = first poll after parent approves)

T=Xms+0    Candle flame blooms: scale 1.0→1.6 (200ms ease-out), opacity 0.7→1.0,
           color-shift ochre→gold; followed by burst fade 300ms → ember 200ms → dismiss

T=Xms+500  Treasure-reveal popup mounts:
             - Overlay fade-in 200ms
             - Radial gradient background ochre→peach expanding from center 0.6s
             - Task emoji enters with phrase-pop spring (300ms cubic-bezier(.175,.885,.32,1.275))
             - Encouraging phrase from celebration.phrases[]
             - Confirm button "太棒了！" fade-in after 400ms
             - 400ms haptic on overlay-mount (single, separate from 3-pulse landings)

T=Xms+500 to user-tap   User taps "太棒了！" to confirm.
                        If user does not tap within 6s, auto-dismiss with same flight sequence.

[Star flight begins on confirm tap]
T=F+0ms    Resolve task-card position via getBoundingClientRect() at confirm-tap time
           (NOT at popup-mount time — popup overlay may have shifted layout).
           Resolve .balance-card position similarly.
           Number of stars = min(taskCount + 2, 8) [existing rule]

T=F+0ms    Popup overlay starts fade-out (300ms); does not block flight

T=F+0 to F+960ms  Each star (i=0..N-1):
                  - Spawn at task-card center + jitter (±8px)
                  - Animate along quadratic Bezier:
                      start: (taskX, taskY)
                      control: ((taskX+balanceX)/2, min(taskY,balanceY) - 200)
                      end: (balanceX, balanceY)
                  - Duration 800ms per star, ease-out cubic
                  - Stagger: i * 120ms
                  - Rotation: rotate(720deg * progress), aligned via Bee Waggle (S3 was rejected; default linear rotation)
                  - Scale curve: 0.5 (0%) → 1.2 (peak at 60%) → 0.8 (100%)
                  - Each landing fires 3-pulse haptic: navigator.vibrate([50,30,50,30,100])
                  - Each landing leaves trail point (S4) — see Trail section below

T=F+800ms  First star arrives at balance card → triggers balance reaction:
             - Card scale 1.0→1.15→1.0 (250ms spring cubic-bezier(.175,.885,.32,1.275))
             - box-shadow glow expand: 0 0 20px → 0 0 40px ochre alpha 0.6 (300ms)
             - Outer shimmer ring: 2px solid ochre alpha 0.8 fade-in 200ms
             - Tier-cascade count-up begins (see Count-Up section)

T=F+800-2400ms  Tier-cascade count-up:
                - Copper digit count-up: 400ms ease-out (starts immediately)
                - Silver digit count-up: 500ms ease-out (starts at +400ms)
                - Gold digit count-up: 600ms ease-out (starts at +900ms)
                - During each tier's count-up: digit font-weight 700 (briefly bold)
                - After each tier settles: font-weight returns to 600
                - Glow persists through entire cascade (1.5s total)

T=F+2400ms      Glow begins fade (400ms)
T=F+2800ms      Glow gone. Balance card enters 3s breathing afterglow (A5):
                - scale 1.0→1.03→1.0 (3s loop, ease-in-out)
                - ochre border alpha 0.3→0.6→0.3 synchronized
                - One full loop, then static

T=F+5800ms      Breathing afterglow ends. Balance returns to static state.
                Trail residue (S4) continues fading until T=F+60_000ms.

[Streak tier layer — runs concurrently with main choreography]
If chore.streak_count >= 7:   add 4 extra sparkle particles to flight (smaller, faster, no haptic)
If chore.streak_count >= 14:  add flame particle trail behind each star (CSS filter: drop-shadow + hue rotation)
If chore.streak_count >= 30:  page-edge gold border-glow pulse during entire flight (single 1.5s pulse)
Tier resolves ONCE per celebration from max(streak_count across batch). Per D1.
```

### Multi-Task Batch (Path C/D)

When `taskCount > 1`:

```
T=0ms       Popup appears with batch summary "完成 {count} 个任务! 获得 {stars} ⭐"
            (existing celebration.multipleTasks key) — confirm button text unchanged
T=F+0ms     Phase 1: per-task mini-burst
              Each task emits 2-3 stars from its own card position (if visible) or
              fallback bottom-anchor (10/30/50/70% x). Stars arc UPWARD ONLY to gathering
              cloud at viewport (50% x, 40% y). Duration 600ms per star, stagger 80ms.
T=F+600ms   Phase 2: gathering cloud forms — all stars now hover at cloud center with
              subtle orbital drift (±15px, 1.5s loop). Cloud glows briefly.
T=F+700ms   Phase 3: unified burst — all gathered stars now stream from cloud to balance
              card on Bezier path (single control point above cloud-center).
              Duration 700ms, no per-star stagger (concentrated stream).
T=F+1400ms  First arrival → balance reactions begin (same as single-task)
```

Cap stars at 12 for batch; if `taskCount + 2 > 12`, scale down per-task contribution.

### Pending-State Candle (A1)

While `status === 'pending_approval'`:

- Render `🕯️` emoji absolutely positioned over the chore-card top-right corner (20px × 20px area)
- CSS animation: opacity 0.7 → 1.0 → 0.8 → 1.0 (3s ease-in-out infinite)
- Subtle horizontal shift: translateX(-1px) → translateX(1px) (2.5s ease-in-out infinite, offset 0.5s)

On `approved` transition:
- Candle bloom: scale 1.0 → 1.6 over 200ms ease-out
- Color shift: filter brightness(1) → brightness(1.4) saturate(1.3)
- Burst fade: opacity 1.0 → 0.0 over 300ms
- DOM removal at 500ms

On `rejected` transition:
- Candle gutter: opacity 1.0 → 0.3 → 0.05 → 0 over 600ms ease-in
- No bloom; flame dies out

### Trail Residue (S4) — Session-Local

After each star arrives at the balance card, append an SVG `<path>` element to a session-scoped overlay layer:

- Path: `M ${startX} ${startY} Q ${controlX} ${controlY} ${endX} ${endY}` (matching the flight Bezier)
- Stroke: `var(--color-brand-ochre)` with `stroke-width: 1.5`, `stroke-dasharray: 4 4`, `stroke-linecap: round`
- Initial opacity: 0.4 → 0 over 60s linear
- Fade triggered via CSS animation, removed from DOM after 60s + 100ms buffer

Per D3: trails are **session-local only**. Page navigation clears them. Not persisted to localStorage.

### Reduced-Motion Mode (D4)

When `window.matchMedia('(prefers-reduced-motion: reduce)').matches === true`:

- **No** popup overlay, **no** star flight, **no** balance scale-pop, **no** glow, **no** breathing, **no** candle flicker, **no** trail, **no** streak-tier layers, **no** haptic
- **Yes** show a non-modal toast at top of screen for 2.5s: `t('celebration.reducedMotionToast')` (e.g., "✨ 任务通过！获得 {stars} ⭐")
- **Yes** balance card briefly inverts colors (ochre ↔ peach swap) over 400ms ease-out as the single subtle reaction cue
- **Yes** counter snaps to new value immediately (no count-up animation)

Watcher: `matchMedia` listener registered in `useCelebration` setup; if user toggles preference mid-session, takes effect on next celebration.

### Haptic Fallback (D5)

```ts
// Centralized in useHaptic() composable
function tryVibrate(pattern: number | number[]): boolean {
  if (typeof navigator === 'undefined') return false
  if (typeof navigator.vibrate !== 'function') return false
  try {
    return navigator.vibrate(pattern)
  } catch {
    return false
  }
}
```

iOS Safari returns `undefined` for `navigator.vibrate` → silent no-op. No visual substitute (per D5).

## DOM Targeting Strategy

### Position Resolution

**Star flight origin (task-card center):**
- Each `.chore-card` element gets `ref` attached on render
- On `confirm` tap, walk approved task IDs → look up corresponding refs → call `el.getBoundingClientRect()`
- Center = `(rect.left + rect.width/2, rect.top + rect.height/2)`
- If element is off-screen (scrolled away): fall back to viewport-anchored origin (50% x, 80% y bottom)

**Star flight target (balance card):**
- `.balance-card` already exists at `ChildTasksPage.vue` line 30
- Use a stable `ref="balanceCardRef"` (currently relies on class selector)
- Target = center via same `getBoundingClientRect()` pattern
- If balance card is off-screen: clamp end Y to `min(rect.bottom, viewport.height - 80px)` to keep flight visible

### Coordinate System

All positions stored as viewport-relative pixels (`fixed` positioning), NOT page-scroll coordinates. Star overlay uses `position: fixed; inset: 0; pointer-events: none; z-index: 999`.

If the user scrolls during the 800ms flight: stars continue along their viewport-relative path (do NOT update target mid-flight). This is acceptable because the balance card uses sticky-top behavior — scrolling does not move it.

### Resize / Orientation Change

If `window.innerWidth` or `innerHeight` changes mid-animation:
- Existing star animations complete on their original Bezier path
- Newly-launched stars (in batch mode, subsequent waves) recompute positions

## Edge Cases

| Edge case | Handling |
|---|---|
| User dismisses popup via system back-gesture before flight starts | Skip flight, still mark `useCelebration.markCelebrated()` so popup doesn't re-fire |
| Approval arrives while child is on a different page (Wishes, Treasures, etc.) | Defer celebration to next `ChildTasksPage` mount (existing `useCelebration` behavior preserves this) |
| Network failure during `markChoreComplete` API call | Existing error path unchanged; no celebration triggered (status didn't transition) |
| Polling timeout (10min) reached without approval | Candle remains flickering; no negative reaction; user can refresh manually |
| Balance polling returns `oldBalance === newBalance` (no change) | Skip C1 + C2 — celebration popup still runs but no balance reaction. Logs a warning (likely a backend sync issue) |
| Multiple celebrations queued back-to-back within 800ms | Merge into single celebration (existing `findPendingCelebrations` aggregates) |
| `taskCount + 2 > 8` (existing cap) for batch path | Cap at 12 for v2 batch path; per-task contribution scales as `floor(12/taskCount)` |
| Streak count is `0` or `undefined` | No streak-tier layer; base celebration only |
| Device with no `requestAnimationFrame` (very old browsers) | Fallback to `setTimeout(16ms)` — but no fallback for flight Bezier; degrade to simple opacity fade |
| User in reduced-motion mode + iOS Safari (no haptic) | Toast + color-invert only; matches reduced-motion path |
| Child interacts with another card during flight (taps complete on a second task) | Allow — second sheet opens normally. Second celebration enqueues behind first |
| App backgrounds during flight (Page Visibility hidden) | Animations pause via existing `useBalancePolling` visibility handling; resume on visible |

## Success Criteria

A v2 celebration is "working" when:

1. **Choreography integrity** — Manual test: tap complete on a parent-gated task → wait for parent approval → popup appears → tap confirm → stars trace a visible arc from the specific task card to the balance card → balance card pops, glows, counts up tier-by-tier → 3s breathing settles. Total elapsed from popup-mount to breathing-end ≤ 8 seconds.

2. **Persistence layer fires** — Candle visible during pending; trails visible after flight; breathing afterglow runs 3s; streak-7+ adds visible sparkle layer.

3. **Reduced-motion respect** — With `prefers-reduced-motion: reduce` set in DevTools, no flight or popup runs; toast appears; counter updates instantly.

4. **iOS Safari graceful** — Same visual choreography as Android Chrome; no JavaScript errors from absent `navigator.vibrate`.

5. **Multi-task batch** — Approving 3 tasks within one polling window produces one celebration with gathering-cloud phase, not three sequential ones.

6. **No backend changes** — `git diff server/` is empty for this work.

7. **Existing v1 path still works** — Cold-arrival celebration (Path C, child opens app to find approved tasks) uses the new choreography correctly.

## i18n Key Additions

All additions to **both** `src/i18n/locales/zh-CN.ts` and `src/i18n/locales/en-US.ts`. Add under existing `celebration.*` namespace.

```ts
celebration: {
  // EXISTING
  phrases: [...],
  singleTask: '获得 {stars} ⭐！',
  multipleTasks: '{count}个任务通过！获得 {stars} ⭐',
  overlayLabel: '任务通过庆祝',

  // NEW for v2
  treasureUnlocked: '宝藏解锁！',           // "Treasure Unlocked!" — popup title on approval arrival
  confirmButton: '太棒了！',                  // "Awesome!" — popup confirm button
  sealTreasureChest: '锁住宝箱！',           // "Seal the Treasure Chest!" — replaces existing chore.completeConfirm in Tasks page
  chestLockedAwaiting: '宝箱已锁，等待爸妈开启 ⏳',  // "Chest locked, waiting for parents to open" — pending-state hint toast
  reducedMotionToast: '✨ 任务通过！获得 {stars} ⭐',  // "Task approved! Earned {stars} stars" — reduced-motion path
  candleAriaLabel: '等待审批中',              // "Awaiting approval" — candle accessibility label
  streakBoostNotice: '🔥 连续 {days} 天！奖励翻倍', // optional — only shown when streak_count crosses threshold mid-flight
}
```

**Existing key reuse:** `chore.completeConfirm` ("确认完成") is renamed at the call site to `celebration.sealTreasureChest`. Do NOT delete `chore.completeConfirm` — it may be referenced elsewhere.

## Engineering Substrate (E1, E3)

### `<FlyToTarget>` Vue Primitive (E1)

**Path:** `frontend/apps/child/src/components/celebration/FlyToTarget.vue` (new directory `celebration/`)

**Props:**
```ts
interface Props {
  origin: { x: number; y: number } | HTMLElement | string  // pixel coords, element ref, or selector
  target: { x: number; y: number } | HTMLElement | string
  particleCount: number              // default 8
  particleType: 'star' | 'coin' | 'sparkle' | 'flame'  // SVG variants
  duration?: number                  // per-particle ms; default 800
  staggerMs?: number                 // default 120
  controlPointOffset?: number        // Bezier control point height above midpoint; default 200
  rotationDeg?: number               // total rotation; default 720
  scaleCurve?: [number, number, number]  // [start, peak, end]; default [0.5, 1.2, 0.8]
  onLandingPerParticle?: () => void  // fired per landing (for haptic trigger)
  onAllLanded?: () => void           // fired once after final landing
}
```

Component manages its own teleported overlay layer and cleans up DOM on unmount. The 7 places that will reuse this primitive eventually (future scope, not v2):
1. Task-approval celebration (this brainstorm)
2. Wish-jar deposit visualization (`ChildWishesPage.vue` — coins flow to jar)
3. Gift-transfer between siblings (when Idea #7 from starcoin doc lands)
4. Blind box reward fly-out (`ChildBlindBoxPage.vue`)
5. Milestone unlock confetti replacement (`MilestoneCelebration.vue`)
6. Treasure-collection animation (when wish becomes treasure)
7. Daily login bonus (future)

### `motionTokens.ts` (E3)

**Path:** `frontend/apps/child/src/utils/motionTokens.ts`

```ts
export const MOTION = {
  durations: {
    instant: 100,
    fast: 200,
    medium: 400,
    slow: 800,
    glacial: 3000,
  },
  easings: {
    standardOut: 'cubic-bezier(0.0, 0.0, 0.2, 1)',
    standardInOut: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
    springPop: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
    accelerate: 'cubic-bezier(0.4, 0.0, 1, 1)',
  },
  scales: {
    press: 0.96,
    pulse: 1.03,
    pop: 1.15,
    burst: 1.2,
  },
  haptic: {
    landing: [50, 30, 50, 30, 100],  // 3-pulse signature
    confirm: [50],
    arrival: [400],                   // popup mount
    final: [150],                     // last-star
  },
} as const
```

All celebration code imports from this single source. Reduced-motion mode does not consult MOTION — that flag short-circuits before any motion executes.

## Dependencies / Assumptions

- **`ChoreInstance.streak_count`** present on every approved chore (verified ✅ `src/api/chores.ts:66`)
- **No CSP restrictions** on inline SVG or `position: fixed` overlays (verified — confetti and current celebration both use these)
- **Vant 4 + Vue 3 reactivity** sufficient for Bezier interpolation via `requestAnimationFrame` (no need for a motion library like Motion One or Framer Motion)
- **Clay design system** has `--color-brand-ochre`, `--color-brand-peach`, `--color-canvas` tokens (verified)
- **Dark mode** must be respected — gold/silver/copper tier colors already adapt via `--color-coin-*-text` tokens. Confirm trail residue stroke color works in dark mode (`#e8b94a` shifts to ochre primary, which is the dark-mode interactive color)

## Outside This Brainstorm's Identity

These are decisions deferred to ce-plan or future brainstorms, intentionally NOT specified here:

- **Specific Vue component file structure** beyond the substrate primitives (E1, E3) — ce-plan decides whether the popup is its own component, lives inside `CelebrationAnimation.vue`, or splits further
- **CSS file organization** — whether motion tokens land in `clay.css`, a new `motion.css`, or only as TS constants
- **State machine for queued celebrations** — exact implementation of the 800ms merge window
- **Test strategy** — unit tests, component tests, or visual regression tests; ce-plan picks
- **Telemetry** — whether to log celebration completion to backend (out of scope for v2)
- **Animation perf budget on low-end devices** — ce-plan decides whether to disable streak-tier layers on devices below a certain RAM threshold

## Open Questions

None blocking ce-plan. Optional product calls that could be revisited later:

- Should the **popup auto-dismiss timeout** (currently 6s) be shorter for repeat users? Could be added in a follow-up if logs show users routinely waiting it out.
- Should **trail residue** be tappable to replay a ghost flight? Cool feature; deferred until we see if children actually notice the trails.
- Should the **page-edge gold pulse** at streak_30 also fire for streak_60, 90, 100 with escalation? Wait for real users to hit streak_30 before designing.

## Visual Choreography (ASCII Timing Chart)

For the **single-task Path B** (parent-gated approval). Read top-to-bottom = time; each column = a layer.

```
TIME    │ TASK CARD     │ CANDLE        │ POPUP         │ STARS         │ BALANCE CARD  │ HAPTIC    │ AUDIO
────────┼───────────────┼───────────────┼───────────────┼───────────────┼───────────────┼───────────┼───────
0       │ tap "完成"     │               │ sheet opens   │               │ static        │           │
0-200   │ pending CSS   │ flicker init  │ "锁住宝箱" tap │               │ static        │  [50]     │
        │               │ (3s loop)     │ + spin + API  │               │               │ confirm   │
200-X   │ pending badge │ flickering    │ closed        │               │ static        │           │
        │ (X = poll)    │ (continuous)  │               │               │               │           │
X+0     │ pending→appr  │ BLOOM 200ms   │               │               │ static        │           │
X+200   │ approved      │ → ember 300ms │               │               │ static        │           │
X+500   │ approved      │ removed       │ MOUNT         │               │ static        │  [400]    │
        │               │               │ radial glow   │               │               │ arrival   │
X+500   │ approved      │               │ phrase pop    │               │ static        │           │
X+900   │ approved      │               │ confirm fade  │               │ static        │           │
        │ (...)         │               │ (waits user)  │               │               │           │
F=0     │ approved      │               │ FADE-OUT 300ms│ launch s0     │ static        │           │
F=120   │ approved      │               │ fading        │ s0 60% s1 0%  │ static        │           │
F=240   │ approved      │               │ gone          │ s1 60% s2 0%  │ static        │           │
F=...   │               │               │               │ (cascade)     │               │           │
F=800   │ approved      │               │               │ s0 LANDS      │ scale 1.15    │ [50,30,   │
        │               │               │               │ + trail seg   │ + glow start  │  50,30,   │
        │               │               │               │               │               │  100]     │
F=920   │               │               │               │ s1 LANDS      │ glow expanding│ [pulse]   │
F=1040  │               │               │               │ s2 LANDS      │ tier-cascade: │ [pulse]   │
        │               │               │               │               │ copper count  │           │
F=1200  │               │               │               │ s4 LANDS      │ +silver count │ [pulse]   │
F=1700  │               │               │               │ all landed    │ +gold count   │           │
F=2400  │               │               │               │ trails fading │ glow fade-out │           │
F=2800  │               │               │               │ (60s decay)   │ BREATHING     │           │
F=5800  │               │               │               │ (40s decay)   │ static        │           │
F=60000 │               │               │               │ trails gone   │ static        │           │
```

For **multi-task Path D batch**, insert a "gathering cloud" phase between F=0 and F=700ms (per-task bursts ascend to viewport (50%, 40%) and orbit briefly, then unified stream to balance card).

For **reduced-motion**, the entire chart collapses to: `T=X+500: toast appears + balance color-invert flash + counter snaps to new value. T=X+2900: toast dismisses.`

## Implementation File Inventory

Concrete files to create or modify. ce-plan will turn this into ordered tasks.

### New files

| Path | Purpose |
|---|---|
| `frontend/apps/child/src/utils/motionTokens.ts` | E3 — centralized motion vocabulary (durations, easings, scales, haptic patterns) |
| `frontend/apps/child/src/composables/useHaptic.ts` | Wraps `navigator.vibrate` with feature-detect + try/catch |
| `frontend/apps/child/src/composables/useReducedMotion.ts` | matchMedia listener; returns reactive `Ref<boolean>` |
| `frontend/apps/child/src/composables/useFlightChoreography.ts` | Orchestrates the timing diagram; consumes `useHaptic` + `useReducedMotion` |
| `frontend/apps/child/src/components/celebration/FlyToTarget.vue` | E1 — reusable particle-flight primitive |
| `frontend/apps/child/src/components/celebration/CandleFlame.vue` | A1 — pending-state flame with bloom/gutter transitions |
| `frontend/apps/child/src/components/celebration/TreasureRevealPopup.vue` | P3 — approval-arrival popup (replaces inline approach in `CelebrationAnimation.vue`) |
| `frontend/apps/child/src/components/celebration/TrailResidue.vue` | S4 — session-local SVG trail layer |
| `frontend/apps/child/src/components/celebration/StreakLayer.vue` | A3 — streak-tier sparkle/flame/page-glow overlay |
| `frontend/apps/child/src/utils/bezier.ts` | Quadratic Bezier interpolation utility (pure functions, testable) |

### Modified files

| Path | Change |
|---|---|
| `frontend/apps/child/src/components/CelebrationAnimation.vue` | Refactor: replace inline star-fly logic with `<FlyToTarget>` + `<TreasureRevealPopup>` orchestration; keep summary-card transition for fallback |
| `frontend/apps/child/src/components/coins/CoinDisplay.vue` | Add `animateAmountChange(from, to)` method; tier-cascade count-up (copper → silver → gold staggered) |
| `frontend/apps/child/src/composables/useCelebration.ts` | Inject `getStreakTier(tasks)` for streak resolution; emit per-tier events for `<StreakLayer>` |
| `frontend/apps/child/src/composables/useBalancePolling.ts` | Add `previousBalance` tracking + emit `balance-changed` event; the celebration consumer triggers C1+C2 on this event rather than on `amount` prop change |
| `frontend/apps/child/src/pages/ChildTasksPage.vue` | (a) attach refs to `.chore-card` for position resolution; (b) add stable `balanceCardRef`; (c) render `<CandleFlame>` overlay on each `pending_approval` card; (d) replace `chore.completeConfirm` text with `celebration.sealTreasureChest`; (e) add lock-spin animation to confirm button |
| `frontend/apps/child/src/i18n/locales/zh-CN.ts` | Add 7 new keys under `celebration.*` namespace |
| `frontend/apps/child/src/i18n/locales/en-US.ts` | Mirror the 7 new keys with English translations |

### Files NOT touched

- Any backend file (`server/**`) — no API changes
- `MilestoneCelebration.vue` — milestone path stays separate; future refactor could share `<FlyToTarget>` but out of scope
- Main app (`frontend/apps/main/**`) — child-app-only change

## Acceptance Test Scenarios

Manual test scenarios, written so a QA engineer (or the user) can run them. ce-plan will decide automation strategy.

### AT-1 — Path A: Immediate-approval single task

**Precondition:** Logged in as a child whose family has `auto_approve_chores: true` (or task is auto-approved by template setting).
**Steps:**
1. Open Tasks page; tap "完成" on an `available` task.
2. In the bottom sheet, tap "锁住宝箱".
**Expected:**
- Lock-icon spins 360° during 300ms; button compresses then bounces.
- Sheet closes ~200ms after tap.
- Within 800ms, treasure-reveal popup mounts with task emoji + encouraging phrase + 400ms haptic.
- Tap "太棒了！". Popup fades out.
- Stars (count = 1 task → 3 stars) arc from task-card position to balance-card on parabolic path. ~800-960ms total.
- Balance card scale-pops, glows ochre, counts up tier-by-tier.
- 3-pulse haptic per landing on Android Chrome; silent on iOS Safari (no errors).
- 3s breathing afterglow on balance card.
- Trail residue visible for ~60s, slowly fading.

### AT-2 — Path B: Parent-gated single task

**Precondition:** Family has `auto_approve_chores: false`. Parent device available.
**Steps:**
1. Child marks task complete → status enters `pending_approval`.
2. Verify candle flame visible on the task card, flickering.
3. Parent device approves the task.
4. Wait up to 5 seconds (polling interval).
**Expected:**
- Candle blooms (200ms grow, color-shift) then fades to ember (300ms) and is removed.
- Within 500ms after candle removal: treasure-reveal popup mounts.
- Continuing from AT-1 step 4 onward, same as AT-1.

### AT-3 — Path D: Multi-task batch (3 tasks)

**Precondition:** 3 tasks pending or approved within 800ms window.
**Steps:**
1. Child completes 3 tasks rapidly OR app loads with 3 newly-approved tasks.
**Expected:**
- Single popup shows "完成 3 个任务! 获得 X ⭐".
- On confirm: per-task mini-bursts launch from each visible card position upward to gathering cloud (50%, 40%).
- Cloud forms with brief orbital drift.
- Unified stream of stars flows from cloud to balance card.
- Balance reaction unchanged from single-task case.
- Total elapsed F=0 to balance-static ≤ 4 seconds.

### AT-4 — Reduced motion

**Precondition:** Set `prefers-reduced-motion: reduce` in DevTools.
**Steps:** Run AT-1.
**Expected:**
- No popup overlay, no stars, no glow, no breathing, no candle flicker, no trail.
- Toast appears at top: "✨ 任务通过！获得 X ⭐" for ~2.5s.
- Balance card briefly inverts colors (ochre↔peach) over 400ms.
- Counter snaps to new value (no count-up).
- Zero `navigator.vibrate` calls.

### AT-5 — iOS Safari haptic absence

**Precondition:** iOS Safari (or Chromium with `Object.defineProperty(navigator, 'vibrate', { value: undefined })` in console).
**Steps:** Run AT-1.
**Expected:**
- Full visual choreography runs identically to Android.
- No JavaScript errors in console.
- No visual substitute appears (per D5).

### AT-6 — Streak-7 tier layer

**Precondition:** Approved task has `streak_count >= 7`.
**Steps:** Run AT-1 with such a task.
**Expected:** Standard celebration PLUS 4 small sparkle particles in the flight (smaller than main stars, faster, no haptic).

### AT-7 — Rejection path (Path E)

**Precondition:** Task pending; parent rejects.
**Steps:**
1. Child marks complete → candle flickers.
2. Parent rejects.
3. Wait for polling tick.
**Expected:**
- Candle gutters out (opacity 1.0 → 0.3 → 0.05 → 0 over 600ms).
- Status badge swaps to `rejected`.
- No popup. No celebration. No haptic.

### AT-8 — Position resolution: scrolled task off-screen

**Precondition:** Task list has 20+ items; the approved task scrolls below the fold during pending wait.
**Steps:** Run AT-2 but scroll down so the task card is no longer visible when approval arrives.
**Expected:**
- Stars launch from viewport-anchored fallback (50% x, 80% y).
- Balance reaction unchanged.
- No JavaScript errors.

### AT-9 — Network failure during confirm tap

**Precondition:** Disable network; child taps "锁住宝箱".
**Steps:** Run AT-1 step 2 with network off.
**Expected:**
- Lock-spin runs (button is purely client-side).
- API call fails; sheet remains open with existing error toast.
- No popup. No celebration.
- Restore network → retry succeeds.

### AT-10 — Backend untouched

**Precondition:** Branch checked out for this work.
**Steps:** `git diff main -- server/`.
**Expected:** Empty output. Zero backend changes.

## Session Log

- 2026-05-24: Ideation (`docs/ideation/2026-05-24-child-celebration-gamefeel-ideation.md` — generated inline, not persisted) produced 48 raw candidates across 6 frames. Selected Alpha (9 components) initially, then expanded to Gamma (added A1, A3, S4, A5).
- 2026-05-24: Brainstorm — 5 product micro-decisions resolved (streak × batch, candle timing, trail persistence, reduced-motion, iOS haptic fallback). Core requirements doc written.
- 2026-05-24: Spec extension — added visual choreography ASCII timing chart, implementation file inventory (10 new + 7 modified), 10 acceptance test scenarios.
