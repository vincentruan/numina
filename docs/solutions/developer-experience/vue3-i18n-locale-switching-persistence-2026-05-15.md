---
title: "Vue 3 i18n Locale Switching with localStorage Persistence"
date: 2026-05-15
category: developer-experience
module: frontend/apps/child i18n
problem_type: developer_experience
component: tooling
severity: medium
applies_when:
  - Vue 3 app uses vue-i18n but lacks runtime locale switching UI
  - Locale files are incomplete or inconsistent across languages
  - Components hardcode locale strings in date/time formatting calls
  - Need to persist user locale preference without server-side storage
tags:
  - vue3
  - i18n
  - locale-switching
  - localStorage-persistence
  - module-singleton
  - computed-reactivity
  - vue-i18n
---

# Vue 3 i18n Locale Switching with localStorage Persistence

## Context

The child app (`frontend/apps/child`) had vue-i18n configured with both `zh-CN` and `en-US` locale files, but the English file was severely incomplete (37 lines vs 257 in zh-CN), there was no runtime locale switching mechanism, and two pages hardcoded `'zh-CN'` in `toLocaleDateString()` calls. The app was effectively Chinese-only despite the infrastructure being in place.

This documents the complete pattern for adding runtime locale switching to a Vue 3 app where locale is client-side state (no server-side `language` field on the user object).

## Guidance

### 1. Create a module-level singleton utility (`src/utils/locale.ts`)

Mirror the existing `darkMode.ts` pattern exactly — module-level `ref` + `watchEffect` at module scope:

```ts
import { ref, watchEffect } from 'vue'
import i18n from '@/i18n'

type Locale = 'zh-CN' | 'en-US'

function getStoredLocale(): Locale {
  const v = localStorage.getItem('child:locale')  // namespace the key
  if (v === 'zh-CN' || v === 'en-US') return v
  return 'zh-CN'
}

// Module-level singleton — shared across all callers
const currentLocale = ref<Locale>(typeof window !== 'undefined' ? getStoredLocale() : 'zh-CN')

if (typeof window !== 'undefined') {
  watchEffect(() => {
    i18n.global.locale.value = currentLocale.value  // drives vue-i18n
    localStorage.setItem('child:locale', currentLocale.value)
  })
}

export function useLocale() {
  function setLocale(locale: Locale) {
    currentLocale.value = locale
  }
  return { currentLocale, setLocale }
}
```

**Why module-level, not component-scoped:** Locale is app-wide state. A module-level ref ensures all components share the same reactive source. The `watchEffect` fires immediately on import, so the stored locale is applied before any component mounts.

**Why `legacy: false` matters:** vue-i18n in Composition API mode exposes `i18n.global.locale` as a `Ref<string>`, so you write `i18n.global.locale.value = ...`. In legacy mode it's a plain string — the pattern above only works with `legacy: false`.

### 2. Initialize before first render (`main.ts`)

A side-effect import is sufficient — the module-level `watchEffect` fires on import:

```ts
import '@/utils/locale' // initialize locale from localStorage before first render
// ... rest of main.ts
app.use(i18n)
app.mount('#app')
```

This prevents a flash of the wrong language on first render.

### 3. Add language switcher UI (reuse existing settings panel CSS)

```ts
// In ChildHomePage.vue (or any settings component)
import { computed } from 'vue'
import { useLocale } from '@/utils/locale'

const { currentLocale, setLocale } = useLocale()

// computed() so labels re-evaluate on locale switch
const languageOptions = computed(() => [
  { value: 'zh-CN' as const, label: t('home.langZhCN') },
  { value: 'en-US' as const, label: t('home.langEnUS') },
])
```

```html
<p class="settings-label">{{ t('home.settingsLanguage') }}</p>
<div class="theme-options">
  <button
    v-for="opt in languageOptions"
    :key="opt.value"
    class="theme-btn"
    :class="{ active: currentLocale === opt.value }"
    @click="setLocale(opt.value)"
  >
    {{ opt.label }}
  </button>
</div>
```

### 4. Fix hardcoded locale strings in date formatting

