---
title: TikTok-style Loading Effect Refactor
date: 2026-05-27
status: draft
type: refactor
scope: frontend/packages/auth
affects:
  - frontend/apps/main
  - frontend/apps/child
---

# TikTok-style Loading Effect Refactor

## Problem

The existing full-screen loading overlay (`@numina/auth` → `LoadingOverlay` + `MusicWaveCanvas` + `GlassMask`) covers route transitions and axios pending requests across both `frontend/apps/main` and `frontend/apps/child`. It uses a 4-color neon cyber palette (`#00d4ff` / `#b967ff` / `#ff2a6d` / `#05ffa1`) and emits Canvas-drawn ripples from an empty center.

Gaps vs the requested visual direction (product owner requested; current 4-color palette reads as generic — TikTok aesthetic differentiates the loading moment):

1. No center "source" — ripples emerge from nothing.
2. No subwoofer pulse — center has no bass-rhythm cue.
3. Palette is 4-color cyber, not the requested TikTok 2-color (`#00f2fe` cyan / `#fe0979` neon red).
4. `GlassMask` backdrop is hardcoded dark tint — no light-mode adapter.
5. Canvas does not switch composite operations by theme — no `screen` / `multiply` blend.
6. `prefers-reduced-motion` media query is not honored.
7. Exit timing is 400ms; spec asks for 300ms.
8. Sizing uses pixel + DPR; not `vmin`-driven so phone vs desktop don't share the same visual weight.

## Goals

Refactor the visual layer (Canvas drawing + GlassMask tint) of the existing loading overlay to:

- Center abstract concentric core with ≈1.6Hz subwoofer pulse.
- TikTok 2-color palette (`#00f2fe` cyan + `#fe0979` neon red), alternating per ripple ID.
- Per-stroke `globalCompositeOperation = 'screen'` (dark) / `'multiply'` (light); GlassMask flips tint accordingly.
- Light-mode palette desaturated (`#00b8c8` / `#d61b6e`) to avoid muddy multiply crossings.
- `prefers-reduced-motion` branch: core slow-breath only (≈1Hz, ±3% scale), no ripples.
- 300ms exit (was 400ms).
- All sizing in `vmin` units so phone (≈375px) and desktop (≥1440px) maintain identical visual weight.

## Non-goals

- ❌ Modify `useLoadingOverlay` state machine (debounce / min-display / watchdog).
- ❌ Modify router guards or axios interceptor wiring.
- ❌ Change `<LoadingOverlay>` mount points in `App.vue`.
- ❌ Modify existing tests in `composables/__tests__/loading.spec.ts`.
- ❌ Pre-render to OffscreenCanvas / Worker. Current main-thread RAF is sufficient.
- ❌ Switch to WebGL / three.js. Bundle cost not justified for a loading effect.
- ❌ Add a parallel/feature-flagged variant. The existing component **is** the loading effect; revert PR if regression.

## Files touched

```
frontend/packages/auth/src/components/LoadingOverlay.vue   ← exit timing only
frontend/packages/auth/src/components/GlassMask.vue        ← theme-aware backdrop
frontend/packages/auth/src/components/MusicWaveCanvas.vue  ← bulk of changes
```

No new files. No new dependencies. No changes outside `frontend/packages/auth/`.

## Architecture

### ARIA / screen reader

The existing `LoadingOverlay.vue` declares `aria-live="polite"` and `aria-label="加载中"` on a generic `<div>`. Add `role="status"` to the same element so the announcement has a semantic landmark (`role="status"` implies `aria-live="polite"`; keep the explicit attribute for legacy AT). The canvas keeps `aria-hidden="true"` (unchanged). No other ARIA changes.

### Component tree (unchanged)

```
LoadingOverlay.vue
├── <GlassMask />          ← reads <html data-theme>, flips backdrop tint
└── <MusicWaveCanvas />    ← single 2D canvas, two draw layers
        ├── drawCore()       runs once/frame — halo disc + inner ring + pulse
        └── drawRipple()     runs per ripple in state.ripples
```

### State (unchanged, owned by `useLoadingOverlay`)

`isLoading` and `isDismissing` come from the existing composable. Refactor does not touch debounce, min-display, watchdog, or HMR singleton logic.

### Theme detection

### GlassMask theme detection (CSS-only — no JS observer needed)

GlassMask is a pure CSS component. Theme switching uses CSS selectors on `data-theme` — the same pattern used throughout `style.css`. No MutationObserver needed:

```css
.glass-mask {
  background: rgba(255, 255, 255, 0.42);
  backdrop-filter: blur(12px) saturate(1.2);
}
.glass-mask.no-backdrop {
  background: rgba(245, 245, 255, 0.88);
}
[data-theme='dark'] .glass-mask {
  background: rgba(1, 1, 32, 0.52);
  backdrop-filter: blur(12px) saturate(1.4);
}
[data-theme='dark'] .glass-mask.no-backdrop {
  background: rgba(1, 1, 32, 0.82);
}
```

### MusicWaveCanvas theme detection (MutationObserver)

MusicWaveCanvas needs a JS-side observer because Canvas2D has no CSS inheritance — blend mode and palette must be read from a reactive ref inside the draw loop:

```ts
const isDark = ref(document.documentElement.dataset.theme === 'dark')
const themeObserver = new MutationObserver(() => {
  isDark.value = document.documentElement.dataset.theme === 'dark'
})
onMounted(() => {
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
})
onUnmounted(() => themeObserver.disconnect())
```

The Canvas reads `p.value` from the computed reference and trusts the observer to keep it fresh — no per-frame `data-theme` polling.

### Reduced-motion detection

```ts
const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
const prefersReduced = ref(reduceQuery.matches)
const onChange = (e: MediaQueryListEvent) => { prefersReduced.value = e.matches }
onMounted(() => reduceQuery.addEventListener('change', onChange))
onUnmounted(() => reduceQuery.removeEventListener('change', onChange))
```

When `prefersReduced.value === true`: `drawRipple()` early-returns; `drawCore()` runs with slower/smaller pulse parameters. Effective FPS drops to ≤10 (100ms frame interval) to reduce compute on devices where the user opted out of motion. When `prefersReduced && dismissing`: skip the scale shrink — fade core alpha `1.0 → 0` linearly over 300ms with no scale change (scale animation is itself a vestibular trigger).

## Animation parameters

All sizing is `vmin`-derived. Compute once on resize:

```ts
// W and H are already physical pixels (canvas.width = parent.clientWidth * DPR).
// Dividing by 100 yields 1 physical vmin directly — do NOT multiply by DPR again.
const unit = Math.min(W, H) / 100
```

All multipliers below are in `unit`, never raw `px`.

### Core (center node)

| Param | Value | Notes |
|---|---|---|
| Halo outer radius | `6 * unit` | ≈22.5px on phone, ≈86px on desktop |
| Halo inner radius | `1.5 * unit` | solid bright center |
| Inner ring radius | `4 * unit` | 1px stroke at 60% opacity |
| Halo gradient | radial `cyan @0.0 → red @0.4 → transparent @1.0` | hue cycles slowly (≈0.05°/frame) |
| Pulse scale | `1 + sin(globalTime * 10) * 0.04` | ≈1.6Hz, ±4% |
| Pulse alpha | `0.85 + sin(globalTime * 10) * 0.15` | 0.7 → 1.0 breath |

`1.6Hz` ≈ a typical sub-bass kick at ~100bpm half-time; chosen because it maps to muscle-memory of music tempo.

### Ripples

| Param | Value | Notes |
|---|---|---|
| `MAX_RIPPLES` | 6 (low-end: 4) | reduced from current 8/5 because per-stroke blend adds cost |
| `WAVE_LIFETIME` | 2800ms | shortened from 3200ms for snappier rhythm |
| `baseRadius` | `8 * unit` | starts just outside the halo |
| `speed` (4 layers) | `[14, 18, 22, 28] * unit / sec` | staggered ≈30% apart |
| `amplitude` (4 layers) | `[5, 4, 3, 2] * unit` | outer rings flatter |
| `frequency` (lobes) | `[6, 8, 10, 13]` | unchanged from existing fractal-noise math |
| `lineWidth` | `[0.8, 0.6, 0.45, 0.3] * unit` | ≈3px phone / ≈11px desktop on outermost |
| Spawn cadence | `320 + sin(globalTime * 0.8) * 100` ms | changed from current 360/120 base/pulse for tighter rhythm; `globalTime` in seconds |

### Palette (alternates by `rippleId % 2`)

```ts
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
}
```

Light palette is ~80% lightness of the dark palette at the same hue. Glow alpha is dropped from `0.55` → `0.30` in light mode to prevent backdrop wash-out.

### Glow strength tiers (kept from existing impl)

| Tier | Outer "halo stroke" pass | Main stroke `shadowBlur` |
|---|---|---|
| High-end | enabled, `globalAlpha = 0.45`, lineWidth × 2.5 | `8 * DPR` |
| Low-end (`hardwareConcurrency ≤ 2` or `deviceMemory ≤ 2`) | **disabled** | `0` |

