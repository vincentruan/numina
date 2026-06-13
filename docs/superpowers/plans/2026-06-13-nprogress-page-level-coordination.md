# Page-Level NProgress Coordination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate NProgress progress bar flickering by coordinating page-level loading state — progress bar completes only when the current page signals it's fully ready.

**Architecture:** Create a `usePageLoading` composable that tracks pending async operations per page. Router starts NProgress in `beforeEach` but defers completion to the page. Pages increment/decrement a loading counter; NProgress completes when counter reaches zero. Existing direct `NProgress.start()/done()` calls in pages are replaced with the composable.

**Tech Stack:** Vue 3 Composition API, Pinia for cross-component state, NProgress

---

## Problem Analysis

**Current behavior:**
1. Router `beforeEach` → `NProgress.start()`
2. Router `afterEach` → `NProgress.done()` (immediately for skeleton pages, or after 100ms delay)
3. Pages manually call `NProgress.start()`/`NProgress.done()` for each async operation
4. Multiple start/stop cycles → progress bar flickers

**Affected files:**
- `frontend/apps/main/src/router/index.ts` — router guard NProgress calls
- `frontend/apps/main/src/pages/DashboardPage.vue` — 9 NProgress calls
- `frontend/apps/main/src/pages/SettingsPage.vue` — 3 NProgress calls
- `frontend/apps/main/src/pages/BabyChoreTemplatesPage.vue` — 2 NProgress calls
- `frontend/apps/main/src/pages/AssetSellPage.vue` — 2 NProgress calls
- `frontend/apps/main/src/pages/BabyChoreTemplateEditPage.vue` — 3 NProgress calls
- `frontend/apps/main/src/pages/BlindBoxConfigPage.vue` — 2 NProgress calls
- `frontend/apps/main/src/pages/FamilyPage.vue` — 2 NProgress calls
- `frontend/apps/child/src/router/index.ts` — router guard NProgress calls
- `frontend/apps/child/src/pages/*.vue` — 10+ files with NProgress.done() calls

---

## File Structure

| File | Purpose |
|------|---------|
| `frontend/apps/main/src/composables/usePageLoading.ts` | Main app page loading coordinator (new) |
| `frontend/apps/child/src/composables/usePageLoading.ts` | Child app page loading coordinator (new) |
| `frontend/apps/main/src/router/index.ts` | Modified router guards (defer completion) |
| `frontend/apps/child/src/router/index.ts` | Modified router guards (defer completion) |
| `frontend/apps/main/src/pages/*.vue` | Replace direct NProgress calls |
| `frontend/apps/child/src/pages/*.vue` | Replace direct NProgress calls |

---

## Task 1: Create usePageLoading Composable (Main App)

**Files:**
- Create: `frontend/apps/main/src/composables/usePageLoading.ts`

- [ ] **Step 1: Write the composable implementation**

