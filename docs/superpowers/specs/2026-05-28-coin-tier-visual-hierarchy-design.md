# Coin Tier Visual Hierarchy — Design

**Date:** 2026-05-28
**Status:** Proposed
**Owner:** Frontend (child app)
**Module:** `frontend/apps/child/src/components/coins/`

## Context

The child app awards "star coins" (星星币) for completing chores. The total amount is automatically split into gold (金) / silver (银) / copper (铜) tiers via `splitCoinTiers()` in `src/utils/coinTier.ts`, then rendered by `CoinDisplay.vue` using three SVG components: `GoldenCoin.vue`, `SilverCoin.vue`, `CopperCoin.vue`.

**Problem.** The three SVGs are structurally identical — same `<defs>`, same single radial gradient, same `<ellipse>` shadow, same `<text>` star — differing only in color tokens. Gold has no visual privilege over silver or copper. For a feature whose entire purpose is to make tiered achievement *feel* tiered, this is a missed opportunity.

**User feedback (verbatim).** "优化下当前儿童功能的星星币的金银铜展示，让他们更具备阶梯不同的设计，比如，给金币更闪耀、更能抓住眼球的svg设计"

## Goals

1. Make the gold > silver > copper hierarchy *immediately* readable at a glance — without comparing them side by side.
2. Give gold a small but consistent attention pull (subtle motion + decorative density) so the child feels rewarded when their balance crosses a 100-copper threshold.
3. Keep silver simple-but-refined; keep copper plainest of the three.
4. Stay inside the Clay design system (cream canvas, no heavy shadows, existing `--color-coin-*` tokens preserved).
5. Respect `prefers-reduced-motion` automatically.

## Non-goals

- No new tier (e.g. platinum, diamond). Three tiers stay.
- No change to `splitCoinTiers()` math, the conversion ratios, or `CoinDisplay.vue`'s cascade animation logic.
- No change to coin balance or ledger backend.
- No change to copper/silver text color tokens beyond what already exists.

## Design

The change is contained to **three SVG component files** plus **one CSS variable addition**. No structural change to `CoinDisplay.vue`, no new components, no new state.

### Visual hierarchy contract

Every dimension below scales monotonically gold → silver → copper. A reader should be able to assign tier rank from any single dimension.

| Dimension | 🥇 Gold | 🥈 Silver | 🥉 Copper |
|---|---|---|---|
| Outer rim | Two-layer (outer halo gradient + inner hairline) | Single hairline | None |
| Radial-gradient stops | 4 (white-cream → bright → mid → deep) | 3 | 3 |
| Highlight | Top-left ellipse blob | Top arc stroke | None |
| Decorative dots on rim | 8 small ochre dots at compass points | None | None |
| Star symbol | Stroked + slight raised look | Plain fill | Plain fill |
| Sparkles | 3 small dots, staggered fade | None | None |
| Motion type | Translation (sheen sweep) + opacity (sparkles) | Opacity only (arc breathing) | None |
| Animation period | 3.2s sheen + 2.4s sparkles | 5s arc breathing | — |

The static layer alone (no animation) already establishes the hierarchy. Animation is additive flair, not the load-bearing tier signal. Note that motion *kind* differs between gold and silver — gold uses positional translation (something is moving across the coin), silver uses opacity breathing only (nothing moves, the highlight just brightens and dims). This kind-difference matters: it means even at similar speeds, gold and silver read as fundamentally different gestures, so future tuning of gold's intensity won't accidentally collide with silver.

### SVG architecture

All three coins share:

- **viewBox** changes from `0 0 40` (current) to `0 0 48`. Reason: the new gold needs a 22-radius outer rim that doesn't get clipped, and a 0–48 grid keeps math clean (center at 24).
- The component still accepts a `size` prop with default `24` (matches the existing default in `GoldenCoin.vue:18`). `width`/`height` map to the prop; the viewBox does the scaling.
- Color stops continue to reference `--color-coin-{gold|silver|copper}-{hi,mid,lo}` so dark-mode token overrides in `clay.css` keep working unchanged.

**Gold-specific elements** (in render order, back to front):