Single biggest perf knob. Low-end detection is unchanged from current implementation.

### Reduced-motion branch

```ts
function drawFrame(now: number) {
  if (prefersReduced.value) {
    drawCore({ pulseFreq: 6.28, pulseAmp: 0.03, cycleHue: false })  // ~1Hz, ±3%
    return  // skip ripple spawn + draw entirely
  }
  drawCore({ pulseFreq: 10, pulseAmp: 0.04, cycleHue: true })
  spawnAndDrawRipples()
}
```

### Draw loop contract

`drawFrame()` begins with `ctx.clearRect(0, 0, W, H)` before any draw call. `globalCompositeOperation` resets to `source-over` after each stroke group to prevent blend leakage between `drawCore` and `drawRipple` layers.

## Light/dark adapter

Three things flip on theme change:

| Element | Dark mode | Light mode |
|---|---|---|
| `GlassMask` backdrop | `rgba(1, 1, 32, 0.52)` + `blur(12px) saturate(1.4)` | `rgba(255, 255, 255, 0.90)` + `blur(12px) saturate(1.2)` |
| `GlassMask` no-backdrop fallback | `rgba(1, 1, 32, 0.82)` | `rgba(245, 245, 255, 0.88)` |
| Canvas `globalCompositeOperation` | `'screen'` | `'multiply'` |
| Stroke + glow palette | full neon | desaturated 80% lightness |

`globalCompositeOperation` is set per stroke from `p.value.blend`. When `isDark` flips, the MutationObserver updates the ref → `p` recomputes → next RAF tick uses the new blend mode. Mid-session theme switches adapt within one frame — no remount.

### Why per-mode palette is necessary

`screen` brightens: full-saturation cyan + red overlapping → luminous purple-white. Reads as glowing流光 on dark backdrop.

`multiply` darkens: full-saturation cyan + red overlapping → near-black at crossings. Reads as "dirty" on light backdrop. Desaturating to `#00b8c8` and `#d61b6e` (same hue, ~80% lightness) keeps multiplied crossings as deep teal-and-burgundy rather than mud. **Note:** `multiply` produces predictable results only when the composite surface is near-white. The light-mode GlassMask opacity is raised to 0.90 so the backing is effectively white — at lower opacities the underlying page content shows through and `multiply` behaves inconsistently.

## Exit sequence (300ms)

When `useLoadingOverlay.hide()` sets `isDismissing.value = true`, the canvas starts a choreographed exit. 300ms later, `<Transition>` unmounts the overlay.

| Time (ms) | Core | Ripples | GlassMask |
|---|---|---|---|
| 0 | scale 1.0, alpha 1.0 | continue spawning until t=0 mark | full blur |
| 0–80 | spawn stops; in-flight ripples continue their lifecycle | — | — |
| 80–220 | scale 1.0 → 0.6, alpha 1.0 → 0.4 | alpha multiplied by `(1 - dismissProgress * 1.5)`, amplitude shrinks | unchanged |
| 220–300 | scale 0.6 → 0, alpha 0.4 → 0 | all dropped (`lifeProgress > 0.8 && dismissing`) | opacity 1.0 → 0 |
| 300 | overlay unmounted | — | — |

All three layers (core, ripples, mask) reach zero simultaneously at t=300ms. No pop.

### State machine reconciliation

`useLoadingOverlay`'s `MIN_DISPLAY_MS = 400` stays. The 300ms exit animation runs **inside** the min-display tail when applicable. Visually: as soon as `isDismissing = true`, the canvas starts collapsing — the overlay never appears "frozen waiting" for min-display to expire.

### CSS timing

`LoadingOverlay.vue`:
```diff
- .overlay-leave-active { transition: opacity 0.35s ease 0.45s; }
+ .overlay-leave-active { transition: opacity 0.3s ease 0s; }
```

`MusicWaveCanvas.vue`:
```diff
- state.dismissProgress = Math.min(1, (now - state.dismissStart) / 400)
+ state.dismissProgress = Math.min(1, (now - state.dismissStart) / 300)
```

**Both the duration (`0.35s → 0.3s`) and the delay (`0.45s → 0s`) must change in the `LoadingOverlay.vue` edit above. Changing only the duration leaves the 0.45s delay intact, producing a 750ms total exit — not the intended 300ms.**

## Edge cases

