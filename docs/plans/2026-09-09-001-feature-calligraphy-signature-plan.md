---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
product_contract_source: ce-brainstorm
product_contract_preservation: unchanged — R1-R6 meaning and IDs preserved; R3 implementation note updated to reflect KTD1 decision
date: 2026-09-09
module: frontend/manifesto
tags: [ceremony, signature, calligraphy, canvas, ux]
applies_when: SignaturePad.vue 渲染管线升级，保持接口不变
---

# Calligraphy Signature Enhancement — Plan

## Summary

**Problem:** The current `SignaturePad.vue` renders all strokes with a uniform-width line (1.5–3px, linear velocity mapping, straight-line segments). The digital signature looks machine-drawn, lacking the warmth and expressiveness of handwriting.

**Approach:** Upgrade the canvas rendering pipeline to simulate fountain-pen calligraphy: (1) smooth Bezier curves replacing straight segments, (2) non-linear velocity-to-width mapping with ease-out curve, (3) tapered stroke ends via deferred tail rendering. Changes apply to both `SignaturePad.vue` (main app) and `ChildSignaturePad.vue` (child app twin). Unit test mock updated for `quadraticCurveTo`. No props interface changes, no new dependencies, no backend changes.

**Key Technical Decisions:**
- KTD1: Taper via deferred tail rendering — buffer last 5 points, render on pointer-up (cleanest visual quality, negligible memory cost)
- KTD2: Bezier control point = previous point, endpoint = midpoint — standard C1 continuity pattern

**Implementation Units:**
- U1: Bezier smoothing + non-linear velocity-width mapping in `onPointerMove`
- U2: Tapered stroke ends via per-stroke point buffering

**Verification:** Visual check across light/dark modes + mobile device + PNG export confirmation.

---

## Problem Frame

Family members sign the manifesto covenant by drawing their signature on a canvas. The current rendering produces uniform-width strokes with angular joints — visually indistinguishable from a basic drawing app. A family covenant deserves a signing experience that feels personal and deliberate. Fountain-pen style calligraphy — smooth curves, gentle width variation, tapered ends — is the minimum expressive threshold for this ceremonial context.

---

## Requirements Trace

All requirements from the requirements-only unified plan are preserved unchanged:

| R-ID | Summary | Covering Unit |
|------|---------|---------------|
| R1 | Quadratic Bezier smoothing | U1 |
| R2 | Non-linear velocity-to-width mapping (sqrt ease-out, 1.0–3.5px) | U1 |
| R3 | Tapered stroke ends (fade-in + fade-out) | U2 |
| R4 | Dark mode compatibility (existing CSS var mechanism) | Verified at integration |
| R5 | `prefers-reduced-motion` compatibility (inherent — no temporal animation) | Verified at integration |
| R6 | Interface preservation (props, events, export unchanged) | Architectural constraint on both U1 and U2 |

---

## Key Technical Decisions

### KTD1: Taper Implementation — Deferred Tail Rendering (session-settled: user-approved)

**Decision:** Buffer all points per stroke; render all except the last TAIL_SIZE (5) points in real-time; on `pointerUp`, render the remaining tail with taper factor applied.

**Alternatives considered:**
- **Approximation** — assume stroke ends after ~20 points and pre-apply fade-out. Risk: visible width discontinuity if stroke ends sooner or later than predicted.
- **Full re-render** — clear canvas and re-draw entire stroke on every frame with updated taper. Risk: expensive for long strokes; requires storing full stroke history + redrawing from scratch.

**Rationale:** Deferred tail uses ~5 points of buffer per stroke (negligible memory). The tail renders once on pointer-up — a single draw operation. Visual quality is identical to full re-render without its cost. Covers R3.

### KTD2: Bezier Control Point Strategy

**Decision:** For each segment, the quadratic Bezier uses the previous point as the control point and the midpoint between previous and current as the endpoint.

**Effect:** Creates C1-continuous curves — the tangent at each join point is automatically aligned because consecutive Bezier segments share a tangent direction through their common midpoint. This is the standard technique for smoothing polyline paths. Covers R1.

---

## Scope Boundaries

### In Scope

- `SignaturePad.vue` (main) and `ChildSignaturePad.vue` (child app twin) internal rendering pipeline: `onPointerDown`, `onPointerMove`, `onPointerUp` handlers
- Velocity-to-width mapping curve and range
- Per-stroke point buffering for taper
- Unit test mock update (`quadraticCurveTo: vi.fn()`)
- Visual verification across light/dark modes and PNG export

### Deferred for Later

- Filled ribbon rendering pipeline (Approach B from ideation) — only if more extreme width variation is needed in the future
- Ink bleed / directional thickness effects — brush calligraphy characteristics, not part of fountain-pen style

### Outside this Product's Identity

- Wax seal animation (Idea 5 from ideation) — independent value point, requires separate brainstorm
- Props interface changes — the component's public contract is fixed per R6

---

## Implementation Units

### U1. Bezier Smoothing + Non-Linear Velocity Mapping

**Goal:** Replace straight-line rendering with smooth Bezier curves and upgrade velocity-to-width mapping from linear to non-linear ease-out.

