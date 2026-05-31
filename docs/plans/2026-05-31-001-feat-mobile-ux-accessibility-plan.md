---
title: "feat: Mobile UX Accessibility — Touch Targets + New User Onboarding"
type: feat
status: planned
date: 2026-05-31
source: docs/brainstorms/2026-05-31-mobile-ux-accessibility-requirements.md
---

# feat: Mobile UX Accessibility — Touch Targets + New User Onboarding

## Overview

Two independent workstreams derived from the brainstorm review. Part A fixes touch target sizes across four components to meet the WCAG 2.1 SC 2.5.5 (AAA) 44×44px standard. Part B builds a 3-step onboarding overlay for new users entering an empty Dashboard. Part A tasks are fully independent of Part B and can be parallelized.

## Requirements Trace

- R1–R3: CSS padding/min-height fixes on StatusSummaryGrid, CategoryGrid, UsageFreqSelector
- R4–R6: Verification-only tasks for FAB, Tab Bar, FAB menu items
- R7–R9: Cross-cutting verification (DevTools tap highlight, dark mode, focus-visible)
- R10–R11: Onboarding trigger conditions and guard logic
- R12–R14: 3-step spotlight overlay implementation
- R15–R18: Interaction and state (skip/next/complete, scroll lock, overlay click guard)
- R19–R21: Accessibility (focus trap, aria-live, Escape key)
- R22–R23: i18n and dark mode for onboarding
- R24–R25: Edge cases (old user guard, browser back/forward)

---

## Part A: Touch Target Fixes

These tasks are independent of each other and of Part B. They can be worked in parallel.

---

### Task A1 — Fix StatusSummaryGrid `.status-tab` touch target

**File:** `frontend/apps/main/src/components/dashboard/StatusSummaryGrid.vue`

**What to change:**

The `.status-tab` rule currently has `padding: 8px 14px` and `min-height: 36px`. The rendered height is ~36px, which is below the 44px target. Increase `min-height` to `44px`. The horizontal dimension is already satisfied by the text content + padding on most tabs, but add `min-width: 44px` as a safety floor.

```css
/* Before */
.status-tab {
  padding: 8px 14px;
  min-height: 36px;
}

/* After */
.status-tab {
  padding: 8px 14px;
  min-height: 44px;
  min-width: 44px;
}
```

Also add `:focus-visible` to `.status-tab` (it is currently missing — only `.grid-item` in CategoryGrid has it):

```css
.status-tab:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
}
```

**Acceptance criteria:**
- DevTools tap highlight shows ≥44px height on every `.status-tab` at 375px viewport
- `:focus-visible` ring appears when tabbing to a status tab with keyboard
- Visual appearance unchanged in light and dark mode (no layout shift, no text wrapping)
- `pnpm typecheck` passes (CSS-only change, no TS impact)

---

### Task A2 — Fix CategoryGrid `.grid-item` touch target

**File:** `frontend/apps/main/src/components/asset/CategoryGrid.vue`

**What to change:**

The `.grid-item` rule has `padding: 8px 4px`. In a 4-column grid on a 375px screen, each column is ~80px wide (satisfying the 44px horizontal requirement). The vertical dimension needs to reach 44px. The current content is a 22px icon + 4px margin + ~12px label = ~38px content height. Increasing vertical padding from `8px` to `11px` top/bottom brings the total to ≥44px.

```css
/* Before */
.grid-item {
  padding: 8px 4px;
}

/* After */
.grid-item {
  padding: 11px 4px;
}
```

The `:focus-visible` rule already exists on `.grid-item` — no change needed there.

**Acceptance criteria:**
- DevTools tap highlight shows ≥44px height on every `.grid-item` at 375px viewport
- 4-column grid layout is visually unchanged (no overflow, no wrapping)
- Selected state border and background render correctly in light and dark mode
- `pnpm typecheck` passes

---

### Task A3 — Fix UsageFreqSelector `.freq-item` touch target

**File:** `frontend/apps/main/src/components/asset/UsageFreqSelector.vue`

**What to change:**

The `.freq-item` rule has `padding: 8px 4px`. In a 5-column flex layout on a 375px screen, each item is ~63px wide (satisfying horizontal). Increase vertical padding to reach 44px total height. Current content: 20px icon + 4px margin + ~12px label = ~36px. Increasing vertical padding from `8px` to `12px` brings total to ≥44px.