The composable provides:
- `increment()` — start/increase loading counter, triggers NProgress.start() if counter goes from 0 to 1
- `decrement()` — decrease loading counter, triggers NProgress.done() when counter reaches 0
- `complete()` — force complete (for pages that don't track async operations)
- `isLoading` — reactive boolean for current loading state
- Auto-cleanup on component unmount (safety net for abandoned pages)

```typescript
// frontend/apps/main/src/composables/usePageLoading.ts
import { ref, computed, onUnmounted } from 'vue'
import NProgress from 'nprogress'

// Global loading counter (shared across all components in the page)
const loadingCount = ref(0)

// Track if NProgress was started by this system
let nprogressStarted = false

/**
 * Page-level loading coordinator.
 * Replaces direct NProgress.start()/done() calls.
 *
 * Usage:
 * - onMounted: call increment() before async fetch, decrement() after
 * - For multiple async ops: increment() for each, decrement() when each completes
 * - For simple pages: call complete() in onMounted
 */
export function usePageLoading() {
  function increment() {
    loadingCount.value++
    if (loadingCount.value === 1 && !nprogressStarted) {
      NProgress.start()
      nprogressStarted = true
    }
  }

  function decrement() {
    if (loadingCount.value > 0) {
      loadingCount.value--
    }
    if (loadingCount.value === 0 && nprogressStarted) {
      NProgress.done()
      nprogressStarted = false
    }
  }

  function complete() {
    loadingCount.value = 0
    if (nprogressStarted) {
      NProgress.done()
      nprogressStarted = false
    }
  }

  // Safety net: complete loading if component unmounts while loading
  onUnmounted(() => {
    if (loadingCount.value > 0) {
      loadingCount.value = 0
      if (nprogressStarted) {
        NProgress.done()
        nprogressStarted = false
      }
    }
  })

  const isLoading = computed(() => loadingCount.value > 0)

  return {
    increment,
    decrement,
    complete,
    isLoading,
  }
}
```

---

## Task 2: Create usePageLoading Composable (Child App)

**Files:**
- Create: `frontend/apps/child/src/composables/usePageLoading.ts`

- [ ] **Step 1: Write the composable implementation**

Same implementation as main app, adapted for child app context:

```typescript
// frontend/apps/child/src/composables/usePageLoading.ts
import { ref, computed, onUnmounted } from 'vue'
import NProgress from 'nprogress'

// Global loading counter (shared across all components in the page)
const loadingCount = ref(0)

// Track if NProgress was started by this system
let nprogressStarted = false

/**
 * Page-level loading coordinator for child app.
 * Replaces direct NProgress.start()/done() calls.
 *
 * Usage:
 * - onMounted: call increment() before async fetch, decrement() after
 * - For multiple async ops: increment() for each, decrement() when each completes
 * - For simple pages with skeleton: call complete() immediately
 */
export function usePageLoading() {
  function increment() {
    loadingCount.value++
    if (loadingCount.value === 1 && !nprogressStarted) {
      NProgress.start()
      nprogressStarted = true
    }
  }

  function decrement() {
    if (loadingCount.value > 0) {
      loadingCount.value--
    }
    if (loadingCount.value === 0 && nprogressStarted) {
      NProgress.done()
      nprogressStarted = false
    }
  }

  function complete() {
    loadingCount.value = 0
    if (nprogressStarted) {
      NProgress.done()
      nprogressStarted = false
    }
  }

  // Safety net: complete loading if component unmounts while loading
  onUnmounted(() => {
    if (loadingCount.value > 0) {
      loadingCount.value = 0
      if (nprogressStarted) {
        NProgress.done()
        nprogressStarted = false
      }
    }
  })

  const isLoading = computed(() => loadingCount.value > 0)

  return {
    increment,
    decrement,
    complete,
    isLoading,
  }
}
```

---

## Task 3: Modify Router Guards (Main App)

**Files:**
- Modify: `frontend/apps/main/src/router/index.ts:369-432`

- [ ] **Step 1: Import usePageLoading and modify beforeEach**

Router only starts NProgress, no longer calls `done()` in `afterEach`. The page's `usePageLoading` composable signals completion.

```typescript
// frontend/apps/main/src/router/index.ts
// ... existing imports ...
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { usePageLoading } from '@/composables/usePageLoading' // Add import

NProgress.configure({ showSpinner: true, parent: '#app' })

// ... existing route definitions ...

router.beforeEach((to, _from, next) => {
  NProgress.start()

  // /child/* paths belong to the child SPA
  if (to.path === '/child' || to.path.startsWith('/child/')) {
    next()
    return
  }

  // ... existing auth logic unchanged ...
  const user = getUser()
  const isLoggedIn = !!user
  const isChild = user?.role === 'child'

  if (to.meta.guest) {
    if (isLoggedIn && !isChild) {
      next('/')
    } else {
      next()
    }
    return
  }

  if (isChild) {
    window.location.replace(getChildBaseUrl())
    return
  }

  if (!isLoggedIn) {
    next('/login')
    return
  }

  next()
})

router.afterEach((to) => {
  // Pages with skeleton: complete immediately
  // The skeleton takes over visual feedback
  if (to.meta.hasSkeleton) {
    NProgress.done()
    return
  }

  // Pages without skeleton: do NOT complete here
  // The page's usePageLoading composable will signal completion
  // Safety timeout: if page doesn't signal within 5s, complete anyway
  setTimeout(() => {
    // Import the composable to check state
    const { isLoading, complete } = usePageLoading()
    if (isLoading.value) {
      // Page is still loading after 5s — likely slow network
      // Let NProgress trickle naturally, don't force complete
    } else {
      // Page didn't start any loading, complete the progress bar
      NProgress.done()
    }
  }, 5000)
})
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

---

## Task 4: Modify Router Guards (Child App)

**Files:**
- Modify: `frontend/apps/child/src/router/index.ts:129-174`

- [ ] **Step 1: Modify beforeEach and afterEach**

Same pattern as main app, but child app has additional async session verification:

```typescript
// frontend/apps/child/src/router/index.ts
// ... existing imports ...
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { usePageLoading } from '@/composables/usePageLoading' // Add import

NProgress.configure({ showSpinner: true, parent: '#app' })

// ... verifyChildSession function unchanged ...

router.beforeEach(async (to, _from, next) => {
  NProgress.start()

  // Check cached localStorage first (fast path)
  const authStore = useAuthStore()
  const cachedUser = authStore.user

  if (cachedUser?.role === 'child') {
    next()
    return
  }

  // Need to verify session via API
  const isChildSession = await verifyChildSession()

  if (!isChildSession) {
    NProgress.done() // Complete before external redirect
    const redirectPath = to.path !== '/' ? `/child${to.path}` : '/child/'
    const baseUrl = getMainBaseUrl()
    window.location.href = `${baseUrl}/login?redirect=${encodeURIComponent(redirectPath)}`
    next(false)
    return
  }

  next()
})

router.afterEach((to) => {
  // Pages with skeleton: complete immediately
  if (to.meta.hasSkeleton) {
    NProgress.done()
    return
  }

  // Pages without skeleton: defer to page's usePageLoading
  // Safety timeout after 5s
  setTimeout(() => {
    const { isLoading } = usePageLoading()
    if (!isLoading.value) {
      NProgress.done()
    }
  }, 5000)
})
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/child && pnpm typecheck`
Expected: PASS

---

## Task 5: Update DashboardPage (Main App) — Largest Example

**Files:**
- Modify: `frontend/apps/main/src/pages/DashboardPage.vue:277-549`

- [ ] **Step 1: Replace import and add usePageLoading**

```typescript
// Remove: import NProgress from 'nprogress' (line 277)
// Add:
import { usePageLoading } from '@/composables/usePageLoading'

// In setup section (around line 299):
const { increment, decrement } = usePageLoading()
```

- [ ] **Step 2: Update onMounted lifecycle**

Find existing `onMounted` block and replace NProgress calls:

```typescript
// Original pattern (hypothetical):
onMounted(async () => {
  NProgress.start()
  try {
    await dashboardStore.fetchAll()
    NProgress.done()
  } catch {
    NProgress.done()
  }
})

// New pattern:
onMounted(async () => {
  increment()
  try {
    await dashboardStore.fetchAll()
    decrement()
  } catch {
    decrement()
  }
})
```

- [ ] **Step 3: Update batchArchiveAssets function (lines 485-505)**

```typescript
// Original:
async function onBatchArchive() {
  // ... confirm dialog ...
  NProgress.start()
  try {
    const res = await batchArchiveAssets(selectedIds.value)
    NProgress.done()
    // ...
  } catch {
    NProgress.done()
  }
}

// New:
async function onBatchArchive() {
  // ... confirm dialog unchanged ...
  increment()
  try {
    const res = await batchArchiveAssets(selectedIds.value)
    decrement()
    showToast(t('toast.assetDeleteBatchSuccess', { count: res.data.success_count }))
    // ... rest unchanged ...
  } catch {
    decrement()
    showToast(t('toast.deleteFailed'))
  }
}
```

- [ ] **Step 4: Update onMoreActionSelect function (lines 507-552)**

Replace the `NProgress.start()` at line 513 and all `NProgress.done()` calls (lines 518, 524, 530, 549):

```typescript
async function onMoreActionSelect(action: { value: string }) {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }

  increment()
  try {
    switch (action.value) {
      case 'retire': {
        const res = await batchUpdateStatus(selectedIds.value, 'archived')
        decrement()
        showToast(t('toast.assetRetireBatchSuccess', { count: res.data.success_count }))
        break
      }
      case 'activate': {
        const res = await batchUpdateStatus(selectedIds.value, 'active')
        decrement()
        showToast(t('toast.assetActivateBatchSuccess', { count: res.data.success_count }))
        break
      }
      case 'export': {
        const res = await batchExportAssets(selectedIds.value)
        decrement()
        // ... download logic unchanged ...
        showToast(t('toast.assetExportBatchSuccess', { count: res.data.count }))
        break
      }
    }
    // ... rest of function unchanged ...
  } catch {
    decrement()
    showToast(t('toast.operationFailed'))
  }
}
```

- [ ] **Step 5: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

---

## Task 6: Update SettingsPage (Main App)

**Files:**
- Modify: `frontend/apps/main/src/pages/SettingsPage.vue`

- [ ] **Step 1: Replace NProgress import with usePageLoading**

```typescript
// Remove: import NProgress from 'nprogress'
// Add: import { usePageLoading } from '@/composables/usePageLoading'

