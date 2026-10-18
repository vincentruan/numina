# About 页面子页面架构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the About page from popup/external-link patterns into independent sub-pages with a shared ContentPage component, and write bilingual legal documents (Terms of Service + Privacy Policy) embedded as frontend content.

**Architecture:** A shared `ContentPage.vue` shell component provides header, scrollable content area, and typography. Four sub-pages (`ChangelogPage`, `TermsPage`, `PrivacyPage`, `LicensesPage`) live under `src/pages/about/`. Legal content is stored as structured section arrays in language-specific data files, selected at runtime by locale.

**Tech Stack:** Vue 3 `<script setup lang="ts">`, Vant 4, TypeScript, vue-i18n, CSS variables for dark mode

**Spec:** `docs/superpowers/specs/2026-10-18-about-page-subpages-design.md`

## Global Constraints

- `<script setup lang="ts">` only — no Options API, no `defineComponent`
- Vant 4 auto-imported — don't manually import Vant components; only import functional API (`showToast`, etc.)
- i18n required for all user-facing strings in templates — legal document body text is exempted per spec §3.4 (separate data files per language)
- CSS variables only — `--text-primary`, `--text-secondary`, `--card-bg`, `--bg-primary`, `--van-border-color`
- Path alias `@/` maps to `src/`
- Date formatting via `locale.value` from `useI18n()` — no hard-coded locale strings
- No new UI libraries, no backend changes, no child app changes

## Review Focus

1. **Dark mode across all new pages** — all text must use `var(--text-primary)` / `var(--text-secondary)`, no hard-coded colors. Verify by toggling theme and checking each page.
2. **Legal content locale switching** — when user changes language, TermsPage and PrivacyPage must show correct language content. Verify by switching locale and checking both pages.
3. **Changelog i18n after data extraction** — changelog entries must still render translated text via `t()`, not raw keys. Verify changelog page shows Chinese/English correctly.
4. **Route navigation back-button** — each sub-page must navigate back to AboutPage (not home) when back arrow is pressed. Verify via browser back button and PageHeader back arrow.
5. **AboutPage menu items** — all four internal items must navigate to correct sub-pages, Project Homepage must still open GitHub in new tab. Verify all 5 menu items.

---

## Task 1: Content Types + ContentPage Component

**Files:**
- Create: `frontend/apps/main/src/pages/about/contentTypes.ts`
- Create: `frontend/apps/main/src/components/common/ContentPage.vue`

**Interfaces:**
```ts
// contentTypes.ts — shared types for all about sub-pages

export interface ContentBlock {
  type: 'paragraph' | 'list'
  text?: string
  items?: string[]
}

export interface ContentSection {
  heading: string
  blocks: ContentBlock[]
}
```

ContentPage props: `{ title: string; lastUpdated?: string }`, default slot for body content.

- [ ] **Step 1: Create `contentTypes.ts`**

Create `src/pages/about/contentTypes.ts` with the interfaces above. These types are consumed by all four sub-pages and their data files.

- [ ] **Step 2: Create `ContentPage.vue`**

Create `src/components/common/ContentPage.vue`:

```vue
<script setup lang="ts">
import PageHeader from '@/components/common/PageHeader.vue'

defineProps<{
  title: string
  lastUpdated?: string
}>()
</script>

<template>
  <div class="content-page">
    <PageHeader :title="title" />
    <div class="content-body">
      <p v-if="lastUpdated" class="content-updated">
        {{ lastUpdated }}
      </p>
      <slot />
    </div>
  </div>
</template>
```

Scoped styles:
- `.content-page` — `min-height: 100vh`
- `.content-body` — `padding: 16px 20px 40px`, `overflow-y: auto`
- `.content-updated` — `font-size: 12px`, `color: var(--text-secondary)`, `margin-bottom: 20px`

