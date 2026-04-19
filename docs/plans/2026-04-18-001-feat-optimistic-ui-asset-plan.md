---
title: feat: Optimistic UI for Asset CRUD Operations
type: feat
status: completed
date: 2026-04-18
origin: docs/brainstorms/2026-04-18-optimistic-ui-asset-requirements.md
---

# feat: Optimistic UI for Asset CRUD Operations

## Overview

Implement optimistic UI updates for Asset create/update/delete operations to eliminate perceived latency on mobile networks. Users see immediate feedback (< 100ms) while API calls proceed in background. Failed operations rollback silently with Toast notification.

## Problem Frame

移动端弱网场景下，用户点击"保存/删除"后等待 1-2 秒才能看到结果，这感觉像"卡住"或"bug"。金融资产管理应该有即时反馈。

**Who is affected:** 所有在移动网络（3G/4G）下使用 Numina 的家庭成员
**What is changing:** Asset 创建/更新/删除操作从 pessimistic 改为 optimistic
**Why it matters:** 每次写操作的感知延迟直接影响用户信任度

*(Note: Problem framing is speculative — no user feedback or latency metrics cited. Proceeding based on mobile UX best practices and user selection during brainstorm.)*

## Requirements Trace

- **R1.** 创建资产时立即将临时资产对象添加到 `assets` 列表顶部
- **R2.** 更新资产时立即在 `assets` 列表中替换对应项
- **R3.** 删除资产时立即从 `assets` 列表中移除对应项
- **R2a/R3a.** 如果受影响资产也是 `currentAsset`，相应更新/清除 currentAsset *(added from feasibility review)*
- **R4.** 服务端返回错误时，立即撤销 UI 变更恢复到操作前状态
- **R5.** 显示 Toast 提示错误信息 — handled by existing interceptor *(resolved: interceptor handles Toast, store only rollback)*
- **R6.** 不阻塞后续操作，用户可以继续编辑其他资产
- **R7.** 创建资产的临时对象使用客户端生成的 UUID
- **R8.** 服务端成功返回后，替换临时 ID 为真实 ID（保持列表位置不变）
- **R9.** 乐观更新仅影响 `assets` 列表，不主动刷新 Dashboard 概览数据
- **R10.** Dashboard 数据在 2 分钟 TTL 过期后自动重新获取 — existing infrastructure
- **R14.** 同步中的资产显示视觉指示器（降低透明度或徽章）*(added from design-lens review P0)*
- **R15.** 用户不能编辑/删除正在同步的资产 *(added from design-lens review)*
- **R11.** 资产价值更新（`updateValue`）保持 pessimistic — Dashboard 依赖精确数值
- **R12.** 资产出售（`sellAsset`）保持 pessimistic — 涉及复杂业务逻辑
- **R13.** 负债操作（Liability）全部保持 pessimistic — 降低实现复杂度

## Scope Boundaries

- **不处理并发冲突** — 家庭成员同时编辑同一资产时，后提交者覆盖前者（服务端无乐观锁）
- **不实现操作队列** — 失败的操作不自动重试，用户手动重试
- **不处理网络断开** — 网络完全断开时请求失败，按 R4 回滚处理
- **不同步计算 Dashboard** — 依赖现有 staleness guard，避免前端聚合逻辑复杂化
- **仅 Asset 启用乐观更新** — Liability 操作保持 pessimistic
- **价值更新不乐观** — Dashboard overview 依赖精确数值

## Context & Research

### Relevant Code and Patterns

- **`frontend/src/stores/chore.ts:20-38`** — Existing optimistic-rollback pattern (reference implementation)
  - Immediately remove from state → API call → rollback on error with resync fallback → Toast
- **`frontend/src/stores/dashboard.ts:123-126`** — `invalidateDashboard()` clears TTL without forcing fetch
- **`frontend/src/stores/dashboard.ts:89-98`** — Request deduplication via module-level `_fetchPromise` lock
- **`frontend/src/api/index.ts:84-167`** — Centralized error Toast handling in interceptor
- **`frontend/src/pages/AssetFormPage.vue:45`** — Current `fetchAll()` call after success (needs removal)
- **`frontend/src/stores/asset.ts`** — Current pessimistic store (target for modification)

### Institutional Learnings

- **Vant 4 uses `:model-value`** — Optimistic values displayed in van-field must use `modelValue` prop for reactivity
- **Interceptor stays stateless** — Pages control composable lifecycle. Store manages optimistic state, interceptor only shows Toast
- **Log rollback events** — Silent rollback creates invisible state inconsistencies. Always log when rollback occurs
- **Request deduplication pattern** — Use `Map<id, Promise>` to track pending operations, return existing Promise instead of new request

