---
title: "feat: Add complete i18n support to child app"
type: feat
status: active
date: 2026-05-15
---

# feat: Add complete i18n support to child app

## Overview

The child app (`frontend/apps/child`) already has vue-i18n wired up with both `zh-CN` and `en-US` locale files, and all pages correctly use `t()`. However, the `en-US.ts` locale file is severely incomplete (37 lines vs 257 in `zh-CN.ts`), there is no mechanism to switch or persist the locale, and two pages hardcode `'zh-CN'` in `toLocaleDateString` calls. This plan completes the i18n infrastructure so the child app can be used in English.

## Problem Frame

Children in international or bilingual families cannot use the app in English. The infrastructure is partially in place but three gaps block it: missing translations, no locale switcher, and no locale persistence.

## Requirements Trace

- R1. All user-facing strings in the child app render correctly in both `zh-CN` and `en-US`
- R2. A language selector in the home page settings panel lets the child switch languages
- R3. The selected language persists across page reloads via `localStorage`
- R4. Date formatting respects the active locale (no hardcoded `'zh-CN'`)
- R5. TypeScript type-checks pass after all changes (`npm run typecheck`)

## Scope Boundaries

- Only `frontend/apps/child` is modified — `frontend/apps/main` is untouched
- No shared `@numina/locale` package is created (decided against in brainstorm)
- Translation quality is best-effort English; no professional translation review is in scope
- No backend API changes — child locale is client-side only (child users have no `language` field on the server)

### Deferred to Separate Tasks

- Adding locale support to `frontend/apps/main` format utilities (`format.ts`, `usePrivacy.ts`, `LiabilityCard.vue`) that also hardcode `'zh-CN'`: separate PR in main app

## Context & Research

### Relevant Code and Patterns

- `frontend/apps/child/src/utils/darkMode.ts` — **reference implementation** to mirror exactly: module-level `ref`, `watchEffect` for side effects + localStorage sync, `typeof window !== 'undefined'` SSR guard, single exported composable
- `frontend/apps/child/src/i18n/index.ts` — `createI18n({ legacy: false, ... })` confirmed; locale accessed as `i18n.global.locale.value` (Composition API mode)
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — 257 lines, 16 sections: `common`, `nav`, `auth`, `errors`, `toast`, `chore`, `home`, `ledger`, `wishes`, `treasures`, `blindBox`, `calendar`, `dayDetail`, `milestone`
- `frontend/apps/child/src/i18n/locales/en-US.ts` — 37 lines; missing: `chore`, `home`, `ledger`, `wishes`, `treasures`, `blindBox`, `calendar`, `dayDetail`, `milestone`; also missing many keys in `auth`, `toast`, `errors`, `common`
- `frontend/apps/child/src/pages/ChildHomePage.vue` — settings panel with `.theme-btn` / `.theme-options` pattern to reuse for language switcher; `settingsExpanded` collapsible section
- `frontend/apps/child/src/pages/ChildTasksPage.vue:101` — `toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })`
- `frontend/apps/child/src/pages/ChildBlindBoxPage.vue:139` — `toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })`
- `frontend/apps/child/src/main.ts` — `app.use(i18n)` with no locale initialization from storage
- `frontend/packages/auth/package.json` — workspace package pattern: `"main": "./src/index.ts"`, raw TS exports, `workspace:*` dep

### Institutional Learnings

- No prior i18n solution docs exist in `docs/solutions/` — this sets a new precedent
- CLAUDE.md mandates all user-facing strings through `t('key')` — no hardcoded strings in `.vue` files (already satisfied by all pages)
- Emoji prefix convention must be preserved in English translations (e.g., `✅ Logged in`, `❌ Wrong PIN`)

### External References

- vue-i18n v9 Composition API: `i18n.global.locale` is a `Ref<string>` when `legacy: false`

## Key Technical Decisions