Typography styles (scoped, deep selectors for slot content):
- `:deep(h2)` — section heading: `font-size: 17px`, `font-weight: 600`, `color: var(--text-primary)`, `margin: 24px 0 12px`
- `:deep(h3)` — sub-heading: `font-size: 15px`, `font-weight: 600`, `color: var(--text-primary)`, `margin: 20px 0 8px`
- `:deep(p)` — `font-size: 14px`, `line-height: 1.8`, `color: var(--text-primary)`, `margin: 0 0 12px`
- `:deep(ul), :deep(ol)` — `padding-left: 20px`, `margin: 0 0 12px`
- `:deep(li)` — `font-size: 14px`, `line-height: 1.8`, `color: var(--text-primary)`, `margin-bottom: 4px`
- `:deep(a)` — `color: var(--van-primary-color)`, `text-decoration: none`
- `:deep(strong)` — `font-weight: 600`

- [ ] **Step 3: Verify typecheck passes**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: No errors related to new files.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/about/contentTypes.ts frontend/apps/main/src/components/common/ContentPage.vue
git commit -m "feat(about): add ContentPage base component and content types"
```

---

## Task 2: Extract Changelog Data + Create ChangelogPage

**Files:**
- Create: `frontend/apps/main/src/pages/about/data/changelog.ts`
- Create: `frontend/apps/main/src/pages/about/ChangelogPage.vue`

**Interfaces:**
- Consumes: `ContentPage` component from Task 1
- Data shape: `{ version: string; date: string; changes: string[] }` where `changes` contains i18n keys

- [ ] **Step 1: Create `data/changelog.ts`**

Migrate changelog data from `AboutPage.vue` lines 20-34. Export typed array:

```ts
import type { } from './contentTypes'  // not needed, changelog uses its own shape

export interface ChangelogEntry {
  version: string
  date: string
  changes: string[]  // i18n keys, resolved at render time via t()
}

export const changelog: ChangelogEntry[] = [
  {
    version: '1.0.0',
    date: '2026-10-16',
    changes: [
      'settings.changelogV1_1',
      'settings.changelogV1_2',
      'settings.changelogV1_3',
      'settings.changelogV1_4',
      'settings.changelogV1_5',
      'settings.changelogV1_6',
      'settings.changelogV1_7',
    ],
  },
]
```

- [ ] **Step 2: Create `ChangelogPage.vue`**

```vue
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ContentPage from '@/components/common/ContentPage.vue'
import { changelog } from './data/changelog'

const { t } = useI18n()
</script>

<template>
  <ContentPage :title="t('settings.changelog')">
    <div v-for="release in changelog" :key="release.version" class="changelog-release">
      <div class="changelog-version">
        <span class="version-tag">v{{ release.version }}</span>
        <span class="version-date">{{ release.date }}</span>
      </div>
      <ul class="changelog-list">
        <li v-for="(changeKey, idx) in release.changes" :key="idx">{{ t(changeKey) }}</li>
      </ul>
    </div>
  </ContentPage>
</template>
```

Scoped styles — reuse the existing changelog styles from `AboutPage.vue` lines 256-288:
- `.changelog-release` — `margin-bottom: 20px`
- `.changelog-version` — flex row, `align-items: center`, `gap: 8px`, `margin-bottom: 8px`
- `.version-tag` — `font-size: 14px`, `font-weight: 600`, `color: var(--van-primary-color)`
- `.version-date` — `font-size: 12px`, `color: var(--text-secondary)`
- `.changelog-list` — `margin: 0`, `padding-left: 20px`, `list-style: disc`
- `.changelog-list li` — `font-size: 14px`, `color: var(--text-primary)`, `line-height: 1.8`

- [ ] **Step 3: Verify typecheck passes**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/about/data/changelog.ts frontend/apps/main/src/pages/about/ChangelogPage.vue
git commit -m "feat(about): add ChangelogPage with extracted data"
```

---

## Task 3: Extract Licenses Data + Create LicensesPage

**Files:**
- Create: `frontend/apps/main/src/pages/about/data/licenses.ts`
- Create: `frontend/apps/main/src/pages/about/LicensesPage.vue`

