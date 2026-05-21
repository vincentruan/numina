# Login Page Background Effect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace firefly particle animation with DeerFlow-style grid overlay + floating glow blobs that drift and breathe.

**Architecture:** Two-layer system: CSS grid pattern on background container, Canvas-rendered glow blobs on bgCanvas. Deer canvas (pixel grid + mask) unchanged. Blobs combine slow drift movement with sinusoidal breathing for size/opacity.

**Tech Stack:** Vue 3, TypeScript, Canvas API, CSS linear-gradient

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/composables/useDeerField.ts` | Glow blob system: constants, data structure, update loop, canvas rendering |
| `src/pages/LoginPage.vue` | CSS grid overlay on `.login-page` background |

---

### Task 1: Add CSS Grid Pattern

**Files:**
- Modify: `src/pages/LoginPage.vue:531` (`.login-page` style block)

- [ ] **Step 1: Add grid pattern CSS to login-page background**

Add grid overlay to the `.login-page` style block, right after the `background: #010120;` line:

```css
.login-page {
  min-height: 100vh;
  background: #010120;
  /* DeerFlow-style grid overlay */
  background-image:
    linear-gradient(rgba(0, 200, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 200, 255, 0.08) 1px, transparent 1px);
  background-size: 50px 50px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: min(15vh, 60px);
  position: relative;
  overflow: hidden;
}
```

- [ ] **Step 2: Verify CSS grid renders**

Run dev server:
```bash
cd frontend/apps/main && npm run dev
```

Open http://localhost:5173/login — grid lines should be visible but subtle (cyan/teal at 8% opacity).

- [ ] **Step 3: Commit CSS changes**

```bash
git add frontend/apps/main/src/pages/LoginPage.vue
git commit -m "feat(login): add DeerFlow-style grid overlay to background

50x50px cyan grid at 8% opacity for tech-forward aesthetic."
```

---

### Task 2: Replace Firefly System with Glow Blob System

**Files:**
- Modify: `src/composables/useDeerField.ts` (full rewrite of firefly section)

- [ ] **Step 1: Replace firefly constants with glow blob constants**

Replace lines 13-48 in `useDeerField.ts` (the firefly constants section) with:

```typescript
// ── Deer pixel grid constants ──────────────────────────────────────────────
const CELL_SIZE = 4
const CELL_GAP = 1
const MAX_ALPHA = 0.45
const FLICKER_RATE = 0.06

// ── Glow blob constants (DeerFlow-style) ───────────────────────────────────
// Large drifting blobs with breathing animation (aurora/nebula effect)
// Blobs combine slow drift + sinusoidal size/opacity pulse
const BLOB_COUNT_BASE = 5
const REFERENCE_AREA = 2_073_600  // 1080×1920

// Size range (large blobs for aurora feel)
const BLOB_RADIUS_MIN = 80
const BLOB_RADIUS_MAX = 150

// Drift speed (px/s) — slow ambient movement
const DRIFT_SPEED_MIN = 5
const DRIFT_SPEED_MAX = 15

// Breathing cycle: 2-4 seconds per full breath
const BREATH_SPEED_MIN = 0.25  // 4s cycle
const BREATH_SPEED_MAX = 0.5   // 2s cycle

// Breathing amplitude: size expansion and opacity boost at peak
const BREATH_SIZE_AMPLITUDE_MIN = 0.2
const BREATH_SIZE_AMPLITUDE_MAX = 0.4
const BREATH_OPACITY_AMPLITUDE_MIN = 0.3
const BREATH_OPACITY_AMPLITUDE_MAX = 0.5

// Base opacity at rest (breathing increases at peak)
const BLOB_OPACITY_MIN = 0.35
const BLOB_OPACITY_MAX = 0.55

// Wander: gradual direction changes
const WANDER_INTERVAL_MIN = 2.0
const WANDER_INTERVAL_MAX = 5.5
const WANDER_ANGLE_MAX = Math.PI * 0.65

// Color palette: cyan/teal variations (DeerFlow aesthetic)
const BLOB_COLORS = [
  [0, 220, 255],    // primary cyan
  [50, 255, 220],   // teal
  [100, 255, 255],  // light cyan
]
```

- [ ] **Step 2: Replace Firefly interface with GlowBlob interface**