1. **Drop shadow** — `<ellipse cx="24" cy="40" rx="18" ry="3" fill="var(--color-coin-gold-lo)" opacity="0.18">`. Replaces the current full-body shadow with a subtle floor shadow.
2. **Outer rim halo** — `<circle cx="24" cy="23" r="22" fill="none" stroke="url(#gold-rim-grad)" stroke-width="2">`, where `gold-rim-grad` is a radial gradient `0%–85%` transparent → `92%` ochre highlight → `100%` deep. Reads as a soft glow ring.
3. **Coin face** — `<circle cx="24" cy="23" r="20" fill="url(#gold-face-grad)">` with 4 stops to give a brighter highlight and deeper shadow than the current 3-stop gradient.
4. **Inner hairline** — `<circle cx="24" cy="23" r="16" stroke="var(--color-coin-gold-lo)" stroke-width="0.6" opacity="0.55">`. A tiny inscribed ring.
5. **Eight rim dots** — small `<circle r="0.7">` at compass positions on the inner rim. Reads as a milled-edge texture.
6. **Highlight blob** — `<ellipse cx="17" cy="15" rx="6" ry="3" fill="#FFFCE0" opacity="0.55">`. Top-left specular highlight, the single biggest "this looks 3D" cue.
7. **Animated sheen** — a 14×48 white linear-gradient `<rect>` rotated 20° and clipped to the coin face, animated `x: -30 → 55` over 3.2s with a hold at the end so each cycle has a long quiet phase. Implemented via SMIL `<animate>` so it works without JS scheduling.
8. **Star** — `<text>★</text>` with `paint-order="stroke"`, fill `#FFFCE0`, stroke `var(--color-coin-gold-lo)` width `0.5`. The thin dark stroke gives the star a raised look against the bright face.
9. **Three sparkles** — small `<circle>` elements with SMIL `<animate attributeName="opacity" values="0;1;0" dur="2.4s">`, each with a `begin` offset so they fire staggered (0s, 0.8s, 1.6s).

**Silver-specific elements** (intentionally simpler than gold, but with its own subtle motion):

1. Floor shadow.
2. Coin face — 3-stop radial gradient (current treatment, unchanged).
3. Hairline rim — single `<circle>` stroke, similar to the current edge.
4. **One arc highlight with breathing animation** — `<path d="M 12 16 A 16 16 0 0 1 32 12">` stroked white, `stroke-linecap="round"`. SMIL `<animate attributeName="opacity" values="0.4;0.7;0.4" dur="5s" repeatCount="indefinite">` so the arc gently brightens and dims like slow metallic reflection. No position change, opacity only.
5. Star — plain fill, no stroke.

The arc-breathing animation is also wrapped under `useReducedMotion()` gating — when motion is reduced, the arc renders at a static `opacity="0.55"` instead of being animated.

**Copper-specific elements** (plainest):

1. Floor shadow (smaller).
2. Coin face — 3-stop radial gradient.
3. Star — plain fill.
4. **Nothing else.** No rim, no highlight arc, no decoration.

### Reduced motion

The gold coin's animations (sheen sweep, sparkle fades) and the silver coin's arc breathing MUST stop under `prefers-reduced-motion: reduce`. Implementation: wrap the `<animate>` elements' parents in a class that gets a CSS rule `@media (prefers-reduced-motion: reduce) { .gold-anim { animation: none; } }`. Since SMIL `<animate>` is not directly controllable via CSS, the practical pattern is:

- Read `useReducedMotion()` (already exists at `src/composables/useReducedMotion.ts`).
- Gold: conditionally render the animated `<rect>` and sparkle `<circle>` elements with `v-if="!reducedMotion"`.
- Silver: conditionally render the arc's `<animate>` child with `v-if="!reducedMotion"`. When motion is reduced, the arc still appears at static `opacity="0.55"`.
- Static decoration (rim, dots, blob, star stroke) remains in all cases for both coins.

This keeps gold and silver visibly tier-superior even with motion disabled.

### Token additions

Two new tokens in `src/assets/clay.css`, in both `:root` and `[data-theme="dark"]` blocks, to support the new highlight + rim halo:

```css
--color-coin-gold-glow:      #FFF6C7;  /* sparkle and highlight blob fill */
--color-coin-gold-deep:      #A87208;  /* 4th-stop deep shadow on gold face */
```

Dark-mode values keep the same hue family but slightly muted to avoid hot-spotting on dark backgrounds. No existing `--color-coin-*` tokens are removed or renamed.

### Sizing behavior

The current default `iconSize` in `CoinDisplay.vue` is 20px. The new gold SVG carries more detail; at 16px the rim dots become noisy. Decision:

- Gold renders identically at all sizes ≥ 16px (acceptable detail loss but not muddy).
- Below 16px, the gold SVG still renders the same elements — we accept some detail loss rather than maintain a separate "small" variant. None of the current call sites use < 16px gold.

If a smaller use case ever appears, we add a `compact` boolean prop later. Not now.

### Animation rhythm

The gold sheen animation uses `keyTimes="0;0.55;1"` with values `-30;55;55`, meaning the band sweeps across in the first 55% of the cycle, then sits invisible (off-coin) for the remaining 45%. This produces ~1.4s of motion + ~1.4s of quiet per cycle — bright enough to draw attention, sparse enough to not strobe in a list with several gold coins visible.

Gold sparkles use a 2.4s cycle with three start offsets (0s, 0.8s, 1.6s), so at any instant only one of three is mid-fade.

The silver arc breathes on a slower 5s cycle (`values="0.4;0.7;0.4"`). Silver's cycle is intentionally desynced from gold's 3.2s — a list mixing gold and silver coins never has the two pulse at the same beat, which prevents the eye from grouping them as one rhythm.

## Alternatives considered

**A. Pure animation, no static change.** Rejected — fails when motion is disabled and adds runtime cost on every list row. Static differentiation is the foundation; motion is the icing.

**B. Different shapes per tier (e.g. gold = star-shaped coin).** Rejected — breaks the "they are all coins of the same currency" mental model. Tiers should feel like the same object at different fineness, not different objects.

**C. Larger gold coin (size scales with tier).** Rejected — `CoinDisplay.vue` aligns coins on a baseline and uses one `iconSize`. Per-tier sizes would require layout rework and could create line-height jitter mid-cascade animation.

**D. 3D rendering / Lottie animation.** Rejected — out of proportion for a 20-32px badge. Inline SVG with SMIL is one or two orders of magnitude lighter and stays inside the Clay system's hand-drawn flat aesthetic.

## Files changed

| File | Change |
|---|---|
| `frontend/apps/child/src/components/coins/GoldenCoin.vue` | Rewrite with new SVG architecture, 4-stop face grad, rim halo, dots, blob, sheen anim, sparkles. Read `useReducedMotion()`, conditionally render anim elements. |
| `frontend/apps/child/src/components/coins/SilverCoin.vue` | Update viewBox to `0 0 48`, add hairline rim and arc highlight with 5s opacity breathing animation. Read `useReducedMotion()`, conditionally render the `<animate>` element. |
| `frontend/apps/child/src/components/coins/CopperCoin.vue` | Update viewBox to `0 0 48`. Strip decorative ring/edge stroke present today. |
| `frontend/apps/child/src/assets/clay.css` | Add `--color-coin-gold-glow` and `--color-coin-gold-deep` in both `:root` and `[data-theme="dark"]`. |
| `frontend/apps/child/src/components/coins/GoldenCoin.test.ts` | New: assert gold renders sheen + sparkles when motion enabled, drops them when reducedMotion ref is true. |
| `frontend/apps/child/src/components/coins/SilverCoin.test.ts` | New: assert silver renders arc `<animate>` when motion enabled and omits it (leaving the static arc) when reducedMotion ref is true. |

`CoinDisplay.vue` and its test are untouched. `coinTier.ts` is untouched.

## Verification

1. `npm run typecheck` — must pass.
2. `npm run lint` — must pass.
3. `npm run test:run` — existing `CoinDisplay.test.ts` cases must still pass (no behavior change to it). New `GoldenCoin.test.ts` covers reduced-motion branch.
4. Manual: open `/` (home page) at desktop and mobile widths, light + dark theme. Confirm gold has visible decoration and animation; silver and copper visibly degrade. Confirm `prefers-reduced-motion: reduce` (set in browser devtools rendering pane) freezes the gold sheen + sparkles.
5. Manual: visit `/ledger` to confirm hero + transaction list rendering looks correct in both themes.

## Out of scope (future work, do not bundle)

- Persistent on/off toggle for coin animations in settings (the Reduced motion question raised this). System-level `prefers-reduced-motion` covers the accessibility case; a user-facing toggle would need its own design pass.
- Triggering a brief "level up" celebration when a child's balance newly crosses into a gold-coin threshold. Could reuse `MilestoneCelebration.vue` but is a separate feature.
- Updating the main app (parent-facing) coin display, if any.
