# Stellar Particle Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current particle system in `useDeerField.ts` with physically accurate stellar particles: bright cores + irregular halos, sinusoidal breathing, 3D depth layering, counter-clockwise drift with noise.

**Architecture:** Canvas 2D + offline sprite cache (16 variants). Particle layer (bgCanvas) rewritten; deer silhouette layer (deerCanvas) unchanged. No changes to LoginPage.vue.

**Tech Stack:** Vue 3, TypeScript, Canvas 2D API, requestAnimationFrame loop

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/composables/useDeerField.ts` | Full rewrite of particle section (lines 1-240 + 316-368), keep deer grid section (lines 103-144) unchanged |

**Boundary identification:**
- Lines 1-64: Particle constants → **REPLACE**
- Lines 65-88: Grid interface + Particle interface → **REPLACE Particle interface, keep Grid**
- Lines 90-96: `debounce` helper → **KEEP**
- Lines 98-99: `rand` helper → **KEEP**
- Lines 103-144: Deer grid helpers (`buildGrid`, `flickerGrid`, `drawGrid`) → **KEEP UNCHANGED**
- Lines 146-240: Particle helpers (`particleCount`, `buildParticles`, `updateParticles`, `drawParticles`, `drawNormalParticle`, `drawStarParticle`) → **REPLACE with new sprite-based system**
- Lines 319-430: Composable main function → **MODIFY (add sprites array, sprite generation call in start())**

---

### Task 1: Replace Particle Constants with New Stellar System Constants

**Files:**
- Modify: `src/composables/useDeerField.ts:1-64`

- [ ] **Step 1: Replace lines 1-64 with new stellar particle constants**

Replace the existing constants block (lines 1-64) with:

```typescript
import { onMounted, onUnmounted, type Ref } from 'vue'

// Two-layer background system:
//   bgCanvas  — stellar particles with bright cores + irregular halos
//   deerCanvas — dim lavender pixel grid masked to deer SVG silhouette (unchanged)

// ── Deer pixel grid constants (unchanged) ──────────────────────────────────────
const CELL_SIZE = 4
const CELL_GAP = 1
const MAX_ALPHA = 0.45
const FLICKER_RATE = 0.06

// ── Stellar particle constants ────────────────────────────────────────────────

// Sprite cache: 16 variants (5 color temps × 3 intensities, rotation dynamic)
const SPRITE_SIZE = 64          // internal size (pixels)
const SPRITE_DPR_MAX = 2        // bake at 2× for retina
const SPRITE_COUNT = 15        // 5 temps × 3 intensities (rotation at drawImage)

// Depth layer percentages
const FAR_RATIO = 0.50
const MID_RATIO = 0.35
const NEAR_RATIO = 0.15

// Far layer (远景): tiny, dim, slow
const FAR_RADIUS_MIN = 0.5
const FAR_RADIUS_MAX = 1.2
const FAR_OPACITY_MIN = 0.25
const FAR_OPACITY_MAX = 0.45
const FAR_SPEED_MIN = 3
const FAR_SPEED_MAX = 6

// Mid layer (中景): medium, moderate
const MID_RADIUS_MIN = 1.2
const MID_RADIUS_MAX = 2.2
const MID_OPACITY_MIN = 0.45
const MID_OPACITY_MAX = 0.65
const MID_SPEED_MIN = 8
const MID_SPEED_MAX = 14

// Near layer (近景): large, bright, fast
const NEAR_RADIUS_MIN = 2.2
const NEAR_RADIUS_MAX = 3.8
const NEAR_OPACITY_MIN = 0.65
const NEAR_OPACITY_MAX = 0.90
const NEAR_SPEED_MIN = 15
const NEAR_SPEED_MAX = 25

// Breathing (sinusoidal pulsation)
const BREATH_SPEED_MIN = 0.15   // 0.15 cycles/s = 6.67s period
const BREATH_SPEED_MAX = 0.35   // 0.35 cycles/s = 2.86s period
const BREATH_SIZE_AMP_MIN = 0.20
const BREATH_SIZE_AMP_MAX = 0.45
const BREATH_OPACITY_AMP_MIN = 0.30
const BREATH_OPACITY_AMP_MAX = 0.55