Replace lines 58-79 (the `Firefly` interface) with:

```typescript
interface GlowBlob {
  x: number
  y: number
  baseRadius: number      // 80-150px
  currentRadius: number   // breathing-modulated
  breathPhase: number     // 0..1 (cycle progress)
  breathSpeed: number     // cycles/s (0.25-0.5)
  breathSizeAmplitude: number   // 0.2-0.4
  breathOpacityAmplitude: number // 0.3-0.5
  baseOpacity: number     // 0.35-0.55
  vx: number              // drift velocity x
  vy: number              // drift velocity y
  wanderTimer: number     // countdown to next direction change
  wanderInterval: number  // 2-5.5s
  colorVariant: number    // index into BLOB_COLORS
}
```

- [ ] **Step 3: Replace buildFireflies with buildBlobs**

Replace the `buildFireflies` function (lines 146-183) with:

```typescript
function blobCount(w: number, h: number): number {
  const area = w * h
  const scale = area / REFERENCE_AREA
  const clamped = Math.max(0.5, Math.min(2.5, scale))
  return Math.max(3, Math.round(BLOB_COUNT_BASE * clamped))
}

function buildBlobs(w: number, h: number): GlowBlob[] {
  const blobs: GlowBlob[] = []
  const count = blobCount(w, h)

  for (let i = 0; i < count; i++) {
    const baseRadius = rand(BLOB_RADIUS_MIN, BLOB_RADIUS_MAX)
    const speed = rand(DRIFT_SPEED_MIN, DRIFT_SPEED_MAX)
    const angle = Math.random() * Math.PI * 2

    blobs.push({
      x: Math.random() * w,
      y: Math.random() * h,
      baseRadius,
      currentRadius: baseRadius,
      breathPhase: Math.random(), // staggered start
      breathSpeed: rand(BREATH_SPEED_MIN, BREATH_SPEED_MAX),
      breathSizeAmplitude: rand(BREATH_SIZE_AMPLITUDE_MIN, BREATH_SIZE_AMPLITUDE_MAX),
      breathOpacityAmplitude: rand(BREATH_OPACITY_AMPLITUDE_MIN, BREATH_OPACITY_AMPLITUDE_MAX),
      baseOpacity: rand(BLOB_OPACITY_MIN, BLOB_OPACITY_MAX),
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      wanderTimer: Math.random() * WANDER_INTERVAL_MAX,
      wanderInterval: rand(WANDER_INTERVAL_MIN, WANDER_INTERVAL_MAX),
      colorVariant: Math.floor(Math.random() * BLOB_COLORS.length),
    })
  }
  return blobs
}
```

- [ ] **Step 4: Replace updateFireflies with updateBlobs**

Replace the `updateFireflies` function (lines 185-247) with:

```typescript
function updateBlobs(blobs: GlowBlob[], dt: number, w: number, h: number) {
  for (const b of blobs) {
    // Drift movement
    b.x += b.vx * dt
    b.y += b.vy * dt

    // Wrap edges smoothly
    const margin = b.currentRadius * 1.5
    if (b.x < -margin) b.x = w + margin
    else if (b.x > w + margin) b.x = -margin
    if (b.y < -margin) b.y = h + margin
    else if (b.y > h + margin) b.y = -margin

    // Wander: gradual direction changes
    b.wanderTimer += dt
    if (b.wanderTimer >= b.wanderInterval) {
      b.wanderTimer = 0
      b.wanderInterval = rand(WANDER_INTERVAL_MIN, WANDER_INTERVAL_MAX)
      const speed = rand(DRIFT_SPEED_MIN, DRIFT_SPEED_MAX)
      const currentAngle = Math.atan2(b.vy, b.vx)
      const newAngle = currentAngle + rand(-WANDER_ANGLE_MAX, WANDER_ANGLE_MAX)
      b.vx = Math.cos(newAngle) * speed
      b.vy = Math.sin(newAngle) * speed
    }

    // Breathing: sinusoidal pulse for radius AND opacity
    b.breathPhase = (b.breathPhase + b.breathSpeed * dt) % 1
    const breathWave = (Math.sin(b.breathPhase * Math.PI * 2) + 1) / 2

    // Radius expands during peak
    b.currentRadius = b.baseRadius * (1 + b.breathSizeAmplitude * breathWave)
  }
}
```

