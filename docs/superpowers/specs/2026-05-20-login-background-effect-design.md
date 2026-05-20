# Login Page Background Effect Design

**Date:** 2026-05-20
**Status:** Approved for implementation

## Overview

Replace the current firefly particle animation on the login page (`/login`) with a DeerFlow-inspired background effect: a visible grid overlay combined with large floating glow blobs that drift and breathe.

## Visual Design

### Grid Pattern
- **Size:** 50px × 50px cells
- **Color:** `rgba(0, 200, 255, 0.08)` — cyan/teal, moderately visible
- **Implementation:** CSS `background-image` with linear-gradient pattern (no canvas)

### Glow Blobs
- **Count:** 4-6 large blobs
- **Size:** 80-150px radius (varies per blob)
- **Color palette:** Cyan/teal variations:
  - `rgba(0, 220, 255, 0.5)` — primary
  - `rgba(50, 255, 220, 0.45)` — secondary
  - `rgba(100, 255, 255, 0.4)` — accent
- **Render:** Canvas radial gradient with blur filter

### Animation Behavior
Each blob combines two effects:

1. **Drift:** Slow ambient movement across screen
   - Speed: 5-15 px/s
   - Direction: Random, with gradual wander changes
   - Edge handling: Wrap around screen edges

2. **Breathing:** Sinusoidal size/opacity pulse
   - Cycle duration: 2-4 seconds (staggered per blob)
   - Size amplitude: 20-40% expansion at peak
   - Opacity amplitude: 30-50% increase at peak
   - Wave shape: Smooth sine wave (no sharp transitions)

### Deer Silhouette Mask
- Retain existing `deerCanvas` with pixel grid effect
- SVG mask applied via CSS `mask-image`
- No changes to deer rendering logic

## Technical Implementation

### Files Modified
| File | Change |
|------|--------|
| `src/composables/useDeerField.ts` | Replace firefly particle system with glow blob system |
| `src/pages/LoginPage.vue` | Add CSS grid pattern to background container |

### Canvas Architecture
- **bgCanvas:** Glow blobs (new implementation)
- **deerCanvas:** Pixel grid + deer mask (unchanged)

### Data Structure
```typescript
interface GlowBlob {
  x: number
  y: number
  baseRadius: number      // 80-150px
  currentRadius: number   // breathing-modulated
  breathPhase: number     // 0..1
  breathSpeed: number     // cycles/s (0.25-0.5)
  breathAmplitude: number // 0.2-0.4
  baseOpacity: number     // 0.35-0.55
  vx: number              // drift velocity
  vy: number
  wanderTimer: number
  wanderInterval: number  // 2-5s
  colorVariant: number    // selects from palette
}
```

### Constants
```typescript
// Blob count at 1080×1920 reference
const BLOB_COUNT_BASE = 5
const REFERENCE_AREA = 2_073_600

// Size range
const BLOB_RADIUS_MIN = 80
const BLOB_RADIUS_MAX = 150

// Drift speed (px/s)
const DRIFT_SPEED_MIN = 5
const DRIFT_SPEED_MAX = 15

// Breathing (2-4s cycle)
const BREATH_SPEED_MIN = 0.25  // 4s cycle
const BREATH_SPEED_MAX = 0.5   // 2s cycle

// Breathing amplitude
const BREATH_SIZE_AMPLITUDE_MIN = 0.2
const BREATH_SIZE_AMPLITUDE_MAX = 0.4
const BREATH_OPACITY_AMPLITUDE_MIN = 0.3
const BREATH_OPACITY_AMPLITUDE_MAX = 0.5

// Wander
const WANDER_INTERVAL_MIN = 2.0
const WANDER_INTERVAL_MAX = 5.5
const WANDER_ANGLE_MAX = Math.PI * 0.65
```

### Rendering Algorithm
```typescript
function drawBlob(ctx, blob, dpr) {
  const x = blob.x * dpr
  const y = blob.y * dpr
  const r = blob.currentRadius * dpr

  // Breathing wave (sinusoidal)
  const breathWave = (Math.sin(blob.breathPhase * Math.PI * 2) + 1) / 2

  // Opacity modulated by breathing
  const opacity = blob.baseOpacity * (1 + breathWave * blob.opacityAmplitude)

  // Select color variant
  const colors = [
    [0, 220, 255],    // cyan
    [50, 255, 220],   // teal
    [100, 255, 255],  // light cyan
  ]
  const [cr, cg, cb] = colors[blob.colorVariant]

  // Radial gradient
  const gradient = ctx.createRadialGradient(x, y, 0, x, y, r)
  gradient.addColorStop(0, `rgba(${cr},${cg},${cb},${opacity.toFixed(2)})`)
  gradient.addColorStop(0.35, `rgba(${cr},${cg},${cb},${(opacity * 0.4).toFixed(2)})`)
  gradient.addColorStop(0.7, `rgba(${cr},${cg},${cb},${(opacity * 0.15).toFixed(2)})`)
  gradient.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)

  ctx.beginPath()
  ctx.arc(x, y, r, 0, Math.PI * 2)
  ctx.fillStyle = gradient
  ctx.fill()
}
```

## Success Criteria

1. **Visual check:** Grid is visible but not overwhelming; blobs feel like aurora/nebula
2. **Animation:** Blobs drift slowly (5-15px/s) while breathing smoothly (2-4s cycle)
3. **Performance:** Frame rate stays above 50fps on mobile devices
4. **Deer mask:** Existing silhouette effect works unchanged

## Implementation Plan

1. Add CSS grid pattern to LoginPage.vue background
2. Refactor `useDeerField.ts`:
   - Remove firefly particle constants and logic
   - Add glow blob constants and data structure
   - Implement `buildBlobs()` initialization
   - Implement `updateBlobs()` with drift + breathing
   - Implement `drawBlobs()` with radial gradient rendering
3. Run `npm run typecheck` to verify
4. Run dev server and visually verify at `/login`

## Notes

- Grid pattern uses CSS, not canvas — simpler and more performant
- Blob system is simpler than firefly: fewer entities, larger sizes
- Breathing uses same sine-wave approach as current firefly implementation
- Color palette matches DeerFlow aesthetic (tech-forward cyan/teal)