Replace `'zh-CN'` literals with `locale.value` from `useI18n()`:

```ts
// Before — hardcoded, won't respond to locale switch
const { t } = useI18n()
const todayLabel = now.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })

// After — reactive
const { t, locale } = useI18n()
const todayLabel = computed(() =>
  now.toLocaleDateString(locale.value, { month: 'long', day: 'numeric', weekday: 'short' })
)
```

For functions called from templates, `locale.value` is reactive during render — no `computed()` wrapper needed, but it's fragile if the call moves outside a template expression:

```ts
function formatExpiry(dateStr: string) {
  return new Date(dateStr).toLocaleDateString(locale.value, { month: 'short', day: 'numeric' })
}
```

### 5. Language option labels — use i18n keys with identical values

The "bootstrap problem" (the label itself needs translation) is solved by storing self-identifying language names as i18n keys with the same value in both locales:

```ts
// zh-CN.ts
home: {
  langZhCN: '🇨🇳 中文',   // same in both locales
  langEnUS: '🇺🇸 English', // same in both locales
}

// en-US.ts
home: {
  langZhCN: '🇨🇳 中文',   // intentionally identical
  langEnUS: '🇺🇸 English', // intentionally identical
}
```

This satisfies the CLAUDE.md rule ("all user-facing strings through `t('key')`") without the bootstrap problem.

### 6. Convert static translated arrays to `computed()`

Any array whose labels come from `t()` must be `computed()` — otherwise labels freeze at component setup time and won't update after a locale switch:

```ts
// Wrong — labels frozen at setup
const themeOptions = [
  { value: 'system', label: t('home.themeSystem') },
]

// Correct — labels re-evaluate reactively
const themeOptions = computed(() => [
  { value: 'system' as const, label: t('home.themeSystem') },
])
```

## Why This Matters

Without this pattern:
- Switching locale via `i18n.global.locale.value` updates `t()` calls in templates, but static arrays (like `themeOptions`) retain their original-language labels until the component remounts
- `toLocaleDateString('zh-CN', ...)` hardcodes always produce Chinese date formats regardless of the active locale
- Without `localStorage` persistence, the locale resets to the default on every page reload

## When to Apply

- Adding locale switching to any Vue 3 app in this monorepo that uses vue-i18n
- When the app's locale is client-side state (no server `language` field) — for server-driven locale (like `frontend/apps/main`), drive `locale.value` from `authStore.user?.language` instead
- When adding any new settings that need localStorage persistence — follow the `darkMode.ts` / `locale.ts` module-level singleton pattern

## Examples

### Complete `locale.ts` (reference implementation)

See `frontend/apps/child/src/utils/locale.ts` — the canonical implementation for client-side locale persistence in this monorepo.

### Reference pattern

`frontend/apps/child/src/utils/darkMode.ts` — the original module-level singleton pattern this implementation mirrors.

### Server-driven locale (main app)

`frontend/apps/main/src/App.vue` — drives locale from `authStore.user?.language` via `watch()` instead of localStorage. Use this approach when the user has a server-side language preference.

## Pitfalls Caught During Review

1. **Static `t()` arrays don't update on locale switch** — `themeOptions` was a plain array; converted to `computed()`. Any array with `t()` labels must be `computed()`.

2. **Bare localStorage key `'locale'` is collision-prone** — if apps share an origin (same domain, different paths), they silently overwrite each other's preference. Use a namespaced key: `'child:locale'`, `'main:locale'`, etc.

3. **Hardcoded language labels in `.vue` files violate CLAUDE.md** — even with the bootstrap rationale, the rule has no carve-out. Store self-identifying labels as i18n keys with identical values in both locales.

## Related

- `frontend/apps/child/CLAUDE.md` — i18n rules for the child app
- `frontend/apps/main/CLAUDE.md` — comprehensive i18n rules (emoji convention, key sections, adding new messages)
- `docs/solutions/best-practices/fastapi-pydantic-validation-error-localization-2026-04-16.md` — backend locale pattern (FastAPI/Pydantic validation errors)