// Flow field: counter-clockwise bias
const CCW_BIAS_MIN = 30         // degrees left offset
const CCW_BIAS_MAX = 60
const NOISE_ANGLE_DELTA = 15    // ±15° perturbation
const TURN_RATE = 0.08          // gradual direction change (8% per frame)

// Edge wrap margin (halo extent)
const HALO_MARGIN_MULTIPLIER = 5

// Stellar color temperatures (realistic distribution)
// [coreR, coreG, coreB, haloR, haloG, haloB, percentage]
const STELLAR_COLORS: Array<{ core: [number, number, number]; halo: [number, number, number]; ratio: number }> = [
  { core: [255, 255, 255], halo: [180, 210, 255], ratio: 0.15 },  // O/B 蓝白巨星
  { core: [255, 255, 255], halo: [230, 235, 255], ratio: 0.30 },  // A 白色
  { core: [255, 250, 235], halo: [255, 230, 180], ratio: 0.30 },  // G 黄/类太阳
  { core: [255, 235, 210], halo: [255, 200, 150], ratio: 0.20 },  // K 橙色
  { core: [255, 220, 200], halo: [255, 170, 120], ratio: 0.05 },  // M 红巨星
]

// Sprite intensity levels
const INTENSITY_LEVELS = ['soft', 'medium', 'bright'] as const
type IntensityLevel = typeof INTENSITY_LEVELS[number]

// Particle count reference
const PARTICLE_COUNT_BASE = 180
const REFERENCE_AREA = 375 * 668  // iPhone 6/7/8 viewport
const PARTICLE_COUNT_MIN = 90
const PARTICLE_COUNT_MAX = 420
```

- [ ] **Step 2: Run typecheck to verify constants**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS (constants only, no usage yet)

- [ ] **Step 3: Commit constants replacement**

```bash
git add src/composables/useDeerField.ts
git commit -m "refactor(login): replace particle constants with stellar system

- Depth layering (far/mid/near) via size/opacity/speed
- Stellar color temperatures (O/B/A/G/K/M distribution)
- Breathing parameters (3-7s cycle, synced size+opacity)
- Flow field counter-clockwise bias constants

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Replace Particle Interface with New Model

**Files:**
- Modify: `src/composables/useDeerField.ts:65-88`

- [ ] **Step 1: Keep Grid interface, replace Particle interface**

Find line 72 (the Particle interface start) and replace through line 88 with:

```typescript
interface Grid {
  cols: number
  rows: number
  alphas: Float32Array
  dpr: number
}

interface Particle {
  // Position (CSS pixels)
  x: number
  y: number

  // Depth layer (immutable after init)
  depth: 'far' | 'mid' | 'near'
  baseRadius: number
  baseOpacity: number
  driftSpeed: number

  // Visual
  spriteIndex: number      // 0..14 (5 temps × 3 intensities)

  // Breathing (independent random seeds)
  breathPhase: number      // 0..1 (cycle progress)
  breathSpeed: number      // cycles/s (0.15-0.35)
  breathSizeAmp: number    // 0.20-0.45
  breathOpacityAmp: number // 0.30-0.55

  // Flow field state
  vx: number
  vy: number
  noiseOffsetX: number     // for simpleNoise2D sampling
  noiseOffsetY: number

  // Derived (per-frame)
  currentRadius: number
  currentOpacity: number
}

interface StarSprite {
  canvas: HTMLCanvasElement
  colorTempIndex: number   // 0-4 (O/B/A/G/K/M)
  intensityIndex: number   // 0-2 (soft/medium/bright)
}
```

- [ ] **Step 2: Run typecheck to verify interface**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS (interface only)

- [ ] **Step 3: Commit interface replacement**

```bash
git add src/composables/useDeerField.ts
git commit -m "refactor(login): replace Particle interface with stellar model

- Depth layer field (far/mid/near)
- Sprite index for cached variant lookup
- Breathing fields with independent seeds
- Flow field noise offset for perturbation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Add Sprite Generation Functions

**Files:**
- Modify: `src/composables/useDeerField.ts:146-153` (insert after `drawGrid` function)

- [ ] **Step 1: Add sprite generation functions after line 144 (after `drawGrid`)**

Insert the following functions after the deer grid section (after `drawGrid`, before the old particle helpers):

```typescript
// ── Sprite generation helpers ───────────────────────────────────────────────

