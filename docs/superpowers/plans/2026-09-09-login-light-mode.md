# Login Page Light Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add light/day mode support to the login page — single-page dynamic switching driven by `data-theme`, with rainbow particles, gradient pixel-grid animals, and glass-morphism form adaptations on white background.

**Architecture:** The existing `useDeerField` composable gains an `isDark` reactive parameter that controls particle sprite colors (rainbow vs white-temperature) and pixel grid color (lavender vs blue-purple-pink gradient). CSS theme switching is achieved via `data-theme` attribute on `<html>` (already set by `App.vue`) — new `.theme-light` overrides in both `LoginPage.vue` scoped styles and `auth-page.css` handle the glass-morphism form, text, and button colors. No new pages, no routing changes.

**Tech Stack:** Vue 3 Composition API, Canvas 2D, CSS custom properties + `data-theme` selector, Vant 4

**Spec:** Brainstorming session 2026-09-09 — approved design: single-page dynamic switch, rainbow particles (per-particle consistent hue), soft blue-purple-pink pixel grid on white, glass-morphism with lavender-tinted borders on white.

## Global Constraints

- `<script setup lang="ts">` only — no Options API
- No `any` / `@ts-ignore`
- i18n required for all user-facing strings (no new user-facing strings in this task — purely visual)
- CSS: scoped styles + `data-theme` selector, no Tailwind
- Dark mode must remain 100% unchanged — zero regression
- Register/JoinFamily pages share `auth-page.css` — their light mode is a bonus side-effect
- `prefers-reduced-motion` must still disable canvas animations

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/apps/main/src/composables/useDeerField.ts` | Modify | Accept `isDark` parameter; rainbow sprites for light mode; gradient pixel grid for light mode |
| `frontend/apps/main/src/pages/LoginPage.vue` | Modify | Detect theme, pass `isDark` to `useDeerField`; add `.theme-light` scoped style overrides for all hardcoded dark colors |
| `frontend/apps/main/src/styles/auth-page.css` | Modify | Add `.theme-light` overrides for shared auth form styles (Register + JoinFamily benefit) |
| `frontend/apps/main/src/components/common/NuminaLogo.vue` | Modify | Accept `theme` prop; switch gradient colors for light mode visibility |

---

### Task 1: Add `isDark` parameter to `useDeerField`

**Files:**
- Modify: `frontend/apps/main/src/composables/useDeerField.ts`

**Interfaces:**
- Consumes: canvas refs from caller
- Produces: `useDeerField(bgCanvasRef, deerCanvasRef, isDark)` — third parameter is optional `Ref<boolean>`, defaults to `true` (dark). When `isDark` changes, sprites rebuild and grid color updates on next frame.

- [ ] **Step 1: Add `RAINBOW_COLORS` constant and light-mode grid color**

After the existing `STELLAR_COLORS` array (line 61), add:

```typescript
// Rainbow palette for light mode — each entry is a distinct hue
// Core and halo use same hue at different lightness (no cross-hue discontinuity)
const RAINBOW_COLORS: Array<{ core: [number, number, number]; halo: [number, number, number] }> = [
  { core: [255, 107, 107], halo: [255, 160, 140] },  // red
  { core: [255, 159, 67],  halo: [255, 190, 120] },  // orange
  { core: [254, 202, 87],  halo: [254, 220, 140] },  // yellow
  { core: [72, 219, 251],  halo: [130, 230, 255] },  // cyan
  { core: [10, 189, 227],  halo: [80, 210, 240] },   // blue
  { core: [95, 39, 205],   halo: [140, 100, 230] },  // indigo
  { core: [162, 155, 254], halo: [195, 190, 255] },  // purple
]
```

- [ ] **Step 2: Add light-mode pixel grid color helper**

After `RAINBOW_COLORS`, add:

```typescript
// Light-mode pixel grid: soft blue-purple-pink gradient
// Each cell gets a random color interpolated between two endpoints
const GRID_LIGHT_START = { r: 120, g: 100, b: 220 }  // blue-purple
const GRID_LIGHT_END = { r: 200, g: 140, b: 200 }     // pink