- [ ] **Step 5: Replace drawFireflies with drawBlobs**

Replace the `drawFireflies` function (lines 249-324) with:

```typescript
function drawBlobs(ctx: CanvasRenderingContext2D, blobs: GlowBlob[], dpr: number) {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  for (const b of blobs) {
    const x = b.x * dpr
    const y = b.y * dpr
    const r = b.currentRadius * dpr

    // Breathing wave for opacity modulation
    const breathWave = (Math.sin(b.breathPhase * Math.PI * 2) + 1) / 2
    const opacity = b.baseOpacity * (1 + b.breathOpacityAmplitude * breathWave)

    // Select color variant
    const [cr, cg, cb] = BLOB_COLORS[b.colorVariant]

    // Radial gradient: bright center → soft edge → transparent
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, r)
    gradient.addColorStop(0, `rgba(${cr},${cg},${cb},${opacity.toFixed(3)})`)
    gradient.addColorStop(0.35, `rgba(${cr},${cg},${cb},${(opacity * 0.4).toFixed(3)})`)
    gradient.addColorStop(0.7, `rgba(${cr},${cg},${cb},${(opacity * 0.15).toFixed(3)})`)
    gradient.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)

    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = gradient
    ctx.fill()
  }
}
```

- [ ] **Step 6: Update composable internals to use blobs**

Replace the composable function body (lines 336-368 in `resize` and `loop`):

In `resize()` function, replace `flies = buildFireflies(vpW, vpH)` with:
```typescript
blobs = buildBlobs(vpW, vpH)
```

In `loop()` function, replace:
```typescript
updateFireflies(flies, dt, vpW, vpH)
drawFireflies(bgCtx, flies, bgDpr)
```
with:
```typescript
updateBlobs(blobs, dt, vpW, vpH)
drawBlobs(bgCtx, blobs, bgDpr)
```

- [ ] **Step 7: Update variable declarations**

Replace line 336:
```typescript
let flies: Firefly[] = []
```
with:
```typescript
let blobs: GlowBlob[] = []
```

- [ ] **Step 8: Remove unused imports and type references**

The file should no longer reference `Firefly`, `NUM_LAYERS`, or any firefly-specific constants. Verify by running typecheck.

- [ ] **Step 9: Run typecheck to verify TypeScript correctness**

```bash
cd frontend/apps/main && npm run typecheck
```

Expected: PASS with no errors related to `useDeerField.ts`

- [ ] **Step 10: Commit glow blob implementation**

```bash
git add frontend/apps/main/src/composables/useDeerField.ts
git commit -m "feat(login): replace firefly particles with DeerFlow glow blobs

- 4-6 large drifting blobs (80-150px radius)
- Cyan/teal color palette for tech-forward aesthetic
- Sinusoidal breathing for size (20-40%) and opacity (30-50%)
- Slow drift movement (5-15px/s) with gradual direction changes
- 2-4 second breathing cycles staggered per blob"
```

---

### Task 3: Visual Verification and Final Commit

**Files:**
- None (verification only)

- [ ] **Step 1: Start dev server and visually verify**

```bash
cd frontend/apps/main && npm run dev
```

Open http://localhost:5173/login and check:

1. **Grid:** Visible but subtle cyan lines at 50px spacing
2. **Blobs:** 4-6 large soft glow spots drifting slowly
3. **Breathing:** Blobs pulse in size/brightness smoothly (2-4s cycle)
4. **Deer silhouette:** Pixel grid + mask still works unchanged
5. **Performance:** No visible lag, smooth animation

- [ ] **Step 2: Create final summary commit (if needed)**

If both previous commits are clean, no additional commit needed. Otherwise, fix any issues and amend.

---

## Self-Review Checklist

After completing all tasks:

1. **Spec coverage:**
   - Grid pattern (50×50, cyan 8%) → Task 1 ✓
   - Glow blobs (4-6, 80-150px) → Task 2 ✓
   - Drift (5-15px/s) → Task 2 ✓
   - Breathing (2-4s, size 20-40%, opacity 30-50%) → Task 2 ✓
   - Deer mask unchanged → Task 2 (no changes to deer section) ✓

2. **Placeholder scan:** No TBD, TODO, or vague instructions ✓

3. **Type consistency:** `GlowBlob` interface matches usage in all functions ✓