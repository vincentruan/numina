# TikTok-style Loading Effect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the loading overlay's visual layer to TikTok 2-color palette with center core, theme-aware blend modes, reduced-motion support, and 300ms exit.

**Architecture:** In-place refactor of 3 existing files in `frontend/packages/auth/`. Canvas keeps its RAF loop and fractal-noise math; we add a `drawCore()` layer, swap palette to 2-color with per-stroke `globalCompositeOperation`, and add theme/motion-pref detection. GlassMask goes CSS-only for theme. LoadingOverlay gets ARIA + exit timing tweaks.

**Tech Stack:** Vue 3 + TypeScript, Canvas 2D API, CSS `[data-theme]` selectors, `matchMedia` / `MutationObserver`

---

## File Structure

```
frontend/packages/auth/src/components/
├── LoadingOverlay.vue    ← ARIA role, exit timing, screen-reader exit announcement
├── GlassMask.vue         ← CSS-only theme switching (drop MutationObserver)
└── MusicWaveCanvas.vue   ← Core: palette, drawCore, theme/motion detection, vmin sizing, exit timing
```

No new files. No new dependencies.

---

### Task 1: GlassMask — CSS-only theme switching

**Files:**
- Modify: `frontend/packages/auth/src/components/GlassMask.vue`

This is the simplest change and stands alone — pure CSS, no JS state interaction.

- [ ] **Step 1: Replace GlassMask.vue with theme-aware CSS**

Replace the entire file content:

```vue
<template>
  <div class="glass-mask" :class="{ 'no-backdrop': !supportsBackdrop }" />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const supportsBackdrop = ref(true)

onMounted(() => {
  supportsBackdrop.value = CSS.supports('backdrop-filter', 'blur(1px)') ||
    CSS.supports('-webkit-backdrop-filter', 'blur(1px)')
})
</script>

<style scoped>
.glass-mask {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.90);
  backdrop-filter: blur(12px) saturate(1.2);
  -webkit-backdrop-filter: blur(12px) saturate(1.2);
}

.glass-mask.no-backdrop {
  background: rgba(245, 245, 255, 0.88);
}

[data-theme='dark'] .glass-mask {
  background: rgba(1, 1, 32, 0.52);
  backdrop-filter: blur(12px) saturate(1.4);
  -webkit-backdrop-filter: blur(12px) saturate(1.4);
}

[data-theme='dark'] .glass-mask.no-backdrop {
  background: rgba(1, 1, 32, 0.82);
}
</style>
```

Key changes: default (light) is now white-tinted at 0.90 opacity; `[data-theme='dark']` selector preserves the existing dark look. The `supportsBackdrop` check stays unchanged.

- [ ] **Step 2: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina_worktrees/ai-native-agent/frontend/packages/auth && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/auth/src/components/GlassMask.vue
git commit -m "feat(GlassMask): add light-mode backdrop via CSS data-theme selectors"
```

---

### Task 2: LoadingOverlay — ARIA role + exit timing

**Files:**
- Modify: `frontend/packages/auth/src/components/LoadingOverlay.vue`

- [ ] **Step 1: Add `role="status"` to the overlay div**

In `LoadingOverlay.vue`, change the overlay `<div>` (lines 3–9) to add `role="status"`:

```vue
    <div
      v-if="isLoading"
      class="loading-overlay"
      :class="{ 'is-dismissing': isDismissing }"
      role="status"
      aria-live="polite"
      aria-label="加载中"
    >