const SPRITE_INTERNAL_SIZE = SPRITE_SIZE * SPRITE_DPR_MAX  // 128px at 2× DPR

function simpleNoise2D(x: number, y: number): number {
  // Lightweight pseudo-Perlin noise using sin/cos combinations
  const v1 = Math.sin(x * 0.01) * Math.cos(y * 0.01)
  const v2 = Math.sin(x * 0.02 + 1.5) * Math.cos(y * 0.015 + 0.7)
  const v3 = Math.sin(x * 0.005 + y * 0.008)
  return (v1 + v2 * 0.5 + v3 * 0.25) / 1.75  // normalize to -1..1
}

function rand(min: number, max: number): number {
  return min + Math.random() * (max - min)
}

function generateStarSprite(
  colorTempIndex: number,
  intensityIndex: number,
  dpr: number = SPRITE_DPR_MAX
): HTMLCanvasElement {
  const sprite = document.createElement('canvas')
  const size = SPRITE_SIZE * dpr  // 128 at 2×
  sprite.width = size
  sprite.height = size
  const ctx = sprite.getContext('2d')!
  const cx = size / 2
  const cy = size / 2

  const colorSpec = STELLAR_COLORS[colorTempIndex]
  const [coreR, coreG, coreB] = colorSpec.core
  const [haloR, haloG, haloB] = colorSpec.halo

  // Intensity affects ray count and halo extent
  const intensityMult = intensityIndex === 2 ? 1.4 : intensityIndex === 1 ? 1.0 : 0.7
  const rayCount = Math.floor((8 + Math.random() * 6) * intensityMult)  // 8-14 rays
  const baseHaloRadius = (size / 2 - 4) * intensityMult  // leave 4px margin

  // 1. Circular glow underlayer (soft radial gradient)
  const glowRadius = baseHaloRadius * 0.9
  const glowGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowRadius)
  glowGrad.addColorStop(0, `rgba(${haloR},${haloG},${haloB},0.35)`)
  glowGrad.addColorStop(0.5, `rgba(${haloR},${haloG},${haloB},0.08)`)
  glowGrad.addColorStop(1, `rgba(${haloR},${haloG},${haloB},0)`)
  ctx.beginPath()
  ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2)
  ctx.fillStyle = glowGrad
  ctx.fill()

  // 2. Irregular radiating rays (random length, width, opacity)
  ctx.save()
  ctx.translate(cx, cy)

  for (let i = 0; i < rayCount; i++) {
    const angle = (i / rayCount) * Math.PI * 2 + Math.random() * 0.3  // base + perturbation
    const rayLength = baseHaloRadius * (0.6 + Math.random() * 0.8)     // 60%-140%
    const rayWidth = (2 + Math.random() * 4) * dpr                     // 2-6px × dpr
    const rayOpacity = 0.12 + Math.random() * 0.15                     // 12%-27%

    // Linear gradient from core outward
    const endX = Math.cos(angle) * rayLength
    const endY = Math.sin(angle) * rayLength
    const rayGrad = ctx.createLinearGradient(0, 0, endX, endY)
    rayGrad.addColorStop(0, `rgba(${haloR},${haloG},${haloB},0.25)`)
    rayGrad.addColorStop(0.4, `rgba(${haloR},${haloG},${haloB},${rayOpacity.toFixed(3)})`)
    rayGrad.addColorStop(0.8, `rgba(${haloR},${haloG},${haloB},0.03)`)
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

  // 3. Bright core (ultra-bright white center, blends to color temp)
  const coreRadius = 4 * dpr  // ~8px at 2×
  const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreRadius)
  coreGrad.addColorStop(0, `rgba(255,255,255,1.0)`)         // pure white
  coreGrad.addColorStop(0.3, `rgba(255,255,255,0.95)`)
  coreGrad.addColorStop(0.6, `rgba(${coreR},${coreG},${coreB},0.7)`)
  coreGrad.addColorStop(1, `rgba(${coreR},${coreG},${coreB},0)`)
  ctx.beginPath()
  ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2)
  ctx.fillStyle = coreGrad
  ctx.fill()

  return sprite
}