- **Mirror `darkMode.ts` exactly**: Module-level `ref` + `watchEffect` in `locale.ts`. The `watchEffect` fires on first import, so importing `useLocale` in `main.ts` is sufficient to initialize the locale before mount — no explicit call needed.
- **Import `i18n` instance inside `locale.ts`**: The `watchEffect` writes to `i18n.global.locale.value` directly, keeping the composable self-contained. This avoids passing the i18n instance around.
- **Language options hardcoded, not i18n keys**: `[{ value: 'zh-CN', label: '🇨🇳 中文' }, { value: 'en-US', label: '🇺🇸 English' }]` — avoids the bootstrap problem where the label itself needs translation.
- **`toLocaleDateString` fix via `useI18n().locale`**: In the two affected pages, use `const { locale } = useI18n()` (already imported) and pass `locale.value` to `toLocaleDateString`. This avoids importing `useLocale` in pages that don't need the setter.
- **`en-US.ts` `calendar.weekdays`**: Change from `['日','一','二','三','四','五','六']` to `['Sun','Mon','Tue','Wed','Thu','Fri','Sat']`.

## Open Questions

### Resolved During Planning

- **Should locale be stored server-side?** No — child users have no `language` field on `ChildUser`. localStorage is the correct layer.
- **Should a shared `@numina/locale` package be created?** No — decided against in brainstorm. The two apps have fundamentally different locale sources (server vs. client).
- **Which `toLocaleDateString` fix approach?** Use `useI18n().locale` (already available in both pages) rather than importing `useLocale`, to minimize the change surface.

### Deferred to Implementation

- Exact English wording for milestone descriptions and toast messages — implementer judgment, following the emoji-prefix convention
- Whether `calendar.weekdays` short names should be locale-aware via `Intl` or static strings — static strings are simpler and consistent with the zh-CN approach

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
localStorage('locale')
       │
       ▼
locale.ts (module-level ref)
  ├── watchEffect → i18n.global.locale.value = currentLocale
  └── watchEffect → localStorage.setItem('locale', currentLocale)
       │
       ├── main.ts: import useLocale (triggers module init before mount)
       │
       └── ChildHomePage.vue settings panel
             language buttons → setLocale(value)
                                      │
                                      ▼
                              currentLocale ref updates
                                      │
                              watchEffect fires → i18n switches
                                      │
                              all t() calls re-render in new locale
```

## Implementation Units

- [ ] **Unit 1: Complete `en-US.ts` locale file**

**Goal:** All 220+ missing keys translated to English so every `t()` call in the child app resolves in `en-US` mode.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `frontend/apps/child/src/i18n/locales/en-US.ts`

**Approach:**
- Add all sections present in `zh-CN.ts` but absent from `en-US.ts`: `chore`, `home`, `ledger`, `wishes`, `treasures`, `blindBox`, `calendar`, `dayDetail`, `milestone`
- Fill missing keys in existing sections: `common` (add `delete`, `edit`), `auth` (add all 16 missing keys), `toast` (add 10 missing keys), `errors` (add 5 missing keys)
- Preserve emoji prefixes on all toast/error strings
- `calendar.weekdays`: `['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']`
- `home.settingsLanguage` key added here (used by Unit 3): `'Language'`
- Interpolation placeholders (`{days}`, `{count}`, `{name}`, etc.) must be identical to zh-CN counterparts

**Patterns to follow:**
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — exact key structure to mirror
- `frontend/apps/main/src/i18n/locales/en-US.ts` — reference for English phrasing of shared concepts (coin types, wish statuses, chore statuses)

**Test scenarios:**
- Test expectation: none — this is a data file with no behavioral logic; correctness is verified by typecheck (Unit 5) and visual inspection during Unit 3/4 testing

**Verification:**
- `npm run typecheck` passes (vue-i18n will warn on missing keys in strict mode)
- Every key present in `zh-CN.ts` has a corresponding key in `en-US.ts` at the same path

---

- [ ] **Unit 2: Create `locale.ts` utility**

**Goal:** A module-level composable that persists locale to `localStorage` and drives `i18n.global.locale.value`, following the `darkMode.ts` pattern exactly.

**Requirements:** R3

**Dependencies:** Unit 1 (en-US.ts must exist and be valid before locale switching is meaningful)

**Files:**
- Create: `frontend/apps/child/src/utils/locale.ts`

**Approach:**
- Module-level `ref<'zh-CN' | 'en-US'>` initialized from `localStorage.getItem('locale')` with `'zh-CN'` fallback
- `typeof window !== 'undefined'` guard around `watchEffect` (SSR safety, consistent with `darkMode.ts`)
- `watchEffect` writes to both `i18n.global.locale.value` and `localStorage`
- Export `useLocale()` returning `{ currentLocale, setLocale }`
- `currentLocale` is the module-level ref (shared singleton — all callers see the same value)
- Import `i18n` from `@/i18n` inside the module

**Patterns to follow:**
- `frontend/apps/child/src/utils/darkMode.ts` — exact structural pattern

**Test scenarios:**
- Happy path: `setLocale('en-US')` updates `currentLocale.value` to `'en-US'`, writes `'en-US'` to `localStorage('locale')`, and sets `i18n.global.locale.value` to `'en-US'`
- Happy path: on module load with `localStorage('locale') = 'en-US'`, `currentLocale.value` initializes to `'en-US'`
- Edge case: `localStorage('locale')` absent or invalid value → `currentLocale.value` defaults to `'zh-CN'`
- Edge case: `setLocale('zh-CN')` after `'en-US'` correctly reverts all three targets

**Verification:**
- `npm run typecheck` passes
- Manual test: switch to English, reload page — English persists

---

- [ ] **Unit 3: Add language switcher to `ChildHomePage.vue` settings panel**

**Goal:** A language selector appears in the collapsible settings section, below the theme selector, using the same button group visual pattern.

**Requirements:** R2, R3

**Dependencies:** Unit 1, Unit 2

**Files:**
- Modify: `frontend/apps/child/src/pages/ChildHomePage.vue`
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts` (add `home.settingsLanguage` key)