Also add `:focus-visible` (currently absent):

```css
/* Before */
.freq-item {
  padding: 8px 4px;
}

/* After */
.freq-item {
  padding: 12px 4px;
}

/* Add */
.freq-item:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
}
```

The `.freq-item` `div` is not keyboard-focusable by default. Add `tabindex="0"` and `role="radio"` (or `role="button"`) in the template, and wire `@keydown.enter` / `@keydown.space` to emit the same event as `@click`:

```html
<div
  v-for="opt in options"
  :key="opt.value"
  class="freq-item"
  :class="{ selected: modelValue === opt.value }"
  role="radio"
  :aria-checked="modelValue === opt.value"
  tabindex="0"
  @click="$emit('update:modelValue', opt.value)"
  @keydown.enter.prevent="$emit('update:modelValue', opt.value)"
  @keydown.space.prevent="$emit('update:modelValue', opt.value)"
>
```

**Acceptance criteria:**
- DevTools tap highlight shows ≥44px height on every `.freq-item` at 375px viewport
- 5-column flex layout is visually unchanged
- Keyboard: Tab reaches each item, Enter/Space selects it, `:focus-visible` ring appears
- `pnpm typecheck` passes

---

### Task A4 — Verify FAB button touch target (R4)

**File:** `frontend/apps/main/src/pages/DashboardPage.vue`

**What to do:**

The FAB is `width: 52px; height: 52px` — already satisfies 44×44px. This is a verification-only task. No code changes.

Steps:
1. Open DevTools > Rendering > "Show tap highlights" (or use the Layers panel)
2. At 375px viewport, confirm the FAB tap highlight is 52×52px
3. Confirm the FAB renders correctly in both light and dark mode (dark mode uses `var(--color-lavender)` background)
4. Record the finding in a comment in this plan (update `status` field to `verified`)

**Acceptance criteria:**
- Documented confirmation that FAB is 52×52px (no code change required)
- No regression introduced

---

### Task A5 — Verify Tab Bar item touch targets (R5)

**File:** `frontend/apps/main/src/components/common/AppTabBar.vue`

**What to do:**

Vant `van-tabbar` default height is 50px. Each item uses `flex: 1; padding: 0 2px`. On a 375px screen:
- 5-tab layout (non-owner): each item is 375/5 = 75px wide — satisfies 44px
- 6-tab layout (owner): each item is 375/6 = 62.5px wide — satisfies 44px

Verify both layouts in DevTools at 375px. If either layout produces an item narrower than 44px (unlikely given the math), add `min-width: 44px` to `.app-tabbar :deep(.van-tabbar-item)`.

**Acceptance criteria:**
- Documented confirmation of tap target width for both 5-tab and 6-tab layouts
- If a fix is needed: `min-width: 44px` added and verified
- No visual regression in either layout

---

### Task A6 — Verify FAB menu item touch targets (R6)

**File:** `frontend/apps/main/src/pages/DashboardPage.vue`

**What to do:**

The `.fab-menu-item` rule already has `min-height: 44px`. Verify the actual rendered height in DevTools at 375px. The items are full-width within the menu container (right-aligned, `align-items: flex-end`), so width is determined by content. Confirm width ≥44px as well.

**Acceptance criteria:**
- Documented confirmation that both FAB menu items (Import Bill, Add Asset) have ≥44×44px tap targets
- No code change required if already satisfied

---

### Task A7 — Cross-cutting verification: DevTools tap highlight audit (R7)

**Scope:** All components modified or verified in A1–A6.

**What to do:**

Using Chrome DevTools at 375px viewport width:
1. Enable Rendering > "Show tap highlights" (or use the accessibility inspector)
2. Systematically tap/hover each interactive element in: StatusSummaryGrid, CategoryGrid, UsageFreqSelector, FAB, Tab Bar (5-tab and 6-tab), FAB menu items
3. Confirm every element shows a tap highlight ≥44×44px
4. Screenshot or note any failures

This task is a gate: if any element fails, the corresponding A1–A6 task must be reopened.

**Acceptance criteria:**
- All interactive elements in scope show ≥44×44px tap highlight
- Findings documented (pass/fail per element)

