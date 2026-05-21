# Login Page Stellar Particle Animation Design

**Date:** 2026-05-21
**Status:** Approved for implementation
**Supersedes:** 2026-05-20-login-background-effect-design.md

## Overview

Replace the current stellar pulsation particle system on the login page (`/login`) with a physically accurate stellar particle animation: bright cores with irregular radiating halos, sinusoidal breathing (synced size + opacity), 3D depth layering, and global counter-clockwise drift with noise perturbation.

## Scope

| Component | Action |
|-----------|--------|
| `bgCanvas` (particle layer) | Full rewrite |
| `deerCanvas` (鹿剪影层) | Keep unchanged |
| `LoginPage.vue` | No changes |

## Visual Design

### Particle Appearance

Each particle simulates a stellar light source:

1. **Core:** Ultra-bright white point (diameter ~8px internal), radial gradient from pure white → color temperature blend
2. **Irregular Radiating Halo:** 8-14 light rays with randomized length (60%-140% of base radius), width (2-6px), and opacity (12%-27%), creating organic "star spikes"
3. **Circular Glow Underlayer:** Soft radial gradient underneath rays, 35% opacity at core edge fading to 0 at halo edge

### Color Temperature Distribution (Realistic Stellar)

| Spectral Type | % | Core RGB | Halo RGB |
|---------------|---|----------|----------|
| O/B (蓝白巨星) | 15% | `255,255,255` | `180,210,255` |
| A (白色) | 30% | `255,255,255` | `230,235,255` |
| G (黄/类太阳) | 30% | `255,250,235` | `255,230,180` |
| K (橙色) | 20% | `255,235,210` | `255,200,150` |
| M (红巨星) | 5% | `255,220,200` | `255,170,120` |

### 3D Depth Layering

| Layer | % | Base Radius | Base Opacity | Drift Speed | Visual Feel |
|-------|---|-------------|--------------|-------------|-------------|
| far (远景) | 50% | 0.5-1.2px | 0.25-0.45 | 3-6 px/s | Tiny, dim, nearly static |
| mid (中景) | 35% | 1.2-2.2px | 0.45-0.65 | 8-14 px/s | Medium brightness, slow drift |
| near (近景) | 15% | 2.2-3.8px | 0.65-0.90 | 15-25 px/s | Large, bright, visible flow |

### Breathing (Sinusoidal Pulsation)

- **Cycle:** 3-7 seconds per particle (randomized: `breathSpeed = 0.15-0.35 cycles/s`)
- **Size amplitude:** 20%-45% expansion at peak
- **Opacity amplitude:** 30%-55% increase at peak
- **Critical:** Size and opacity share the same `breathWave` phase — ensures physical consistency (no "big but dim" or "small but bright" artifacts)

### Global Flow Field

- **Pattern:** Diffuse drift with counter-clockwise bias + noise perturbation (not centered vortex)
- **Mechanism:** Each particle's initial drift angle = (angle toward screen center) + 30-60° left offset → overall counter-clockwise trend
- **Noise:** Lightweight pseudo-Perlin noise (`simpleNoise2D`) adds ±15° angle perturbation per frame
- **Edge handling:** Smooth wrap-around with halo margin (no sudden pop-in/out)

## Technical Implementation

### Architecture

```
LoginPage.vue
├── bgCanvas (z:0) — Stellar particles (useDeerField.ts, rewritten)
│   ├── Sprite cache generation (offline, 16 variants)
│   ├── Breathing update (math only)
│   ├── Flow field update (math + noise)
│   └── drawImage batch render
├── deerCanvas (z:1) — Deer silhouette (unchanged)
│   ├── Pixel grid + flicker
│   └── SVG mask (blob URL)
└── login-content (z:2) — Form/PIN
```

### Rendering Approach: Canvas 2D + Offline Sprite Cache

**Why not WebGL:** Medium density (150-200 mobile) is within Canvas 2D capability; WebGL adds complexity and dependency cost for minimal benefit.

