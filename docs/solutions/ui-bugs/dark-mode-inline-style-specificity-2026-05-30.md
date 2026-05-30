---
title: "Dark mode CSS rules silently lose to inline style attributes"
date: 2026-05-30
module: frontend
component: frontend_main
problem_type: ui_bug
severity: high
symptoms:
  - "Primary text invisible in dark mode while light mode renders correctly"
  - "[data-theme='dark'] selectors appear to have no effect even though Devtools shows them"
  - "Card or container background stays light-pastel in dark mode regardless of theme attribute"
  - "Adding more specific selectors (e.g. nesting deeper) does not fix the override"
root_cause: css_specificity
resolution_type: refactor
tags: [css, dark-mode, specificity, inline-style, vue3, theming, important, accessibility, wcag]
---

# Dark mode CSS rules silently lose to inline style attributes

## Problem

A scoped CSS rule under `[data-theme='dark']` does not override an element's background or color when the element carries an inline `style="..."` attribute. The dark mode override is silently ignored — light pastel backgrounds bleed into dark mode and white text becomes invisible on the unchanged light surface.

The bug surfaces with high severity in `InsightsTab.vue` (资产分析-洞悉 → 智能发现 cards), where 5 cards each declared their light-mode gradient via inline `style="background: linear-gradient(...)"`. The matching `[data-theme='dark'] .insight-stat-card:nth-child(N)` rules in `<style scoped>` had zero visual effect because inline styles win the cascade.

## Symptoms

- In dark mode, primary text (asset names, category labels) renders white on a light pastel background and is essentially unreadable
- Toggling `data-theme='dark'` on `<html>` correctly flips text colors driven by `var(--text-primary)`, but card backgrounds stay frozen at the light-mode pastel
- DevTools shows the `[data-theme='dark']` rule is *parsed and matched* but *crossed out* under the inline `style` attribute
- Other `[data-theme='dark']` rules in the same component (those targeting elements without inline style) work correctly — the failure looks intermittent, not systemic, and that masks the root cause

## What Didn't Work

- **Adding `!important` to every dark-mode rule** — Works, but ten `!important` declarations is a code smell, not a fix. It also requires a matching `!important` for any *light-mode override* that ever needs to compete with the dark rule, which compounds the maintenance burden.
- **Increasing selector specificity** (`[data-theme='dark'] .parent .child .insight-stat-card { ... }`) — Inline style still wins. The CSS specification gives inline `style` attributes a specificity of (1,0,0,0) — strictly higher than any selector specificity, regardless of nesting depth. The only ways to beat it are `!important` or eliminating the inline style.
- **`@media (prefers-color-scheme: dark)`** — Same cascade rules apply. Media queries don't change specificity; they only gate when a rule applies.
- **Adding more `[data-theme='dark']` overrides for `--text-primary`** — Treats the symptom (white text invisible) without touching the cause (background never went dark). Text color was already correct via `var(--text-primary)`; the bug was always about the surface beneath it.

## Solution

Move per-instance backgrounds (and any other property toggled by theme) **out of inline `style` attributes and into CSS classes**. Introduce a semantic modifier class per variant; declare both light- and dark-mode rules against that class.

```vue
<!-- Before: inline style wins the cascade — dark mode silently ignored -->
<div class="insight-stat-card" style="background: linear-gradient(135deg, #f3f0ff, #e8f4ff)">
  <div class="isc-icon" style="background: #ede9ff">🛍️</div>
  ...
</div>

<!-- After: modifier class — dark mode rule wins by normal specificity -->
<div class="insight-stat-card isc-card--yoy">
  <div class="isc-icon">🛍️</div>
  ...
</div>
```

```css
/* Light mode — bare class rule, specificity (0,1,0) */
.isc-card--yoy { background: linear-gradient(135deg, #f3f0ff, #e8f4ff); }
.isc-card--yoy .isc-icon { background: #ede9ff; }

/* Dark mode — attribute + class, specificity (0,2,0) > (0,1,0). No !important needed. */
[data-theme='dark'] .isc-card--yoy {
  background: linear-gradient(135deg, rgba(189, 187, 255, 0.14), rgba(147, 197, 253, 0.08));
}
[data-theme='dark'] .isc-card--yoy .isc-icon {
  background: rgba(189, 187, 255, 0.22);
}
```

Three knock-on benefits beyond fixing the visible bug:

1. **No `:nth-child(N)` fragility.** The original code mapped colors to DOM position with `[data-theme='dark'] .insight-stat-card:nth-child(1)` … `:nth-child(5)`. Adding a 6th card (or wrapping one in `v-if`) silently misroutes every gradient. Modifier classes bind color to *meaning*, not position.
2. **Adding cards is safe.** A 6th card without a matching `.isc-card--xxx` rule renders with no background — visibly broken at first glance, not silently broken in dark mode only.
3. **CSS specificity is principled again.** No more `!important` arms race when a future hover or focus state needs to compete with the dark rule.

## Why This Works

CSS specificity assigns inline `style` attributes a weight of (1,0,0,0) — written in the four-component form (inline, ID, class/attr/pseudo-class, type). That outranks **any** selector built from classes, attributes, or pseudo-classes. The matrix:

| Source | Specificity | Beats inline style? |
|--------|------------|---------------------|
| `[data-theme='dark'] .foo` | (0,2,0) | ❌ |
| `[data-theme='dark'] body .foo .bar` | (0,2,1) | ❌ |
| `#main [data-theme='dark'] .foo` | (1,2,0) — same column as inline | ❌ (ID specificity is column 2, not column 1) |
| `inline style="..."` | (1,0,0,0) | — |
| `inline style="...!important"` | `!important` lane | wins over everything except later `!important` |
| `selector { prop: x !important }` | `!important` lane | beats inline `style` without `!important` |

The only paths that *do* outrank inline `style` are `!important` (loud, easy to grep, sticky) or a different inline `style !important`. Refactoring the inline declaration *out* of the markup changes the comparison: a bare class rule is (0,1,0), and `[data-theme='dark'] .foo` is (0,2,0) — which now wins by normal cascade rules, no `!important` required.

The framework angle: in a Vue 3 SFC with `<style scoped>`, scoped styles are post-processed with a data attribute (`[data-v-xxx]`), which adds (0,1,0) to every selector. That helps scoped rules win against *unscoped* class selectors but does **not** help against inline `style` — `[data-v-xxx]` is still column 2, inline `style` is column 1.

## Prevention

- **Never use inline `style="background:..."` (or any color/theme-sensitive property) on elements that need to respond to dark mode.** Move the value into a CSS class. Inline `style` is acceptable only for properties that genuinely cannot be expressed declaratively — dynamic widths from JS state, position calculations, etc. — and even then prefer `:style` bound to a computed (which is still subject to the same specificity rules; the warning still applies).
- **Use semantic modifier classes for per-instance theming** (`.isc-card--yoy`, `.isc-card--high`, etc.), not `:nth-child(N)`. Position-based selectors silently break under reordering, conditional rendering, or future card additions.
- **In Vue 3 SFCs, prefer `<style scoped>` + class names + CSS variables** (`var(--text-primary)`, `var(--bg-secondary)`) over hardcoded colors. Theme tokens are defined in `src/style.css` under `:root` and `[data-theme='dark']`; consume them by name so theme switching is automatic.
- **When tempted to write `!important`, ask: what is forcing this?** Trace the higher-specificity rule first. If the answer is "an inline `style` attribute on the element," the right fix is removing the inline style, not adding `!important`. If the answer is "a third-party component's internal styles," `!important` is sometimes the only option, but document why.
- **WCAG contrast in dark mode**: when stacking white text at `rgba(255, 255, 255, A)` over a tinted dark surface, the composite contrast is sensitive to *both* the alpha and the underlying tint. Spot-check: white at α=0.55 over `#12122a` with a 14% color tint computes to ≈5:1 (passes AA at 4.5:1, but only just). Dropping below α=0.5 on tinted surfaces routinely fails AA — keep secondary labels at α≥0.55, captions at α≥0.6 if you want comfortable margins.

## Related Issues

- `frontend/apps/main/src/components/insights/InsightsTab.vue` — original site of the bug; refactored to modifier classes (`.isc-card--{yoy,high,low,long,top}`)
- `frontend/apps/main/src/style.css` — design tokens (`--text-primary`, `--text-secondary`, `--card-bg`, `--color-lavender`) consumed by the dark-mode rules
- `frontend/apps/main/CLAUDE.md §Dark/Light mode` — project rule mandating CSS variable consumption over hardcoded colors; this bug was a violation of that rule via inline `style` attribute, not via raw color literals in a class
- `frontend/apps/main/DESIGN.md` — Together AI-inspired dual-atmosphere palette; dark mode uses `#010120` / `#12122a` as the canvas
