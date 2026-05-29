# Coin Tier Visual Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make gold > silver > copper coin SVGs in the child app visibly tier-differentiated, with gold gaining decorative density and a respectful animation.

**Architecture:** Three SVG component files (`GoldenCoin.vue`, `SilverCoin.vue`, `CopperCoin.vue`) get rewritten under a shared `viewBox="0 0 48"`. Gold gains an outer halo ring, 8 rim dots, a highlight blob, an animated diagonal sheen, and three staggered sparkles. Silver gains one arc highlight that breathes in opacity (5s cycle, opacity-only — different motion *kind* from gold's translation). Copper is stripped to its plainest form. The `useReducedMotion()` composable gates both gold's and silver's animation elements via Vue `v-if`. CSS adds two new gold-only tokens. `CoinDisplay.vue` and `coinTier.ts` are NOT touched.

**Tech Stack:** Vue 3 (`<script setup lang="ts">`), inline SVG with SMIL `<animate>`, vitest + @vue/test-utils, CSS variables in `clay.css`.

---

## Spec Reference

Source spec: `docs/superpowers/specs/2026-05-28-coin-tier-visual-hierarchy-design.md`. All design decisions (color stops, rim dot positions, sheen timing, reduced-motion handling) are locked there. This plan executes them, it does not redesign them.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/apps/child/src/assets/clay.css` | Modify | Add 2 new gold-only tokens in `:root` and `[data-theme="dark"]` |
| `frontend/apps/child/src/components/coins/CopperCoin.vue` | Rewrite | Plainest tier — viewBox 48, just face + star + floor shadow |
| `frontend/apps/child/src/components/coins/SilverCoin.vue` | Rewrite | Mid tier — copper + hairline rim + arc highlight with 5s opacity breathing, gated by `useReducedMotion()` |
| `frontend/apps/child/src/components/coins/GoldenCoin.vue` | Rewrite | Top tier — silver + halo ring + 8 rim dots + highlight blob + sheen anim + sparkles, gated by `useReducedMotion()` |
| `frontend/apps/child/src/components/coins/GoldenCoin.test.ts` | Create | Cover gold's reduced-motion conditional render branch |
| `frontend/apps/child/src/components/coins/SilverCoin.test.ts` | Create | Cover silver's reduced-motion conditional render branch |

`CoinDisplay.vue`, `CoinDisplay.test.ts`, `coinTier.ts`, and the existing `useReducedMotion.ts` composable are untouched.

## Working directory

All commands run from `frontend/apps/child/` unless noted. Path aliases: `@/` maps to `src/`.

---

## Task 1: Add gold-only CSS tokens

**Files:**
- Modify: `frontend/apps/child/src/assets/clay.css:21-33` and `frontend/apps/child/src/assets/clay.css:131-144`

These two new tokens are referenced by the rewritten `GoldenCoin.vue` in Task 4. Adding them first means the gold component can reference real tokens from the start instead of hex literals.

- [ ] **Step 1.1: Add tokens in `:root` block**

In `frontend/apps/child/src/assets/clay.css`, find the `--color-coin-copper-text: #8b4513;` line (around line 33) and add immediately after it (before the blank line that ends the coin-color group):

```css
  --color-coin-gold-glow:  #FFF6C7;
  --color-coin-gold-deep:  #A87208;
```

- [ ] **Step 1.2: Add tokens in `[data-theme="dark"]` block**

Find the dark-mode `--color-coin-copper-text: #c07840;` line (around line 144) and add immediately after it:

```css
  --color-coin-gold-glow:  #FFF6C7;
  --color-coin-gold-deep:  #b07a10;
```

(Dark-mode `gold-deep` is slightly brighter than light-mode to avoid over-darkening on dark surfaces, matching the existing pattern where dark-mode `gold-lo` is `#c8960b` vs light's `#B8860B`.)

- [ ] **Step 1.3: Verify both tokens are present in both blocks**

Run from `frontend/apps/child/`:

```bash
grep -n "color-coin-gold-glow\|color-coin-gold-deep" src/assets/clay.css
```

Expected output: 4 lines (2 in `:root`, 2 in `[data-theme="dark"]`).

- [ ] **Step 1.4: Run typecheck**

Run from `frontend/apps/child/`:

```bash
npm run typecheck
```

Expected: no errors. CSS changes don't affect TS, but this confirms we haven't accidentally broken anything else.

- [ ] **Step 1.5: Commit**

```bash
git add frontend/apps/child/src/assets/clay.css
git commit -m "feat(child/clay): add gold-glow and gold-deep coin tokens

Two new tokens to support the rewritten GoldenCoin SVG: glow for the
sparkle/highlight fills, deep for the 4th radial-gradient stop and the
star stroke. Defined in both :root and [data-theme=\"dark\"] blocks."
```

---

## Task 2: Rewrite CopperCoin.vue (plainest tier)

**Files:**
- Modify: `frontend/apps/child/src/components/coins/CopperCoin.vue`

Copper is the baseline tier. The current component has a decorative outer edge stroke and a relatively bright shadow under the coin; the spec calls for stripping these so copper sits clearly below silver in visual density.

- [ ] **Step 2.1: Replace the entire file content**

Overwrite `frontend/apps/child/src/components/coins/CopperCoin.vue` with:

```vue
<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" class="copper-coin">
    <defs>
      <radialGradient id="copper-grad" cx="35%" cy="32%" r="70%">
        <stop class="stop-hi" offset="0%" />
        <stop class="stop-mid" offset="60%" />
        <stop class="stop-lo" offset="100%" />
      </radialGradient>
    </defs>
    <ellipse cx="24" cy="40" rx="16" ry="2" class="coin-shadow" opacity="0.12" />
    <circle cx="24" cy="23" r="20" fill="url(#copper-grad)" />
    <text x="24" y="29.5" text-anchor="middle" font-size="20" font-weight="900" fill="#FFE9D1" opacity="0.85">★</text>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 24 })
</script>

<style scoped>
.copper-coin .stop-hi  { stop-color: var(--color-coin-copper-hi); }
.copper-coin .stop-mid { stop-color: var(--color-coin-copper-mid); }
.copper-coin .stop-lo  { stop-color: var(--color-coin-copper-lo); }
.copper-coin .coin-shadow { fill: var(--color-coin-copper-lo); }
</style>
```

Note: the gradient `id="copper-grad"` matches the original — keeps any external CSS hooks happy (none currently exist, but consistency is cheap).

- [ ] **Step 2.2: Run typecheck**

```bash
npm run typecheck
```

Expected: no errors.

- [ ] **Step 2.3: Run existing CoinDisplay tests**

```bash
npm run test:run -- CoinDisplay
```

Expected: PASS — `CoinDisplay.test.ts` already passes regardless of the inner SVG details, since it only inspects the `.copper`/`.silver`/`.gold` count spans.

- [ ] **Step 2.4: Commit**

```bash
git add frontend/apps/child/src/components/coins/CopperCoin.vue
git commit -m "refactor(child/coins): simplify CopperCoin to plainest tier

Strip the decorative outer edge stroke and shrink the floor shadow.
viewBox bumped to 0 0 48 to align with the new SilverCoin/GoldenCoin
that need extra room for rim decoration. Star size and weight bumped
for legibility under the new viewBox."
```

---

## Task 3: Rewrite SilverCoin.vue (mid tier with opacity-breathing animation)

**Files:**
- Modify: `frontend/apps/child/src/components/coins/SilverCoin.vue`

Silver gets two extras vs copper:
1. A hairline rim stroke.
2. A single bright arc highlight on the upper-left whose `opacity` slowly breathes between 0.4 and 0.7 on a 5s loop.

The breathing animation is intentionally opacity-only (not positional like gold's sheen). This makes silver's motion *kind* clearly different from gold's — even at similar speeds the two never read as the same gesture. The `<animate>` element is gated under `useReducedMotion()`; when motion is reduced, the arc renders at static `opacity="0.55"`.

- [ ] **Step 3.1: Replace the entire file content**

Overwrite `frontend/apps/child/src/components/coins/SilverCoin.vue` with:

```vue
<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" class="silver-coin">
    <defs>
      <radialGradient id="silver-grad" cx="35%" cy="32%" r="70%">
        <stop class="stop-hi" offset="0%" />
        <stop class="stop-mid" offset="50%" />
        <stop class="stop-lo" offset="100%" />
      </radialGradient>
    </defs>
    <ellipse cx="24" cy="40" rx="17" ry="2.5" class="coin-shadow" opacity="0.15" />
    <circle cx="24" cy="23" r="20" fill="url(#silver-grad)" />
    <circle cx="24" cy="23" r="20" fill="none" class="coin-edge" stroke-width="1" opacity="0.7" />
    <path
      d="M 12 16 A 16 16 0 0 1 32 12"
      class="silver-arc"
      stroke-width="1.6"
      fill="none"
      :opacity="reducedMotion ? 0.55 : undefined"
      stroke-linecap="round"
      data-test="silver-arc"
    >
      <animate
        v-if="!reducedMotion"
        attributeName="opacity"
        values="0.4;0.7;0.4"
        dur="5s"
        repeatCount="indefinite"
        data-test="silver-arc-animate"
      />
    </path>
    <text x="24" y="29.5" text-anchor="middle" font-size="20" font-weight="900" fill="#FFFFFF" opacity="0.92">★</text>
  </svg>
</template>

<script setup lang="ts">
import { useReducedMotion } from '@/composables/useReducedMotion'

withDefaults(defineProps<{ size?: number }>(), { size: 24 })

const reducedMotion = useReducedMotion()
</script>

<style scoped>
.silver-coin .stop-hi  { stop-color: var(--color-coin-silver-hi); }
.silver-coin .stop-mid { stop-color: var(--color-coin-silver-mid); }
.silver-coin .stop-lo  { stop-color: var(--color-coin-silver-lo); }
.silver-coin .coin-shadow { fill: var(--color-coin-silver-lo); }
.silver-coin .coin-edge   { stroke: var(--color-coin-silver-hi); }
.silver-coin .silver-arc  { stroke: #FFFFFF; }
</style>
```

Notes:
- The `silver-arc` uses literal `#FFFFFF` rather than a token because its purpose is a pure specular highlight, not a tinted brand color — and the existing copper/silver/gold token set has no "highlight white" entry. Keeping it inline avoids inventing a one-off token.
- `:opacity="reducedMotion ? 0.55 : undefined"` sets a static opacity ONLY when motion is reduced. When motion is allowed, `opacity` is `undefined` (no attribute set), letting the `<animate>` drive it. This matters because if both static `opacity` and `<animate>` are present, browsers vary on which wins.
- `data-test="silver-arc"` and `data-test="silver-arc-animate"` give the test stable selectors.

- [ ] **Step 3.2: Run typecheck**

```bash
npm run typecheck
```

Expected: no errors.

- [ ] **Step 3.3: Run existing CoinDisplay tests**

```bash
npm run test:run -- CoinDisplay
```

Expected: PASS.

- [ ] **Step 3.4: Commit**

```bash
git add frontend/apps/child/src/components/coins/SilverCoin.vue
git commit -m "feat(child/coins): give SilverCoin an opacity-breathing arc highlight

viewBox 0 0 48 to match new copper/gold. Adds one upper-left arc
stroke whose opacity breathes between 0.4 and 0.7 on a 5s loop —
opacity-only motion, no position change. This is intentionally a
different motion kind from gold's positional sheen sweep, so the
three tiers read as three distinct gestures.

The <animate> element is gated under useReducedMotion(); when motion
is reduced, the arc renders at static opacity 0.55."
```

---

## Task 4: Rewrite GoldenCoin.vue (top tier, with reduced-motion gating)

**Files:**
- Modify: `frontend/apps/child/src/components/coins/GoldenCoin.vue`

This is the centerpiece. Gold gets:
- Floor shadow
- Outer halo ring (radial-gradient stroke)
- Coin face (4-stop radial gradient)
- Inner hairline circle
- 8 rim dots at compass positions
- Top-left highlight ellipse
- Animated diagonal sheen (sweeps across face every 3.2s)
- Stroked star
- 3 staggered sparkle dots

The animated `<rect>` (sheen) and the three sparkle `<circle>`s are wrapped in `v-if="!reducedMotion"`. The static decoration is always rendered.

- [ ] **Step 4.1: Replace the entire file content**

Overwrite `frontend/apps/child/src/components/coins/GoldenCoin.vue` with:

```vue
<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" class="golden-coin">
    <defs>
      <radialGradient id="gold-face-grad" cx="35%" cy="32%" r="70%">
        <stop class="stop-glow" offset="0%" />
        <stop class="stop-hi" offset="35%" />
        <stop class="stop-mid" offset="70%" />
        <stop class="stop-deep" offset="100%" />
      </radialGradient>
      <radialGradient id="gold-rim-grad" cx="50%" cy="50%" r="50%">
        <stop class="stop-rim-clear" offset="85%" stop-opacity="0" />
        <stop class="stop-rim-bright" offset="92%" stop-opacity="0.9" />
        <stop class="stop-rim-deep" offset="100%" stop-opacity="1" />
      </radialGradient>
      <linearGradient id="gold-sheen-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0" />
        <stop offset="45%" stop-color="#FFFFFF" stop-opacity="0.75" />
        <stop offset="55%" stop-color="#FFFFFF" stop-opacity="0.75" />
        <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0" />
      </linearGradient>
      <clipPath id="gold-face-clip">
        <circle cx="24" cy="23" r="20" />
      </clipPath>
    </defs>

    <ellipse cx="24" cy="40" rx="18" ry="3" class="coin-shadow" opacity="0.18" />

    <circle cx="24" cy="23" r="22" fill="none" stroke="url(#gold-rim-grad)" stroke-width="2" />

    <circle cx="24" cy="23" r="20" fill="url(#gold-face-grad)" />

    <g class="rim-dots" opacity="0.55">
      <circle cx="24" cy="6" r="0.7" />
      <circle cx="36.7" cy="10.3" r="0.7" />
      <circle cx="41" cy="23" r="0.7" />
      <circle cx="36.7" cy="35.7" r="0.7" />
      <circle cx="24" cy="40" r="0.7" />
      <circle cx="11.3" cy="35.7" r="0.7" />
      <circle cx="7" cy="23" r="0.7" />
      <circle cx="11.3" cy="10.3" r="0.7" />
    </g>

    <circle cx="24" cy="23" r="16" fill="none" class="inner-ring" stroke-width="0.6" opacity="0.55" />

    <ellipse cx="17" cy="15" rx="6" ry="3" class="highlight-blob" opacity="0.55" />

    <g v-if="!reducedMotion" clip-path="url(#gold-face-clip)" data-test="gold-sheen">
      <rect x="-30" y="0" width="14" height="48" fill="url(#gold-sheen-grad)" transform="rotate(20 24 23)">
        <animate attributeName="x" values="-30;55;55" dur="3.2s" keyTimes="0;0.55;1" repeatCount="indefinite" />
      </rect>
    </g>

    <text x="24" y="29.5" text-anchor="middle" font-size="20" font-weight="900" class="gold-star" stroke-width="0.5" paint-order="stroke">★</text>

    <g v-if="!reducedMotion" class="sparkles" data-test="gold-sparkles">
      <circle cx="11" cy="13" r="1.1">
        <animate attributeName="opacity" values="0;1;0" dur="2.4s" begin="0s" repeatCount="indefinite" />
      </circle>
      <circle cx="38" cy="14" r="0.9">
        <animate attributeName="opacity" values="0;1;0" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
      </circle>
      <circle cx="36" cy="34" r="0.8">
        <animate attributeName="opacity" values="0;1;0" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
      </circle>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { useReducedMotion } from '@/composables/useReducedMotion'

withDefaults(defineProps<{ size?: number }>(), { size: 24 })

const reducedMotion = useReducedMotion()
</script>

<style scoped>
.golden-coin .stop-glow { stop-color: var(--color-coin-gold-glow); }
.golden-coin .stop-hi   { stop-color: var(--color-coin-gold-hi); }
.golden-coin .stop-mid  { stop-color: var(--color-coin-gold-mid); }
.golden-coin .stop-deep { stop-color: var(--color-coin-gold-deep); }
.golden-coin .stop-rim-clear  { stop-color: var(--color-coin-gold-mid); }
.golden-coin .stop-rim-bright { stop-color: var(--color-coin-gold-hi); }
.golden-coin .stop-rim-deep   { stop-color: var(--color-coin-gold-deep); }
.golden-coin .coin-shadow { fill: var(--color-coin-gold-deep); }
.golden-coin .rim-dots circle { fill: var(--color-coin-gold-deep); }
.golden-coin .inner-ring { stroke: var(--color-coin-gold-deep); }
.golden-coin .highlight-blob { fill: var(--color-coin-gold-glow); }
.golden-coin .gold-star { fill: var(--color-coin-gold-glow); stroke: var(--color-coin-gold-deep); }
.golden-coin .sparkles circle { fill: var(--color-coin-gold-glow); }
</style>
```

Key technical notes:
- `useReducedMotion()` returns a `Readonly<Ref<boolean>>`. In template, Vue auto-unwraps refs, so `v-if="!reducedMotion"` reads correctly. The composable internally manages a singleton media-query listener — no setup or teardown needed here.
- `data-test="gold-sheen"` and `data-test="gold-sparkles"` give the test a stable selector.
- The rim-dot positions (compass: top, top-right diag, right, bottom-right diag, bottom, bottom-left diag, left, top-left diag) are computed from a 17-radius circle around (24, 23), placing them just outside the inner-ring (r=16) and inside the coin face (r=20).
- `paint-order="stroke"` on the star ensures the deep-gold stroke renders behind the glow fill — crucial for the raised-letter effect.

- [ ] **Step 4.2: Run typecheck**

```bash
npm run typecheck
```

Expected: no errors.

- [ ] **Step 4.3: Run existing CoinDisplay tests**

```bash
npm run test:run -- CoinDisplay
```

Expected: PASS — `CoinDisplay.test.ts` only inspects the `.gold` count span, not the SVG internals, so it's unaffected.

- [ ] **Step 4.4: Commit**

```bash
git add frontend/apps/child/src/components/coins/GoldenCoin.vue
git commit -m "feat(child/coins): rewrite GoldenCoin as the top tier

Gold now carries a multi-layer rim (halo + hairline), 8 decorative rim
dots, a 4-stop face gradient, a top-left highlight blob, a stroked
star, and two animations: a diagonal sheen sweeping across the face on
a 3.2s loop, and three staggered sparkle dots. The animated elements
are gated behind useReducedMotion() — when prefers-reduced-motion is
set, they don't render at all and the static decoration alone carries
the tier signal."
```

---

## Task 5: Test the reduced-motion gating

**Files:**
- Create: `frontend/apps/child/src/components/coins/GoldenCoin.test.ts`

The test mocks `matchMedia` (the same way `useReducedMotion.test.ts` already does at lines 8-30), mounts the component twice — once with motion allowed, once with motion reduced — and verifies the `data-test` selectors are present in the first case and absent in the second.

The `useReducedMotion` composable holds singleton state in module scope (see `useReducedMotion.ts:5-6`). For the test to reset between cases, we use `vi.resetModules()` and re-import the component each time, mirroring the pattern in `useReducedMotion.test.ts:11`.

- [ ] **Step 5.1: Write the failing test**

Create `frontend/apps/child/src/components/coins/GoldenCoin.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

describe('GoldenCoin reduced-motion gating', () => {
  let mqMatches: boolean

  beforeEach(() => {
    mqMatches = false
    vi.resetModules()
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        get matches() {
          return mqMatches
        },
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
        media: '(prefers-reduced-motion: reduce)',
        onchange: null,
      })),
    })
  })

  it('renders sheen and sparkles when motion is allowed', async () => {
    mqMatches = false
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    expect(wrapper.find('[data-test="gold-sheen"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="gold-sparkles"]').exists()).toBe(true)
  })

  it('omits sheen and sparkles when prefers-reduced-motion is set', async () => {
    mqMatches = true
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    expect(wrapper.find('[data-test="gold-sheen"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="gold-sparkles"]').exists()).toBe(false)
  })

  it('always renders the static decoration regardless of motion preference', async () => {
    mqMatches = true
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    const html = wrapper.html()
    expect(html).toContain('class="rim-dots"')
    expect(html).toContain('class="highlight-blob"')
    expect(html).toContain('class="inner-ring"')
  })
})
```

- [ ] **Step 5.2: Run the test to verify it passes**

The implementation already exists from Task 4, so this test should pass on first run (it's a verification test for the Task 4 contract, not a TDD-style "fail first" test — Task 4 was the one bigger implementation, and writing a failing test before that big rewrite would have meant scaffolding a stub component, which adds churn for no real safety gain in a single-file rewrite).

```bash
npm run test:run -- GoldenCoin
```

Expected: 3 tests pass.

If a test fails, the most likely cause is that `data-test` attributes weren't added in Task 4 — re-check the template against Step 4.1.

- [ ] **Step 5.3: Run typecheck**

```bash
npm run typecheck
```

Expected: no errors.

- [ ] **Step 5.4: Commit**

```bash
git add frontend/apps/child/src/components/coins/GoldenCoin.test.ts
git commit -m "test(child/coins): cover GoldenCoin reduced-motion gating

Three cases: motion allowed renders both sheen and sparkles; reduced
motion omits both; static decoration (rim dots, highlight blob, inner
ring) renders in both cases."
```

---

## Task 6: Test the silver reduced-motion gating

**Files:**
- Create: `frontend/apps/child/src/components/coins/SilverCoin.test.ts`

Same pattern as Task 5, but verifying silver: when motion is allowed, the `<animate>` element is rendered inside the arc; when motion is reduced, the `<animate>` is omitted but the arc itself is still present at a static opacity.

- [ ] **Step 6.1: Write the test**

Create `frontend/apps/child/src/components/coins/SilverCoin.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

describe('SilverCoin reduced-motion gating', () => {
  let mqMatches: boolean

  beforeEach(() => {
    mqMatches = false
    vi.resetModules()
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        get matches() {
          return mqMatches
        },
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
        media: '(prefers-reduced-motion: reduce)',
        onchange: null,
      })),
    })
  })

  it('renders the breathing animate element when motion is allowed', async () => {
    mqMatches = false
    const { default: SilverCoin } = await import('./SilverCoin.vue')
    const wrapper = mount(SilverCoin)
    expect(wrapper.find('[data-test="silver-arc"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="silver-arc-animate"]').exists()).toBe(true)
  })

  it('omits the animate element but keeps the static arc when prefers-reduced-motion is set', async () => {
    mqMatches = true
    const { default: SilverCoin } = await import('./SilverCoin.vue')
    const wrapper = mount(SilverCoin)
    const arc = wrapper.find('[data-test="silver-arc"]')
    expect(arc.exists()).toBe(true)
    expect(arc.attributes('opacity')).toBe('0.55')
    expect(wrapper.find('[data-test="silver-arc-animate"]').exists()).toBe(false)
  })
})
```

- [ ] **Step 6.2: Run the test**

```bash
npm run test:run -- SilverCoin
```

Expected: 2 tests pass.

- [ ] **Step 6.3: Run typecheck**

```bash
npm run typecheck
```

Expected: no errors.

- [ ] **Step 6.4: Commit**

```bash
git add frontend/apps/child/src/components/coins/SilverCoin.test.ts
git commit -m "test(child/coins): cover SilverCoin reduced-motion gating

Two cases: motion allowed renders the <animate> child of the arc;
reduced motion omits <animate> but keeps the arc itself at static
opacity 0.55."
```

---

## Task 7: Final verification

**Files:** none (verification only)

- [ ] **Step 7.1: Run lint on the entire src tree**

```bash
npm run lint
```

Expected: no errors. Specifically watch for: unused imports, missing semicolons, `as any` slipping in.

- [ ] **Step 7.2: Run the full test suite**

```bash
npm run test:run
```

Expected: all tests pass. New test files `GoldenCoin.test.ts` and `SilverCoin.test.ts` run alongside `CoinDisplay.test.ts`, `useReducedMotion.test.ts`, and others.

- [ ] **Step 7.3: Run typecheck once more**

```bash
npm run typecheck
```

Expected: no errors.

- [ ] **Step 7.4: Manual visual check**

Start the dev server (NOT from an automated agent — do this manually):

```bash
npm run dev
```

Open http://localhost:5174 in the browser. Verify:

1. On the home page (hero balance card, ochre background): gold coins show the halo + dots + sheen sweep + sparkles. Silver shows the arc highlight slowly breathing in opacity (5s cycle). Copper is plain and static.
2. Watch a list with both gold and silver visible — the gold sheen (3.2s) and silver arc breathing (5s) should NOT pulse on the same beat. They should feel like two different rhythms.
3. The `prefers-reduced-motion: reduce` toggle (Chrome DevTools → Rendering panel → Emulate CSS media feature `prefers-reduced-motion: reduce`) should: (a) remove gold sheen and sparkles from the DOM, (b) freeze silver's arc at static opacity 0.55. Reload after toggling — the singleton in `useReducedMotion` reads the initial state, so a fresh page load is needed.
4. Toggle dark theme via the home settings panel. Verify the gold and silver coins are still legible — `--color-coin-gold-glow` and `--color-coin-gold-deep` use dark-mode values from Task 1.
5. Visit `/ledger` — confirm balance card, transaction list, and the gift sheet still render correctly.

This step is manual and does NOT block the commit chain — but the plan is not complete until a human eyeballs it.

---

## Self-Review Notes

**Spec coverage check:**
- Visual hierarchy contract (spec §Visual hierarchy contract): Tasks 2/3/4 each implement one tier, covering all rows of the table including the new "Motion type" and "Animation period" rows.
- SVG architecture (spec §SVG architecture): viewBox 48, 4-stop gold face, halo, dots, blob, sheen, sparkles, stroked star — all in Task 4. Silver arc + breathing animation — Task 3.
- Reduced motion (spec §Reduced motion): Task 4 wires `useReducedMotion()` + `v-if` for gold; Task 3 does the same for silver. Task 5 covers gold with three tests; Task 6 covers silver with two tests.
- Token additions (spec §Token additions): Task 1.
- Sizing behavior (spec §Sizing behavior): no separate task — the spec explicitly says we accept some detail loss below 16px and add a `compact` prop later if needed. Nothing to implement now.
- Animation rhythm (spec §Animation rhythm): the `keyTimes`, `dur`, and `begin` values in Task 4 (gold) and Task 3 (silver 5s breathing) match the spec exactly.

**Placeholder scan:** No "TBD", "implement later", or vague handwaves. Every code block is complete and runnable.

**Type/name consistency:**
- `useReducedMotion()` returns `Readonly<Ref<boolean>>` (verified at `useReducedMotion.ts:22`); used identically in Tasks 3, 4, 5, 6.
- Token names `--color-coin-gold-glow` / `--color-coin-gold-deep` match between Task 1 (definition) and Task 4 (consumption).
- `data-test` selectors `gold-sheen` / `gold-sparkles` match between Task 4 (template) and Task 5 (queries). `silver-arc` / `silver-arc-animate` match between Task 3 and Task 6.
- viewBox `0 0 48` is the same in all three SVG files — copper/silver/gold all line up.

---

## Plan complete

Plan saved to `docs/superpowers/plans/2026-05-28-coin-tier-visual-hierarchy.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
