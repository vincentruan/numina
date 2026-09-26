# Area 15 — UI Quality & Design System Audit

Cross-cutting UI quality checks that verify design-system compliance, mobile
responsiveness, dark-mode correctness, accessibility basics, PWA behavior,
and Vant4 component usage across both apps.

> **When to run:** After functional areas (Phase 3/4/5) when time permits,
> or standalone via `"ui quality test"` / `"设计审查"` / `"UI 质量检查"`.
> Estimated duration: ~25-35 min.

## Prerequisites

- Adult session `$SID` active (from Phase 2)
- Child session `$SID_CHILD` active (from Phase 5)
- Browser viewport set to **375×812** (iPhone 13/14 baseline) for all cases
- Dark mode testable: user preference toggle or system `prefers-color-scheme`

## Design System Reference

### Main App — "Together AI" (cool palette)

| Role | Light | Dark | Token |
|------|-------|------|-------|
| Canvas | `#ffffff` | `#010120` | `--bg-primary` |
| Surface | `#f5f5ff` / `#f7f8fa` | `#12122a` | `--card-bg` |
| Primary text | `#0a0a0a` | `#f5f5f5` | `--text-primary` |
| Secondary text | `#616161` | `#c8c8d0` | `--text-secondary` |
| CTA/Primary | `#010120` | `#bdbbff` (lavender) | `--van-primary-color` |
| Error | `#b30000` | adjusted | `--color-error` |
| Success | `#1a7a4a` | `#2f9e44` | `--color-success` |

- Dark mode via `<van-config-provider :theme="resolvedTheme">` + `data-theme` on `<html>`
- Typography: Space Grotesk (display) / Inter (body) / system mono
- Radius scale: `--radius-xs` (4px) → `--radius-xl` (30px)
- **Red line:** No inline `style="color:..."` — all theming via CSS variables

### Child App — "Clay" (warm palette)

| Role | Light | Dark | Token |
|------|-------|------|-------|
| Canvas | `#fffaf0` (warm cream) | `#0a1a1a` (dark teal) | `--color-canvas` |
| Card surface | `#f5f0e0` | `#152828` | `--color-surface-card` |
| Primary text | `#0a0a0a` | `#f0ece0` | `--color-ink` |
| Secondary text | `#3a3a3a` | `#c0bcb0` | `--color-body` |
| CTA/Primary | `#0a0a0a` | `#e8b94a` (ochre gold) | `--color-primary` |

- Dark mode via CSS only (`useDarkMode()` + `[data-theme="dark"]` selectors)
- **Iron rule:** Every CSS token must be defined in both `:root` and `[data-theme="dark"]`
- Brand accents: Pink `#ff4d8b`, Teal `#1a3a3a`, Lavender `#b8a4ed`, Peach `#ffb084`, Ochre `#e8b94a`, Mint `#a4d4c5`, Coral `#ff6b5a`

## Test Cases

### UIQ.1 — Mobile viewport baseline (both apps)

Set viewport to 375×812. Navigate to each app's home page.

**Main app checks:**
- [ ] No horizontal scrollbar at any tab (Dashboard, Finance, AI, Baby, Settings)
- [ ] AppTabBar fully visible with all icons + labels, no truncation
- [ ] PageHeader title fits without ellipsis on narrow screens
- [ ] Card content (`van-cell-group inset`) does not overflow viewport

**Child app checks:**
- [ ] ChildTabBar 5 items visible, icons + labels not truncated
- [ ] Home page coin/reward displays fit without overflow
- [ ] Task list items readable at 375px width

**Verification:** `screenshot` at 375px. Look for horizontal scroll indicators or clipped content.

### UIQ.2 — Dark mode visual verification (main app)

Toggle dark mode (Settings → appearance, or inspect `data-theme` attribute).

**Check these pages in dark mode:**
- [ ] Dashboard: all cards have dark background (`#12122a`), text readable
- [ ] Finance hub: tab bar, card backgrounds, amount text contrast
- [ ] AI chat: message bubbles, input box, streaming indicators
- [ ] Settings: cell-group backgrounds, divider visibility
- [ ] Forms: field backgrounds, placeholder text visible, picker popup backgrounds

**Red flags (known failure patterns from `docs/solutions/ui-bugs/`):**
- Inline `style="background:..."` that doesn't flip → white card on dark canvas
- Text at alpha < 0.5 over dark tinted surfaces fails WCAG AA
- ECharts charts still using light-mode palette (MutationObserver not triggered)

**Verification:** Screenshot each page in dark mode. Check that no element has a light background bleeding through.

### UIQ.3 — Dark mode visual verification (child app)

Toggle child app dark mode.

**Check:**
- [ ] Canvas shifts from warm cream (`#fffaf0`) to dark teal (`#0a1a1a`)
- [ ] Card surfaces shift to `#152828`
- [ ] Text shifts to warm light (`#f0ece0`)
- [ ] Coin components (gold/silver/copper) remain visible with adjusted gradients
- [ ] Celebration animations still visible (if triggered)
- [ ] Calendar heat colors shift to teal-green tones

**Iron rule check:** Any element still showing light-mode colors means a CSS token is missing the `[data-theme="dark"]` definition.

### UIQ.4 — Vant4 component pattern compliance

Spot-check Vant4 component usage patterns across both apps:

**`:model-value` vs `:value` (HIGH — known silent failure):**
- [ ] Open any page with a picker field (e.g., asset form → category picker)
- [ ] Select a value from the popup
- [ ] Verify the `van-field` updates to show the selected value
- [ ] If field shows initial value but doesn't update → `:value` bug (should be `:model-value`)