function buildSprites(dpr: number = SPRITE_DPR_MAX): StarSprite[] {
  const sprites: StarSprite[] = []

  for (let tempIdx = 0; tempIdx < STELLAR_COLORS.length; tempIdx++) {
    for (let intIdx = 0; intIdx < INTENSITY_LEVELS.length; intIdx++) {
      sprites.push({
        canvas: generateStarSprite(tempIdx, intIdx, dpr),
        colorTempIndex: tempIdx,
        intensityIndex: intIdx,
      })
    }
  }

  return sprites  // 5 × 3 = 15 sprites
}
```

- [ ] **Step 2: Run typecheck to verify sprite functions**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS (functions defined but not called yet)

- [ ] **Step 3: Commit sprite generation functions**

```bash
git add src/composables/useDeerField.ts
git commit -m "feat(login): add stellar sprite generation functions

- generateStarSprite(): core + irregular rays + circular glow
- buildSprites(): 15 variants (5 temps × 3 intensities)
- simpleNoise2D(): lightweight pseudo-Perlin noise

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Replace Particle Helper Functions

**Files:**
- Modify: `src/composables/useDeerField.ts` (replace old particle helpers section)

- [ ] **Step 1: Delete old particle helper functions (lines 146-315 in original)**

Delete the following functions entirely:
- `particleCount()` (old version)
- `buildParticles()` (old version)
- `updateParticles()` (old version)
- `drawParticles()` (old version)
- `drawNormalParticle()`
- `drawStarParticle()`

- [ ] **Step 2: Add new particle helper functions after sprite generation**

Insert the following after `buildSprites()`:

```typescript
// ── Particle helpers ───────────────────────────────────────────────────────

function computeParticleCount(w: number, h: number): number {
  const area = w * h
  const scale = Math.sqrt(area / REFERENCE_AREA)

  if (w >= 1280) {
    return Math.min(PARTICLE_COUNT_MAX, Math.round(PARTICLE_COUNT_BASE * scale))
  }
  if (w >= 768) {
    return Math.min(320, Math.round(PARTICLE_COUNT_BASE * scale))
  }

  // Mobile: scale by height ratio
  const heightFactor = h / 668
  return Math.round(PARTICLE_COUNT_BASE * Math.max(0.85, Math.min(1.15, heightFactor)))
}

function assignDepthLayer(): 'far' | 'mid' | 'near' {
  const r = Math.random()
  if (r < FAR_RATIO) return 'far'
  if (r < FAR_RATIO + MID_RATIO) return 'mid'
  return 'near'
}

function assignColorTemp(): number {
  const r = Math.random()
  let cumulative = 0
  for (let i = 0; i < STELLAR_COLORS.length; i++) {
    cumulative += STELLAR_COLORS[i].ratio
    if (r < cumulative) return i
  }
  return STELLAR_COLORS.length - 1
}

function getDepthParams(depth: 'far' | 'mid' | 'near'): {
  radiusMin: number; radiusMax: number
  opacityMin: number; opacityMax: number
  speedMin: number; speedMax: number
} {
  switch (depth) {
    case 'far':
      return {
        radiusMin: FAR_RADIUS_MIN, radiusMax: FAR_RADIUS_MAX,
        opacityMin: FAR_OPACITY_MIN, opacityMax: FAR_OPACITY_MAX,
        speedMin: FAR_SPEED_MIN, speedMax: FAR_SPEED_MAX,
      }
    case 'mid':
      return {
        radiusMin: MID_RADIUS_MIN, radiusMax: MID_RADIUS_MAX,
        opacityMin: MID_OPACITY_MIN, opacityMax: MID_OPACITY_MAX,
        speedMin: MID_SPEED_MIN, speedMax: MID_SPEED_MAX,
      }
    case 'near':
      return {
        radiusMin: NEAR_RADIUS_MIN, radiusMax: NEAR_RADIUS_MAX,
        opacityMin: NEAR_OPACITY_MIN, opacityMax: NEAR_OPACITY_MAX,
        speedMin: NEAR_SPEED_MIN, speedMax: NEAR_SPEED_MAX,
      }
  }
}

function initParticleFlow(p: Particle, w: number, h: number): void {
  // Angle toward screen center
  const cx = w / 2
  const cy = h / 2
  const toCenterAngle = Math.atan2(cy - p.y, cx - p.x)

  // Counter-clockwise bias: +30-60° left offset
  const biasOffset = (CCW_BIAS_MIN + Math.random() * (CCW_BIAS_MAX - CCW_BIAS_MIN)) * Math.PI / 180

  // Base drift direction = away from center + left offset (逆时针趋势)
  const baseAngle = toCenterAngle + biasOffset + Math.PI

  // Add random noise (±40°)
  const noiseAngle = baseAngle + (Math.random() - 0.5) * 80 * Math.PI / 180

  p.vx = Math.cos(noiseAngle) * p.driftSpeed
  p.vy = Math.sin(noiseAngle) * p.driftSpeed

  // Noise offsets for future perturbation sampling
  p.noiseOffsetX = Math.random() * 1000
  p.noiseOffsetY = Math.random() * 1000
}

function buildParticles(w: number, h: number): Particle[] {
  const particles: Particle[] = []
  const count = computeParticleCount(w, h)

  for (let i = 0; i < count; i++) {
    const depth = assignDepthLayer()
    const params = getDepthParams(depth)
    const colorTempIdx = assignColorTemp()
    const intensityIdx = Math.floor(Math.random() * INTENSITY_LEVELS.length)

    const baseRadius = rand(params.radiusMin, params.radiusMax)
    const baseOpacity = rand(params.opacityMin, params.opacityMax)
    const driftSpeed = rand(params.speedMin, params.speedMax)

    const p: Particle = {
      x: Math.random() * w,
      y: Math.random() * h,
      depth,
      baseRadius,
      baseOpacity,
      driftSpeed,
      spriteIndex: colorTempIdx * INTENSITY_LEVELS.length + intensityIdx,
      breathPhase: Math.random(),  // staggered start
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

function updateBreathing(p: Particle, dt: number): void {
  // Phase advances
  p.breathPhase = (p.breathPhase + p.breathSpeed * dt) % 1

  // Sinusoidal wave: 0→1→0 smooth cycle
  const breathWave = (Math.sin(p.breathPhase * Math.PI * 2) + 1) / 2

  // Synced size + opacity (same phase = physical consistency)
  p.currentRadius = p.baseRadius * (1 + p.breathSizeAmp * breathWave)
  p.currentOpacity = p.baseOpacity * (1 + p.breathOpacityAmp * breathWave)
}

function updateFlowField(p: Particle, dt: number, time: number): void {
  // Noise perturbation: ±15° angle delta
  const noiseVal = simpleNoise2D(
    p.noiseOffsetX + time * 0.05,
    p.noiseOffsetY + time * 0.05
  )
  const noiseDelta = noiseVal * NOISE_ANGLE_DELTA * Math.PI / 180

  // Current velocity angle
  const currentAngle = Math.atan2(p.vy, p.vx)
  const targetAngle = currentAngle + noiseDelta

  // Gradual turn (avoid sudden direction change)
  const newAngle = currentAngle + (targetAngle - currentAngle) * TURN_RATE

  // Speed maintained at driftSpeed, ±5% variation
  const newSpeed = p.driftSpeed * (0.95 + Math.random() * 0.1)

  p.vx = Math.cos(newAngle) * newSpeed
  p.vy = Math.sin(newAngle) * newSpeed

  // Position update
  p.x += p.vx * dt
  p.y += p.vy * dt
}

function wrapEdges(p: Particle, w: number, h: number): void {
  // Margin = halo extent (currentRadius × 5)
  const margin = p.currentRadius * HALO_MARGIN_MULTIPLIER

  if (p.x < -margin) p.x = w + margin
  else if (p.x > w + margin) p.x = -margin

  if (p.y < -margin) p.y = h + margin
  else if (p.y > h + margin) p.y = -margin
}

function updateParticles(particles: Particle[], dt: number, w: number, h: number, time: number): void {
  for (const p of particles) {
    updateBreathing(p, dt)
    updateFlowField(p, dt, time)
    wrapEdges(p, w, h)
  }
}

function drawParticles(
  ctx: CanvasRenderingContext2D,
  particles: Particle[],
  sprites: StarSprite[],
  dpr: number
): void {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  // Sort by depth for proper layering (far first, near last)
  const sorted = [...particles].sort((a, b) => {
    if (a.depth === 'far' && b.depth !== 'far') return -1
    if (a.depth === 'near' && b.depth !== 'near') return 1
    if (a.depth === 'mid' && b.depth === 'far') return 1
    if (a.depth === 'mid' && b.depth === 'near') return -1
    return 0
  })

  for (const p of sorted) {
    const sprite = sprites[p.spriteIndex]
    const spriteCanvas = sprite.canvas

    // Scale: currentRadius (CSS px) × dpr → sprite display size
    // Sprite internal size = 64px, baked at 2× = 128px
    const displaySize = p.currentRadius * dpr * (SPRITE_INTERNAL_SIZE / SPRITE_SIZE) / SPRITE_SIZE
    // Simplified: displaySize = currentRadius × dpr × 2 (since SPRITE_DPR_MAX = 2)
    const finalSize = p.currentRadius * dpr * SPRITE_DPR_MAX

    // Draw position: center the sprite on particle position
    const drawX = p.x * dpr - finalSize / 2
    const drawY = p.y * dpr - finalSize / 2

    ctx.globalAlpha = p.currentOpacity
    ctx.drawImage(spriteCanvas, drawX, drawY, finalSize, finalSize)
  }

  ctx.globalAlpha = 1
}
```