**Approach:**
- Add `home.settingsLanguage: '语言'` to `zh-CN.ts` (English equivalent already added in Unit 1)
- Import `useLocale` from `@/utils/locale` in the script block
- Destructure `{ currentLocale, setLocale }` from `useLocale()`
- Language options array hardcoded (not i18n): `[{ value: 'zh-CN', label: '🇨🇳 中文' }, { value: 'en-US', label: '🇺🇸 English' }]`
- Template: add a `<p class="settings-label">{{ t('home.settingsLanguage') }}</p>` + `<div class="theme-options">` block with buttons using `.theme-btn` and `.active` class bound to `currentLocale === opt.value`
- Button click calls `setLocale(opt.value)`
- No new CSS needed — reuse `.settings-label`, `.theme-options`, `.theme-btn`, `.theme-btn.active`

**Patterns to follow:**
- Existing theme selector block in `ChildHomePage.vue` (lines ~70–80) — identical structure

**Test scenarios:**
- Happy path: tapping `🇺🇸 English` button activates it (`.active` class), page re-renders in English
- Happy path: tapping `🇨🇳 中文` button switches back to Chinese
- Happy path: active button reflects `currentLocale` on page load (persisted value)
- Edge case: settings panel collapsed — language switcher not visible, no interaction possible

**Verification:**
- Settings panel shows language selector below theme selector
- Switching language re-renders all `t()` strings on the page without reload
- Active button highlights correctly on initial load

---

- [ ] **Unit 4: Fix hardcoded `'zh-CN'` locale in two pages**

**Goal:** `ChildTasksPage.vue` and `ChildBlindBoxPage.vue` use the active locale for date formatting instead of always using Chinese.

**Requirements:** R4

**Dependencies:** Unit 2

**Files:**
- Modify: `frontend/apps/child/src/pages/ChildTasksPage.vue`
- Modify: `frontend/apps/child/src/pages/ChildBlindBoxPage.vue`

**Approach:**
- Both pages already import `useI18n` and call `const { t } = useI18n()` — extend to also destructure `locale`: `const { t, locale } = useI18n()`
- `ChildTasksPage.vue:101`: replace `'zh-CN'` with `locale.value` in the `toLocaleDateString` call. Note: `todayLabel` is computed at module load time as a `const` — it must become a `computed()` or be moved inside `onMounted` to be reactive to locale changes
- `ChildBlindBoxPage.vue:139`: replace `'zh-CN'` with `locale.value` in `formatExpiry`. Since `formatExpiry` is a plain function called in the template, it will re-evaluate when `locale` changes as long as `locale` is reactive (it is, as a `Ref`)

**Patterns to follow:**
- `frontend/apps/main/src/App.vue` — `const { locale } = useI18n()` pattern

