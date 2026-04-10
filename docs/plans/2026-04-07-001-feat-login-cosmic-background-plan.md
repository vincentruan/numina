---
title: feat: Login page cosmic star background animation
type: feat
status: active
date: 2026-04-07
---

# feat: Login page cosmic star background animation

## Overview

Implement a lightweight, smooth, degradable cosmic star background animation for the login page using Canvas 2D. The animation must work reliably on H5 mobile devices and low-power PCs while maintaining login form readability.

## Problem Frame

The current login page uses a static gradient background (`linear-gradient(135deg, #667eea 0%, #764ba2 100%)`). This provides no visual depth or atmosphere. The user wants a subtle cosmic star animation that:
- Creates a "deep space slowly rotating" atmosphere (not game-loading screen effects)
- Runs smoothly on mobile and low-power devices
- Respects accessibility (reduced motion preferences)
- Does not interfere with form readability

## Requirements Trace

- R1. Canvas 2D implementation (no Three.js/WebGL/shaders)
- R2. Device tier classification with graceful degradation (high/medium/low)
- R3. Performance optimization: FPS limiting, object pooling, minimal redraws
- R4. Accessibility: visibility pause, reduced motion support
- R5. Resize handling with debouncing (150ms)
- R6. High DPI support with capped devicePixelRatio (max 2)
- R7. Login form readability preserved (z-index layering, no visual competition)
- R8. Code maintainability: centralized configuration, clear structure
- R9. Only login page affected (no pollution to other pages)
- R10. Memory safety: proper cleanup on component unmount

## Scope Boundaries

- **Non-goals:**
  - No WebGL/Three.js implementation
  - No particle explosion or game-style effects
  - No large light blobs or high-saturation gradients
  - No animation on other pages (register/join-family could reuse composable later, but not in this scope)
  - No changes to login form business logic or validation

## Context & Research

### Relevant Code and Patterns

- `LoginPage.vue`: Uses `linear-gradient(135deg, #667eea 0%, #764ba2 100%)` — brand gradient, also used in `RegisterPage.vue`
- CSS variables defined in `style.css`: `--theme-gradient-start`, `--theme-gradient-end` (iOS-style blue, separate from login gradient)
- Cleanup pattern: `onUnmounted` used across components (App.vue, AssetListPage.vue, DashboardPage.vue)
- No existing canvas animation, no `requestAnimationFrame` usage in codebase
- `<script setup lang="ts">` standard for all Vue components
- Vant components auto-imported (no manual imports needed)

### Institutional Learnings

- No canvas animation patterns documented in `docs/solutions/`
- ALTCHA captcha doc mentions mobile performance briefly, but not animation-specific

### External References

- MDN Canvas API for 2D drawing primitives
- `requestAnimationFrame` best practices for animation loops
- `prefers-reduced-motion` media query handling
- Page Visibility API (`visibilitychange` event)

## Key Technical Decisions

- **D1: Canvas 2D only** — Native Canvas API sufficient for star particles; avoids WebGL overhead and library dependencies
- **D2: Composable pattern** — `useStarField` composable encapsulates animation logic, reusable for register/join-family pages later
- **D3: Configuration file** — `starField.config.ts` centralizes all visual and performance parameters
- **D4: Device tier detection** — Use `navigator.hardwareConcurrency`, `prefers-reduced-motion`, viewport width, and touch capability for tier classification
- **D5: Object pooling** — Star and meteor arrays initialized once, recycled on boundary exit (no per-frame object creation)
- **D6: FPS throttling** — Time-based frame limiting rather than naive `requestAnimationFrame` (target: 30fps high, 24fps medium, 18fps low)
- **D7: Static gradient as base** — Keep existing CSS gradient as fallback and bottom layer; canvas stars overlay above

## Open Questions

### Resolved During Planning

- Q: Should the gradient background be replaced or augmented?
  - **Resolution:** Augmented. Canvas stars overlay on existing gradient. Gradient remains as fallback for reduced-motion mode.

- Q: Should RegisterPage and JoinFamilyPage also receive the animation?
  - **Resolution:** Not in this scope. Composable will be reusable for future extension.

### Deferred to Implementation

- Q: Exact star colors that complement the `#667eea → #764ba2` gradient
  - **Deferred:** Will be tuned visually during implementation; config file allows easy adjustment.

- Q: Final meteor trail length and opacity curve
  - **Deferred:** Will be tuned during testing on actual devices.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### Component Architecture

```
LoginPage.vue
├── <canvas> (absolute, z-index: 0)
│   └── useStarField composable
│       ├── starField.config.ts (parameters)
│       ├── Star[] (pooled, recycled)
│       ├── Meteor[] (pooled, limited)
│       └── Animation loop (RAF + FPS throttle)
├── <div class="login-content"> (relative, z-index: 1)
│   ├── login-header
│   ├── login-form
│   └── login-links
```

### Animation Loop Flow