**Interfaces:**
- Consumes: `ContentPage` component from Task 1
- Data shape: `{ name: string; license: string; url: string }`

- [ ] **Step 1: Create `data/licenses.ts`**

Migrate OSS component data from `AboutPage.vue` lines 46-61:

```ts
export interface OSSComponent {
  name: string
  license: string
  url: string
}

export const ossComponents: OSSComponent[] = [
  { name: 'Vue 3', license: 'MIT', url: 'https://vuejs.org' },
  { name: 'Vant 4', license: 'MIT', url: 'https://vant-ui.github.io/vant' },
  { name: 'FastAPI', license: 'MIT', url: 'https://fastapi.tiangolo.com' },
  { name: 'SQLAlchemy', license: 'MIT', url: 'https://www.sqlalchemy.org' },
  { name: 'DeerFlow', license: 'MIT', url: 'https://github.com/bytedance/deer-flow' },
  { name: 'LangChain', license: 'MIT', url: 'https://www.langchain.com' },
  { name: 'LangGraph', license: 'MIT', url: 'https://github.com/langchain-ai/langgraph' },
  { name: 'ECharts', license: 'Apache-2.0', url: 'https://echarts.apache.org' },
  { name: 'DuckDB', license: 'MIT', url: 'https://duckdb.org' },
  { name: 'Vite', license: 'MIT', url: 'https://vitejs.dev' },
  { name: 'Pinia', license: 'MIT', url: 'https://pinia.vuejs.org' },
  { name: 'vue-i18n', license: 'MIT', url: 'https://vue-i18n.intlify.dev' },
  { name: 'Tavily', license: 'MIT', url: 'https://tavily.com' },
  { name: 'e2b', license: 'Apache-2.0', url: 'https://e2b.dev' },
]
```

- [ ] **Step 2: Create `LicensesPage.vue`**

Uses `ContentPage` wrapper. Two sections:
1. AGPL-3.0 notice paragraph at top (i18n key `settings.licensedUnder`)
2. Component list with name (as link), license badge

```vue
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ContentPage from '@/components/common/ContentPage.vue'
import { ossComponents } from './data/licenses'

const { t } = useI18n()
</script>

<template>
  <ContentPage :title="t('settings.openSourceLicenses')">
    <p class="licenses-intro">{{ t('settings.licensedUnder') }}</p>
    <div class="licenses-list">
      <div v-for="comp in ossComponents" :key="comp.name" class="license-item">
        <a :href="comp.url" target="_blank" rel="noopener" class="license-name">{{ comp.name }}</a>
        <span class="license-badge">{{ comp.license }}</span>
      </div>
    </div>
  </ContentPage>
</template>
```

Scoped styles — reuse existing OSS styles from `AboutPage.vue` lines 291-319:
- `.licenses-intro` — `font-size: 14px`, `color: var(--text-secondary)`, `margin-bottom: 16px`, `line-height: 1.6`
- `.license-item` — flex row, `justify-content: space-between`, `align-items: center`, `padding: 10px 0`, `border-bottom: 1px solid var(--van-border-color)`
- `.license-item:last-child` — `border-bottom: none`
- `.license-name` — `font-size: 14px`, `color: var(--van-primary-color)`, `text-decoration: none`
- `.license-badge` — `font-size: 12px`, `color: var(--text-secondary)`, `background: var(--card-bg)`, `padding: 2px 8px`, `border-radius: 4px`

