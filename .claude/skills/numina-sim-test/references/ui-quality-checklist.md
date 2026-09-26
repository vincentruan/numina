# UI Quality Testing Reference

Design system knowledge, mobile H5/PWA testing principles, and Vant4 component
patterns for the Numina sim-test pipeline. Consolidated from `ui-ux-pro-max`,
`frontend-design` skills, and project `docs/solutions/`.

> **This file is reference material.** The test cases live in
> [`area15-ui-quality.md`](../groups/g1-adult-stable/area15-ui-quality.md).
> Read this when you need deeper context on WHY a check exists.

## Mobile-First Testing Principles

### Viewport Priority Order

Test at these widths (narrowest first — mobile-first):

| Width | Device | Why |
|-------|--------|-----|
| 320px | iPhone SE (1st gen) | Smallest supported — overflow bugs surface here |
| 375px | iPhone 13/14 baseline | Primary target for both apps |
| 414px | iPhone 14 Plus / Pro Max | Largest phone — safe-area bottom is 34px |
| 768px | iPad mini | Tablet breakpoint — layout should adapt, not break |

**Rule:** If it works at 375px, it works everywhere wider. Test 320px for edge cases.

### Touch Target Requirements

| Element type | Minimum size | Gap between |
|-------------|-------------|-------------|
| Icon button | 44×44px (iOS) / 48×48dp (Material) | ≥ 8px |
| Tab bar item | 44×44px tap zone | Built-in by Vant |
| List item action | Full row height (≥ 44px) | — |
| Swipe action button | ≥ 44px wide when fully revealed | — |
| Form field clear (×) | 44×44px tap area (visual can be smaller) | — |

**Anti-pattern:** Visual icon is 24×24 but no padding → actual tap target is 24×24. Fix: extend hit area via padding.

### Safe Area Compliance

For PWA `display: standalone` and notched devices:

```
┌──────────────────────────┐
│ ← status bar / notch →   │  env(safe-area-inset-top)
├──────────────────────────┤
│                          │
│    Content area          │
│                          │
├──────────────────────────┤
│ ← home indicator area →  │  env(safe-area-inset-bottom)
└──────────────────────────┘
```

**Must respect safe areas:**
- Fixed headers (PageHeader)
- Bottom tab bars (AppTabBar, ChildTabBar)
- Fixed bottom CTA bars (form submit, AI chat input)
- PWA install prompt
- Offline banner

**Project implementation:**
- Main: `padding-bottom: calc(50px + env(safe-area-inset-bottom))` on MainLayout
- Child: same pattern on ChildLayout
- AIChatBox: `position: fixed; inset: 0` — verify it covers full viewport

### PWA-Specific Checks

| Check | How | Pass criteria |
|-------|-----|---------------|
| SW registered | `navigator.serviceWorker.controller !== null` | truthy |
| Offline banner | Throttle network → offline | `offline-banner` visible |
| Install prompt | Check for PWA install UI | Bottom sheet with slide-up transition |
| Cached chunks | Navigate to code-split route after offline | Route renders (not white screen) |
| Manifest | Check `/manifest.webmanifest` | Icons at 192px + 512px + maskable |

## Design Quality Anti-Patterns (from `frontend-design`)

These are "AI-generated design tells" — if spotted in screenshots, flag them:

| Anti-pattern | What to look for |
|-------------|-------------------|
| SaaS card kit | Identical rounded cards, same shadow on everything, gradient washes |
| Template chrome | Tracked-out ALL-CAPS eyebrows, middle-dot meta strings, spaced em dashes |
| Warm cream + terracotta | Cream bg `#F4F1EA` + terracotta accent `#D97757` (NOT our palette) |
| Dark + acid accent | Near-black + acid green (NOT our dark mode) |
| Typographic accent | One word in italic/bold/color in a headline |
| Careless specificity | CSS classes cancelling each other out (padding/margin conflicts) |

**Our palettes are distinct:**
- Main: cool navy/lavender (`#010120` / `#bdbbff`)
- Child: warm cream/ochre (`#fffaf0` / `#e8b94a`)

Neither matches the anti-pattern palettes. If screenshots look generic, flag it.

## Vant4 Component Patterns (Project-Specific)

### Correct Usage Table

| Need | Use | Anti-pattern |
|------|-----|--------------|
| Card/section | `van-cell-group inset` | Custom div with border |
| List + scroll | `van-list` inside `van-pull-refresh` | Custom infinite scroll |
| Empty state | `EmptyState` (wraps `van-empty`) | Raw `van-empty` or custom |
| Loading | `van-skeleton` / `van-loading` | Blank white during load |
| Confirm | `showConfirmDialog()` | Custom modal |
| Toast | `showToast({ message: t('key') })` | `alert()` or custom toast |
| Picker | readonly `van-field` + `van-popup` + `van-picker` | Native `<select>` |
| Tabs | `van-tabs` with pull-refresh per tab | Custom tab component |
| Swipe actions | `van-swipe-cell` with `#right` slot | Custom swipe handler |
| Forms | `van-form` + `van-field` with `rules` | Manual validation |
| Dark theme | `<van-config-provider :theme>` (main) | Inline style overrides |