```
onMounted
  → detectDeviceTier()
  → initializeStars(tierConfig)
  → startAnimation()

AnimationLoop:
  → check elapsed time since last frame
  → if elapsed >= targetInterval:
      → clear canvas (optional: partial clear)
      → update star positions (recycle out-of-bounds)
      → update meteor positions/spawning
      → draw stars (circle primitives, no shadowBlur)
      → draw meteors (line segments with opacity fade)
  → requestAnimationFrame(next)

onUnmounted
  → stopAnimation()
  → remove resize listener
  → remove visibility listener
```

### Layer Composition

| Layer | Rendering | Update Frequency | Notes |
|-------|-----------|------------------|-------|
| A. Gradient base | CSS (once) | None | `linear-gradient(135deg, #667eea → #764ba2)`, bottom layer |
| B. Far stars | Canvas 2D | Per-frame (slow drift) | Most stars, smallest, slowest |
| C. Mid stars | Canvas 2D | Per-frame | Medium count, some twinkle |
| D. Near bright stars | Canvas 2D | Per-frame | Few, subtle twinkle |
| E. Meteors | Canvas 2D | Per-frame (conditional) | Low frequency, disabled on low tier |

## Implementation Units

- [ ] **Unit 1: Create star field configuration file**

**Goal:** Centralize all visual and performance parameters in a TypeScript configuration file.

**Requirements:** R8

**Dependencies:** None

**Files:**
- Create: `frontend/src/composables/starField.config.ts`

**Approach:**
- Define typed configuration object with tier-specific presets
- Include: star counts, speeds, sizes, twinkle parameters, meteor settings, FPS targets
- Export helper function to get config for device tier

**Patterns to follow:**
- TypeScript strict typing with explicit interfaces
- Constants file pattern (similar to existing `utils/` style)

**Test scenarios:**
- Test expectation: none — configuration file has no runtime behavior to test

**Verification:**
- TypeScript compiles without errors
- Configuration structure is self-documenting

---

- [ ] **Unit 2: Create device tier detection utility**

**Goal:** Implement device capability detection to classify high/medium/low tiers.

**Requirements:** R2

**Dependencies:** None

**Files:**
- Create: `frontend/src/utils/deviceTier.ts`