- [ ] **Step 3: Verify typecheck passes**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/about/data/licenses.ts frontend/apps/main/src/pages/about/LicensesPage.vue
git commit -m "feat(about): add LicensesPage with extracted component data"
```

---

## Task 4: Write Terms of Service (Chinese + English)

**Files:**
- Create: `frontend/apps/main/src/pages/about/data/terms-zh.ts`
- Create: `frontend/apps/main/src/pages/about/data/terms-en.ts`

**Interfaces:**
- Consumes: `ContentSection`, `ContentBlock` from `contentTypes.ts`
- Both files export `termsContent: ContentSection[]`

- [ ] **Step 1: Create `data/terms-zh.ts`**

Write the full Chinese Terms of Service. 13 sections per spec §3.1. Use `ContentSection`/`ContentBlock` types.

The content must be rigorous, legally sound, and specific to Numina's actual tech stack. Write as a senior IT lawyer would — covering:
- AGPL-3.0 obligations clearly stated
- Self-deployment model: user controls all data
- AI features: data goes to third-party providers (LangChain, LangGraph, Tavily, e2b) after de-identification
- Behavioral analytics and error reporting
- "As-is" disclaimer with no warranties
- Liability limitation
- Forward-looking clauses for future SaaS commercialization

Content must be **readable** — not pure legalese. Users should understand their rights and obligations.

Last updated date: `2026-10-18`

Export shape:
```ts
import type { ContentSection } from '../contentTypes'

export const termsContent: ContentSection[] = [
  {
    heading: '1. 接受条款',
    blocks: [
      { type: 'paragraph', text: '欢迎使用 Numina...' },
      // ... full content
    ],
  },
  // ... all 13 sections
]
```

- [ ] **Step 2: Create `data/terms-en.ts`**

Write the English version matching the Chinese version semantically. Same 13 sections, same structure. Must be natural English legal prose — not a literal translation.

Export shape:
```ts
import type { ContentSection } from '../contentTypes'

export const termsContent: ContentSection[] = [
  // ... matching English content
]
```

- [ ] **Step 3: Verify typecheck passes**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS — data files must conform to `ContentSection[]` type.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/about/data/terms-zh.ts frontend/apps/main/src/pages/about/data/terms-en.ts
git commit -m "feat(about): add bilingual Terms of Service content"
```

---

## Task 5: Write Privacy Policy (Chinese + English)

**Files:**
- Create: `frontend/apps/main/src/pages/about/data/privacy-zh.ts`
- Create: `frontend/apps/main/src/pages/about/data/privacy-en.ts`

**Interfaces:**
- Consumes: `ContentSection`, `ContentBlock` from `contentTypes.ts`
- Both files export `privacyContent: ContentSection[]`

- [ ] **Step 1: Create `data/privacy-zh.ts`**

Write the full Chinese Privacy Policy. 11 sections per spec §3.2. Key sections requiring technical accuracy:

**Section 2 (信息收集)** — must accurately describe:
- Registration data (username, password hash)
- Asset/financial data (manually entered)
- Behavioral analytics (page views, feature usage — no PII)
- Error logs (stack traces, device info)
- What is NOT collected (biometrics, health data, third-party ad tracking)

**Section 3 (信息使用)** — must explain:
- AI data processing flow: user enables AI → data de-identified → sent to third-party (LangChain/LangGraph/Tavily/e2b)
- De-identification specifics: strip user identifiers, convert absolute amounts to relative ratios
- Behavioral analytics for product improvement only

**Section 4 (数据存储与安全)** — must distinguish:
- Self-hosted: data on user's own server, Numina team has zero access
- Future SaaS: encrypted at rest, TLS in transit, access controls

**Section 5 (第三方数据共享)** — must name actual providers and describe de-identification before sharing

Last updated date: `2026-10-18`

- [ ] **Step 2: Create `data/privacy-en.ts`**

English version matching Chinese version semantically. Same 11 sections, same structure. Natural English legal prose.