- [ ] **Step 3: Run typecheck to verify particle helpers**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Commit particle helper functions**

```bash
git add src/composables/useDeerField.ts
git commit -m "feat(login): add stellar particle helper functions

- computeParticleCount(): responsive count based on viewport
- assignDepthLayer()/assignColorTemp(): weighted random selection
- initParticleFlow(): counter-clockwise bias initialization
- updateBreathing(): sinusoidal synced size+opacity
- updateFlowField(): noise perturbation, gradual turn
- drawParticles(): sprite-based batch render with depth sort

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Update Composable Main Function

**Files:**
- Modify: `src/composables/useDeerField.ts:319-430` (the `useDeerField` function)

- [ ] **Step 1: Add sprites array to composable state**

Find line 327 (`let particles: Particle[] = []`) and add after it:

```typescript
let sprites: StarSprite[] = []
let animTime = 0
```

- [ ] **Step 2: Update resize() to rebuild particles**

In the `resize()` function, the line `particles = buildParticles(vpW, vpH)` should already be correct. Verify it exists.

- [ ] **Step 3: Update loop() to pass sprites and time**

Replace the `loop()` function (find `function loop(ts: number)` block) with:

```typescript
function loop(ts: number) {
  if (!paused && bgCtx && deerCtx && grid && sprites.length > 0) {
    const dt = lastTime === 0 ? 0.016 : Math.min((ts - lastTime) / 1000, 0.1)
    lastTime = ts
    animTime += dt

    updateParticles(particles, dt, vpW, vpH, animTime)
    drawParticles(bgCtx, particles, sprites, bgDpr)

    flickerGrid(grid.alphas, dt)
    drawGrid(deerCtx, grid)
  }
  rafId = requestAnimationFrame(loop)
}
```

- [ ] **Step 4: Add sprite generation in start()**

In the `start()` function, find the line `resize()` and add after it:

```typescript
// Generate sprite cache (one-time, ~50-80ms)
sprites = buildSprites(bgDpr)
```

- [ ] **Step 5: Clean up sprites in stop()**

In the `stop()` function, add at the end (before the closing brace):

```typescript
sprites = []
animTime = 0
```

- [ ] **Step 6: Run typecheck to verify composable changes**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 7: Commit composable updates**

```bash
git add src/composables/useDeerField.ts
git commit -m "feat(login): integrate stellar sprite system into composable

- Add sprites array and animTime state
- Generate sprite cache in start()
- Pass sprites and time to drawParticles
- Clean up sprites in stop()

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Remove Unused Old Constants and Verify

**Files:**
- Modify: `src/composables/useDeerField.ts`

- [ ] **Step 1: Search for and remove any remaining old particle constants**