```

`role="status"` provides a semantic landmark for screen readers. It implies `aria-live="polite"`, so we keep the explicit attribute for legacy AT compatibility.

- [ ] **Step 2: Change exit transition to 300ms with no delay**

Replace the CSS transition:

```css
.overlay-leave-active {
  transition: opacity 0.3s ease 0s;
}
```

This changes BOTH the duration (0.35s → 0.3s) AND removes the delay (0.45s → 0s). The old delay existed to let the 400ms wave animation play first; with the new 300ms exit choreography driven by Canvas, the delay is no longer needed.

- [ ] **Step 3: Add screen-reader exit announcement**

Add a visually-hidden span for the exit announcement. The full template becomes:

```vue
<template>
  <span class="sr-only" aria-live="polite">{{ exitMessage }}</span>
  <Transition name="overlay" @after-leave="onAfterLeave">
    <div
      v-if="isLoading"
      class="loading-overlay"
      :class="{ 'is-dismissing': isDismissing }"
      role="status"
      aria-live="polite"
      aria-label="加载中"
    >
      <GlassMask />
      <MusicWaveCanvas :dismissing="isDismissing" />
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useLoadingOverlay } from '../composables/loading'
import GlassMask from './GlassMask.vue'
import MusicWaveCanvas from './MusicWaveCanvas.vue'

const { isLoading, isDismissing } = useLoadingOverlay()

const exitMessage = ref('')

function onAfterLeave() {
  exitMessage.value = '加载完成'
  setTimeout(() => { exitMessage.value = '' }, 1000)
}
</script>
```

Note: the `加载完成` string is inside the `@numina/auth` package, which is a shared component. Since the consuming apps already use `加载中` hardcoded in the same component, this follows the existing pattern. A future i18n refactor can extract both strings.

- [ ] **Step 4: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina_worktrees/ai-native-agent/frontend/packages/auth && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/auth/src/components/LoadingOverlay.vue
git commit -m "feat(LoadingOverlay): add role=status, 300ms exit, screen-reader completion announcement"
```

---

### Task 3: MusicWaveCanvas — theme and reduced-motion detection

**Files:**
- Modify: `frontend/packages/auth/src/components/MusicWaveCanvas.vue`

This task adds the reactive refs for theme and motion preference. No drawing changes yet — just the detection wiring.

- [ ] **Step 1: Add imports and detection refs**

Replace the import line (line 6):

```ts
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
```

Add theme detection after the `FRAME_INTERVAL` constant (after line 24):

```ts
// ── Theme detection ─────────────────────────────────────────────────────────────

const isDark = ref(document.documentElement.dataset.theme === 'dark')
const themeObserver = new MutationObserver(() => {
  isDark.value = document.documentElement.dataset.theme === 'dark'
})

// ── Reduced-motion detection ───────────────────────────────────────────────────

const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
const prefersReduced = ref(reduceQuery.matches)
const onMotionChange = (e: MediaQueryListEvent) => { prefersReduced.value = e.matches }
```

- [ ] **Step 2: Add PALETTE and blend computed**

Add after the reduced-motion detection:

```ts
// ── TikTok 2-color palette ────────────────────────────────────────────────────

const PALETTE = {
  dark: {
    cyan: '#00f2fe', cyanGlow: 'rgba(0,242,254,0.55)',
    red:  '#fe0979', redGlow:  'rgba(254,9,121,0.55)',
    blend: 'screen' as GlobalCompositeOperation,
  },
  light: {
    cyan: '#00b8c8', cyanGlow: 'rgba(0,184,200,0.30)',
    red:  '#d61b6e', redGlow:  'rgba(214,27,110,0.30)',
    blend: 'multiply' as GlobalCompositeOperation,
  },
} as const

const p = computed(() => isDark.value ? PALETTE.dark : PALETTE.light)
```

- [ ] **Step 3: Wire observers into lifecycle**

In the `onMounted` callback (after `rafBox.id = requestAnimationFrame(loop)`), add:

```ts
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
  reduceQuery.addEventListener('change', onMotionChange)
```

In the `onUnmounted` callback, add:

```ts
  themeObserver.disconnect()
  reduceQuery.removeEventListener('change', onMotionChange)
```

- [ ] **Step 4: Delete the old `NEON_COLORS` constant**

Remove lines 45–51 (the 4-color `NEON_COLORS` array). It's replaced by `PALETTE`.

- [ ] **Step 5: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina_worktrees/ai-native-agent/frontend/packages/auth && npx tsc --noEmit`
Expected: PASS (unused-variable warnings for `p` are fine — we'll use it in Task 4)

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/auth/src/components/MusicWaveCanvas.vue
git commit -m "feat(MusicWaveCanvas): add theme observer, reduced-motion detection, TikTok 2-color palette"
```