**Popup teleport in swipeable tabs:**
- [ ] Navigate to Finance → swipeable tab with a filter/action that opens a popup
- [ ] If popup is invisible but clicks register "blind" → missing `teleport="body"`
- [ ] Check AI time-machine (`/ai/time-machine`) action sheet specifically

**Three-state rendering:**
- [ ] Dashboard: skeleton → empty → content (pull-to-refresh + van-list)
- [ ] Finance lists: skeleton → empty → content
- [ ] Verify no blank white flash during loading (skeleton should appear within 300ms)

**Form submit buttons:**
- [ ] Full-width `van-button round block type="primary"` inside padded container
- [ ] No horizontal margin overflow (check at 320px width)

### UIQ.5 — Touch target sizing (mobile H5)

At 375×812 viewport, verify interactive elements:

- [ ] All icon-only buttons (close, back, settings gear) ≥ 44×44px tap area
- [ ] Bottom tab bar items have comfortable spacing (≥ 8px between tap zones)
- [ ] Swipe-action buttons (`van-swipe-cell`) fully reveal at 375px
- [ ] FAB button (if present) doesn't overlap tab bar or safe area
- [ ] Form field clear buttons (×) are tappable, not just visual

**How to verify:** Use browser driver's evaluate to measure `getBoundingClientRect()` on interactive elements. Flag any with width or height < 44px.

```javascript
// Touch target audit snippet
document.querySelectorAll('button, [role="button"], .van-icon, .van-cell, .van-tabbar-item')
  .forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 44 || r.height < 44) {
      console.warn('Small touch target:', el.className, r.width, r.height);
    }
  });
```

### UIQ.6 — Safe area compliance (PWA / notch devices)

Simulate safe-area insets using CSS override:

```css
/* Inject via browser driver to simulate iPhone notch */
:root { --safe-area-inset-bottom: 34px; }
```

- [ ] Main app: AppTabBar doesn't overlap home indicator
- [ ] Main app: Fixed bottom bars (AI chat input, form submit) clear safe area
- [ ] Child app: ChildTabBar clears safe area
- [ ] AI chat input box (`AIChatBox`) doesn't get cut off at bottom
- [ ] PWA install prompt doesn't overlap tab bar

### UIQ.7 — PWA offline behavior

- [ ] Both apps show `offline-banner` when network is throttled to offline
- [ ] Banner dismisses when network restores
- [ ] Service worker registration is present (check `navigator.serviceWorker.controller`)
- [ ] PWA install prompt appears (check for `useInstallPrompt` bottom sheet)

**How to test offline:** Use browser driver to set network throttling or navigate to a cached page after going offline.

### UIQ.8 — Accessibility basics

At 375×812 viewport:

- [ ] All icon-only buttons have `aria-label` (spot-check 5 icons per app)
- [ ] Form fields have visible labels (not placeholder-only)
- [ ] Tab order follows visual order (tab through Dashboard → first few elements)
- [ ] Focus rings visible on interactive elements (2-4px)
- [ ] `prefers-reduced-motion`: celebration animations in child app respect this
- [ ] Color is not the only indicator (e.g., status badges have text/icon + color)

**Verification:** Use accessibility tree snapshot to check for missing names on interactive elements.

### UIQ.9 — NProgress behavior (regression of 3 known bugs)

- [ ] Navigate between 3+ pages with skeleton loaders → single continuous progress bar (no flicker)
- [ ] Navigate to a non-skeleton route → progress bar completes (no stuck spinner)
- [ ] Scroll down a page, then trigger navigation → progress bar visible at top (not scrolled away)

### UIQ.10 — Cross-app style consistency

Verify that shared patterns are consistent between main and child apps:

| Pattern | Main app | Child app | Match? |
|---------|----------|-----------|--------|
| Empty state | `EmptyState.vue` (wraps `van-empty`) | `EmptyState.vue` (own impl) | Same visual weight |
| Page header | `PageHeader.vue` | `PageHeader.vue` | Same height/padding |
| Icon wrapper | `IIcon.vue` | `IIcon.vue` | Same sizing |
| Offline banner | present | present | Same position/style |
| PWA install prompt | present | present | Same animation |
| Loading skeleton | `van-skeleton` | skeleton components | Same timing |
| Pull-to-refresh | `van-pull-refresh` | `van-pull-refresh` | Same threshold |

## Failure Taxonomy for UIQ Cases

| Code | Meaning | Example |
|------|---------|---------|
| `UI-OVERFLOW` | Viewport overflow | Horizontal scroll at 375px |
| `UI-DARK` | Dark mode defect | Inline style not flipping |
| `UI-CONTRAST` | Contrast failure | Text unreadable in either mode |
| `UI-TOUCH` | Touch target too small | Icon button < 44×44px |
| `UI-SAFE` | Safe area violation | Tab bar behind home indicator |
| `UI-PWA` | PWA defect | No offline banner, SW not registered |
| `UI-A11Y` | Accessibility defect | Missing aria-label, no focus ring |
| `UI-VANT` | Vant4 pattern violation | `:value` instead of `:model-value` |
| `UI-CONSIST` | Cross-app inconsistency | Different empty-state styles |
| `UI-PROGRESS` | NProgress regression | Flicker / stuck / invisible |

## Known Pitfalls Reference

These are verified historical bugs — if any reappear, flag immediately:

1. **Inline style specificity** → dark mode override silently defeated
2. **`:value` on van-field** → reactive display frozen (no Vue warning)
3. **Transition + KeepAlive + :key** → permanent blank router-view
4. **Popup inside swipeable tabs** → clipped, clicks register blind
5. **Full-width button + margin** → viewport overflow on 320px
6. **NProgress parent: '#app'** → bar invisible when scrolled
7. **Onboarding overlay z-index** → blocks tab bar navigation
8. **Action sheet in transformed container** → needs `teleport="body"`