**Test scenarios:**
- Happy path: with `en-US` active, `ChildTasksPage` date hero shows English date format (e.g., "Thursday, May 15")
- Happy path: with `en-US` active, `ChildBlindBoxPage` bonus expiry dates show English short format (e.g., "May 15")
- Happy path: switching locale while on `ChildTasksPage` updates `todayLabel` reactively (requires `computed()` fix)
- Edge case: `locale.value` is `'zh-CN'` — output identical to current behavior

**Verification:**
- With English selected, date strings on Tasks and BlindBox pages render in English format
- `npm run typecheck` passes

---

- [ ] **Unit 5: Initialize locale from `localStorage` in `main.ts`**

**Goal:** The app boots with the persisted locale active, so the first render is already in the correct language.

**Requirements:** R3

**Dependencies:** Unit 2

**Files:**
- Modify: `frontend/apps/child/src/main.ts`

**Approach:**
- Import `useLocale` from `@/utils/locale` before `app.use(i18n)`
- Calling `useLocale()` (or simply importing the module) triggers the module-level `watchEffect`, which immediately sets `i18n.global.locale.value` to the stored locale before the app mounts
- The import alone is sufficient — no explicit function call needed, matching the `darkMode.ts` pattern where the module-level side effects fire on import
- Add a brief comment explaining why the import is here

**Patterns to follow:**
- `frontend/apps/child/src/utils/darkMode.ts` — module-level initialization via import side effect

**Test scenarios:**
- Happy path: with `localStorage('locale') = 'en-US'`, app boots and first render is in English (no flash of Chinese)
- Happy path: with no `localStorage('locale')`, app boots in `zh-CN` (default)
- Edge case: `localStorage('locale') = 'invalid'` → app boots in `zh-CN`

**Verification:**
- Hard-reload with English stored → app renders in English immediately
- `npm run typecheck` passes

---

- [ ] **Unit 6: Typecheck and smoke test**

**Goal:** Confirm all changes compile cleanly and the full locale switch flow works end-to-end.

**Requirements:** R1–R5

**Dependencies:** Units 1–5

**Files:**
- No new files — verification only

**Approach:**
- Run `npm run typecheck` in `frontend/apps/child`
- Manually verify: open app → switch to English → reload → English persists → switch back to Chinese → reload → Chinese persists
- Verify all 8 pages render without missing-key warnings in the browser console

**Test scenarios:**
- Test expectation: none — this unit is verification-only, not a code change

**Verification:**
- `npm run typecheck` exits 0
- No `[vue-i18n] Not found 'xxx' key` warnings in browser console in either locale
- All pages render correctly in both `zh-CN` and `en-US`

## System-Wide Impact

- **Interaction graph:** `locale.ts` module-level `watchEffect` fires on every `setLocale()` call, updating `i18n.global.locale.value` which triggers vue-i18n to re-render all `t()` calls across all mounted components simultaneously
- **Error propagation:** No error paths — locale switching is a pure client-side state change with no API calls
- **State lifecycle risks:** `todayLabel` in `ChildTasksPage.vue` is currently a `const` computed at module load — it must be converted to a `computed()` ref to be reactive; otherwise it will show the wrong language after a locale switch without reload
- **Unchanged invariants:** All existing `t()` call sites are untouched; `zh-CN` behavior is identical to current; `darkMode.ts` and theme switching are unaffected; `@numina/auth` package is unmodified

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `todayLabel` not reactive after locale switch | Convert from `const` to `computed()` in Unit 4 |
| `en-US.ts` missing a key causes silent fallback to key path string | Run `typecheck` after Unit 1; vue-i18n logs warnings for missing keys in dev mode |
| Module-level `watchEffect` in `locale.ts` fires before `i18n` is initialized | `i18n` is a module-level singleton exported from `@/i18n/index.ts` — it is initialized at import time, before any component mounts |
| Language switcher label itself needs translation | Labels are hardcoded (`'🇨🇳 中文'`, `'🇺🇸 English'`) — no i18n dependency |

## Sources & References

- Reference implementation: `frontend/apps/child/src/utils/darkMode.ts`
- i18n instance: `frontend/apps/child/src/i18n/index.ts`
- zh-CN source of truth: `frontend/apps/child/src/i18n/locales/zh-CN.ts`
- English phrasing reference: `frontend/apps/main/src/i18n/locales/en-US.ts`
- Settings panel pattern: `frontend/apps/child/src/pages/ChildHomePage.vue`