| Case | Handling |
|---|---|
| Theme switch mid-loading | MutationObserver fires → palette/blend swap on next frame. No remount. |
| `prefers-reduced-motion` toggled mid-session | `matchMedia.change` listener flips ref → next frame skips ripple spawn, core slows. |
| Tab backgrounded | RAF auto-pauses (browser). On refocus, existing `state.lastSpawn = now` guard prevents accumulated-time burst. |
| Fast theme flicker | MutationObserver coalesces to next-frame read. Worst case 1 frame mismatched ≈16ms. |
| `globalCompositeOperation` unsupported | Universal support; no fallback needed. Failure would already mean Canvas2D missing. |
| `backdrop-filter` unsupported | Existing `.no-backdrop` fallback extended for light mode. |
| Watchdog fires (30s) | `isVisible = false` instantly; `<Transition>` unmounts canvas. Watchdog bypasses the choreographed 300ms exit (hard cut is acceptable for a timeout error state). |
| Canvas exit completes before `isVisible` flips | When `remaining > 300ms` (MIN_DISPLAY_MS not yet elapsed), canvas reaches zero at t=300ms but overlay stays mounted for up to ~100ms more. Acceptable — `clearRect` + no draws produces a blank frame. |
| HMR during dev | Existing `import.meta.hot?.data` singleton preserves state. Unchanged. |
| User navigates mid-dismiss | Canvas unmounts before exit completes; next page renders. Acceptable for sub-300ms case. |

## Integration points (verify, do not change)

| Trigger | File | Mechanism |
|---|---|---|
| Route navigation | `frontend/apps/main/src/router/index.ts` | `beforeEach` → `useLoadingOverlay().show()`, `afterEach` → `.hide()` |
| Axios | `frontend/apps/main/src/api/index.ts` | `increment()` / `decrement()` |
| Child app navigation | `frontend/apps/child/src/router/index.ts` | same pattern |

Mount points:
- `frontend/apps/main/src/App.vue` — must contain `<LoadingOverlay />` at root.
- `frontend/apps/child/src/App.vue` — same.

## Performance budget

Before claiming done, manually verify all 3:

1. **Phone (375px viewport, 4× CPU throttle in DevTools)** — RAF holds 30fps minimum during steady-state ripple emission.
2. **Desktop (1440px, no throttle)** — RAF holds 60fps with all 6 ripples + glow.
3. **Theme toggle during loading** — no flash, no canvas clear, palette swaps within 1 frame.

Quality gates:
- `cd frontend/apps/main && npm run typecheck` passes.
- `cd frontend/apps/main && npm run lint` passes.
- `cd frontend/apps/main && npm run test:run` passes without test changes.
- `cd frontend/apps/child && npm run typecheck` passes.
- `cd frontend/apps/child && npm run test:run` passes without test changes.

## Test strategy

Existing tests in `composables/__tests__/loading.spec.ts` assert the state machine (debounce, min-display, watchdog, dismiss-flip reactivity). **No changes needed** — none of them depend on exit duration or visual layer.

No new unit tests for the Canvas drawing. Visual verification is manual. Reasoning: canvas pixel output is not meaningfully unit-testable in jsdom, and adding a snapshot test of `MusicWaveCanvas` mount would only assert "canvas element exists" which doesn't catch regressions worth blocking on.

## Rollout

Single PR. No feature flag. No parallel variant. Existing `LoadingOverlay` is the only loading effect, so there's nothing to A/B against.

Rollback: revert PR. State machine and integration points are untouched, so revert is clean.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Light-mode multiply crossings still read "dirty" on some screens | medium | Desaturated palette + reduced glow alpha + GlassMask at 0.90 opacity address this; manual check at light backdrop is part of perf budget. |
| 1.6Hz core pulse feels seizure-inducing for sensitive users | low | `prefers-reduced-motion` branch covers this — pulse drops to ≈1Hz, ripples removed. |
| Per-stroke `globalCompositeOperation` cost noticeable on low-end | low | Low-end path already skips outer-halo pass; `MAX_RIPPLES = 4` on low-end caps total composite ops. |
| TikTok palette clashes with Numina brand tokens (`#010120` midnight) | medium | Accepted — user explicitly chose strict TikTok palette in clarification Q1. Loading is treated as a "branded moment", not persistent chrome. |
| Bundle-size regression | none | No dependency added; net diff is <100 lines in 3 existing files. |

## Open questions

None at spec-write time. All clarifications were resolved in brainstorm Q1–Q4:

- Q1: TikTok palette wins over brand-token interpretation.
- Q2: Center is abstract concentric core (no literal note/speaker icon).
- Q3: Per-stroke `globalCompositeOperation` (not element-level blend).
- Q4: Reduced-motion = slow-breath core only, no ripples.

If any of these need to be revisited, this spec must be updated before planning.
