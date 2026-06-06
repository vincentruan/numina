# Frontend Interaction Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the completed implementation of Icon, Loading, and Splash Screen unification across main and child apps; optionally implement emoji-to-icon Phase 2 migration.

**Architecture:** Icon system uses vite-plugin-svg-icons-ng for local SVG sprites + @iconify/vue for Iconify icons. Loading uses reference-counted showLoading/hideLoading helpers. Splash screens use pure HTML+CSS spinners that auto-dismiss on Vue mount.

**Tech Stack:** Vue 3, TypeScript, Vite, Vant 4, vite-plugin-svg-icons-ng, @iconify/vue

---

## Implementation Status Summary

| Spec Item | Status |
|-----------|--------|
| IIcon.vue (main) | ✅ Implemented at `src/components/IIcon.vue` |
| IIcon.vue (child) | ✅ Implemented at `src/components/IIcon.vue` |
| SvgIcon.vue (main) | ✅ Implemented at `src/components/SvgIcon.vue` |
| SvgIcon.vue (child) | ✅ Implemented at `src/components/SvgIcon.vue` |
| vite-plugin-svg-icons-ng (main) | ✅ Configured in `vite.config.ts` |
| vite-plugin-svg-icons-ng (child) | ✅ Configured in `vite.config.ts` |
| virtual:svg-icons-register (main) | ✅ Imported in `src/main.ts:5` |
| virtual:svg-icons-register (child) | ✅ Imported in `src/main.ts:5` |
| @iconify/vue (main) | ✅ In package.json dependencies |
| @iconify/vue (child) | ✅ In package.json dependencies |
| vite-plugin-svg-icons-ng (main) | ✅ In package.json devDependencies |
| vite-plugin-svg-icons-ng (child) | ✅ In package.json devDependencies |
| loading.ts (main) | ✅ Implemented at `src/utils/loading.ts` |
| loading.ts (child) | ✅ Implemented at `src/utils/loading.ts` |
| Splash screen (main) | ✅ Implemented in `index.html:13-29` |
| Splash screen (child) | ✅ Implemented in `index.html:10-26` |
| icons/svg/*.svg (main) | ✅ 37 SVG files extracted |
| icons/svg/*.svg (child) | ✅ .gitkeep placeholder exists |
| Template `<svg><use>` → `<SvgIcon>` | ✅ Migrated (14 files use SvgIcon) |
| Page-level `<van-loading>` replacement | ✅ No occurrences found |
| Dead code cleanup | ✅ plugins/loading.ts deleted, router/guards/ deleted |
| icon.ts utility | ✅ Updated for SvgIcon at `src/utils/icon.ts` |
| IIcon actual usage | ⏳ Not used yet (available for future) |
| Emoji-to-Icon Phase 2-4 | ⏳ Optional future improvements |

---

## Task 1: Verification — Build Both Apps

**Files:**
- Verify: `frontend/apps/main/`
- Verify: `frontend/apps/child/`

- [ ] **Step 1: Run lint + typecheck for main app**

Run: `cd frontend/apps/main && pnpm lint && pnpm typecheck`
Expected: Both pass with no errors

- [ ] **Step 2: Run lint + typecheck for child app**

Run: `cd frontend/apps/child && pnpm lint && pnpm typecheck`
Expected: Both pass with no errors

- [ ] **Step 3: Build main app**

Run: `cd frontend/apps/main && pnpm build`
Expected: Build succeeds, no errors

- [ ] **Step 4: Build child app**

Run: `cd frontend/apps/child && pnpm build`
Expected: Build succeeds, no errors

- [ ] **Step 5: Verify SVG sprite generation**

Run: `cd frontend/apps/main && grep -r "icon-" dist/assets/*.js | head -5`
Expected: Shows icon symbol IDs in bundle (confirms sprite generation)

---

## Task 2: Optional — Emoji-to-Icon Phase 2 Migration (Main App)

> **Note:** This is optional per spec §4 "Migration Path". Skip if not needed.

**Goal:** Replace ✅❌⚠️ emoji prefixes in toast calls with Vant built-in types.

**Files:**
- Modify: Multiple files in `frontend/apps/main/src/pages/` and `src/components/`

### 2.1 Search for Emoji Toast Patterns

- [ ] **Step 1: Find success toast patterns**

Run: `cd frontend/apps/main && grep -rn "showToast.*✅" src/`
Expected: List of files with success emoji toast calls

- [ ] **Step 2: Find error toast patterns**

Run: `cd frontend/apps/main && grep -rn "showToast.*❌" src/`
Expected: List of files with error emoji toast calls

- [ ] **Step 3: Find warning toast patterns**

Run: `cd frontend/apps/main && grep -rn "showToast.*⚠️" src/`
Expected: List of files with warning emoji toast calls

### 2.2 Create Toast Helper Module (Optional)

**Files:**
- Create: `frontend/apps/main/src/utils/toast.ts`

- [ ] **Step 4: Write toast helper module**

```typescript
// frontend/apps/main/src/utils/toast.ts
import { showSuccessToast, showFailToast, showToast, showLoadingToast } from 'vant'

// Re-export Vant toast APIs for consistent imports
export { showSuccessToast, showFailToast, showLoadingToast }

// Custom toast helpers for common patterns
export function showWarningToast(message: string): void {
  showToast({ message, icon: 'warning-o' })
}

export function showInfoToast(message: string): void {
  showToast({ message, icon: 'info-o' })
}

export function showLockToast(message: string): void {
  showToast({ message, icon: 'lock' })
}

export function showDeleteToast(message: string): void {
  showToast({ message, icon: 'delete-o' })
}
```

- [ ] **Step 5: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: Passes

- [ ] **Step 6: Commit toast helper module**

Run: `cd frontend/apps/main && git add src/utils/toast.ts && git commit -m "feat(utils): add toast helper module for Vant icon types"`
Expected: Commit succeeds

---

## Task 3: Optional — Replace Emoji Toast Calls (Sample Migration)

> **Note:** This demonstrates the pattern. Full migration requires updating i18n keys to remove emoji prefixes.

**Files:**
- Modify: `frontend/apps/main/src/pages/DashboardPage.vue` (sample)

- [ ] **Step 1: Read current toast usage in DashboardPage**

Read: `frontend/apps/main/src/pages/DashboardPage.vue`
Focus: Lines 478-505 (handleBatchDelete and onMoreActionSelect functions)

- [ ] **Step 2: Identify toast calls with emoji**

Current pattern in DashboardPage.vue:
```typescript
showToast(t('toast.assetDeleteBatchSuccess', { count: res.data.success_count }))
showToast(t('toast.deleteFailed'))
showToast(t('toast.assetRetireBatchSuccess', { count: res.data.success_count }))
```

These use i18n keys that include emoji prefixes. To migrate:
1. Update i18n keys to remove emoji
2. Use showSuccessToast/showFailToast instead of showToast

- [ ] **Step 3: Check i18n file for emoji prefixes**

Read: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
Focus: `toast.*` keys

- [ ] **Step 4: Document migration pattern**

Migration pattern (DO NOT IMPLEMENT WITHOUT USER APPROVAL):

```typescript
// Before (emoji in i18n)
showToast(t('toast.assetDeleteSuccess'))  // i18n: "✅ 资产已删除"

// After (Vant built-in)
showSuccessToast(t('toast.assetDeleteSuccess'))  // i18n: "资产已删除" (no emoji)
```

This requires updating both:
1. The toast API call (showToast → showSuccessToast)
2. The i18n string (remove ✅ prefix)

---

## Scope Boundaries

### IN scope (completed)
- IIcon + SvgIcon component creation ✅
- vite-plugin-svg-icons-ng setup ✅
- Sprite sheet extraction → individual SVG files ✅
- Template `<svg><use>` → `<SvgIcon>` migration ✅
- Loading helper utility ✅
- Splash screen for both apps ✅
- Dead code cleanup ✅

### OUT of scope
- Inline SVG component migration (AIBrainIcon, CurrencyIcon, coins, etc.)
- Mass showToast() replacement (317 calls stay as-is with emoji)
- Axios interceptor for global loading
- Business logic changes
- SSE/stream request loading
- New UI libraries

### OPTIONAL scope (Phase 2-4 from spec)
- Replace ✅❌⏳⚠️ with Vant built-in toast types
- Use `icon: 'warning-o'` for Vant-provided icons
- Create `<ToastIcon>` wrapping `<IIcon>` for specialized icons (🤖📡💰🎨🔥🎉)

---

## Verification Commands

```bash
# Full verification
cd frontend/apps/main && pnpm lint && pnpm typecheck && pnpm build
cd frontend/apps/child && pnpm lint && pnpm typecheck && pnpm build

# Verify SVG sprite generation
cd frontend/apps/main && ls -la src/icons/svg/  # Should show 37 SVG files
cd frontend/apps/child && ls -la src/icons/svg/  # Should show .gitkeep

# Verify component usage
cd frontend/apps/main && grep -rn "<SvgIcon" src/  # Should show 14 files
cd frontend/apps/main && grep -rn "<IIcon" src/    # Should show 0 (available for future)
```