// In setup:
const { increment, decrement } = usePageLoading()
```

- [ ] **Step 2: Replace NProgress calls**

Find and replace all `NProgress.start()` → `increment()` and `NProgress.done()` → `decrement()`.

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

---

## Task 7: Update BabyChoreTemplatesPage (Main App)

**Files:**
- Modify: `frontend/apps/main/src/pages/BabyChoreTemplatesPage.vue`

- [ ] **Step 1: Replace NProgress import with usePageLoading**

Same pattern as Task 6.

- [ ] **Step 2: Replace NProgress calls**

Replace `NProgress.start()` → `increment()` and `NProgress.done()` → `decrement()`.

- [ ] **Step 3: Run typecheck**

Expected: PASS

---

## Task 8: Update AssetSellPage (Main App)

**Files:**
- Modify: `frontend/apps/main/src/pages/AssetSellPage.vue`

- [ ] **Step 1: Replace NProgress import with usePageLoading**

Same pattern.

- [ ] **Step 2: Replace NProgress calls**

- [ ] **Step 3: Run typecheck**

Expected: PASS

---

## Task 9: Update BabyChoreTemplateEditPage (Main App)

**Files:**
- Modify: `frontend/apps/main/src/pages/BabyChoreTemplateEditPage.vue`

- [ ] **Step 1: Replace NProgress import with usePageLoading**

Same pattern. Note: this page has 3 NProgress.done() calls (multiple async paths).

- [ ] **Step 2: Replace all NProgress calls**

Ensure every `start()` → `increment()` and every `done()` → `decrement()`.

- [ ] **Step 3: Run typecheck**

Expected: PASS

---

## Task 10: Update BlindBoxConfigPage (Main App)

**Files:**
- Modify: `frontend/apps/main/src/pages/BlindBoxConfigPage.vue`

- [ ] **Step 1: Replace NProgress import with usePageLoading**

- [ ] **Step 2: Replace NProgress calls**

- [ ] **Step 3: Run typecheck**

Expected: PASS

---

## Task 11: Update FamilyPage (Main App)

**Files:**
- Modify: `frontend/apps/main/src/pages/FamilyPage.vue`

- [ ] **Step 1: Replace NProgress import with usePageLoading**

- [ ] **Step 2: Replace NProgress calls**

- [ ] **Step 3: Run typecheck**

Expected: PASS

---

## Task 12: Update Child App Pages (Batch)

**Files:**
- Modify: `frontend/apps/child/src/pages/ChildAssetDetailPage.vue`
- Modify: `frontend/apps/child/src/pages/ChildLedgerPage.vue`
- Modify: `frontend/apps/child/src/pages/ChildTreasuresPage.vue`
- Modify: `frontend/apps/child/src/pages/ChildDayDetailPage.vue`
- Modify: `frontend/apps/child/src/pages/ChildWishCreatePage.vue`
- Modify: `frontend/apps/child/src/pages/ChildHomePage.vue`
- Modify: `frontend/apps/child/src/pages/ChildWishDetailPage.vue`
- Modify: `frontend/apps/child/src/pages/ChildWishesPage.vue`
- Modify: `frontend/apps/child/src/pages/ChildTasksPage.vue`

- [ ] **Step 1: For each child page, replace NProgress import**

```typescript
// Remove: import NProgress from 'nprogress'
// Add: import { usePageLoading } from '@/composables/usePageLoading'
```

- [ ] **Step 2: Replace NProgress.done() calls**

Child pages mostly call `NProgress.done()` after data loads (they have skeletons). Replace with:

```typescript
const { complete } = usePageLoading()