---

### Task A8 — Cross-cutting verification: light/dark mode visual check (R8)

**Scope:** All components modified in A1–A3.

**What to do:**

For each modified component (StatusSummaryGrid, CategoryGrid, UsageFreqSelector):
1. Toggle `data-theme="dark"` on `<html>` (or use the app's theme switcher)
2. Visually confirm: no color bleed, no invisible text, selected state renders correctly, border colors use CSS variables (not hardcoded)
3. Confirm the increased padding does not cause layout overflow or unexpected wrapping in dark mode

**Acceptance criteria:**
- All three components render correctly in both light and dark mode after padding changes
- No hardcoded colors introduced by the changes

---

### Task A9 — Cross-cutting verification: focus-visible on all modified components (R9)

**Scope:** StatusSummaryGrid (A1), UsageFreqSelector (A3). CategoryGrid already has `:focus-visible`.

**What to do:**

1. Tab through the page with keyboard only
2. Confirm `:focus-visible` ring appears on `.status-tab` (added in A1) and `.freq-item` (added in A3)
3. Confirm the ring uses `var(--van-primary-color)` (light) / `var(--color-lavender)` (dark) — the dark mode override for `--van-primary-color` is already set globally, so no extra rule is needed
4. Confirm no focus ring appears on mouse click (`:focus-visible` vs `:focus` distinction)

**Acceptance criteria:**
- Keyboard focus ring visible on all modified interactive elements
- No focus ring on mouse click
- Ring color adapts to dark mode automatically via CSS variable

---

## Part B: New User Onboarding Flow

These tasks have dependencies. Work them in the order listed. Part B can be started in parallel with Part A but the onboarding component (B2) should not be integrated into DashboardPage (B3) until B2 is complete.

---

### Task B1 — Add i18n keys for onboarding copy (R22)

**Files:**
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

**What to add:**

Add an `onboarding` namespace to both locale files (lockstep). Keys needed:

```ts
// zh-CN.ts
onboarding: {
  step1Title: '家庭资产全貌',
  step1Body: '这里展示您家庭的净资产、总资产和负债，随时掌握财务全局。',
  step2Title: '添加第一笔资产',
  step2Body: '点击右下角的按钮，记录您的第一笔资产，开始管理家庭财富。',
  step3Title: '邀请家人一起管理',
  step3Body: '在设置中生成邀请码，让家人加入，共同维护家庭资产。',
  skip: '跳过',
  next: '下一步',
  finish: '完成',
  stepIndicator: '{current} / {total}',
},
```

```ts
// en-US.ts
onboarding: {
  step1Title: 'Your Family Finances at a Glance',
  step1Body: 'This card shows your net worth, total assets, and liabilities — your complete financial picture.',
  step2Title: 'Add Your First Asset',
  step2Body: 'Tap the button in the bottom-right corner to record your first asset and start tracking.',
  step3Title: 'Invite Your Family',
  step3Body: 'Go to Settings to generate an invite code and bring your family on board.',
  skip: 'Skip',
  next: 'Next',
  finish: 'Done',
  stepIndicator: '{current} / {total}',
},
```

**Acceptance criteria:**
- Both locale files compile without TypeScript errors (`pnpm typecheck`)
- Keys are present and identical in structure in both files
- No hardcoded Chinese strings in the onboarding component (verified in B2)

---

### Task B2 — Build OnboardingOverlay component (R12–R21, R23)

**File to create:** `frontend/apps/main/src/components/common/OnboardingOverlay.vue`

**Props:**

```ts
defineProps<{
  steps: Array<{
    targetSelector: string  // CSS selector for the element to spotlight
    titleKey: string        // i18n key
    bodyKey: string         // i18n key
  }>
}>()

defineEmits<{
  complete: []
  skip: []
}>()
```

**Template structure:**

```html
<teleport to="body">
  <van-overlay :show="visible" :z-index="1000" :lock-scroll="true" class="onboarding-overlay" @click.self.prevent>
    <!-- Spotlight cutout via box-shadow -->
    <div class="spotlight" :style="spotlightStyle" aria-hidden="true" />

    <!-- Step card -->
    <div
      ref="cardRef"
      class="onboarding-card"
      role="dialog"
      aria-modal="true"
      :aria-label="t('onboarding.step' + (currentStep + 1) + 'Title')"
    >
      <!-- aria-live region for step announcements -->
      <div aria-live="polite" aria-atomic="true" class="sr-only">
        {{ t(steps[currentStep].titleKey) }} — {{ t(steps[currentStep].bodyKey) }}
      </div>

      <p class="step-indicator">{{ t('onboarding.stepIndicator', { current: currentStep + 1, total: steps.length }) }}</p>
      <h3 class="step-title">{{ t(steps[currentStep].titleKey) }}</h3>
      <p class="step-body">{{ t(steps[currentStep].bodyKey) }}</p>

      <div class="step-actions">
        <button ref="skipBtnRef" class="btn-skip" @click="onSkip">{{ t('onboarding.skip') }}</button>
        <button ref="nextBtnRef" class="btn-next" @click="onNext">
          {{ currentStep < steps.length - 1 ? t('onboarding.next') : t('onboarding.finish') }}
        </button>
      </div>
    </div>
  </van-overlay>
</teleport>
```

**Key implementation details:**

1. **Spotlight positioning (R13, R14):** On each step change, call `getBoundingClientRect()` on the target element (resolved via `document.querySelector(step.targetSelector)`). Compute the spotlight as a `box-shadow` with a large spread on a positioned `div`:

   ```ts
   function updateSpotlight() {
     const el = document.querySelector(steps[currentStep].targetSelector)
     if (!el) return
     const rect = el.getBoundingClientRect()
     const padding = 8
     spotlightStyle.value = {
       position: 'fixed',
       top: `${rect.top - padding}px`,
       left: `${rect.left - padding}px`,
       width: `${rect.width + padding * 2}px`,
       height: `${rect.height + padding * 2}px`,
       borderRadius: '12px',
       boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.6)',
       pointerEvents: 'none',
       zIndex: 1001,
     }
   }
   ```

   Call `updateSpotlight()` in `onMounted`, on each step change (via `watch(currentStep, ...)`), and on `window.resize`.

2. **Scroll lock (R18):** `van-overlay` with `:lock-scroll="true"` handles `overflow: hidden` on body. Verify this is sufficient; if not, manually set `document.body.style.overflow = 'hidden'` on mount and restore on unmount.

3. **Overlay click guard (R17):** The `van-overlay` `@click.self.prevent` prevents closing on backdrop click. Do not emit `skip` or `complete` from the overlay click handler.

4. **Focus trap (R19):** On mount and on each step change, focus the "Next/Finish" button. Intercept `Tab` and `Shift+Tab` on the card to cycle only between `skipBtnRef` and `nextBtnRef`:

   ```ts
   function onKeydown(e: KeyboardEvent) {
     if (e.key === 'Escape') { onSkip(); return }
     if (e.key !== 'Tab') return
     e.preventDefault()
     if (e.shiftKey) {
       // move focus to skip if on next, or next if on skip
       if (document.activeElement === skipBtnRef.value) nextBtnRef.value?.focus()
       else skipBtnRef.value?.focus()
     } else {
       if (document.activeElement === nextBtnRef.value) skipBtnRef.value?.focus()
       else nextBtnRef.value?.focus()
     }
   }
   ```

   Attach `onKeydown` to the card element via `@keydown` or `document.addEventListener` (remove on unmount).

5. **Escape key (R21):** Handled inside `onKeydown` above.

6. **aria-live (R20):** The `sr-only` div with `aria-live="polite"` re-announces on each step change because its text content changes reactively.

7. **Dark mode (R23):** All colors use CSS variables. The overlay background is `rgba(0,0,0,0.6)` (acceptable in both modes). Card uses `var(--card-bg)`, text uses `var(--text-primary)` / `var(--text-secondary)`. Button uses `var(--van-primary-color)`. Add `[data-theme='dark']` overrides only if the default variables are insufficient.

**CSS skeleton:**

```css
.onboarding-overlay {
  /* van-overlay already covers viewport; no extra positioning needed */
}
.spotlight {
  /* positioned via inline style from JS */
}
.onboarding-card {
  position: fixed;
  bottom: 80px;   /* above tab bar */
  left: 16px;
  right: 16px;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 20px 16px 16px;
  box-shadow: 0 8px 32px rgba(1, 1, 32, 0.18);
  z-index: 1002;
}
[data-theme='dark'] .onboarding-card {
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}
.step-indicator {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 6px;
}
.step-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}
.step-body {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 16px;
}
.step-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.btn-skip {
  background: none;
  border: none;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 10px 8px;
  min-height: 44px;
  min-width: 44px;
}
.btn-next {
  flex: 1;
  background: var(--van-primary-color);
  color: var(--color-on-primary);
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  padding: 12px 20px;
  min-height: 44px;
  cursor: pointer;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

**Acceptance criteria:**
- Component renders the spotlight correctly around each target element at 375px and 414px viewport widths
- Spotlight repositions on step change and on window resize
- Tab key cycles only between Skip and Next/Finish buttons
- Escape key triggers skip
- `aria-live` region text updates on each step change
- Clicking the dark overlay area does NOT close the overlay
- Scroll is locked while overlay is visible
- Skip and Next/Finish buttons are ≥44×44px tap targets
- Component renders correctly in light and dark mode
- All strings use `t('onboarding.*')` — no hardcoded text
- `pnpm typecheck` passes

---

### Task B3 — Add onboarding trigger logic to DashboardPage (R10, R11, R16, R24, R25)

**File:** `frontend/apps/main/src/pages/DashboardPage.vue`

**Depends on:** B2 (component must exist), B1 (i18n keys must exist)

**What to add:**

1. Import `OnboardingOverlay` and add it to the template (after the FAB template block, before closing `</div>`):

   ```html
   <OnboardingOverlay
     v-if="showOnboarding"
     :steps="onboardingSteps"
     @complete="onOnboardingComplete"
     @skip="onOnboardingComplete"
   />
   ```

2. Define the steps array (computed, so i18n keys resolve reactively):

   ```ts
   const onboardingSteps = computed(() => [
     {
       targetSelector: '.net-worth-card',   // adjust to actual class on NetWorthCard root
       titleKey: 'onboarding.step1Title',
       bodyKey: 'onboarding.step1Body',
     },
     {
       targetSelector: '.fab',
       titleKey: 'onboarding.step2Title',
       bodyKey: 'onboarding.step2Body',
     },
     {
       targetSelector: '.app-tabbar .van-tabbar-item:last-child',  // settings tab
       titleKey: 'onboarding.step3Title',
       bodyKey: 'onboarding.step3Body',
     },
   ])
   ```

   Note: verify the actual CSS selector for NetWorthCard's root element before finalizing. If it has no stable class, add `class="net-worth-card"` to its root `<div>` in `NetWorthCard.vue`.

3. Trigger logic (R10, R11):

   ```ts
   const ONBOARDING_KEY = 'onboarding_completed'
   const showOnboarding = ref(false)

   function checkOnboardingTrigger() {
     const alreadyCompleted = localStorage.getItem(ONBOARDING_KEY) === 'true'
     if (alreadyCompleted) return
     // Guard: only trigger when asset count is 0 (R11, R24)
     const assetCount = overview.value?.asset_count ?? null
     if (assetCount === null) return  // data not yet loaded
     if (assetCount > 0) return       // old user who cleared localStorage
     showOnboarding.value = true
   }

   function onOnboardingComplete() {
     localStorage.setItem(ONBOARDING_KEY, 'true')
     showOnboarding.value = false
   }
   ```

4. Call `checkOnboardingTrigger()` inside the `.then()` callback of `dashboardStore.fetchAll()` in `onMounted`, after the overview data is available:

   ```ts
   dashboardStore.fetchAll().then(() => {
     checkOnboardingTrigger()   // add this line
     const initialStatus = activeStatus.value || 'in_use'
     dashboardStore.fetchAssetsPage(initialStatus, 1, 20, undefined)
     dashboardStore.fetchCategoryCounts(initialStatus)
   })
   ```

5. Browser back/forward handling (R25): `showOnboarding` is a reactive ref scoped to the component instance. If the user navigates away and returns, `onMounted` runs again and `checkOnboardingTrigger()` re-evaluates. Since `localStorage` is not set until complete/skip, the overlay will re-show from Step 1 on return — which is the specified behavior.

**Acceptance criteria:**
- New user (asset_count === 0, no localStorage key) sees the overlay on Dashboard load
- User with assets (asset_count > 0) does NOT see the overlay even if localStorage key is absent
- Completing or skipping sets `localStorage.onboarding_completed = 'true'` and hides the overlay
- Returning to Dashboard after navigating away (without completing) shows the overlay again from Step 1
- `pnpm typecheck` passes

---

### Task B4 — Verify NetWorthCard selector for spotlight targeting

**File:** `frontend/apps/main/src/components/dashboard/NetWorthCard.vue`

**Depends on:** B3 (need to know what selector is used)

**What to do:**

Read `NetWorthCard.vue` and confirm the root element has a stable, unique CSS class (e.g., `.net-worth-card`). If it does not, add `class="net-worth-card"` to the root element. This is a prerequisite for the Step 1 spotlight to target correctly.

**Acceptance criteria:**
- `NetWorthCard.vue` root element has a stable class that can be used as a CSS selector
- The selector used in `onboardingSteps` in B3 resolves to exactly one element in the DOM when Dashboard is loaded
- `pnpm typecheck` passes

---

### Task B5 — End-to-end onboarding flow verification

**Depends on:** B1, B2, B3, B4

**What to do:**

Manual verification checklist at 375px and 414px viewport widths:

1. Clear localStorage, open Dashboard with 0 assets → overlay appears on Step 1
2. Step 1 spotlight covers NetWorthCard; card text matches zh-CN strings
3. Click "下一步" → Step 2 spotlight covers FAB; `aria-live` region updates
4. Click "下一步" → Step 3 spotlight covers Settings tab
5. Click "完成" → overlay disappears; `localStorage.onboarding_completed === 'true'`
6. Reload page → overlay does NOT reappear
7. Clear localStorage, add one asset, reload → overlay does NOT appear (asset_count > 0 guard)
8. Clear localStorage, open Dashboard with 0 assets, press Escape → overlay disappears; localStorage key set
9. Clear localStorage, open Dashboard with 0 assets, Tab through buttons → focus cycles between Skip and Next only
10. Toggle dark mode → overlay card and spotlight render correctly
11. Switch language to English → all strings show English copy
12. Resize window while overlay is open → spotlight repositions to track target element

**Acceptance criteria:**
- All 12 checklist items pass
- No console errors during the flow
- `pnpm typecheck` and `pnpm test:run` pass (no regressions)

---

## Dependency Graph

```
Part A (all independent, parallelizable):
  A1 → A7, A8, A9
  A2 → A7, A8
  A3 → A7, A8, A9
  A4 → A7
  A5 → A7
  A6 → A7

Part B (ordered by dependency):
  B1 (i18n keys)
    ↓
  B2 (OnboardingOverlay component)  ←  B4 (NetWorthCard selector check)
    ↓
  B3 (DashboardPage integration)
    ↓
  B5 (end-to-end verification)
```

Part A and Part B can be worked in parallel. B1 can start immediately alongside A1–A6.

---

## Files Touched

| Task | File |
|------|------|
| A1 | `frontend/apps/main/src/components/dashboard/StatusSummaryGrid.vue` |
| A2 | `frontend/apps/main/src/components/asset/CategoryGrid.vue` |
| A3 | `frontend/apps/main/src/components/asset/UsageFreqSelector.vue` |
| A4, A6 | `frontend/apps/main/src/pages/DashboardPage.vue` (verify only) |
| A5 | `frontend/apps/main/src/components/common/AppTabBar.vue` (verify only, possible min-width) |
| B1 | `frontend/apps/main/src/i18n/locales/zh-CN.ts`, `en-US.ts` |
| B2 | `frontend/apps/main/src/components/common/OnboardingOverlay.vue` (new file) |
| B3 | `frontend/apps/main/src/pages/DashboardPage.vue` |
| B4 | `frontend/apps/main/src/components/dashboard/NetWorthCard.vue` (possible class addition) |

---

## Out of Scope

Per the brainstorm document:
- Accessibility labels (aria-label) full audit — separate iteration
- 8dp Spacing Grid System — global style refactor, separate iteration
- Skeleton Loading — covered in quick-wins-ux-performance plan
- Onboarding animation/transition polish — basic functionality first
- Onboarding completion rate analytics/instrumentation
- A/B testing of onboarding copy