### Key Pattern Reference (chore.ts)

```typescript
// Optimistic-rollback pattern to follow
async function approvePendingChore(id: string) {
  const idx = pendingApprovals.value.findIndex(i => i.id === id)
  if (idx === -1) return
  const removed = pendingApprovals.value.splice(idx, 1)[0]  // OPTIMISTIC REMOVE
  try {
    await choreApi.approveChore(id)
  } catch {
    try {
      await fetchPendingApprovals()  // RESYNC FALLBACK
    } catch {
      if (!pendingApprovals.value.find(i => i.id === removed.id)) {
        pendingApprovals.value.splice(idx, 0, removed)  // MANUAL RESTORE
      }
    }
    showFailToast('审批失败，请重试')
  }
}
```

## Key Technical Decisions

- **Use nanoid for temp IDs** — No UUID library exists in frontend. Add nanoid (small, URL-safe)
- **Follow chore.ts pattern** — Existing proven optimistic-rollback implementation
- **No extra Toast in store** — Interceptor handles all error Toasts (resolves double Toast issue)
- **Use invalidateDashboard() instead of fetchAll()** — Clear TTL, let staleness guard refresh naturally
- **Add syncing visual indicator** — Opacity 0.7 + small badge "同步中" on asset cards (resolves P0 finding)
- **Disable edit/delete on syncing assets** — Prevent user confusion from operating on pending state
- **Sync currentAsset with assets list** — Update/clear currentAsset on optimistic operations (resolves P1 finding)

## Open Questions

### Resolved During Planning

- **Temp ID generation:** Use nanoid — generate at function entry before optimistic insert
- **Double Toast issue:** Store methods don't call showToast — interceptor handles all error Toasts
- **Dashboard handling:** Use `invalidateDashboard()` after success — AssetFormPage removes fetchAll() call
- **currentAsset sync:** Add R2a/R3a — update/clear currentAsset alongside assets list operations

### Deferred to Implementation

- **Temp object field prefilling:** Copy all form fields + nanoid ID + placeholder for server-only fields (user_id, created_at)
- **Rollback snapshot strategy:** CREATE stores tempId for splice removal; UPDATE stores original object for restore; DELETE stores deleted object + original index for re-insert
- **Syncing indicator styling:** Opacity 0.7 + badge position/size — implementation experimentation

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

**Asset Store Optimistic Update Flow:**