**Sprite Cache Strategy:**

- Generate 16 star sprite variants at startup: 5 color temps × 3 intensities × rotation (dynamic via drawImage)
- Each sprite: 128×128 canvas (2× DPR), containing core + irregular rays + circular glow
- Frame loop: Only `drawImage(sprite, x, y, size, size)` + `globalAlpha` — no per-frame gradient/ray computation

**Sprite Generation Algorithm:**

```typescript
function generateStarSprite(colorTemp, intensity, rotationDeg): Canvas {
  // 1. Core: radial gradient, white center → color temp blend
  // 2. Irregular rays: 8-14 rays, random length/width/opacity, linear gradient fade
  // 3. Circular glow underlayer: radial gradient, 35% → 0
  // Rotation applied at drawImage time, not baked into sprite
}
```

### Particle Data Model

```typescript
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
  spriteIndex: number  // 0..15

  // Breathing (independent random seeds)
  breathPhase: number      // 0..1
  breathSpeed: number      // cycles/s
  breathSizeAmp: number    // 0.20-0.45
  breathOpacityAmp: number // 0.30-0.55

  // Flow field state
  vx: number
  vy: number
  noiseOffsetX: number
  noiseOffsetY: number

  // Derived (per-frame)
  currentRadius: number
  currentOpacity: number
}
```

### Flow Field Algorithm

```typescript
function initParticleFlow(p, w, h) {
  // Angle toward screen center
  const toCenterAngle = atan2(h/2 - p.y, w/2 - p.x)

  // Counter-clockwise bias: +30-60° left offset
  const biasOffset = (30 + random()*30) * PI/180

  // Base drift direction = away from center + left offset
  const baseAngle = toCenterAngle + biasOffset + PI

  // Add random noise (±40°)
  const noiseAngle = baseAngle + (random()-0.5) * 80 * PI/180

  p.vx = cos(noiseAngle) * p.driftSpeed
  p.vy = sin(noiseAngle) * p.driftSpeed
}

function updateParticleFlow(p, dt, time) {
  // Noise perturbation: ±15° angle delta
  const noiseVal = simpleNoise2D(
    p.noiseOffsetX + time * 0.05,
    p.noiseOffsetY + time * 0.05
  )
  const noiseDelta = noiseVal * 15 * PI/180

  // Gradual turn (avoid sudden direction change)
  const currentAngle = atan2(p.vy, p.vx)
  const targetAngle = currentAngle + noiseDelta
  const newAngle = currentAngle + (targetAngle - currentAngle) * 0.08

  // Speed maintained at driftSpeed, ±5% variation
  const newSpeed = p.driftSpeed * (0.95 + random()*0.1)

  p.vx = cos(newAngle) * newSpeed
  p.vy = sin(newAngle) * newSpeed
  p.x += p.vx * dt
  p.y += p.vy * dt
}
```

### Lightweight Noise Function

```typescript
function simpleNoise2D(x: number, y: number): number {
  const v1 = sin(x * 0.01) * cos(y * 0.01)
  const v2 = sin(x * 0.02 + 1.5) * cos(y * 0.015 + 0.7)
  const v3 = sin(x * 0.005 + y * 0.008)
  return (v1 + v2 * 0.5 + v3 * 0.25) / 1.75  // normalize to -1..1
}
```

### Breathing Update

```typescript
function updateBreathing(p, dt) {
  p.breathPhase = (p.breathPhase + p.breathSpeed * dt) % 1

  // Sinusoidal: 0→1→0 smooth cycle
  const breathWave = (sin(p.breathPhase * PI * 2) + 1) / 2

  // Synced size + opacity (same phase = physical consistency)
  p.currentRadius = p.baseRadius * (1 + p.breathSizeAmp * breathWave)
  p.currentOpacity = p.baseOpacity * (1 + p.breathOpacityAmp * breathWave)

  return breathWave
}
```

### Rendering Loop

