# Loading Animation Polar Rotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the expanding-ripple loading animation in `MusicWaveCanvas.vue` with 5–9 polar-coordinate closed curves that continuously rotate and organically deform inside a clipped circle, producing a TikTok-logo liquid-flow effect.

**Architecture:** Single file change — only the drawing logic inside `MusicWaveCanvas.vue` is replaced. The `Ripple` lifecycle system, noise functions, and `drawCore` are deleted; a static `LineParams` array initialized once at mount replaces them. All infrastructure (RAF loop, resize, theme, dismiss state machine, device detection, reduced-motion) is kept verbatim.

**Tech Stack:** Vue 3 `<script setup lang="ts">`, Canvas 2D API, `requestAnimationFrame`

---

## File Map

| Action | File |
|--------|------|
| Modify | `frontend/packages/auth/src/components/MusicWaveCanvas.vue` |
| Verify | `frontend/apps/main/src/composables/__tests__/loading.spec.ts` (run only, no edits) |

---

### Task 1: Delete dead code — Ripple system, noise functions, drawCore

**Files:**
- Modify: `frontend/packages/auth/src/components/MusicWaveCanvas.vue`

This task removes everything that will no longer exist. Do this first so the file is clean before adding the new logic.

- [ ] **Step 1: Delete the `Ripple` interface and all wave constants**

Remove these blocks entirely from the `<script setup>` section:

```ts
// DELETE: interface Ripple { ... }
// DELETE: const MAX_RIPPLES = ...
// DELETE: const WAVE_LIFETIME = ...
// DELETE: const DISMISS_DURATION = ...  ← keep this one: 300ms is still used by dismiss
// DELETE: const LAYER_CONFIGS = [...]
// DELETE: function spawnInterval(...) { ... }
```

Keep `DISMISS_DURATION = 300` — the dismiss state machine still uses it.

- [ ] **Step 2: Delete the three noise utility functions**

Remove these functions entirely:

```ts
// DELETE: function hash(n: number): number { ... }
// DELETE: function smoothNoise(t: number): number { ... }
// DELETE: function fractalNoise(t: number, octaves: number = 3): number { ... }
```

- [ ] **Step 3: Delete `drawCore`**

Remove the entire `drawCore` function (lines ~121–163 in the original).

- [ ] **Step 4: Verify the file still compiles (expected: errors from missing references)**

```bash
cd frontend/packages/auth
npx tsc --noEmit 2>&1 | head -40
```

Expected: type errors referencing `Ripple`, `drawCore`, `fractalNoise` — these confirm the old code is gone and the new code isn't wired yet. That's correct at this stage.

---

### Task 2: Add `LineParams` type and `makeLineParams` factory

**Files:**
- Modify: `frontend/packages/auth/src/components/MusicWaveCanvas.vue`

Add after the `PALETTE` block (after the `const p = computed(...)` line):

- [ ] **Step 1: Add the `LineParams` interface and constants**

```ts
// ── Polar curve parameters ────────────────────────────────────────────────────

interface LineParams {
  basePhase: number
  rotSpeed: number   // rad/s, negative = counter-clockwise
  n1: number         // primary radial harmonic count
  n2: number         // secondary radial harmonic count
  n3: number         // slow wobble harmonic count
  amp1: number       // primary amplitude (relative to R)
  amp2: number       // secondary amplitude
  amp3: number       // wobble amplitude
  drift1: number     // phase drift speed for harmonic 1
  drift2: number     // phase drift speed for harmonic 2
  drift3: number     // phase drift speed for harmonic 3
  baseR: number      // base radius scale (relative to R)
}

const LINE_COUNT_HIGH = 9
const LINE_COUNT_LOW  = 5
const STEPS_HIGH = 200
const STEPS_LOW  = 120
const DISMISS_DURATION = 300
```

- [ ] **Step 2: Add `makeLineParams` factory**