function getLightGridColor(): string {
  const t = Math.random()
  const r = Math.round(GRID_LIGHT_START.r + (GRID_LIGHT_END.r - GRID_LIGHT_START.r) * t)
  const g = Math.round(GRID_LIGHT_START.g + (GRID_LIGHT_END.g - GRID_LIGHT_START.g) * t)
  const b = Math.round(GRID_LIGHT_START.b + (GRID_LIGHT_END.b - GRID_LIGHT_START.b) * t)
  return `${r},${g},${b}`
}
```

- [ ] **Step 3: Add `generateRainbowSprite` function**

After `generateStarSprite` (around line 243), add a new function that generates a sprite using a single rainbow hue consistently:

```typescript
function generateRainbowSprite(
  colorIndex: number,
  intensityIndex: number,
  dpr: number = SPRITE_DPR_MAX
): HTMLCanvasElement {
  const sprite = document.createElement('canvas')
  const size = SPRITE_SIZE * dpr
  sprite.width = size
  sprite.height = size
  const ctx = sprite.getContext('2d')!
  const cx = size / 2
  const cy = size / 2

  const colorSpec = RAINBOW_COLORS[colorIndex]
  const [coreR, coreG, coreB] = colorSpec.core
  const [haloR, haloG, haloB] = colorSpec.halo

  const intensityMult = intensityIndex === 2 ? 1.4 : intensityIndex === 1 ? 1.0 : 0.7
  const rayCount = Math.floor((8 + Math.random() * 6) * intensityMult)
  const baseHaloRadius = (size / 2 - 4) * intensityMult

  // 1. Circular glow underlayer — same hue, softer
  const glowRadius = baseHaloRadius * 0.9
  const glowGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowRadius)
  glowGrad.addColorStop(0, `rgba(${haloR},${haloG},${haloB},0.30)`)
  glowGrad.addColorStop(0.5, `rgba(${haloR},${haloG},${haloB},0.06)`)
  glowGrad.addColorStop(1, `rgba(${haloR},${haloG},${haloB},0)`)
  ctx.beginPath()
  ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2)
  ctx.fillStyle = glowGrad
  ctx.fill()

  // 2. Irregular radiating rays — same hue
  ctx.save()
  ctx.translate(cx, cy)

  for (let i = 0; i < rayCount; i++) {
    const angle = (i / rayCount) * Math.PI * 2 + Math.random() * 0.3
    const rayLength = baseHaloRadius * (0.6 + Math.random() * 0.8)
    const rayWidth = (2 + Math.random() * 4) * dpr
    const rayOpacity = 0.10 + Math.random() * 0.12

    const endX = Math.cos(angle) * rayLength
    const endY = Math.sin(angle) * rayLength
    const rayGrad = ctx.createLinearGradient(0, 0, endX, endY)
    rayGrad.addColorStop(0, `rgba(${haloR},${haloG},${haloB},0.20)`)
    rayGrad.addColorStop(0.4, `rgba(${haloR},${haloG},${haloB},${rayOpacity.toFixed(3)})`)
    rayGrad.addColorStop(0.8, `rgba(${haloR},${haloG},${haloB},0.02)`)
    rayGrad.addColorStop(1, `rgba(${haloR},${haloG},${haloB},0)`)

    ctx.beginPath()
    ctx.moveTo(0, 0)
    ctx.lineTo(endX, endY)
    ctx.strokeStyle = rayGrad
    ctx.lineWidth = rayWidth
    ctx.lineCap = 'round'
    ctx.stroke()
  }

  ctx.restore()

  // 3. Bright core — same hue, white center blending to hue
  const coreRadius = 4 * dpr
  const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreRadius)
  coreGrad.addColorStop(0, `rgba(255,255,255,0.95)`)
  coreGrad.addColorStop(0.35, `rgba(${coreR},${coreG},${coreB},0.85)`)
  coreGrad.addColorStop(0.7, `rgba(${coreR},${coreG},${coreB},0.5)`)
  coreGrad.addColorStop(1, `rgba(${coreR},${coreG},${coreB},0)`)
  ctx.beginPath()
  ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2)
  ctx.fillStyle = coreGrad
  ctx.fill()

  return sprite
}
```

- [ ] **Step 4: Modify `buildSprites` to accept `isDark`**

Replace the existing `buildSprites` function with:

```typescript
function buildSprites(dpr: number = SPRITE_DPR_MAX, isDark: boolean = true): StarSprite[] {
  const sprites: StarSprite[] = []

  if (isDark) {
    // Dark mode: original white-temperature stellar colors
    for (let tempIdx = 0; tempIdx < STELLAR_COLORS.length; tempIdx++) {
      for (let intIdx = 0; intIdx < INTENSITY_LEVELS.length; intIdx++) {
        sprites.push({
          canvas: generateStarSprite(tempIdx, intIdx, dpr),
          colorTempIndex: tempIdx,
          intensityIndex: intIdx,
        })
      }
    }
  } else {
    // Light mode: rainbow colors — each hue × each intensity
    for (let colorIdx = 0; colorIdx < RAINBOW_COLORS.length; colorIdx++) {
      for (let intIdx = 0; intIdx < INTENSITY_LEVELS.length; intIdx++) {
        sprites.push({
          canvas: generateRainbowSprite(colorIdx, intIdx, dpr),
          colorTempIndex: colorIdx,
          intensityIndex: intIdx,
        })
      }
    }
  }

  return sprites
}
```

- [ ] **Step 5: Update `assignColorTemp` to use the correct color count**

The `assignColorTemp` function references `STELLAR_COLORS.length`. It needs to work for both modes. Add a parameter:

```typescript
function assignColorTemp(colorCount: number): number {
  const r = Math.random()
  // Uniform distribution for rainbow; weighted for stellar
  return Math.floor(r * colorCount)
}
```

Then update `buildParticles` to accept `isDark`:

```typescript
function buildParticles(w: number, h: number, isDark: boolean = true): Particle[] {
  const particles: Particle[] = []
  const count = computeParticleCount(w, h)
  const colorCount = isDark ? STELLAR_COLORS.length : RAINBOW_COLORS.length

  for (let i = 0; i < count; i++) {
    const depth = assignDepthLayer()
    const params = getDepthParams(depth)
    const colorTempIdx = assignColorTemp(colorCount)
    const intensityIdx = Math.floor(Math.random() * INTENSITY_LEVELS.length)

    const baseRadius = rand(params.radiusMin, params.radiusMax)
    // Light mode: reduce base opacity so particles don't overwhelm white bg
    const opacityScale = isDark ? 1.0 : 0.6
    const baseOpacity = rand(params.opacityMin, params.opacityMax) * opacityScale
    const driftSpeed = rand(params.speedMin, params.speedMax)

    const p: Particle = {
      x: Math.random() * w,
      y: Math.random() * h,
      depth,
      baseRadius,
      baseOpacity,
      driftSpeed,
      spriteIndex: colorTempIdx * INTENSITY_LEVELS.length + intensityIdx,
      breathPhase: Math.random(),
      breathSpeed: rand(BREATH_SPEED_MIN, BREATH_SPEED_MAX),
      breathSizeAmp: rand(BREATH_SIZE_AMP_MIN, BREATH_SIZE_AMP_MAX),
      breathOpacityAmp: rand(BREATH_OPACITY_AMP_MIN, BREATH_OPACITY_AMP_MAX),
      vx: 0,
      vy: 0,
      noiseOffsetX: 0,
      noiseOffsetY: 0,
      currentRadius: baseRadius,
      currentOpacity: baseOpacity,
    }

    initParticleFlow(p, w, h)
    particles.push(p)
  }

  return particles
}
```

- [ ] **Step 6: Update `drawGrid` to accept light-mode color**

Replace `drawGrid` with a version that accepts an `isDark` flag:

```typescript
function drawGrid(ctx: CanvasRenderingContext2D, grid: Grid, isDark: boolean = true) {
  const { cols, rows, alphas, dpr } = grid
  const step = (CELL_SIZE + CELL_GAP) * dpr
  const size = CELL_SIZE * dpr

  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  // Pre-generate light-mode colors per cell (stored once, reused per frame)
  // For performance, generate a color lookup on first light-mode draw
  if (!isDark) {
    for (let c = 0; c < cols; c++) {
      for (let r = 0; r < rows; r++) {
        const a = alphas[c * rows + r]
        if (a < 0.01) continue
        // Each cell gets a stable color from its index (deterministic, no per-frame random)
        const cellT = ((c * 7 + r * 13) % 100) / 100
        const cr = Math.round(GRID_LIGHT_START.r + (GRID_LIGHT_END.r - GRID_LIGHT_START.r) * cellT)
        const cg = Math.round(GRID_LIGHT_START.g + (GRID_LIGHT_END.g - GRID_LIGHT_START.g) * cellT)
        const cb = Math.round(GRID_LIGHT_START.b + (GRID_LIGHT_END.b - GRID_LIGHT_START.b) * cellT)
        // Light mode: increase max alpha slightly for visibility on white
        const scaledA = Math.min(a * 1.3, 0.55)
        ctx.fillStyle = `rgba(${cr},${cg},${cb},${scaledA})`
        ctx.fillRect(c * step, r * step, size, size)
      }
    }
  } else {
    for (let c = 0; c < cols; c++) {
      for (let r = 0; r < rows; r++) {
        const a = alphas[c * rows + r]
        if (a < 0.01) continue
        ctx.fillStyle = `rgba(189,187,255,${a})`
        ctx.fillRect(c * step, r * step, size, size)
      }
    }
  }
}
```

- [ ] **Step 7: Update the `useDeerField` composable signature and internals**

Add `isDark` parameter as a `Ref<boolean>` (imported from vue), store it, and react to changes:

```typescript
import { onMounted, onUnmounted, watch, type Ref } from 'vue'