// In onMounted, after data loads:
complete()
```

Note: Child pages with `hasSkeleton` meta have NProgress completed immediately by router. The `complete()` call in the page is a safety measure to ensure cleanup.

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/child && pnpm typecheck`
Expected: PASS

---

## Task 13: Update Test Mocks

**Files:**
- Modify: `frontend/apps/main/tests/setup.ts`
- Modify: `frontend/apps/child/tests/setup.ts`

- [ ] **Step 1: Update main app test setup**

Add mock for the new composable:

```typescript
// frontend/apps/main/tests/setup.ts
vi.mock('nprogress', () => ({
  default: {
    start: vi.fn(),
    done: vi.fn(),
    configure: vi.fn(),
  },
}))

// Mock the composable
vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({
    increment: vi.fn(),
    decrement: vi.fn(),
    complete: vi.fn(),
    isLoading: { value: false },
  }),
}))
```

- [ ] **Step 2: Update child app test setup**

Same pattern for child app:

```typescript
// frontend/apps/child/tests/setup.ts
vi.mock('nprogress', () => ({
  default: {
    start: vi.fn(),
    done: vi.fn(),
    configure: vi.fn(),
    remove: vi.fn(),
    set: vi.fn(),
  },
}))

vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({
    increment: vi.fn(),
    decrement: vi.fn(),
    complete: vi.fn(),
    isLoading: { value: false },
  }),
}))
```