### Toast Convention (i18n Required)

```typescript
// ✅ Correct — i18n key
showSuccessToast(t('toast.addSuccess'))
showFailToast(t('toast.operationFailed'))
showLoadingToast(t('toast.loading'))
showToast({ message: t('key'), icon: 'warning-o' })

// ❌ Wrong — hardcoded string
showSuccessToast('Added!')
showFailToast('Failed')
```

### Known Vant4 Gotchas

1. **`:model-value` not `:value`** on `van-field` — `:value` renders once and freezes
2. **`teleport="body"`** required on popups inside `<van-tabs animated swipeable>`
3. **`van-pull-refresh`** should wrap at tab level, not page level (each tab has own scroll)
4. **Icon-only buttons** need `aria-label` — Vant doesn't add this automatically
5. **`van-config-provider`** only in main app — child app uses CSS-only dark mode

## Accessibility Checklist (Mobile H5)

### CRITICAL (Must Pass)

- [ ] Color contrast ≥ 4.5:1 for normal text (both modes)
- [ ] Color contrast ≥ 3:1 for large text (both modes)
- [ ] Touch targets ≥ 44×44px
- [ ] Icon-only buttons have `aria-label`
- [ ] Focus rings visible (2-4px) on interactive elements
- [ ] Form fields have labels (not placeholder-only)
- [ ] Color is not the only indicator (status badges need text/icon too)

### HIGH (Should Pass)

- [ ] Tab order matches visual order
- [ ] `prefers-reduced-motion` respected (celebration animations disabled)
- [ ] Semantic HTML (`<button>`, `<nav>`, `<main>` — not `<div>` for everything)
- [ ] Error messages near their fields with recovery path
- [ ] Sequential heading hierarchy (h1 → h2 → h3, no level skip)

### MEDIUM (Nice to Have)

- [ ] Dynamic ARIA bindings (`:aria-expanded`, `:aria-selected`)
- [ ] Screen reader focus order matches visual order
- [ ] Decorative icons have `aria-hidden="true"`
- [ ] Input `inputmode` matches expected keyboard (email, tel, number)

## Dark Mode Testing Methodology

### Main App ("Together AI")

**Mechanism:** `<van-config-provider :theme="resolvedTheme">` wraps the app.
Theme resolves from user preference or system `prefers-color-scheme`.
Also sets `data-theme` attribute on `<html>` for CSS variable switching.

**Test approach:**
1. Navigate to Settings → Appearance → toggle dark mode
2. Verify `data-theme="dark"` on `<html>`
3. Screenshot each major page
4. Check: no light backgrounds bleeding through, text readable, charts updated

**Common failures:**
- Inline `style="background:..."` defeats `[data-theme='dark']` CSS rules
- ECharts charts don't update (MutationObserver not triggered)
- Third-party widget (CAPTCHA) doesn't respond to theme change

### Child App ("Clay")

**Mechanism:** `useDarkMode()` composable sets `[data-theme="dark"]` on `<html>`.
NO `<van-config-provider>`. All overrides via CSS selectors targeting `[data-theme="dark"]`.

**Iron rule:** Every CSS token must be defined in BOTH `:root` AND `[data-theme="dark"]`.

**Test approach:**
1. Navigate to child Settings → toggle dark mode
2. Verify `[data-theme="dark"]` on `<html>`
3. Screenshot each child tab
4. Check: warm cream → dark teal transition, coin gradients adjusted, text readable

**Common failures:**
- New CSS token added to `:root` but forgotten in `[data-theme="dark"]`
- Vant component not overridden (check 25+ components in `clay.css`)
- Smooth theme transition (`transition: background-color 0.2s`) causes flash

## Cross-App Consistency Matrix

These patterns must behave identically (visually) across both apps:

| Pattern | Expected behavior | How to verify |
|---------|-------------------|---------------|
| Empty state | Same visual weight, centered, with description | Screenshot both |
| Loading skeleton | Appears within 300ms, same pulse animation | Time + screenshot |
| Pull-to-refresh | Same threshold, same spinner | Compare feel |
| Toast messages | Same position (top), same duration (3s), same style | Trigger + compare |
| Dialog/popup | Same overlay opacity, same animation | Trigger + compare |
| Page transitions | Main: none (KeepAlive only). Child: `page-fade` | Navigate + observe |
| Offline banner | Same position (top), same style | Toggle offline |
| PWA install prompt | Same position (bottom), same slide-up | Check for presence |

**Differences that are intentional:**
- Main uses `van-config-provider` for dark mode; Child uses CSS-only
- Main has more data-heavy layouts; Child has gamification/animation layer
- Main uses `Space Grotesk + Inter`; Child uses its own Clay typography
- Child has celebration animations, coin effects, blind box mechanics