```
┌─────────────────────────────────────────────────────────────────┐
│                     Optimistic Update Pattern                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [CREATE]                                                        │
│  ┌─────────┐    ┌──────────────┐    ┌────────────────────────┐   │
│  │ User    │───▶│ Generate     │───▶│ Insert temp asset      │   │
│  │ clicks  │    │ nanoid()     │    │ at top (opacity 0.7)   │   │
│  │ save    │    │              │    │                        │   │
│  └─────────┘    └──────────────┘    └────────────────────────┘   │
│                         │                        │               │
│                         ▼                        ▼               │
│                  ┌──────────────┐    ┌────────────────────────┐   │
│                  │ API create   │───▶│ Success: Replace temp  │   │
│                  │ in background│    │ ID with server ID      │   │
│                  └──────────────┘    │ Remove syncing badge   │   │
│                         │            └────────────────────────┘   │
│                         ▼                        │               │
│                  ┌──────────────┐    ┌────────────────────────┐   │
│                  │ Error from   │───▶│ Rollback: Splice       │   │
│                  │ server       │    │ remove by tempId       │   │
│                  └──────────────┘    │ Interceptor shows Toast│   │
│                                      └────────────────────────┘   │
│                                                                  │
│  [UPDATE]                                                        │
│  ┌─────────┐    ┌──────────────┐    ┌────────────────────────┐   │
│  │ User    │───▶│ Snapshot     │───▶│ Replace in assets[]    │   │
│  │ clicks  │    │ original     │    │ Mark syncing (opacity) │   │
│  │ save    │    │ object       │    │                        │   │
│  └─────────┘    └──────────────┘    └────────────────────────┘   │
│                         │                        │               │
│                         ▼                        ▼               │
│                  ┌──────────────┐    ┌────────────────────────┐   │
│                  │ API update   │───▶│ Success: Use server    │   │
│                  │ in background│    │ response, remove badge │   │
│                  └──────────────┘    └────────────────────────┘   │
│                         │                        │               │
│                         ▼                        ▼               │
│                  ┌──────────────┐    ┌────────────────────────┐   │
│                  │ Error from   │───▶│ Rollback: Restore      │   │
│                  │ server       │    │ from snapshot          │   │
│                  └──────────────┘    │ Interceptor shows Toast│   │
│                                      └────────────────────────┘   │
│                                                                  │
│  [DELETE]                                                        │
│  ┌─────────┐    ┌──────────────┐    ┌────────────────────────┐   │
│  │ User    │───▶│ Snapshot     │───▶│ Remove from assets[]   │   │
│  │ clicks  │    │ object +     │    │                        │   │
│  │ delete  │    │ index        │    │                        │   │
│  └─────────┘    └──────────────┘    └────────────────────────┘   │
│                         │                        │               │
│                         ▼                        ▼               │
│                  ┌──────────────┐    ┌────────────────────────┐   │
│                  │ API delete   │───▶│ Success: No further    │   │
│                  │ in background│    │ action needed          │   │
│                  └──────────────┘    └────────────────────────┘   │
│                         │                        │               │
│                         ▼                        ▼               │
│                  ┌──────────────┐    ┌────────────────────────┐   │
│                  │ Error from   │───▶│ Rollback: Re-insert    │   │
│                  │ server       │    │ at saved index         │   │
│                  └──────────────┘    │ Interceptor shows Toast│   │
│                                      └────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**State tracking requirements:**
- `_pendingOperations: Map<string, Promise>` — track in-flight requests for deduplication
- `_syncingIds: Set<string>` — track asset IDs currently syncing (for visual indicator + disable edit/delete)

## Implementation Units

- [ ] **Unit 1: Add nanoid and syncing state tracking**

**Goal:** Add dependency for temp ID generation and track syncing asset IDs in store

**Requirements:** R7, R14, R15

**Dependencies:** None

**Files:**
- Modify: `frontend/package.json` — add nanoid
- Modify: `frontend/src/stores/asset.ts` — add `_syncingIds` Set and `isSyncing(id)` helper

**Approach:**
- Add nanoid package for URL-safe temp IDs
- Add module-level `_syncingIds: Set<string>` to track assets in sync state
- Export `isSyncing(id: string): boolean` for use in UI components

**Patterns to follow:**
- `dashboard.ts:11` — module-level dedup lock pattern

**Test scenarios:**
- Test expectation: none — pure infrastructure setup, no behavioral change

**Verification:**
- nanoid installed and importable
- `_syncingIds` Set initialized in asset store

---

- [ ] **Unit 2: Implement optimistic create with rollback**

**Goal:** Asset creation shows immediate feedback, rollback on error

**Requirements:** R1, R4, R7, R8, R14, R2a

**Dependencies:** Unit 1

**Files:**
- Modify: `frontend/src/stores/asset.ts` — `createAsset()` function
- Modify: `frontend/src/stores/asset.ts` — add `_pendingOperations` Map for request dedup
- Test: `frontend/src/stores/asset.test.ts` (create if needed)

**Approach:**
1. Generate tempId with nanoid() at function entry
2. Build temp asset object with form data + tempId + placeholder fields
3. Insert at top of assets list with syncing state (add to `_syncingIds`)
4. Check for existing pending operation (dedup) — return existing Promise if found
5. Call API in background
6. On success: find by tempId, replace with server response, remove from `_syncingIds`
7. On error: splice remove by tempId, remove from `_syncingIds`, throw (interceptor handles Toast)
8. If currentAsset.id === tempId, update currentAsset too

**Execution note:** Test-first — start with failing test for optimistic create + rollback behavior

**Patterns to follow:**
- `chore.ts:20-38` — optimistic remove → API → rollback with resync fallback → Toast
- `dashboard.ts:136-138` — request dedup via module-level Promise lock

**Test scenarios:**
- **Happy path:** Create asset → appears in list immediately with syncing indicator → API succeeds → syncing indicator removed, ID replaced with server ID
- **Error path:** Create asset → appears in list → API returns 422 → asset removed from list, syncing indicator cleared, Toast shown by interceptor
- **Dedup:** Rapid double-click save → only one API call, same Promise returned for both invocations
- **currentAsset sync:** Create asset → currentAsset set to new asset → API succeeds → currentAsset updated with server response

**Verification:**
- New asset appears in list before API call completes
- API error causes rollback (asset removed from list)
- No double Toast (interceptor handles, store doesn't call showToast)

---

- [ ] **Unit 3: Implement optimistic update with rollback**

**Goal:** Asset update shows immediate feedback, rollback on error

**Requirements:** R2, R4, R14, R2a

**Dependencies:** Unit 1

**Files:**
- Modify: `frontend/src/stores/asset.ts` — `updateAsset()` function
- Test: `frontend/src/stores/asset.test.ts`

**Approach:**
1. Snapshot original asset object before modification (deep copy)
2. Find asset in list, replace with updated version, add to `_syncingIds`
3. If currentAsset.id matches, update currentAsset too
4. Check pending operations — return existing Promise if found
5. Call API in background
6. On success: use server response, remove from `_syncingIds`
7. On error: restore from snapshot, remove from `_syncingIds`, throw

**Execution note:** Test-first — start with failing test for optimistic update + rollback

**Patterns to follow:**
- `chore.ts:20-38` — optimistic modify → API → rollback on error

**Test scenarios:**
- **Happy path:** Update asset name → change appears immediately with syncing indicator → API succeeds → syncing indicator removed
- **Error path:** Update asset → change appears → API returns 403 → change reverted to original, syncing indicator cleared, Toast shown
- **currentAsset sync:** Update asset while viewing detail → currentAsset shows new name immediately → API succeeds → currentAsset matches server response
- **Concurrent update:** Two rapid updates → second returns first's Promise → only one API call

**Verification:**
- Update appears in list before API call
- API error causes rollback to original state
- currentAsset synchronized with assets list

---

- [ ] **Unit 4: Implement optimistic delete with rollback**

**Goal:** Asset delete removes immediately, rollback on error

**Requirements:** R3, R4, R3a

**Dependencies:** Unit 1

**Files:**
- Modify: `frontend/src/stores/asset.ts` — `deleteAsset()` function
- Test: `frontend/src/stores/asset.test.ts`

**Approach:**
1. Find asset index before removal
2. Snapshot deleted asset + its index
3. Remove from assets list, add to `_syncingIds` (conceptually — asset is gone, but track operation)
4. If currentAsset.id matches, clear currentAsset
5. Check pending operations — return existing Promise if found
6. Call API in background
7. On success: remove from `_syncingIds`, no further action
8. On error: re-insert at saved index, remove from `_syncingIds`, restore currentAsset if applicable, throw

**Execution note:** Test-first — start with failing test for optimistic delete + rollback

**Patterns to follow:**
- `chore.ts:20-38` — optimistic remove → API → rollback with manual restore

**Test scenarios:**
- **Happy path:** Delete asset → disappears from list → API succeeds → no further action needed
- **Error path:** Delete asset → disappears → API returns 500 → asset reappears at original position, Toast shown
- **currentAsset sync:** Delete asset while viewing detail → currentAsset cleared → API fails → currentAsset restored
- **Position preservation:** Delete middle asset → API fails → asset reappears at correct middle position

**Verification:**
- Asset disappears from list before API call
- API error causes re-insertion at original position
- currentAsset restored on rollback

---

- [ ] **Unit 5: Add syncing visual indicator to AssetCard**

**Goal:** Users can distinguish syncing vs confirmed assets

**Requirements:** R14, R15

**Dependencies:** Unit 1

**Files:**
- Modify: `frontend/src/components/asset/AssetCard.vue` — syncing indicator UI (opacity 0.7 + badge)
- Modify: `frontend/src/pages/AssetDetailPage.vue` — disable edit/delete/sell/retire buttons when syncing
- Test: `tests/asset-syncing-indicator.sh` (shell script following project convention)

**Approach:**
1. Access `assetStore.isSyncing(asset.id)` from component
2. When syncing: apply opacity 0.7, show small "同步中" badge in top-left (opposite to existing status badge top-right)
3. Disable edit/delete/sell/retire buttons in AssetDetailPage.vue when syncing (dimmed + aria-disabled="true")
4. Remove indicator when syncing state clears

**Patterns to follow:**
- Vant components use `:model-value` for reactive bindings
- Toast feedback handled by interceptor

**Test scenarios:**
- **Happy path:** Create asset → card shows "同步中" badge + dimmed → API succeeds → badge disappears, opacity restored
- **Edit disabled:** Click save → syncing indicator appears → click edit button → disabled, no action
- **Delete disabled:** Click delete → syncing → click delete again → disabled
- **Opacity transition:** Badge appears with smooth transition, not abrupt

**Verification:**
- Syncing asset visually distinct from confirmed asset
- Edit/delete actions blocked on syncing assets
- Indicator transitions smoothly

---

- [ ] **Unit 6: Update AssetFormPage for Dashboard handling**

**Goal:** Remove fetchAll() call, use invalidateDashboard() instead

**Requirements:** R9, R10

**Dependencies:** Units 2-4 (optimistic operations implemented)

**Files:**
- Modify: `frontend/src/pages/AssetFormPage.vue` — replace `fetchAll()` with `invalidateDashboard()`

**Approach:**
- Remove `await dashboardStore.fetchAll()` after create/update success from AssetFormPage.vue
- `invalidateDashboard()` already called by asset store methods (create/update/delete)
- Rely on existing staleness guard — dashboard refreshes naturally within 2 minutes

**Patterns to follow:**
- `dashboard.ts:180-184` — invalidateDashboard() clears TTL without forcing fetch

**Test scenarios:**
- **Happy path:** Create asset → assets list shows new item → dashboard shows stale data → navigate away and back within 2 min → dashboard still stale → wait 2 min → dashboard refreshed
- **No immediate fetch:** Create asset → no network request to dashboard endpoints immediately → dashboard bundle endpoint not called

**Verification:**
- No dashboard API call immediately after asset CRUD
- Dashboard refreshes within 2 minutes via staleness guard

---

- [ ] **Unit 7: Add request deduplication for concurrent operations**

**Goal:** Prevent duplicate API calls when user rapidly clicks

**Requirements:** R6 (implicit — concurrent operations handled correctly)

**Dependencies:** Unit 1

**Files:**
- Modify: `frontend/src/stores/asset.ts` — add `_pendingOperations: Map<string, Promise>` tracking

**Approach:**
- Already partially implemented in Units 2-4
- Ensure all three operations (create/update/delete) check and store pending Promises
- Use asset ID (or tempId for create) as key
- Clear Promise from map in finally block

**Patterns to follow:**
- `dashboard.ts:136-138` — module-level dedup lock pattern

**Test scenarios:**
- **Double create:** Rapid double-click save → same tempId used for both calls → single API request → single success callback
- **Double update:** Update asset twice rapidly → single API request → latest change sent
- **Pending check:** First call in-flight → second call returns first's Promise → both wait for same result

**Verification:**
- Rapid clicks don't cause duplicate API requests
- Same Promise returned for concurrent operations on same asset

## System-Wide Impact

- **Interaction graph:** 
  - `AssetFormPage.vue` calls `invalidateDashboard()` instead of `fetchAll()`
  - `AssetCard.vue` checks `isSyncing()` for visual indicator and action blocking
  - API interceptor shows Toast on error — store methods only rollback, don't add extra Toast
- **Error propagation:** 
  - API errors flow through interceptor → Toast shown → store catches → rollback → throw (for caller handling)
  - No double Toast (interceptor handles, store doesn't duplicate)
- **State lifecycle risks:**
  - Temp asset with nanoid ID exists until server confirmation — must be removed on error
  - `_syncingIds` Set must be cleared in all error paths to avoid stuck indicators
  - `_pendingOperations` Map must clear in finally block to avoid stuck locks
- **API surface parity:** 
  - Liability operations unchanged — remain pessimistic
  - Asset updateValue and sellAsset unchanged — remain pessimistic
- **Integration coverage:**
  - AssetCard visual indicator syncs with store state
  - AssetFormPage routing after success works with optimistic state
- **Unchanged invariants:**
  - Dashboard overview calculation remains server-side
  - No client-side aggregation logic added
  - Liability store behavior unchanged

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Syncing indicator stuck after error | Medium | High | Clear `_syncingIds` in all error paths (catch + finally) |
| Double Toast shown | Low | Medium | Store doesn't call showToast — interceptor handles all errors |
| Dashboard shows stale data for 2 min | Medium | Low | Accepted per R9-R10 — users see list immediately, overview delayed |
| Concurrent edits overwrite silently | Low | Medium | Accepted per scope boundary — last-write-wins, no optimistic lock |
| Temp ID conflicts with server ID | Very Low | High | nanoid generates unique IDs, collision unlikely |
| Position loss on rollback | Medium | Medium | Store original index for DELETE rollback, splice at exact position |

**Dependencies:**
- nanoid package (new dependency)
- Existing dashboard staleness guard (already implemented)
- Existing API interceptor (no changes needed)

## Documentation / Operational Notes

- **Rollback logging:** Add console.warn when rollback occurs — helps debugging state issues
- **Temp ID format:** nanoid(21) — URL-safe, 21 chars, collision-resistant
- **Syncing badge:** Small text "同步中" in corner, opacity 0.7, transitions 200ms

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-18-optimistic-ui-asset-requirements.md](../brainstorms/2026-04-18-optimistic-ui-asset-requirements.md)
- **Pattern reference:** `frontend/src/stores/chore.ts:20-38` — optimistic-rollback pattern
- **Staleness guard:** `frontend/src/stores/dashboard.ts:140-144` — TTL-based refresh
- **Interceptor:** `frontend/src/api/index.ts:152-172` — centralized error Toast