```ts
function makeLineParams(index: number, total: number): LineParams {
  const basePhase = (index / total) * Math.PI * 2
  const rotDir = (index % 2 === 0) ? 1 : -1
  const rotSpeed = (0.18 + index * 0.04) * rotDir

  return {
    basePhase,
    rotSpeed,
    n1: 2 + (index % 4),
    n2: 3 + (index % 3),
    n3: 1,
    amp1: 0.22 + (index % 3) * 0.07,
    amp2: 0.12 + (index % 2) * 0.06,
    amp3: 0.08,
    drift1: 0.29 + index * 0.05,
    drift2: 0.17 + index * 0.08,
    drift3: 0.11 + index * 0.03,
    baseR:  0.55 + (index % 5) * 0.06,
  }
}
```

- [ ] **Step 3: Verify no new type errors introduced**

```bash
cd frontend/packages/auth
npx tsc --noEmit 2>&1 | head -40
```

Expected: same errors as Task 1 (missing `drawCore` etc.) — no new errors.

---

### Task 3: Add `drawPolarCurve` function

**Files:**
- Modify: `frontend/packages/auth/src/components/MusicWaveCanvas.vue`

Add after `makeLineParams`. This replaces `drawCore` + the ripple draw block.

- [ ] **Step 1: Add `drawPolarCurve`**

```ts
// ── Draw a single polar rotating curve ───────────────────────────────────────

function drawPolarCurve(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  R: number,
  params: LineParams,
  t: number,
  alpha: number,
  lineWidth: number,
  palette: { color: string; glowColor: string; blend: GlobalCompositeOperation },
  skipGlow: boolean,
): void {
  const { rotSpeed, basePhase, n1, n2, n3, amp1, amp2, amp3, drift1, drift2, drift3, baseR } = params
  const rotation = t * rotSpeed + basePhase
  const STEPS = LOW_END ? STEPS_LOW : STEPS_HIGH

  const pts: Array<[number, number]> = []
  for (let i = 0; i <= STEPS; i++) {
    const theta = (i / STEPS) * Math.PI * 2
    const r = R * (
      baseR
      + amp1 * Math.sin(n1 * theta + t * drift1)
      + amp2 * Math.sin(n2 * theta - t * drift2 + 1.3)
      + amp3 * Math.cos(n3 * theta + t * drift3)
    )
    const angle = theta + rotation
    pts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)])
  }

  ctx.save()
  ctx.globalCompositeOperation = palette.blend
  ctx.globalAlpha = alpha

  ctx.beginPath()
  const first = pts[0]!
  ctx.moveTo(first[0], first[1])
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i]![0], pts[i]![1])
  ctx.closePath()

  if (!skipGlow) {
    ctx.shadowBlur = lineWidth * 10
    ctx.shadowColor = palette.glowColor
    ctx.strokeStyle = palette.color
    ctx.lineWidth = lineWidth * 2.0
    ctx.stroke()
  }

  ctx.shadowBlur = 0
  ctx.strokeStyle = palette.color
  ctx.lineWidth = lineWidth * 0.8
  ctx.stroke()

  ctx.restore()
}
```

- [ ] **Step 2: Verify no new type errors**

```bash
cd frontend/packages/auth
npx tsc --noEmit 2>&1 | head -40
```

Expected: errors still only from missing references to old deleted code (`Ripple`, etc.) — not from the new functions.

---

### Task 4: Replace `state` object and `makeDrawFrame` with new draw loop

**Files:**
- Modify: `frontend/packages/auth/src/components/MusicWaveCanvas.vue`

This is the core replacement. The old `state` object had `ripples`, `lastSpawn`, `nextRippleId`. The new one has `lines` (initialized once) plus the same dismiss tracking fields.

- [ ] **Step 1: Replace the `state` object declaration**

Find and replace the old `state` block:

```ts
// OLD — delete this entire block:
const state = {
  ripples: [] as Ripple[],
  nextRippleId: 0,
  lastSpawn: 0,
  globalTime: 0,
  lastFrameTime: 0,
  dismissProgress: 0,
  dismissStart: null as number | null,
}
```

Replace with:

```ts
const lineCount = LOW_END ? LINE_COUNT_LOW : LINE_COUNT_HIGH

const state = {
  lines: [] as LineParams[],
  globalTime: 0,
  lastFrameTime: 0,
  dismissProgress: 0,
  dismissStart: null as number | null,
}
```

- [ ] **Step 2: Replace `makeDrawFrame` with new `drawFrame` function**

Delete the entire `makeDrawFrame` function and the `const drawFrame = makeDrawFrame(state)` call.

Add in their place:

```ts
// ── Draw frame ────────────────────────────────────────────────────────────────

function drawFrame(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, now: number): void {
  const W = canvas.width
  const H = canvas.height
  const cx = W / 2
  const cy = H / 2
  const unit = Math.min(W, H)
  const framePalette = p.value

  const effectiveInterval = prefersReduced.value ? 100 : FRAME_INTERVAL
  if (now - state.lastFrameTime < effectiveInterval) return

  ctx.clearRect(0, 0, W, H)

  // Dismiss progress
  if (props.dismissing) {
    if (state.dismissStart === null) state.dismissStart = now
    state.dismissProgress = Math.min(1, (now - state.dismissStart) / DISMISS_DURATION)
  } else {
    state.dismissStart = null
    state.dismissProgress = 0
  }

  const deltaTime = state.lastFrameTime === 0 ? 0 : (now - state.lastFrameTime) / 1000
  state.globalTime += deltaTime
  state.lastFrameTime = now

  const t = state.globalTime

  const dismissScale = props.dismissing
    ? 1 - state.dismissProgress * 0.5 * (prefersReduced.value ? 0 : 1)
    : 1
  const dismissAlpha = props.dismissing
    ? Math.max(0, 1 - state.dismissProgress * 1.3)
    : 1

  const R = unit * 0.44
  const clipR = unit * 0.46
  const lineWidth = unit * 0.007

  // Clip all curves to circle
  ctx.save()
  ctx.beginPath()
  ctx.arc(cx, cy, clipR, 0, Math.PI * 2)
  ctx.clip()

  // Scale transform for dismiss animation
  ctx.save()
  ctx.translate(cx, cy)
  ctx.scale(dismissScale, dismissScale)
  ctx.translate(-cx, -cy)

  const skipGlow = LOW_END

  for (let i = 0; i < state.lines.length; i++) {
    const params = state.lines[i]!
    const isCyan = i % 2 === 0
    const palette = {
      color:     isCyan ? framePalette.cyan  : framePalette.red,
      glowColor: isCyan ? framePalette.cyanGlow : framePalette.redGlow,
      blend:     framePalette.blend,
    }

    const breathPhase = prefersReduced.value
      ? 0
      : t * 0.8 + (i / state.lines.length) * Math.PI * 2
    const breathAlpha = prefersReduced.value
      ? 0.6
      : 0.55 + Math.sin(breathPhase) * 0.2

    const rotSpeedFactor = prefersReduced.value ? 0.15 : 1

    drawPolarCurve(
      ctx, cx, cy, R,
      { ...params, rotSpeed: params.rotSpeed * rotSpeedFactor },
      t,
      breathAlpha * dismissAlpha,
      lineWidth,
      palette,
      skipGlow,
    )
  }

  ctx.restore()
  ctx.restore()
}
```

- [ ] **Step 3: Update `loop` to call `drawFrame` directly (not via closure)**

The `loop` function currently calls `drawFrame(canvas, ctx, now)` — this should still work since `drawFrame` is now a plain function in scope. Verify it reads:

```ts
function loop(now: number) {
  rafBox.id = requestAnimationFrame(loop)
  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  drawFrame(canvas, ctx, now)
}
```

No change needed if it already looks like this.

- [ ] **Step 4: Update `onMounted` to initialize `state.lines` instead of resetting ripple fields**

Find the `onMounted` block. Replace the state reset lines:

```ts
// OLD reset lines inside onMounted — delete these:
state.ripples = []
state.nextRippleId = 0
state.lastSpawn = 0
```

Replace with:

```ts
state.lines = Array.from({ length: lineCount }, (_, i) => makeLineParams(i, lineCount))
```

Keep the rest of `onMounted` unchanged (`state.globalTime = 0`, `state.lastFrameTime = 0`, etc.).

- [ ] **Step 5: Update `watch(() => props.dismissing, ...)` to remove ripple reset**

Find the watcher block:

```ts
watch(() => props.dismissing, (val) => {
  if (!val) {
    state.dismissProgress = 0
    state.dismissStart = null
    state.ripples = []       // ← DELETE this line
    state.lastSpawn = 0      // ← DELETE this line
  }
})
```

After edit it should be:

```ts
watch(() => props.dismissing, (val) => {
  if (!val) {
    state.dismissProgress = 0
    state.dismissStart = null
  }
})
```

---

### Task 5: Typecheck and test

**Files:**
- Run only — no edits

- [ ] **Step 1: Typecheck the auth package**

```bash
cd frontend/packages/auth
npx tsc --noEmit 2>&1
```

Expected output: no errors. If errors appear, they will name the exact line — fix them before continuing.

- [ ] **Step 2: Typecheck the main app (catches cross-package issues)**

```bash
cd frontend/apps/main
npm run typecheck 2>&1
```

Expected: no errors.

- [ ] **Step 3: Run existing loading tests**

```bash
cd frontend/apps/main
npm run test:run -- src/composables/__tests__/loading.spec.ts 2>&1
```

Expected: all tests pass. These tests cover the `useLoadingOverlay` composable state logic — they don't test canvas rendering, so they should be unaffected.

- [ ] **Step 4: Run full test suite**

```bash
cd frontend/apps/main
npm run test:run 2>&1
```

Expected: all tests pass.

---

### Task 6: Commit

**Files:**
- `frontend/packages/auth/src/components/MusicWaveCanvas.vue`

- [ ] **Step 1: Stage and commit**

```bash
cd frontend/packages/auth
git add src/components/MusicWaveCanvas.vue
git commit -m "feat(auth): replace ripple waves with polar rotation loading animation

- Remove Ripple lifecycle, fractalNoise, drawCore, spawn logic
- Add polar coordinate closed-curve model with 5-9 lines
- Adjacent lines counter-rotate for liquid convection feel
- Three radial harmonics per line drift independently for organic deformation
- Preserve: RAF loop, dismiss state machine, theme reactivity, low-end/reduced-motion degradation"
```

---

## Self-Review Checklist

- **Spec coverage:**
  - [x] Polar coordinate model (Task 2 `makeLineParams` + Task 3 `drawPolarCurve`)
  - [x] Counter-rotating adjacent lines (`rotDir = index % 2 === 0 ? 1 : -1` in Task 2)
  - [x] 5–9 lines, LOW_END fixed at 5 (Task 4 `lineCount`)
  - [x] Circle clip (`ctx.clip()` in Task 4 `drawFrame`)
  - [x] LOW_END: skip glow pass, 120 pts (Task 3 `skipGlow`, `STEPS_LOW`)
  - [x] prefers-reduced-motion: near-static rotation (Task 4 `rotSpeedFactor = 0.15`)
  - [x] Dismiss scale + alpha (Task 4 `dismissScale`, `dismissAlpha`)
  - [x] Dark/light theme palette (Task 4 uses existing `p.value`)
  - [x] All non-drawing infrastructure preserved (Tasks 1–4 leave RAF, resize, etc. untouched)

- **Type consistency:**
  - `LineParams` defined in Task 2, used in Task 3 (`params: LineParams`) and Task 4 (`state.lines: LineParams[]`) — consistent
  - `drawPolarCurve` palette arg type matches what Task 4 constructs — consistent
  - `DISMISS_DURATION` defined in Task 2, used in Task 4 — consistent
  - `LOW_END`, `DPR`, `TARGET_FPS`, `FRAME_INTERVAL`, `p`, `prefersReduced`, `props` — all preserved from original, no renames

- **No placeholders:** All steps contain complete code. No TBD.