export function useDeerField(
  bgCanvasRef: { value: HTMLCanvasElement | null },
  deerCanvasRef: { value: HTMLCanvasElement | null },
  isDark: Ref<boolean> = ref(true),
) {
  // ... existing internal variables ...
  let currentIsDark = isDark.value

  // In the start() function, use currentIsDark:
  //   sprites = buildSprites(SPRITE_DPR_MAX, currentIsDark)
  //   particles = buildParticles(vpW, vpH, currentIsDark)  // in resize()

  // In the loop() function, pass currentIsDark to drawGrid:
  //   drawGrid(deerCtx, grid, currentIsDark)

  // Watch for theme changes:
  watch(isDark, (newVal) => {
    currentIsDark = newVal
    // Rebuild sprites for new color mode
    sprites = buildSprites(SPRITE_DPR_MAX, currentIsDark)
    // Rebuild particles with new sprite indices and opacity
    particles = buildParticles(vpW, vpH, currentIsDark)
  })
```

Specifically, update:
1. `resize()` — change `particles = buildParticles(vpW, vpH)` → `particles = buildParticles(vpW, vpH, currentIsDark)`
2. `start()` — change `sprites = buildSprites(SPRITE_DPR_MAX)` → `sprites = buildSprites(SPRITE_DPR_MAX, currentIsDark)`
3. `loop()` — change `drawGrid(deerCtx, grid)` → `drawGrid(deerCtx, grid, currentIsDark)`

- [ ] **Step 8: Verify typecheck passes**

Run: `cd frontend && pnpm --filter main typecheck`
Expected: PASS — no type errors

- [ ] **Step 9: Commit**

```bash
git add frontend/apps/main/src/composables/useDeerField.ts
git commit -m "feat(login): add isDark parameter to useDeerField for rainbow particles + gradient grid"
```

---

### Task 2: LoginPage.vue — theme detection and background color switching

**Files:**
- Modify: `frontend/apps/main/src/pages/LoginPage.vue`

**Interfaces:**
- Consumes: `useDeerField(bgCanvasRef, deerCanvasRef, isDark)` from Task 1
- Produces: login page with `data-theme`-aware background and `isDark` ref passed to canvas

- [ ] **Step 1: Add theme detection logic**

In the `<script setup>` section, after the existing imports (line 260-270), add:

```typescript
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
```

Replace the existing `import { ref, onMounted } from 'vue'` at line 260.

Then add the theme detection after `const showPassword = ref(false)` (around line 281):

```typescript
// Theme detection — follow data-theme set by App.vue
const isDark = ref(document.documentElement.getAttribute('data-theme') !== 'light')

// Watch for system theme changes when no explicit user preference
let themeMediaQuery: MediaQueryList | null = null
onMounted(() => {
  themeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  const handler = () => {
    // Only auto-switch if user hasn't set explicit preference
    const currentTheme = document.documentElement.getAttribute('data-theme')
    if (!currentTheme || currentTheme === '') {
      isDark.value = themeMediaQuery!.matches
    }
  }
  themeMediaQuery.addEventListener('change', handler)
})

onUnmounted(() => {
  if (themeMediaQuery) {
    themeMediaQuery.removeEventListener('change', () => {})
  }
})

// Also watch data-theme attribute changes (user changes theme in settings)
const themeObserver = new MutationObserver(() => {
  const theme = document.documentElement.getAttribute('data-theme')
  if (theme === 'light') isDark.value = false
  else if (theme === 'dark') isDark.value = true
})

onMounted(() => {
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})

onUnmounted(() => {
  themeObserver.disconnect()
})
```

Wait — `onMounted` and `onUnmounted` are called twice. Consolidate with the existing `onMounted` at line 350. Instead, set up the observer inline (outside lifecycle hooks — MutationObserver doesn't need Vue lifecycle):

```typescript
// Theme detection — follow data-theme set by App.vue
const isDark = ref(document.documentElement.getAttribute('data-theme') !== 'light')

const themeObserver = new MutationObserver(() => {
  const theme = document.documentElement.getAttribute('data-theme')
  if (theme === 'light') isDark.value = false
  else if (theme === 'dark') isDark.value = true
  else isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
})
themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

onUnmounted(() => {
  themeObserver.disconnect()
})
```

- [ ] **Step 2: Pass `isDark` to `useDeerField`**

Change line 285:
```typescript
// Before:
useDeerField(bgCanvasRef, deerCanvasRef)

// After:
useDeerField(bgCanvasRef, deerCanvasRef, isDark)
```

- [ ] **Step 3: Add light-mode background and text color overrides in scoped styles**

At the end of the `<style scoped>` block (before `</style>` at line 1447), add:

```css
/* ── Light mode overrides ─────────────────────────────────────────── */
:global(.theme-light) .login-page,
.login-page[data-theme-light] {
  background: #ffffff;
}

:global(.theme-light) .login-content {
  /* Ensure content is above white bg */
}

:global(.theme-light) .app-subtitle .subtitle-char {
  /* Keep rainbow chars — they work on white */
}

:global(.theme-light) .step0-subtitle,
:global(.theme-light) .pin-hint,
:global(.theme-light) .pin-display-name,
:global(.theme-light) .pin-username,
:global(.theme-light) .account-name,
:global(.theme-light) .emoji-loading {
  color: #1a1a2e;
}

:global(.theme-light) .account-subtitle,
:global(.theme-light) .pin-username-sub {
  color: rgba(26, 26, 46, 0.55);
}

:global(.theme-light) .account-role {
  color: rgba(26, 26, 46, 0.65);
}

:global(.theme-light) .pin-error {
  color: #d32f2f;
}

/* Glass-morphism form fields — light mode */
:global(.theme-light) .login-form :deep(.van-cell) {
  background: rgba(255, 255, 255, 0.65);
  border: 2px solid rgba(180, 170, 230, 0.3);
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

:global(.theme-light) .login-form :deep(.van-cell):focus-within {
  border-color: rgba(120, 100, 220, 0.6);
  background: rgba(255, 255, 255, 0.8);
  box-shadow:
    0 0 0 3px rgba(120, 100, 220, 0.15),
    0 0 12px rgba(120, 100, 220, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

:global(.theme-light) .login-form :deep(.van-field__label) {
  color: rgba(26, 26, 46, 0.9);
}

:global(.theme-light) .login-form :deep(.van-field__control) {
  color: #1a1a2e;
  caret-color: rgba(120, 100, 220, 0.9);
}

:global(.theme-light) .login-form :deep(.van-field__placeholder) {
  color: rgba(26, 26, 46, 0.35);
}

:global(.theme-light) .login-form :deep(.van-field__right-icon) {
  color: rgba(120, 100, 220, 0.7);
}

/* Buttons — light mode */
:global(.theme-light) .form-actions :deep(.van-button--primary) {
  --van-button-primary-background: rgba(100, 80, 200, 0.85);
  --van-button-primary-border-color: rgba(120, 100, 220, 0.5);
  --van-button-primary-color: #fff;
  box-shadow: 0 2px 12px rgba(100, 80, 200, 0.25);
}

:global(.theme-light) .form-actions :deep(.van-button--primary:active) {
  --van-button-primary-background: rgba(100, 80, 200, 0.95);
  box-shadow: 0 2px 16px rgba(100, 80, 200, 0.35);
}

/* PIN slots — light mode */
:global(.theme-light) .pin-slot {
  border-color: rgba(120, 100, 220, 0.4);
}

:global(.theme-light) .pin-slot.filled {
  background: rgba(120, 100, 220, 0.8);
  border-color: rgba(120, 100, 220, 0.8);
  box-shadow: 0 0 8px rgba(120, 100, 220, 0.3);
}

/* Numpad — light mode */
:global(.theme-light) .numpad-btn {
  border-color: rgba(180, 170, 230, 0.25);
  background: rgba(255, 255, 255, 0.7);
  color: #1a1a2e;
}

:global(.theme-light) .numpad-btn:hover:not(:disabled) {
  background: rgba(120, 100, 220, 0.08);
  border-color: rgba(120, 100, 220, 0.35);
}

:global(.theme-light) .numpad-btn:active:not(:disabled) {
  background: rgba(120, 100, 220, 0.15);
  border-color: rgba(120, 100, 220, 0.5);
}

:global(.theme-light) .numpad-action {
  background: rgba(120, 100, 220, 0.08) !important;
  border-color: rgba(120, 100, 220, 0.35) !important;
  color: rgba(100, 80, 200, 0.9) !important;
}

/* Emoji grid — light mode */
:global(.theme-light) .emoji-btn {
  border-color: rgba(180, 170, 230, 0.25);
  background: rgba(255, 255, 255, 0.7);
}

:global(.theme-light) .emoji-btn:hover:not(:disabled) {
  background: rgba(120, 100, 220, 0.08);
  border-color: rgba(120, 100, 220, 0.35);
}

:global(.theme-light) .emoji-pin-slot {
  border-color: rgba(120, 100, 220, 0.3);
  background: rgba(255, 255, 255, 0.6);
}

:global(.theme-light) .emoji-pin-slot.filled {
  background: rgba(120, 100, 220, 0.12);
  border-color: rgba(120, 100, 220, 0.7);
}

:global(.theme-light) .emoji-action-btn {
  border-color: rgba(120, 100, 220, 0.3);
  background: rgba(255, 255, 255, 0.6);
  color: rgba(100, 80, 200, 0.9);
}

/* Account carousel — light mode */
:global(.theme-light) .account-card {
  background: rgba(255, 255, 255, 0.65);
  border-color: rgba(180, 170, 230, 0.3);
}

:global(.theme-light) .account-card.selected {
  border-color: rgba(120, 100, 220, 0.7);
  box-shadow: 0 0 16px rgba(120, 100, 220, 0.2);
}

:global(.theme-light) .account-avatar--add {
  background: rgba(120, 100, 220, 0.12);
  color: rgba(100, 80, 200, 0.8);
}

:global(.theme-light) .carousel-arrow {
  background: rgba(120, 100, 220, 0.1);
  color: rgba(100, 80, 200, 0.8);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

:global(.theme-light) .account-swipe :deep(.van-swipe__indicator) {
  background: rgba(120, 100, 220, 0.25);
}

:global(.theme-light) .account-swipe :deep(.van-swipe__indicator--active) {
  background: rgba(120, 100, 220, 0.8);
}

/* Links — light mode */
:global(.theme-light) .login-links a {
  color: rgba(100, 80, 200, 0.9);
}

:global(.theme-light) .divider {
  color: rgba(26, 26, 46, 0.3);
}

/* Back button — light mode */
:global(.theme-light) .back-btn-primary {
  --van-button-primary-background: rgba(255, 255, 255, 0.6);
  --van-button-primary-border-color: rgba(180, 170, 230, 0.35);
  --van-button-primary-color: rgba(26, 26, 46, 0.7);
}

/* PIN confirm + quick login — light mode */
:global(.theme-light) .pin-confirm-btn,
:global(.theme-light) .quick-login-btn {
  --van-button-primary-background: rgba(100, 80, 200, 0.85);
  --van-button-primary-border-color: rgba(120, 100, 220, 0.5);
  --van-button-primary-color: #fff;
  box-shadow: 0 2px 12px rgba(100, 80, 200, 0.2);
}

/* Flash animation — light mode */
:global(.theme-light) @keyframes flash {
  0% { background: rgba(120, 100, 220, 0.05); box-shadow: none; }
  40% { background: rgba(120, 100, 220, 0.25); box-shadow: 0 0 12px rgba(120, 100, 220, 0.2); }
  100% { background: rgba(120, 100, 220, 0.05); box-shadow: none; }
}
```

- [ ] **Step 4: Verify typecheck**

Run: `cd frontend && pnpm --filter main typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/LoginPage.vue
git commit -m "feat(login): add light mode theme detection and CSS overrides to LoginPage"
```

---

### Task 3: auth-page.css — shared light mode styles

**Files:**
- Modify: `frontend/apps/main/src/styles/auth-page.css`

**Interfaces:**
- Consumes: `data-theme="light"` on `<html>`
- Produces: light-mode glass-morphism for Register and JoinFamily pages

- [ ] **Step 1: Add light mode overrides to auth-page.css**

Append to the end of `auth-page.css`:

```css
/* ── Light mode overrides (Register + JoinFamily pages) ────────────── */

:root[data-theme="light"] .auth-page {
  background: #ffffff;
}

:root[data-theme="light"] .auth-title {
  color: #1a1a2e;
}

:root[data-theme="light"] .auth-subtitle {
  color: rgba(26, 26, 46, 0.7);
}

:root[data-theme="light"] .auth-form :deep(.van-cell),
:root[data-theme="light"] .auth-form .van-cell {
  background: rgba(255, 255, 255, 0.65);
  border: 2px solid rgba(180, 170, 230, 0.3);
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

:root[data-theme="light"] .auth-form :deep(.van-cell):focus-within,
:root[data-theme="light"] .auth-form .van-cell:focus-within {
  border-color: rgba(120, 100, 220, 0.6);
  background: rgba(255, 255, 255, 0.8);
  box-shadow:
    0 0 0 3px rgba(120, 100, 220, 0.15),
    0 0 12px rgba(120, 100, 220, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

:root[data-theme="light"] .auth-form :deep(.van-field__label),
:root[data-theme="light"] .auth-form .van-field__label {
  color: rgba(26, 26, 46, 0.9);
}

:root[data-theme="light"] .auth-form :deep(.van-field__control),
:root[data-theme="light"] .auth-form .van-field__control {
  color: #1a1a2e;
  caret-color: rgba(120, 100, 220, 0.9);
}

:root[data-theme="light"] .auth-form :deep(.van-field__placeholder),
:root[data-theme="light"] .auth-form .van-field__placeholder {
  color: rgba(26, 26, 46, 0.35);
}

:root[data-theme="light"] .auth-form :deep(.van-field__right-icon),
:root[data-theme="light"] .auth-form .van-field__right-icon {
  color: rgba(120, 100, 220, 0.7);
}

:root[data-theme="light"] .form-actions :deep(.van-button--primary),
:root[data-theme="light"] .form-actions .van-button--primary {
  --van-button-primary-background: rgba(100, 80, 200, 0.85);
  --van-button-primary-border-color: rgba(120, 100, 220, 0.5);
  --van-button-primary-color: #fff;
  box-shadow: 0 2px 12px rgba(100, 80, 200, 0.25);
}

:root[data-theme="light"] .form-actions :deep(.van-button--primary:active),
:root[data-theme="light"] .form-actions .van-button--primary:active {
  --van-button-primary-background: rgba(100, 80, 200, 0.95);
  box-shadow: 0 2px 16px rgba(100, 80, 200, 0.35);
}

:root[data-theme="light"] .auth-links a {
  color: rgba(100, 80, 200, 0.9);
}

:root[data-theme="light"] .auth-links .divider {
  color: rgba(26, 26, 46, 0.3);
}
```

Note: Register and JoinFamily pages use `@import '@/styles/auth-page.css'` inside `<style scoped>`. The `:root[data-theme="light"]` selectors pierce scoped boundaries because `:root` is global. But since the `@import` is inside scoped styles, we may need the non-scoped duplication. Test both forms — if scoped `:root` doesn't work, add a separate `<style>` (non-scoped) block in those pages, or move the light-mode overrides into a separate unscoped file.

- [ ] **Step 2: Verify typecheck**

Run: `cd frontend && pnpm --filter main typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/styles/auth-page.css
git commit -m "feat(login): add light mode overrides to shared auth-page.css"
```

---

### Task 4: NuminaLogo — light mode gradient

**Files:**
- Modify: `frontend/apps/main/src/components/common/NuminaLogo.vue`

**Interfaces:**
- Consumes: `data-theme` attribute on `<html>` or parent context
- Produces: logo with visible gradient on white background

- [ ] **Step 1: Add theme-aware gradient colors**

The logo currently uses:
- `textGrad`: white→white (line 51-54) — invisible on white bg
- `flourishGrad`: `#bdbbff`→`#e8e4ff`→`#ffd6a5` (line 46-50)

For light mode, the text needs a dark-to-medium gradient, and the flourish needs more saturated colors.

Add a computed property in `<script setup>`:

```typescript
import { computed, useId, ref, onMounted, onUnmounted } from 'vue'

// ... existing uid/ids code ...

// Theme detection for logo colors
const isDark = ref(document.documentElement.getAttribute('data-theme') !== 'light')

const themeObserver = new MutationObserver(() => {
  const theme = document.documentElement.getAttribute('data-theme')
  isDark.value = theme !== 'light'
})

onMounted(() => {
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})

onUnmounted(() => {
  themeObserver.disconnect()
})
```

- [ ] **Step 2: Update gradient stop-colors based on theme**

In the template, replace the hardcoded gradient stops with theme-aware values:

For `textGrad` (line 51-54):
```html
<linearGradient :id="ids.textGrad" x1="0%" y1="0%" x2="0%" y2="100%">
  <stop offset="0%" :stop-color="isDark ? '#ffffff' : '#1a1a2e'" />
  <stop offset="100%" :stop-color="isDark ? 'rgba(255,255,255,0.85)' : 'rgba(26,26,46,0.75)'" />
</linearGradient>
```

For `flourishGrad` (line 46-50):
```html
<linearGradient :id="ids.flourishGrad" x1="0%" y1="0%" x2="100%" y2="0%">
  <stop offset="0%" :stop-color="isDark ? '#bdbbff' : '#7c6cc4'" :stop-opacity="isDark ? 0.7 : 0.9" />
  <stop offset="45%" :stop-color="isDark ? '#e8e4ff' : '#5a4a9e'" :stop-opacity="1" />
  <stop offset="100%" :stop-color="isDark ? '#ffd6a5' : '#c4884a'" :stop-opacity="isDark ? 0.8 : 0.9" />
</linearGradient>
```

For the shimmer gradient — keep it working for both modes:
```html
<linearGradient :id="ids.shimmerGrad" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0%" :stop-color="isDark ? '#ffffff' : '#7c6cc4'" stop-opacity="0" />
  <stop offset="35%" :stop-color="isDark ? '#ffffff' : '#7c6cc4'" stop-opacity="0" />
  <stop offset="50%" :stop-color="isDark ? '#ffffff' : '#7c6cc4'" :stop-opacity="isDark ? 0.9 : 0.4" />
  <stop offset="65%" :stop-color="isDark ? '#ffffff' : '#7c6cc4'" stop-opacity="0" />
  <stop offset="100%" :stop-color="isDark ? '#ffffff' : '#7c6cc4'" stop-opacity="0" />
</linearGradient>
```

Also update the shimmer mask strokes — the mask uses `stroke="white"` which works as a mask regardless of theme (masks are luminance-based), so no change needed there.

- [ ] **Step 3: Verify typecheck**

Run: `cd frontend && pnpm --filter main typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/components/common/NuminaLogo.vue
git commit -m "feat(login): add light mode gradient to NuminaLogo"
```

---

### Task 5: Visual verification and polish

**Files:**
- No new files — manual testing and potential micro-adjustments

- [ ] **Step 1: Run the dev server and test both modes**

```bash
cd frontend && pnpm dev
```

Test checklist:
1. Open login page with system in dark mode → verify it looks identical to before (no regression)
2. Switch system to light mode (or toggle in settings if logged in elsewhere) → verify:
   - Background is white
   - Rainbow particles visible but not overwhelming
   - Pixel animal grid shows blue-purple-pink gradient
   - Form fields have glass effect with lavender borders on white
   - Text is dark and readable
   - Buttons are purple-tinted
   - NuminaLogo is visible with dark gradient
   - Subtitle rainbow chars still colorful
3. Test all 3 login steps (carousel → password → PIN) in light mode
4. Test Register and JoinFamily pages in light mode
5. Test with `prefers-reduced-motion: reduce` → canvas should be hidden in both modes

- [ ] **Step 2: Fix any visual issues discovered**

Common issues to watch for:
- AltchaWidget captcha may need light-mode overrides (check its styling)
- TrustedDeviceCard already has `.theme-light` overrides — verify they work
- Swipe indicators on account carousel
- Any remaining `#fff` or `rgba(255,255,255,...)` text that's now invisible on white

- [ ] **Step 3: Run full typecheck + lint**

```bash
cd frontend && pnpm -r typecheck && pnpm -r lint
```

Expected: PASS

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(login): polish light mode visual details"
```

---

## Summary of Color Decisions

| Element | Dark Mode | Light Mode |
|---------|-----------|------------|
| Page background | `#010120` | `#ffffff` |
| Particles | 5 white-temperature stellar colors | 7 rainbow hues (red→purple), per-particle consistent hue |
| Particle opacity | 1.0× | 0.6× (reduced for white bg) |
| Pixel grid | `rgba(189,187,255,α)` lavender | `rgba(120~200, 100~140, 200~220, α)` blue-purple-pink gradient |
| Grid max alpha | 0.45 | 0.55 (slightly higher for visibility) |
| Form field bg | `rgba(255,255,255,0.06)` | `rgba(255,255,255,0.65)` |
| Form field border | `rgba(189,187,255,0.35)` | `rgba(180,170,230,0.3)` |
| Text primary | `#fff` | `#1a1a2e` |
| Text secondary | `rgba(255,255,255,0.8)` | `rgba(26,26,46,0.7)` |
| Button bg | `rgba(255,255,255,0.12)` glass | `rgba(100,80,200,0.85)` solid purple |
| Button text | `#fff` | `#fff` |
| Accent | `#bdbbff` | `rgba(120,100,220)` family |
| Logo text | white gradient | `#1a1a2e` gradient |
| Logo flourish | `#bdbbff` pastel | `#7c6cc4` saturated |