- [ ] **Step 3: Verify typecheck passes**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/about/data/privacy-zh.ts frontend/apps/main/src/pages/about/data/privacy-en.ts
git commit -m "feat(about): add bilingual Privacy Policy content"
```

---

## Task 6: Create TermsPage + PrivacyPage

**Files:**
- Create: `frontend/apps/main/src/pages/about/TermsPage.vue`
- Create: `frontend/apps/main/src/pages/about/PrivacyPage.vue`

**Interfaces:**
- Consumes: `ContentPage` from Task 1, `ContentSection` rendering, `termsContent` from Task 4, `privacyContent` from Task 5

Both pages follow the same pattern: import both language versions, select by locale, render sections with paragraphs and lists.

- [ ] **Step 1: Create `TermsPage.vue`**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ContentPage from '@/components/common/ContentPage.vue'
import { termsContent as termsZh } from './data/terms-zh'
import { termsContent as termsEn } from './data/terms-en'
import type { ContentSection } from './contentTypes'

const { t, locale } = useI18n()

const content = computed<ContentSection[]>(() =>
  locale.value.startsWith('zh') ? termsZh : termsEn
)
</script>

<template>
  <ContentPage :title="t('settings.termsOfService')" last-updated="2026-10-18">
    <section v-for="section in content" :key="section.heading">
      <h2>{{ section.heading }}</h2>
      <template v-for="(block, idx) in section.blocks" :key="idx">
        <p v-if="block.type === 'paragraph'">{{ block.text }}</p>
        <ul v-else-if="block.type === 'list'">
          <li v-for="(item, iidx) in block.items" :key="iidx">{{ item }}</li>
        </ul>
      </template>
    </section>
  </ContentPage>
</template>
```

No additional scoped styles needed — ContentPage provides all typography via `:deep()` selectors.

- [ ] **Step 2: Create `PrivacyPage.vue`**

Same pattern as TermsPage but imports privacy data and uses `settings.privacyPolicy` as title:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ContentPage from '@/components/common/ContentPage.vue'
import { privacyContent as privacyZh } from './data/privacy-zh'
import { privacyContent as privacyEn } from './data/privacy-en'
import type { ContentSection } from './contentTypes'

const { t, locale } = useI18n()

const content = computed<ContentSection[]>(() =>
  locale.value.startsWith('zh') ? privacyZh : privacyEn
)
</script>

<template>
  <ContentPage :title="t('settings.privacyPolicy')" last-updated="2026-10-18">
    <section v-for="section in content" :key="section.heading">
      <h2>{{ section.heading }}</h2>
      <template v-for="(block, idx) in section.blocks" :key="idx">
        <p v-if="block.type === 'paragraph'">{{ block.text }}</p>
        <ul v-else-if="block.type === 'list'">
          <li v-for="(item, iidx) in block.items" :key="iidx">{{ item }}</li>
        </ul>
      </template>
    </section>
  </ContentPage>
</template>
```

- [ ] **Step 3: Verify typecheck passes**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/about/TermsPage.vue frontend/apps/main/src/pages/about/PrivacyPage.vue
git commit -m "feat(about): add TermsPage and PrivacyPage with locale-based content"
```

---

## Task 7: Refactor AboutPage + Add Routes + i18n

**Files:**
- Modify: `frontend/apps/main/src/pages/AboutPage.vue`
- Modify: `frontend/apps/main/src/router/index.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

**Interfaces:**
- Consumes: all four sub-pages from Tasks 2, 3, 6

- [ ] **Step 1: Refactor `AboutPage.vue`**

Remove:
- `showChangelog` ref (line 36)
- `showOpenSource` ref (line 37)
- `changelog` data array (lines 14-34) — moved to `data/changelog.ts`
- `ossComponents` data array (lines 40-61) — moved to `data/licenses.ts`
- `ReleaseNote` interface (lines 14-18)
- `OSSComponent` interface (lines 40-44)
- Changelog popup template (lines 130-147)
- Open Source popup template (lines 150-162)
- All popup-related CSS (lines 226-319)

Keep:
- App info header (logo, name, description, version)
- Menu cell group
- Footer
- `openProjectUrl()` function
- `copyVersion()` function

Change menu cells to use router navigation:
```vue
<van-cell
  :title="t('settings.changelog')"
  icon="notes-o"
  is-link
  to="/settings/about/changelog"
/>
<van-cell
  :title="t('settings.termsOfService')"
  icon="shield-o"
  is-link
  to="/settings/about/terms"