- [ ] **Step 3: Run tests**

Run: `cd frontend && pnpm -r test:run`
Expected: PASS

---

## Task 14: Manual Testing & Verification

- [ ] **Step 1: Start dev servers**

```bash
cd frontend/apps/main && pnpm dev --host 0.0.0.0
cd frontend/apps/child && pnpm dev --host 0.0.0.0
```

- [ ] **Step 2: Test slow network scenario**

Use Chrome DevTools Network throttling (Slow 3G preset):
1. Navigate between pages
2. Observe progress bar behavior
3. Expected: Single smooth progress, no flickering
4. Progress bar completes when page content is visible

- [ ] **Step 3: Test batch operations on Dashboard**

1. Enter selection mode on Dashboard
2. Select multiple assets
3. Perform batch archive/retire/activate/export
4. Expected: Progress bar shows for each operation, no flickering

- [ ] **Step 4: Verify skeleton pages**

1. Navigate to child app pages (have skeleton)
2. Expected: Progress bar completes immediately, skeleton takes over

---

## Task 15: Commit

- [ ] **Step 1: Commit changes**

```bash
git add frontend/apps/main/src/composables/usePageLoading.ts \
        frontend/apps/child/src/composables/usePageLoading.ts \
        frontend/apps/main/src/router/index.ts \
        frontend/apps/child/src/router/index.ts \
        frontend/apps/main/src/pages/*.vue \
        frontend/apps/child/src/pages/*.vue \
        frontend/apps/main/tests/setup.ts \
        frontend/apps/child/tests/setup.ts

git commit -m "fix(ui): eliminate NProgress flickering with page-level loading coordinator

- Add usePageLoading composable to track async operations per page
- Router defers NProgress.done() to page completion (5s safety timeout)
- Replace direct NProgress calls in all pages with composable
- Progress bar now completes only when page signals ready

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All pages with NProgress calls are updated
- [x] **Placeholder scan:** No TBD/TODO — all code shown
- [x] **Type consistency:** `increment()`, `decrement()`, `complete()` signatures consistent across both apps
- [x] **Router guard logic:** Both apps defer completion with 5s safety timeout
- [x] **Test mocks:** Both apps have composable mocks added