**Approach:**
- Detect: `prefers-reduced-motion`, `navigator.hardwareConcurrency`, viewport width, touch capability
- Optional: `navigator.deviceMemory` if available (don't rely on it)
- Tier rules:
  - LOW: reduced-motion preference OR cores <= 2 OR narrow screen with touch
  - MEDIUM: typical mobile, low-power PC
  - HIGH: newer mobile, mid-high PC
- Return tier string ('low' | 'medium' | 'high') and boolean flags

**Patterns to follow:**
- Pure function exports, no side effects
- Type-safe return values

**Test scenarios:**
- Happy path: `getDeviceTier()` returns valid tier string
- Edge case: reduced-motion preference forces low tier
- Edge case: hardwareConcurrency = 2 results in low tier
- Edge case: narrow viewport (width < 400) with touch device gets low tier

**Verification:**
- Function returns one of three valid tier values
- Reduced-motion always maps to low tier

---

- [ ] **Unit 3: Create useStarField composable**

**Goal:** Implement the core Canvas 2D animation composable with RAF loop, object pooling, and cleanup.

**Requirements:** R1, R3, R5, R6, R10

**Dependencies:** Unit 1, Unit 2

**Files:**
- Create: `frontend/src/composables/useStarField.ts`

**Approach:**
- Accept canvas ref element as parameter
- Initialize star arrays based on device tier config
- Implement RAF loop with FPS throttling (time-based)
- Handle resize with debounce (150ms)
- Handle visibility change (pause when hidden)
- Support capped devicePixelRatio (max 2)
- Return `{ start, stop, isRunning }`
- Ensure cleanup: cancelAnimationFrame, removeEventListener on stop()

**Execution note:** Start with the animation loop structure and FPS throttling, then add star/meteor rendering.

**Patterns to follow:**
- Vue 3 composable pattern (returns reactive refs and functions)
- Cleanup pattern from existing components (store handles in module scope, clear in returned stop function)

**Technical design:**

```ts
// Directional structure (not implementation code)
interface Star {
  x: number; y: number; r: number; alpha: number;
  speedX: number; speedY: number;
  twinklePhase: number; twinkleSpeed: number;
  layer: 'far' | 'mid' | 'near';
}

interface Meteor {
  x: number; y: number; vx: number; vy: number;
  life: number; maxLife: number; active: boolean;
}

function useStarField(canvasRef: Ref<HTMLCanvasElement | null>) {
  // Tier detection → config selection
  // Star array initialization (once, pooled)
  // Meteor pool (small, limited active count)
  // Animation loop: time-check → update → draw
  // Resize handler: debounce → resize canvas → recompute DPR
  // Visibility handler: pause/resume
  // Return: start(), stop(), isRunning ref
}
```

**Test scenarios:**
- Happy path: `start()` initiates animation loop
- Happy path: `stop()` cancels animation and removes listeners
- Edge case: calling `start()` multiple times doesn't create duplicate loops
- Edge case: resize event triggers canvas dimension update
- Edge case: visibilitychange pauses and resumes correctly
- Edge case: DPR > 2 is capped to 2
- Integration: stars recycle when crossing canvas boundary

**Verification:**
- Animation runs without memory leaks (DevTools heap stable over 60s)
- Resize updates canvas dimensions correctly
- Visibility pause stops RAF loop
- Cleanup removes all listeners

---

- [ ] **Unit 4: Integrate cosmic background into LoginPage**

**Goal:** Add canvas element and composable to LoginPage with proper z-index layering.

**Requirements:** R7, R9

**Dependencies:** Unit 3

**Files:**
- Modify: `frontend/src/pages/LoginPage.vue`

**Approach:**
- Add `<canvas>` element at top of template, absolute positioned, z-index 0, aria-hidden="true" (decorative, not accessible to screen readers)
- Wrap existing content in `<div class="login-content">` with relative position, z-index 1
- Import and call `useStarField` in script
- Add `onMounted` to start animation, `onUnmounted` to stop
- Preserve existing gradient as CSS background (canvas overlays)
- No changes to form logic or validation

**Patterns to follow:**
- Existing component structure: `<script setup lang="ts">`, `<style scoped>`
- Lifecycle pattern: onMounted/onUnmounted for resource management

**Test scenarios:**
- Happy path: canvas renders behind form content
- Happy path: form inputs are fully interactive (pointer-events: none on canvas)
- Edge case: form readability maintained (white text on gradient + stars visible)
- Edge case: keyboard navigation through form fields (Tab, Shift+Tab) works unchanged; focus indicators visible above canvas layer
- Integration: login submit flow unchanged

**Verification:**
- Canvas positioned correctly (absolute, inset 0, z-index 0)
- Form content positioned above canvas (relative, z-index 1)
- Login flow functional (submit, validation, navigation)

---

- [ ] **Unit 5: Verify performance and accessibility**

**Goal:** Confirm animation meets performance targets and accessibility requirements.

**Requirements:** R2, R3, R4

**Dependencies:** Unit 4

**Files:**
- Test: Manual device testing (no automated test file)

**Approach:**
- Visual inspection on Chrome DevTools (FPS, CPU, memory)
- Test reduced-motion preference (Chrome accessibility settings)
- Test visibility pause (switch tabs, minimize window)
- Test resize behavior (window resize, DevTools device emulation)
- Verify form readability (contrast, no distraction)

**Test scenarios:**
- Manual: Animation runs at target FPS (±2fps) on simulated devices
- Manual: Reduced-motion mode shows static stars or minimal drift
- Manual: Tab switch pauses animation, returns resume
- Manual: Resize doesn't cause visual glitches
- Manual: Form text readable against background

**Verification:**
- No console errors
- FPS within target range for each tier (high: 30fps, medium: 24fps, low: 18fps)
- Reduced-motion respected
- Memory stable over 2-minute session

---

- [ ] **Unit 6: TypeScript type check and build verification**

**Goal:** Ensure code compiles and builds without errors.

**Requirements:** R8

**Dependencies:** Unit 1, Unit 2, Unit 3, Unit 4

**Files:**
- Run: `frontend/` build check

**Approach:**
- Run `npx vue-tsc -b --noEmit` to verify TypeScript
- Run `npm run build` to verify production build

**Test scenarios:**
- Happy path: TypeScript check passes with no errors
- Happy path: Production build completes successfully

**Verification:**
- `vue-tsc` exits with code 0
- `npm run build` produces dist files

## System-Wide Impact

- **Interaction graph:** None — animation is isolated to LoginPage, no callbacks or middleware
- **Error propagation:** Canvas errors logged silently, no user-facing error messages
- **State lifecycle risks:** RAF handle must be cancelled on unmount; resize/visibility listeners must be removed
- **API surface parity:** None — no API changes
- **Integration coverage:** Manual visual testing sufficient; no cross-layer dependencies
- **Unchanged invariants:** Login authentication flow, form validation, navigation unchanged

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Mobile performance degradation | Medium | High | Device tier detection, FPS limiting, object pooling, capped DPR |
| Memory leak from listeners | Low | Medium | Explicit cleanup in `stop()` and `onUnmounted` |
| Reduced-motion not respected | Low | Medium | Explicit check in tier detection, force low tier |
| Canvas context overhead on low devices | Medium | Low | Minimal star count on low tier, no meteors, reduced twinkle |
| Visual distraction from form | Low | High | Subtle alpha values, no large shapes, z-index layering |

## Documentation / Operational Notes

- Parameters tunable in `starField.config.ts`:
  - **More restrained:** Reduce star counts, lower alpha, disable meteors, slow speeds
  - **More dreamy:** Increase twinkle intensity, add more bright stars, enable meteors on medium tier
- Future extension: `useStarField` can be imported into `RegisterPage.vue` and `JoinFamilyPage.vue` with zero changes
- No feature flag needed — animation is always-on with graceful degradation

## Sources & References

- **Origin:** Direct user request (no requirements document)
- Related code: `frontend/src/pages/LoginPage.vue`, `frontend/src/composables/useAuth.ts`
- MDN Canvas API: https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API
- Page Visibility API: https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API