/>
<van-cell
  :title="t('settings.privacyPolicy')"
  icon="lock"
  is-link
  to="/settings/about/privacy"
/>
<van-cell
  :title="t('settings.openSourceLicenses')"
  icon="certificate"
  is-link
  to="/settings/about/licenses"
/>
<van-cell
  :title="t('settings.projectHomepage')"
  icon="link-o"
  is-link
  @click="openProjectUrl"
/>
```

The resulting file should be ~80 lines (header + menu + footer + script), down from 321.

- [ ] **Step 2: Add routes in `router/index.ts`**

Add four new routes after the existing `settings/about` route (line ~368):

```ts
{
  path: 'settings/about/changelog',
  name: 'AboutChangelog',
  component: () => import('@/pages/about/ChangelogPage.vue'),
},
{
  path: 'settings/about/terms',
  name: 'AboutTerms',
  component: () => import('@/pages/about/TermsPage.vue'),
},
{
  path: 'settings/about/privacy',
  name: 'AboutPrivacy',
  component: () => import('@/pages/about/PrivacyPage.vue'),
},
{
  path: 'settings/about/licenses',
  name: 'AboutLicenses',
  component: () => import('@/pages/about/LicensesPage.vue'),
},
```

- [ ] **Step 3: Verify no new i18n keys needed**

The menu cell titles (`settings.changelog`, `settings.termsOfService`, `settings.privacyPolicy`, `settings.openSourceLicenses`, `settings.projectHomepage`) already exist in both locale files. The `ContentPage` title prop uses the same keys. No new i18n keys needed.

- [ ] **Step 4: Run typecheck + lint**

Run: `cd frontend/apps/main && pnpm typecheck && pnpm lint`
Expected: PASS for both

- [ ] **Step 5: Visual verification**

Open the app in browser and verify:
1. `/settings/about` — menu shows 5 items, no popups
2. Click "更新日志" → navigates to `/settings/about/changelog`, shows version timeline, back arrow returns to about
3. Click "用户协议" → navigates to `/settings/about/terms`, shows legal content, back arrow returns
4. Click "隐私政策" → navigates to `/settings/about/privacy`, shows legal content, back arrow returns
5. Click "开源组件声明" → navigates to `/settings/about/licenses`, shows component list, back arrow returns
6. Click "项目主页" → opens GitHub in new tab (unchanged)
7. Switch language → Terms and Privacy pages switch content language
8. Toggle dark mode → all pages render correctly

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(about): refactor AboutPage to use sub-page routes"
```

---

## Task 8: Apply UI/UX Design Polish

**Files:**
- Modify: `frontend/apps/main/src/components/common/ContentPage.vue`
- Modify: `frontend/apps/main/src/pages/about/ChangelogPage.vue`
- Modify: `frontend/apps/main/src/pages/about/LicensesPage.vue`
- Modify: `frontend/apps/main/src/pages/about/TermsPage.vue`
- Modify: `frontend/apps/main/src/pages/about/PrivacyPage.vue`

This task invokes the `ui-ux-pro-max` skill to review and refine the visual design of each page, ensuring mobile-first quality, proper touch targets, smooth scrolling, and WCAG AA accessibility.

- [ ] **Step 1: Invoke ui-ux-pro-max skill for ContentPage review**

Review the base ContentPage component for:
- Typography hierarchy (h2/h3/p sizing and spacing)
- Line height and readability for long-form content
- Touch target sizes for any interactive elements
- Scroll behavior and safe area handling

- [ ] **Step 2: Apply design refinements**

Based on the review, refine:
- ContentPage typography and spacing
- ChangelogPage timeline visual hierarchy
- LicensesPage list layout and badge styling
- TermsPage/PrivacyPage section spacing

- [ ] **Step 3: Run typecheck + lint**

Run: `cd frontend/apps/main && pnpm typecheck && pnpm lint`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "style(about): apply UI/UX design polish to sub-pages"
```