---

### Task 4: MusicWaveCanvas — core animation, palette swap, vmin sizing, blend mode, exit timing

**Files:**
- Modify: `frontend/packages/auth/src/components/MusicWaveCanvas.vue`

This is the bulk task. It replaces the ripple configuration, adds `drawCore()`, swaps palette usage, adds per-stroke blend mode, converts to vmin sizing, and changes exit timing.

- [ ] **Step 1: Replace configuration constants**

Replace lines 41–65 (from `// Configuration` through the `spawnInterval` function) with:

```ts
// ── Configuration ──────────────────────────────────────────────────────────────

const MAX_RIPPLES = LOW_END ? 4 : 6
const WAVE_LIFETIME = 2800  // ms for a wave to fully expand and fade
const DISMISS_DURATION = 300  // ms for the choreographed exit

const LAYER_CONFIGS = [
  { amplitude: 5, frequency: 6,  speed: 14, lineWidth: 0.8 },
  { amplitude: 4, frequency: 8,  speed: 18, lineWidth: 0.6 },
  { amplitude: 3, frequency: 10, speed: 22, lineWidth: 0.45 },
  { amplitude: 2, frequency: 13, speed: 28, lineWidth: 0.3 },
]

// Breathing rhythm: spawn interval pulses between fast and slow
function spawnInterval(globalTime: number): number {
  const base = LOW_END ? 420 : 320
  const pulse = Math.sin(globalTime * 0.8) * (LOW_END ? 60 : 100)
  return base + pulse
}
```

- [ ] **Step 2: Add `drawCore` function**

Add after the `fractalNoise` function (after line 92), before `// ── Animation state`:

```ts
// ── Core animation ─────────────────────────────────────────────────────────────

function drawCore(
  ctx: CanvasRenderingContext2D,
  cx: number, cy: number,
  unit: number,
  globalTime: number,
  pulseFreq: number,
  pulseAmp: number,
  cycleHue: boolean,
  dismissScale: number,
  dismissAlpha: number,
) {
  const pulse = Math.sin(globalTime * pulseFreq) * pulseAmp
  const scale = (1 + pulse) * dismissScale
  const alpha = (0.85 + Math.sin(globalTime * pulseFreq) * 0.15) * dismissAlpha

  const outerR = 6 * unit * scale
  const innerR = 1.5 * unit * scale
  const ringR = 4 * unit * scale

  ctx.save()
  ctx.globalAlpha = alpha
  ctx.globalCompositeOperation = 'source-over'

  // Halo gradient disc
  const palette = p.value
  const grad = ctx.createRadialGradient(cx, cy, innerR, cx, cy, outerR)
  grad.addColorStop(0, palette.cyan)
  grad.addColorStop(0.4, palette.red)
  grad.addColorStop(1, 'transparent')
  ctx.fillStyle = grad
  ctx.beginPath()
  ctx.arc(cx, cy, outerR, 0, Math.PI * 2)
  ctx.fill()

  // Inner ring
  ctx.globalAlpha = alpha * 0.6
  ctx.strokeStyle = palette.cyan
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.arc(cx, cy, ringR, 0, Math.PI * 2)
  ctx.stroke()

  ctx.restore()
}
```

- [ ] **Step 3: Rewrite `makeDrawFrame` to use unit-based sizing, palette, and blend mode**

Replace the entire `makeDrawFrame` function (lines 101–241) with:

```ts
function makeDrawFrame(
  state: {
    ripples: Ripple[]
    nextRippleId: number
    lastSpawn: number
    globalTime: number
    lastFrameTime: number
    dismissProgress: number
    dismissStart: number | null
  }
) {
  return function drawFrame(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, now: number) {
    const W = canvas.width
    const H = canvas.height
    const cx = W / 2
    const cy = H / 2

    // vmin-derived unit — W/H are already physical pixels
    const unit = Math.min(W, H) / 100

    ctx.clearRect(0, 0, W, H)

    // Effective FPS for reduced-motion
    const effectiveInterval = prefersReduced.value ? 100 : FRAME_INTERVAL
    if (now - state.lastFrameTime < effectiveInterval) return

    // Update dismiss progress (300ms)
    if (props.dismissing) {
      if (state.dismissStart === null) state.dismissStart = now
      state.dismissProgress = Math.min(1, (now - state.dismissStart) / DISMISS_DURATION)
    } else {
      state.dismissStart = null
      state.dismissProgress = 0
    }

    const deltaTime = (now - state.lastFrameTime) / 1000
    state.globalTime += deltaTime

    // Dismiss animation values
    const dismissScale = props.dismissing
      ? 1 - state.dismissProgress * 0.6 * (prefersReduced.value ? 0 : 1)
      : 1
    const dismissAlpha = props.dismissing
      ? Math.max(0, 1 - state.dismissProgress * (prefersReduced.value ? 1 : 1.2))
      : 1

    // ── Draw core ─────────────────────────────────────────────────────────────
    if (prefersReduced.value) {
      drawCore(ctx, cx, cy, unit, state.globalTime, 6.28, 0.03, false, dismissScale, dismissAlpha)
    } else {
      drawCore(ctx, cx, cy, unit, state.globalTime, 10, 0.04, true, dismissScale, dismissAlpha)
    }

    // ── Reduced-motion: skip ripples ──────────────────────────────────────────
    if (prefersReduced.value) {
      // Clean up expired ripples (from before motion pref changed)
      state.ripples = state.ripples.filter(r => {
        const lifeProgress = (now - r.birth) / 1000 / (WAVE_LIFETIME / 1000)
        return lifeProgress < 1 && !(props.dismissing && state.dismissProgress > 0.8)
      })
      return
    }

    // ── Spawn new ripples ─────────────────────────────────────────────────────
    if (!props.dismissing && now - state.lastSpawn > spawnInterval(state.globalTime)) {
      const configIdx = state.nextRippleId % LAYER_CONFIGS.length
      const config = LAYER_CONFIGS[configIdx]
      const isCyan = state.nextRippleId % 2 === 0
      const palette = p.value
      const color = isCyan ? palette.cyan : palette.red
      const glowColor = isCyan ? palette.cyanGlow : palette.redGlow
      state.ripples.push({
        id: state.nextRippleId++,
        birth: now,
        baseRadius: 8 * unit,
        amplitude: config.amplitude * unit,
        frequency: config.frequency,
        speed: config.speed * unit,
        color,
        glowColor,
        lineWidth: config.lineWidth * unit,
        noiseSeed: Math.random() * 1000,
      })
      state.lastSpawn = now

      if (state.ripples.length > MAX_RIPPLES) {
        state.ripples.shift()
      }
    }

    // ── Draw each ripple ──────────────────────────────────────────────────────
    const POINTS = LOW_END ? 60 : 90
    const blendMode = p.value.blend

    state.ripples.forEach((ripple) => {
      const age = (now - ripple.birth) / 1000
      const lifeProgress = age / (WAVE_LIFETIME / 1000)

      if (lifeProgress >= 1 || (props.dismissing && state.dismissProgress > 0.8)) {
        return
      }

      const currentRadius = ripple.baseRadius + ripple.speed * age

      let lifeAlpha: number
      if (lifeProgress < 0.15) {
        lifeAlpha = lifeProgress / 0.15
      } else if (lifeProgress > 0.6) {
        lifeAlpha = 1 - (lifeProgress - 0.6) / 0.4
      } else {
        lifeAlpha = 1
      }

      const dismissAlpha = props.dismissing ? Math.max(0, 1 - state.dismissProgress * 1.5) : 1
      const alpha = lifeAlpha * dismissAlpha * 0.9

      const expansionDecay = Math.max(0.3, 1 - lifeProgress * 0.7)
      const currentAmp = ripple.amplitude * expansionDecay * (props.dismissing ? (1 - state.dismissProgress) : 1)

      const noiseTime = state.globalTime * 1.5 + ripple.noiseSeed
      const radiusNoise = fractalNoise(noiseTime * 0.7, 3) * 8 * unit * (1 - lifeProgress * 0.5)
      const angleNoise = fractalNoise(noiseTime * 0.5 + 100, 3) * 0.3

      const currentLineWidth = ripple.lineWidth * Math.max(0.3, 1 - lifeProgress * 0.65)

      const pts: Array<[number, number]> = []
      for (let i = 0; i <= POINTS; i++) {
        const angle = (i / POINTS) * Math.PI * 2 + angleNoise
        const wavePhase = age * 3 + ripple.noiseSeed * 0.1
        const waveNoise = fractalNoise(angle * ripple.frequency / (2 * Math.PI) + wavePhase, 2)
        const waveOffset = currentAmp * Math.sin(angle * ripple.frequency + wavePhase) * (0.5 + waveNoise * 0.5)
        const r = currentRadius + radiusNoise + waveOffset
        pts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)])
      }

      function tracePath() {
        ctx.beginPath()
        ctx.moveTo(pts[0][0], pts[0][1])
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1])
        ctx.closePath()
      }

      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(W, H) * 0.5)
      grad.addColorStop(0, ripple.color)
      grad.addColorStop(0.65, ripple.color)
      const glowStop = ripple.glowColor.replace(/[\d.]+\)$/, '0.0)')
      grad.addColorStop(1, glowStop)

      // Outer glow pass (high-end only)
      if (!LOW_END) {
        ctx.save()
        ctx.globalCompositeOperation = blendMode
        ctx.globalAlpha = alpha * 0.45
        ctx.shadowBlur = 18 * DPR
        ctx.shadowColor = ripple.glowColor
        ctx.strokeStyle = grad
        ctx.lineWidth = currentLineWidth * 2.5
        tracePath()
        ctx.stroke()
        ctx.restore()
      }

      // Main stroke
      ctx.save()
      ctx.globalCompositeOperation = blendMode
      ctx.globalAlpha = alpha
      ctx.shadowBlur = LOW_END ? 0 : 8 * DPR
      ctx.shadowColor = ripple.glowColor
      ctx.strokeStyle = grad
      ctx.lineWidth = currentLineWidth
      tracePath()
      ctx.stroke()
      ctx.restore()
    })

    // Clean up expired ripples
    state.ripples = state.ripples.filter(r => {
      const lifeProgress = (now - r.birth) / 1000 / (WAVE_LIFETIME / 1000)
      return lifeProgress < 1 && !(props.dismissing && state.dismissProgress > 0.8)
    })
  }
}
```