```typescript
function drawParticles(ctx, particles, sprites, dpr) {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  for (const p of particles) {
    const scale = p.currentRadius * dpr / 64  // sprite internal size = 64px
    const alpha = p.currentOpacity

    ctx.globalAlpha = alpha
    ctx.drawImage(
      sprites[p.spriteIndex],
      p.x * dpr - scale * 64 / 2,
      p.y * dpr - scale * 64 / 2,
      scale * 64,
      scale * 64
    )
  }
  ctx.globalAlpha = 1
}
```

### Particle Count (Responsive)

| Device | Width | Count | Sprite DPR |
|--------|-------|-------|------------|
| Low-end mobile | <375px | 90-120 | 1× |
| Mobile | 375-767px | 150-200 | 1× or 2× |
| Tablet | 768-1279px | 250-320 | 2× |
| Desktop | ≥1280px | 350-420 | 2× |

```typescript
function computeParticleCount(w, h): number {
  if (w >= 1280) return min(420, 180 * sqrt(area / (375*668)))
  if (w >= 768)  return min(320, 180 * sqrt(area / (375*668)))
  return round(180 * clamp(h/668, 0.85, 1.15))
}
```

### DPR Handling

```typescript
const dpr = min(devicePixelRatio, 2)  // cap at 2× to save memory
bgCanvas.width = vw * dpr
bgCanvas.height = vh * dpr

// Sprites baked at 128×128 (2× internal 64×64)
// Display: scale = currentRadius × dpr / 64
```

### Performance Budget (Target 60fps)

| Operation | Est. Time (200 particles, mobile) |
|-----------|----------------------------------|
| Sprite generation (one-time) | 50-80ms (startup) |
| Breathing update | 0.8ms |
| Flow field update | 1.2ms |
| drawImage batch | 3-5ms |
| Deer grid update | 0.5ms |
| **Total per frame** | **5-7ms** (余量 >10ms) |

**Memory:** <2MB (16 sprites × 64KB + particle array + grid)

### Low-End Device Degradation

```typescript
const isLowEnd = navigator.hardwareConcurrency <= 2 ||
                 (navigator.deviceMemory || 4) < 2

if (isLowEnd) {
  particleCountFactor = 0.6     // 150 → 90
  useNoisePerturbation = false  // linear drift only
}
```

### Accessibility

Existing `prefers-reduced-motion` support in `LoginPage.vue` disables both canvases.

## Files Modified

| File | Change |
|------|--------|
| `src/composables/useDeerField.ts` | Rewrite particle system (constants, sprite generation, particle model, flow field, breathing, render loop); keep deer grid section unchanged |
| `src/pages/LoginPage.vue` | No changes |

## Success Criteria

1. **Visual:** Particles look like stellar light sources with bright white cores + organic irregular halos
2. **Depth:** Clear far/mid/near distinction via size/opacity/speed
3. **Breathing:** Smooth sinusoidal cycle, synced size+opacity, 3-7s per particle
4. **Flow:** Overall counter-clockwise trend without centered vortex; organic noise perturbation
5. **Performance:** 60fps stable on mid-range mobile (150-200 particles)
6. **Responsive:** Particle count and DPR scale appropriately across devices
7. **Deer mask:** Existing silhouette effect works unchanged

## Implementation Plan

1. Rewrite `useDeerField.ts`:
   - Add sprite generation constants and `generateStarSprite()` function
   - Add `buildSprites()` call in `start()`
   - Replace particle constants with new depth/color/breathing values
   - Replace `Particle` interface with new model
   - Replace `buildParticles()` with depth-aware initialization + flow init
   - Replace `updateParticles()` with breathing + flow field updates
   - Replace `drawParticles()` with sprite-based drawImage batch
   - Keep `buildGrid/flickerGrid/drawGrid/applyMask` unchanged
2. Run `npm run typecheck` to verify
3. Run dev server and visually verify at `/login` (both Step 1 and Step 2)