**Requirements:** R1 (Bezier smoothing), R2 (non-linear velocity-width mapping)

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/components/manifesto/SignaturePad.vue` — modify `onPointerMove` handler
- `frontend/apps/child/src/components/manifesto/ChildSignaturePad.vue` — mirror identical changes (twin component)
- `frontend/apps/main/tests/unit/components/SignaturePad.spec.ts` — add `quadraticCurveTo: vi.fn()` to `mockCtx` (line ~15-26)

**Approach:**

1. In `onPointerMove`, replace `ctx.lineTo(pos.x, pos.y)` with `ctx.quadraticCurveTo(lastX, lastY, midX, midY)` where `midX = (lastX + pos.x) / 2` and `midY = (lastY + pos.y) / 2`. The previous point serves as the Bezier control point; the midpoint serves as the endpoint. Per KTD2.
2. Replace the linear velocity-to-width formula with non-linear ease-out:
   - `referenceVelocity = 2.0` (px/ms, tunable constant)
   - `normalizedVelocity = clamp(velocity / referenceVelocity, 0, 1)`
   - `lineWidth = 1.0 + 2.5 * (1 - sqrt(normalizedVelocity))`
   - Range: 1.0px (fast) to 3.5px (slow)
3. Initialize `lastMidX/lastMidY` on `onPointerDown` to avoid a null first segment.

**Patterns to follow:** Existing velocity calculation at `SignaturePad.vue:99-107` (keep the velocity computation logic, only change the width derivation).

**Test scenarios:**
- Draw a slow straight line → width should be close to 3.5px, smoothly uniform
- Draw a fast flick → width should taper to ~1.0px at the fast segment
- Draw a curved path (letter "S") → no visible angular joints at pointer sample boundaries
- Width transitions should be gradual, not step-like (sqrt curve vs old linear)
- Existing unit tests still pass after mockCtx gains `quadraticCurveTo` stub

**Verification:** Visual comparison with the previous rendering — Bezier curves should eliminate polygonal appearance; width variation should be more expressive across speed range.

---

### U2. Tapered Stroke Ends

**Goal:** Each stroke (pointer-down to pointer-up) tapers at both ends — gradually narrowing at the start (pen touchdown) and end (pen liftoff) — simulating fountain-pen behavior.

**Requirements:** R3 (tapered stroke ends)

**Dependencies:** U1 (uses the updated width calculation from U1)

**Files:**
- `frontend/apps/main/src/components/manifesto/SignaturePad.vue` — modify `onPointerDown`, `onPointerMove`, `onPointerUp` handlers; add stroke buffer ref
- `frontend/apps/child/src/components/manifesto/ChildSignaturePad.vue` — mirror identical changes (twin component)

**Approach:**

1. Add a `strokeBuffer: { x: number, y: number, width: number }[]` ref to track all points in the current stroke, including their computed width.
2. On `onPointerDown`: clear `strokeBuffer`.
3. On `onPointerMove`: push the new point (with computed width from U1's mapping) into `strokeBuffer`. Render all segments except the last TAIL_SIZE (5) using Bezier curves from U1. The last TAIL_SIZE points are held in the buffer, not yet drawn.
4. On `onPointerUp`: render the remaining tail segments with taper factor applied:
   - For the tail (last min(TAIL_SIZE, remaining) points), compute `taperFactor = (i + 1) / tailLength`
   - Multiply each segment's width by its taperFactor (width goes from full → 0)
   - If total stroke length < 2 × TAIL_SIZE, the fade-in and fade-out overlap — compute both factors and use the minimum: `factor = min(fadeInFactor, fadeOutFactor)`
5. Define `TAIL_SIZE = 5` as a module-level constant.

**Edge cases:**
- Very short strokes (< 5 points): apply combined taper (fadeIn × fadeOut overlap)
- Extremely fast strokes: taper still applies based on point count, not time
- `onPointerUp` with empty or single-point buffer: no-op

**Patterns to follow:** Existing pointer handler structure at `SignaturePad.vue:80-120`. The `drawing` flag already tracks stroke lifecycle — use it to guard buffer operations.

**Test scenarios:**
- Covers AE2. Draw a single stroke → first ~5 points should gradually widen from 0 to full width (fade-in)
- Covers AE2. Draw a single stroke → last ~5 points should gradually narrow from full width to 0 (fade-out)
- Draw a very short stroke (2–3 points) → should show combined taper without artifacts
- Lift finger without moving (single-point stroke) → no crash, no visible output

**Verification:** Visual inspection confirms smooth taper at both ends of every stroke. No abrupt width changes at stroke start or end.

---

## Verification Contract

| Gate | Method | Criteria |
|------|--------|----------|
| AE1 (straight line smoothing) | Visual: draw straight line, inspect for joints | No angular transitions; curve is C1-continuous |
| AE2 (tapered signature "张伟") | Visual: write name, inspect start/end of each stroke | Gradual fade-in at start, fade-out at end |
| AE3 (export verification) | Visual: export PNG → embed in ClassicTemplate preview on both light and dark backgrounds | No white halo, no invisible ink, signature legible |
| Dark mode visual | Visual: switch to dark mode, sign, verify ink color | Ink follows `--color-ink` via `getCSSVariableValue`; no inline-style specificity issue |
| Mobile performance | Smoke: sign normally on a low-end mobile device | No perceptible frame drops during drawing |
| Interface preservation | Code review: diff confirms only internal handler logic changed | Props, events, emit payload unchanged; `ManifestoSignPage.vue` untouched |
| Child twin sync | Code review: `ChildSignaturePad.vue` matches `SignaturePad.vue` rendering logic | Both components produce identical calligraphy output |
| Unit test pass | `pnpm --filter main test:unit -- SignaturePad` | Existing tests pass with updated `quadraticCurveTo` mock |

---

## Definition of Done

- [ ] R1–R6 all implemented and verified
- [ ] All visual verification gates pass (Verification Contract table above)
- [ ] Exported PNG quality matches or exceeds the previous rendering on both light and dark backgrounds
- [ ] No props, events, or parent component changes (R6)
- [ ] `ChildSignaturePad.vue` synced with `SignaturePad.vue` (twin parity)
- [ ] Unit test passes (`SignaturePad.spec.ts` with `quadraticCurveTo` mock)
- [ ] Both `SignaturePad.vue` and `ChildSignaturePad.vue` pass lint and type check