Key differences from the original:
1. `unit` computed from `Math.min(W, H) / 100` (no `* DPR`)
2. `drawCore()` called before ripples
3. Palette colors from `p.value` (2-color alternating by `nextRippleId % 2`)
4. `ctx.globalCompositeOperation = blendMode` per stroke group
5. `prefersReduced` gates ripple spawn and drops effective FPS to 10
6. `DISMISS_DURATION = 300` instead of hardcoded 400
7. Reduced-motion dismiss: no scale shrink (alpha-only fade)
8. Glow stop uses regex replace for `0.0)` instead of hardcoded `0.6)` → `0.0)`

- [ ] **Step 4: Update `Ripple` interface**

The `Ripple` interface (lines 28–39) stays the same — no field changes needed.

- [ ] **Step 5: Update `loop` function to use `drawFrame` directly**

The existing `loop` function (lines 274–283) had its own FPS throttle inside. Now `drawFrame` handles that. Replace `loop`:

```ts
function loop(now: number) {
  rafBox.id = requestAnimationFrame(loop)
  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  drawFrame(canvas, ctx, now)
  state.lastFrameTime = now
}
```

Wait — the FPS throttle is now inside `drawFrame` via `effectiveInterval`. But `state.lastFrameTime` must be updated only when we actually draw. Let me keep `lastFrameTime` update inside `drawFrame` instead. Update the loop:

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

And the `lastFrameTime` update moves into `drawFrame` — add after the `effectiveInterval` check:

```ts
    if (now - state.lastFrameTime < effectiveInterval) return
    state.lastFrameTime = now
```