After all previous tasks, check if these old constants still exist and remove them:
- `PARTICLE_COUNT_BASE` (old value ~40, different from new 180)
- `STAR_RATIO` (old concept, now using depth layers)
- `STAR_RADIUS_MIN/MAX`, `NORMAL_RADIUS_MIN/MAX` (replaced by depth params)
- `STAR_CYCLE_MIN/MAX`, `NORMAL_CYCLE_MIN/MAX` (replaced by BREATH_SPEED)
- `STAR_OPACITY_MIN/MAX`, `NORMAL_OPACITY_MIN/MAX` (replaced by depth params)
- `STAR_HALO_MULTIPLIER` (now HALO_MARGIN_MULTIPLIER)
- `PARTICLE_COLORS` array (replaced by STELLAR_COLORS)
- Any other star-specific constants from the old system

Run: `grep -n "STAR_RATIO\|NORMAL_RADIUS\|PARTICLE_COLORS\|STAR_CYCLE\|STAR_HALO" src/composables/useDeerField.ts`
Expected: No matches (all removed)

- [ ] **Step 2: Run typecheck to verify clean state**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS with no errors related to `useDeerField.ts`

- [ ] **Step 3: Commit cleanup (if any changes)**

If any unused constants were removed:

```bash
git add src/composables/useDeerField.ts
git commit -m "refactor(login): remove unused old particle constants

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

If no changes needed, skip this commit.

---

### Task 7: Visual Verification and Final Integration

**Files:**
- None (verification only)

- [ ] **Step 1: Start dev server**

Run: `cd frontend/apps/main && npm run dev`

- [ ] **Step 2: Open login page and verify stellar particle effect**

Navigate to `http://localhost:5173/login` and check:

1. **Bright cores:** White center visible on all particles
2. **Irregular halos:** Rays/spikes visible, not uniform radial gradient
3. **Depth layering:** Clear size/opacity/speed differences (far tiny/dim, near large/bright)
4. **Breathing:** Smooth sinusoidal cycle, 3-7s period, synced size+opacity
5. **Flow:** Counter-clockwise trend without centered vortex
6. **Deer silhouette:** Pixel grid + mask still works unchanged
7. **Performance:** Smooth 60fps, no stuttering

- [ ] **Step 3: Test both login stages**

- Step 1 (username/password form): Verify particles animate
- Step 2 (PIN entry): Verify same particle effect continues

- [ ] **Step 4: Test responsive scaling**

Resize browser window and verify particle count adjusts appropriately.

- [ ] **Step 5: Test on mobile viewport**

Use browser DevTools mobile emulation (e.g., iPhone 6/7/8) and verify 60fps performance.

- [ ] **Step 6: Create final summary commit (if needed)**

If any fixes were made during verification:

```bash
git add src/composables/useDeerField.ts
git commit -m "fix(login): stellar particle visual refinements

[describe specific fix]

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Checklist

After completing all tasks:

1. **Spec coverage:**
   - Bright core + irregular rays → Task 3 (generateStarSprite) ✓
   - Color temperature distribution → Task 1 (STELLAR_COLORS) ✓
   - Depth layering → Task 1 (FAR/MID/NEAR constants) + Task 4 (assignDepthLayer) ✓
   - Breathing (synced size+opacity) → Task 4 (updateBreathing) ✓
   - Counter-clockwise flow → Task 4 (initParticleFlow + updateFlowField) ✓
   - Noise perturbation → Task 3 (simpleNoise2D) + Task 4 ✓
   - Sprite cache → Task 3 + Task 5 ✓
   - Deer grid unchanged → Tasks preserve lines 103-144 ✓

2. **Placeholder scan:** No TBD, TODO, or vague instructions ✓

3. **Type consistency:** `Particle` interface matches usage in all functions ✓
   - `depth: 'far' | 'mid' | 'near'` → used in `assignDepthLayer()`, `getDepthParams()`, `drawParticles()` sort
   - `spriteIndex: number` → used in `buildParticles()`, `drawParticles()`
   - `breathPhase/Speed/SizeAmp/OpacityAmp` → used in `updateBreathing()`
   - `vx/vy/noiseOffsetX/noiseOffsetY` → used in `initParticleFlow()`, `updateFlowField()`

4. **Execution:** Subagent-driven-development recommended for parallel task execution with two-stage review.