- [ ] **Step 6: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina_worktrees/ai-native-agent/frontend/packages/auth && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/packages/auth/src/components/MusicWaveCanvas.vue
git commit -m "feat(MusicWaveCanvas): TikTok 2-color palette, drawCore, vmin sizing, blend mode, 300ms exit, reduced-motion"
```

---

### Task 5: Quality gates — typecheck, lint, existing tests

**Files:**
- No modifications — verification only.

- [ ] **Step 1: Run typecheck for both apps**

Run:
```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/ai-native-agent/frontend/apps/main && npm run typecheck
cd /Users/vincentruan/geek_space/github/numina_worktrees/ai-native-agent/frontend/apps/child && npm run typecheck
```
Expected: Both PASS

- [ ] **Step 2: Run lint**

Run:
```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/ai-native-agent/frontend && npm run lint
```
Expected: PASS (fix any lint errors if they appear)

- [ ] **Step 3: Run existing state-machine tests**

Run:
```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/ai-native-agent/frontend/apps/main && npm run test:run
```
Expected: All existing tests pass (none depend on visual layer or exit duration)

---

### Task 6: Visual verification — manual

**Files:**
- No modifications — manual check only.

This task cannot be automated in CI. It requires a running dev server and browser DevTools.

- [ ] **Step 1: Start dev server and verify dark mode**

1. `cd frontend/apps/main && npm run dev`
2. Open http://localhost:5173 in browser
3. Navigate between pages — verify:
   - Center core appears with ≈1.6Hz pulse
   - Ripples emit outward in cyan and red alternating
   - `screen` blend produces luminous purple-white crossings
   - Exit animation collapses in ~300ms (no pop)

- [ ] **Step 2: Switch to light mode and verify**

1. Toggle to light theme in Settings
2. Navigate between pages — verify:
   - GlassMask shows white-tinted backdrop (not dark)
   - Ripples use desaturated `#00b8c8` / `#d61b6e` palette
   - `multiply` blend produces deep teal-and-burgundy crossings (not mud)
   - Glow is less intense (0.30 alpha vs 0.55)

- [ ] **Step 3: Verify reduced-motion**

1. Open DevTools → Rendering → check "Emulate CSS media feature prefers-reduced-motion: reduce"
2. Navigate — verify:
   - No ripples at all
   - Core shows slow breathing pulse (~1Hz)
   - Exit is alpha-only fade (no scale shrink)

- [ ] **Step 4: Verify phone viewport**

1. DevTools → toggle device toolbar → iPhone SE (375px)
2. Verify sizes look proportional (not tiny, not huge)
3. Throttle CPU 4× — verify no obvious frame drops

---

## Self-Review

**1. Spec coverage:**

| Spec requirement | Task |
|---|---|
| Center abstract concentric core with ≈1.6Hz subwoofer pulse | Task 4 (drawCore) |
| TikTok 2-color palette, alternating per ripple ID | Task 3 (PALETTE) + Task 4 (spawn logic) |
| Per-stroke `globalCompositeOperation` screen/multiply | Task 4 (blendMode per stroke) |
| Light-mode palette desaturated | Task 3 (PALETTE.light) |
| `prefers-reduced-motion` branch | Task 3 (detection) + Task 4 (branch logic) |
| 300ms exit | Task 2 (CSS) + Task 4 (DISMISS_DURATION) |
| All sizing in vmin units | Task 4 (unit computation) |
| GlassMask theme-aware | Task 1 (CSS selectors) |
| ARIA `role="status"` | Task 2 |
| Screen-reader exit announcement | Task 2 |
| Reduced-motion exit: alpha-only fade, no scale | Task 4 |
| Canvas clear + blend reset contract | Task 4 (clearRect + source-over resets) |
| Light-mode GlassMask at 0.90 opacity | Task 1 |
| Quality gates (typecheck, lint, test) for both apps | Task 5 |

**2. Placeholder scan:** No TBD, TODO, or "implement later" found. All steps contain actual code.

**3. Type consistency:** `p` computed returns `PALETTE.dark | PALETTE.light`; `drawCore` uses `p.value` to read colors; `Ripple` interface unchanged; `blendMode` typed as `GlobalCompositeOperation`. All consistent.
