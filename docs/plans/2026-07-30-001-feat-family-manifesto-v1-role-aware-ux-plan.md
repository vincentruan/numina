---
title: Family Manifesto V1 - Role-Aware UX - Plan
type: feat
date: 2026-07-30
origin: docs/family-manifesto-design.md
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: legacy-requirements
execution: code
---

# Family Manifesto V1 - Role-Aware UX - Plan

## Goal Capsule

- **Objective:** Implement the V1 Family Manifesto items — role-aware shimmer, celebration enhancement, swipe-to-complete, animated tab bar, member notification, child toast differentiation, dialog classification, and mystery bonus consolation — so each of the 3 roles (Owner/Member/Child) experiences the design principles (P1–P4) in daily use.
- **Authority:** Product decisions from `docs/family-manifesto-design.md` and companion docs; implementation decisions in this plan.
- **Stop conditions:** All V1 items implemented with tests passing; cross-app consistency verified (no semantic token drift, animation ≤ 2000ms hard cap).
- **Execution profile:** Incremental — each unit is independently mergeable. Frontend-heavy; minimal backend changes (i18n keys, possibly one reward-flow endpoint adjustment).

---

## Product Contract

### Summary

Implement 8 V1 interaction enhancements that bring the Family Manifesto's 4 design principles (Control without Anxiety, Participation without Spectating, Achievement without Pressure, Pause is Respect) to life across main app (Owner/Member) and child app (Child). The work extends existing infrastructure — the celebration composable, blind box system, `van-skeleton` usage, and `ChildTabBar` — rather than building parallel mechanisms.

### Problem Frame

The Family Manifesto (`docs/family-manifesto-design.md`) defines experience principles for Numina's 3 roles but the current codebase has gaps: shimmer is uniform (no role differentiation), child task completion has celebration but no swipe gesture, the blind box / mystery bonus system exists but is not connected to task completion reward flow, member notifications have no implementation, child errors use the same toast patterns as adults, and destructive dialogs don't differentiate by role.

### Requirements

**Shimmer & Loading**

- R1. A reusable `RoleShimmer` component renders role-appropriate loading states — Owner/Member see standard `van-skeleton` skeleton screens, Child sees Clay brand-color pulsing with micro-bounce animation.
- R2. `RoleShimmer` replaces ad-hoc loading patterns in at least the child task list page and the main app dashboard skeleton.

**Celebration & Task Completion**

- R3. Task completion in the child app triggers a celebration animation ≤ 1500ms that includes positive visual feedback (confetti/burst) and plays automatically on successful completion.
- R4. Celebration is integrated with the existing `useCelebration` composable and `CelebrationAnimation.vue` rather than a new system.

**Swipe-to-Complete**

- R5. Child can complete a task via a swipe-right gesture on the task item, with visual progress feedback during the swipe.
- R6. Swipe threshold and animation follow the interaction-rules timing norms (≤ 2000ms total, spring easing for child).

**Animated Tab Bar**

- R7. Child tab bar items have a subtle bounce/scale animation on tap, consistent with the Clay playful style.
- R8. Animation uses CSS transitions (no JS animation library), ≤ 250ms per item.

**Member Notification**

- R9. Member sees notification via `van-notify` top bar when: family settings change affects them, a new member joins, or they are deactivated. V1 scope is local-only (notification appears on the device where the action occurs); cross-device push requires WebSocket infrastructure (deferred).
- R10. Notification auto-dismisses after 3s. No separate notification preference page.

**Child Toast Differentiation**

- R11. Error states in the child app use inline温和提示 (gentle inline prompts) instead of `showFailToast`, following P3's de-penalization principle.
- R12. The word "错误" (error) does not appear in child-facing messages — use " Oops" / "出了点小问题" instead.

**Dialog Classification**

- R13. Destructive confirmations in the main app use bottom slide-up panels (not center dialogs) for Owner operations, following P1's "control without anxiety" principle.
- R14. Child app never uses center `van-dialog` for destructive operations — use inline undo snackbar instead.

**Mystery Bonus Consolation**

- R15. When mystery bonus (~20% variable ratio per manifesto; codebase `base_draw_prob` is 0.30 — accepted as the V1 implementation of the ~20% design intent) does NOT trigger on task completion, show a consolation message ("下次一定！") instead of nothing, to prevent disappointment.
- R16. Consolation uses the existing blind box `DrawAnimation` flow or a lightweight inline alternative.

**Owner Impact Description**

- R17. Family config page items show an "impact description" explaining how the setting affects family members' experience.

### Scope Boundaries

**Not in V1:**
- P5 sound/haptic layer (H5 API reliability insufficient)
- Child "My Room" homepage redesign (high cost, long-term vision)
- Encouraging empty states (current empty states acceptable)
- D8 dual-date picker (interval buttons cover 90% of cases)
- Logout route fix (bug fix, not manifesto scope)

**Deferred to follow-up:**
- O6 — Owner impact scope showing specific numbers ("影响 3 个家庭成员") vs. descriptive text. V1 implements descriptive text (R17/U9); numeric display deferred.

### Open Questions

- **WebSocket client infrastructure (U5 cross-device notification).** RESOLVED: V1 does not depend on WebSocket. System is "用完即走" — notifications are passive checks on page entry only. Cross-device push deferred entirely.
- **Celebration double-trigger prevention (U2).** RESOLVED: Keep existing batch/poll model (necessary for async parent approval). Do NOT add real-time `celebrateTaskComplete()`. Instead: (a) fix the `pollForApproval` gap so it updates `chores` ref on approval, which triggers the existing watcher → celebration. (b) Enhance celebration animation ≤ 1500ms. The localStorage guard in `celebrationState.ts` prevents double-celebration.
- **Swipe UX for pending-approval tasks (U3).** RESOLVED: Swipe must differentiate completion vs pending. Show "已提交" (submitted) with clock icon for pending_approval, show "已完成" (completed) with checkmark for auto-approved.
- **ChildInlineError placement model (U6).** RESOLVED: Unified slide-down banner across all 8 pages.
- **Main app showConfirmDialog scope (U7).** RESOLVED: 5 destructive files → BottomSheetConfirm (AssetListPanel, LiabilityListPanel ×3, WishSavingsLogDialog, BabyChoreTemplatesPage, AssetSellPage). 3 auth pages stay as center dialog (LogoutPage, SettingsPage, ChangePasswordPage). ChallengeList deferred.
- **Main app RoleShimmer (U1).** RESOLVED: V1 skips main app RoleShimmer. Owner and Member share the same app with no role-differentiated rendering. Only child app RoleShimmer is implemented in V1.

### Sources

- `docs/family-manifesto-design.md` — core vision + principles
- `docs/design/family-interaction-rules.md` — interaction rules (shimmer timing, dialog classification, animation norms, notification matrix)
- `docs/design/family-manifesto-deferred-items.md` — V1 item selection + priority
- `docs/design-tokens.md` — cross-app token mapping
- `docs/ideation/child-ui-interaction-ideas.md` — original child UI ideas

---

## Planning Contract

### Key Technical Decisions

KTD1. **RoleShimmer as per-app CSS-scoped Vue component (not shared package).** ESLint `no-restricted-imports` blocks cross-app source imports, and the child app's `skeletons/` directory already has 11+ dedicated skeleton components. A shared package would require declaring Vant as a peer dependency — not worth the coupling. Instead: create `RoleShimmer.vue` in child app (consuming Clay tokens from `clay.css`) and a thin `RoleShimmer.vue` wrapper in main app (consuming Together AI tokens). Both consume the same semantic token names but different values, per the design-tokens.md contract.

KTD2. **Keep existing batch/poll celebration model, fix the `pollForApproval` gap.** The celebration system uses `checkAndTriggerCelebration` on page load + `watch(chores)` reactive trigger, with `celebrationState.ts` localStorage guard preventing double-celebration. This batch model is necessary — approval is async (parent on separate device, default `auto_approve_hours = 24h`). The one gap: `pollForApproval` detects approval but only triggers blind box, not celebration. Fix: when poll detects `approved`, update the chore in `chores` ref → watcher auto-fires celebration. No new real-time trigger mechanism needed. Use `motionTokens.ts` for animation constants.

KTD3. **Native touch events for swipe-to-complete, no gesture library.** `WishConstellationCard.vue` already uses `touchstart`/`touchend` patterns for peek interactions. A `useSwipeComplete` composable with configurable threshold (default 60% of item width) and spring-back animation using `motionTokens.ts` easings follows this established pattern. A gesture library (hammerjs, etc.) would add bundle weight for one interaction. Touch area must be ≥ 48×48dp per the mobile UX accessibility plan.

KTD4. **CSS-only tab bar animation using existing `ChildTabBar.vue` wrapper.** The current `ChildTabBar.vue` (72 lines) wraps `van-tabbar` with 5 tabs. Adding CSS `transition` on the icon container for `transform: scale()` with a spring-like `cubic-bezier(0.34, 1.56, 0.64, 1)` (matching `motionTokens.ts` spring easing) achieves the Clay bouncy feel without JS. The layout already has a `page-fade` CSS transition on `<router-view>`.

KTD5. **`van-notify` for member notifications — passive page-entry checks, no WebSocket.** Vant 4 provides `showNotify()` as a function-call API (auto-imported like `showToast`). The system is "用完即走" — notifications are passive checks on page entry (compare local data with server), not real-time push. No WebSocket client infrastructure needed. Cross-device push is deferred entirely.

KTD6. **Child inline error component, not toast variant.** Create a `ChildInlineError.vue` component that renders a soft Clay-styled message with a gentle icon (not the Vant fail icon). This replaces `showFailToast` calls in child pages. The component uses `--color-surface-soft` background and `--color-ink` text for a non-punitive appearance.

KTD7. **Bottom-sheet for destructive Owner operations.** Replace `showConfirmDialog` with a custom `BottomSheetConfirm.vue` component using `van-popup` (position="bottom") for destructive operations on the main app. The sheet includes "影响预览" text. Child app destructive operations use inline snackbar with undo.

KTD8. **Consolation message via inline toast after `checkAutoDraw()`.** The task completion flow already calls `checkAutoDraw()` after auto-approval, which triggers the blind box draw with `base_draw_prob` (currently 0.30). When the draw does NOT trigger, show a consolation toast. The full blind box `DrawAnimation` is reserved for the dedicated `ChildBlindBoxPage` — for task-completion consolation, use `showToast({ message: t('reward.consolation') })` with a gentle tone. This avoids double-animation (celebration + full draw) and keeps the consolation lightweight.

### Assumptions

- The existing blind box API (`blindBoxApi.draw()`) already returns whether a bonus was triggered. The frontend just needs to handle the non-trigger case with consolation text.
- `van-notify` is available via Vant 4 auto-import (confirmed: Vant 4.9.24 is installed, `showNotify` is in the Vant package).
- The child task completion API call (`PATCH /chores/:id/complete`) already exists and returns success/failure. No new backend endpoint needed.
- Family config API returns setting descriptions; the "impact description" can be computed client-side from the setting key (no backend schema change needed for V1).

---

## Implementation Units

### U1. RoleShimmer Shared Component

**Goal:** Create a reusable `RoleShimmer` component that renders role-appropriate loading states.

**Requirements:** R1, R2

**Dependencies:** None (foundational)

**Files:**
- `frontend/apps/child/src/components/RoleShimmer.vue` (new)
- `frontend/apps/child/src/components/__tests__/RoleShimmer.spec.ts` (new)
- `frontend/apps/child/src/pages/ChildTasksPage.vue` (modify — replace `ChildTasksSkeleton` usage with RoleShimmer)

**Approach:**
1. Create `RoleShimmer.vue` in child app with a `variant` prop: `'skeleton'` (standard `van-skeleton`) and `'clay-pulse'` (Child Clay brand-color pulsing).
2. For `variant="clay-pulse"`: render 3 rounded rectangles using Clay brand colors (`--color-brand-pink`, `--color-brand-ochre`, `--color-brand-teal`) with a `@keyframes clay-pulse` animation (`scale(0.98) → scale(1.0)`, 1.2s ease-in-out infinite). Use CSS classes, never inline styles (dark mode specificity pitfall).
3. For `variant="skeleton"`: delegate to `van-skeleton` with standard timing (300ms).
4. The component receives variant as prop (role detection happens at the call site).
5. Replace `ChildTasksSkeleton` usage in `ChildTasksPage.vue` with `<RoleShimmer variant="clay-pulse" />`.
6. Use `useReducedMotion()` to degrade animation to fade when `prefers-reduced-motion: reduce`.
7. **Main app RoleShimmer deferred** — Owner and Member share the same app, no role-differentiated rendering. Current skeletons stay unchanged.

**Patterns to follow:** `frontend/apps/child/src/assets/clay.css` for Clay brand color tokens; `frontend/apps/main/src/components/dashboard/DashboardSkeleton.vue` for existing skeleton pattern.

**Test scenarios:**
- Renders Clay brand-color pulsing rectangles when `variant="clay-pulse"`
- Renders `van-skeleton` when `variant="skeleton"`
- Animation duration is ≤ 2000ms (per interaction-rules hard cap)
- `prefers-reduced-motion: reduce` degrades to fade (50ms)
- Respects dark mode (Clay dark tokens from `clay.css`)

**Verification:** Component renders correctly in both variants; existing `ChildTasksPage` loading state uses the new component; `pnpm typecheck` and `pnpm test:run` pass in child app.

---

### U2. Celebration Enhancement for Task Completion

**Goal:** Ensure task approval triggers celebration animation ≤ 1500ms, and close the `pollForApproval` gap where approval detection doesn't trigger celebration.

**Requirements:** R3, R4

**Dependencies:** None

**Files:**
- `frontend/apps/child/src/composables/useCelebration.ts` (modify — enhance animation, ensure ≤ 1500ms)
- `frontend/apps/child/src/pages/ChildTasksPage.vue` (modify — fix `pollForApproval` to update `chores` ref on approval)
- `frontend/apps/child/src/components/CelebrationAnimation.vue` (modify — add task-complete variant if needed)
- `frontend/apps/child/src/utils/celebrationState.ts` (modify — no changes needed, localStorage guard already prevents double-celebration)
- `frontend/apps/child/src/components/CelebrationAnimation.test.ts` (modify — add duration test)

**Approach:**
1. **Do NOT add real-time `celebrateTaskComplete()`.** The existing batch/poll model is necessary — approval is fundamentally async (parent approves on separate device, default `auto_approve_hours = 24h`). The `celebrationState.ts` localStorage guard already prevents double-celebration.
2. **Fix the `pollForApproval` gap.** Currently when background polling detects approval, it only calls `checkAutoDraw()` (blind box) but does NOT update the `chores` ref. Fix: when `pollForApproval` detects `status === 'approved'`, update the corresponding chore in `chores.value` — this triggers the existing `watch(chores)` watcher which calls `checkAndTriggerCelebration`. This closes the "child waiting on page" scenario.
3. **Ensure celebration animation ≤ 1500ms.** Review `CelebrationAnimation.vue` total duration. If any sub-animation exceeds 1500ms, cap it.
4. The celebration fires on the existing `watch(chores)` reactive path — no new trigger mechanism needed.

**Patterns to follow:** Existing `CelebrationAnimation.test.ts` for test patterns; `useFlightChoreography.ts` for coin flight integration; `MilestoneCelebration.vue` for duration cap pattern.

**Test scenarios:**
- Task completion triggers celebration animation
- Celebration duration is ≤ 1500ms
- Celebration does not block UI interaction during animation
- `prefers-reduced-motion: reduce` degrades celebration to simple fade
- Celebration fires only once per completion (no double-trigger on re-render)

**Verification:** Completing a task in child app shows celebration; animation completes within 1500ms; existing celebration tests still pass.

---

### U3. Swipe-to-Complete Gesture

**Goal:** Child can complete a task by swiping right on the task item.

**Requirements:** R5, R6

**Dependencies:** U2 (celebration should fire after swipe-complete)

**Files:**
- `frontend/apps/child/src/composables/useSwipeComplete.ts` (new)
- `frontend/apps/child/src/pages/ChildTasksPage.vue` (modify — integrate swipe into existing task card list inline)
- `frontend/apps/child/src/composables/__tests__/useSwipeComplete.spec.ts` (new)

**Approach:**
1. Create `useSwipeComplete` composable:
   - Tracks `touchstart` X position and `touchmove` delta
   - When swipe distance exceeds 60% of item width, show a "complete" indicator (checkmark icon slides in from left)
   - On `touchend` past threshold: trigger completion API call (`POST /child/chores/${instanceId}/complete`) + celebration (from U2)
   - On `touchend` before threshold: spring-back animation using `motionTokens.ts` easing (`cubic-bezier(0.34, 1.56, 0.64, 1)`, 250ms)
   - Touch area must be ≥ 48×48dp per accessibility plan
   - Vertical touch is not captured (only horizontal delta > vertical delta triggers swipe)
2. Integrate into `ChildTasksPage.vue` task list items — the page already has a rich task card layout with `BalanceHero`, date navigation, and pull-refresh.
3. Visual feedback during swipe: background color shifts to `--color-success` as swipe progresses; icon appears at 60%.
4. **Differentiate completion vs pending.** After the API call returns:
   - If `status === 'approved'` (auto-approved): show ✅ checkmark + green flash — "已完成"
   - If `status === 'pending_approval'`: show 🕐 clock icon + amber tint — "已提交，等待确认"
   - The existing button-based completion flow remains as fallback (accessibility). Swipe is an additional shortcut.
5. Prevent double-fire: during swipe animation, disable the completion button. Use an optimistic lock flag (`completingInstanceId`) to prevent both swipe and button from firing simultaneously.

**Patterns to follow:** `WishConstellationCard.vue` for touch event patterns; Clay `--color-success` token for progress color; interaction-rules §3.1 for child animation timing (200ms stagger + micro-bounce).

**Test scenarios:**
- Swipe past 60% threshold triggers completion
- Swipe before threshold springs back
- Touch events don't interfere with scroll (vertical touch is not captured)
- Completion triggers celebration (U2 integration)
- Already-completed tasks cannot be swiped again
- Animation total duration ≤ 2000ms

**Verification:** Swipe gesture completes tasks; vertical scroll is not interrupted; celebration fires after swipe-complete.

---

### U4. Animated Tab Bar

**Goal:** Child tab bar has bouncy animation on tab change.

**Requirements:** R7, R8

**Dependencies:** None

**Files:**
- `frontend/apps/child/src/components/ChildTabBar.vue` (modify — add animation CSS)
- `frontend/apps/child/src/assets/clay.css` (modify — add tab bar animation tokens if needed)

**Approach:**
1. Add CSS transition to `van-tabbar-item` icon container:
   ```css
   .tab-bar-wrapper :deep(.van-tabbar-item) {
     transition: transform 250ms cubic-bezier(0.34, 1.56, 0.64, 1);
   }
   .tab-bar-wrapper :deep(.van-tabbar-item--active) {
     transform: scale(1.1);
   }
   ```
2. Add a subtle "landing" bounce when switching tabs — the new active item scales up from 0.9 to 1.1 then settles at 1.0 (via CSS animation on class add).
3. Ensure the animation respects `prefers-reduced-motion`.
4. Keep the existing route navigation logic unchanged.

**Patterns to follow:** `ChildTabBar.vue` current structure; Clay design system's playful tone from `clay.css`.

**Test scenarios:**
- Active tab has scale animation on selection
- Animation duration ≤ 250ms
- `prefers-reduced-motion: reduce` disables the bounce
- Dark mode: animation works correctly with Clay dark tokens
- Tab route navigation still functions correctly

**Verification:** Visual inspection of tab bar animation; existing tab navigation tests pass.

---

### U5. Member Notification via van-notify

**Goal:** Member sees notification via `van-notify` top bar for relevant events, using passive page-entry checks (no WebSocket).

**Requirements:** R9, R10

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/composables/useMemberNotify.ts` (new)
- `frontend/apps/main/src/pages/FamilyConfigPage.vue` (modify — trigger notify on family config change)
- `frontend/apps/main/src/pages/DashboardPage.vue` (modify — trigger notify on family events)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add notification messages)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — add notification messages)
- `frontend/apps/main/src/composables/__tests__/useMemberNotify.spec.ts` (new)

**Approach:**
1. Create `useMemberNotify` composable wrapping `showNotify` from Vant 4:
   - `notifyConfigChange(message)` — shows notification when family settings have changed
   - `notifyFamilyEvent(type, payload)` — shows notification for member join, deactivation, etc.
   - All notifications: `duration: 3000`, `type: 'primary'` (non-error), auto-dismiss.
2. **Passive check model (no WebSocket).** System is "用完即走" — notifications are triggered by passive checks on page entry.
   - On `onMounted` / `onActivated` of key pages (Dashboard, Family), check for changes via data comparison.
   - For config changes: compare local family settings version with server on page entry. If different, show `notifyConfigChange`.
   - For family events: compare local member list with server on page entry.
3. In `FamilyConfigPage.vue`: after owner saves a family setting, show local `notifyConfigChange("设置已更新")` to confirm the save on the owner's own device.
4. i18n keys: `notify.configChanged`, `notify.memberJoined`, `notify.memberDeactivated`.

**Patterns to follow:** Vant 4 `showNotify` function-call API (auto-imported); existing `showToast` usage patterns in main app.

**Test scenarios:**
- Config change triggers notification with correct message
- Notification auto-dismisses after 3000ms
- Multiple notifications don't stack (latest replaces previous, or queue)
- Non-member roles don't receive member notifications
- i18n keys resolve correctly in both zh-CN and en-US

**Verification:** Changing a family setting as owner triggers notification for members; notification disappears after 3s.

---

### U6. Child Toast Error Differentiation

**Goal:** Child app uses gentle inline error messages instead of `showFailToast`.

**Requirements:** R11, R12

**Dependencies:** None

**Files:**
- `frontend/apps/child/src/components/ChildInlineError.vue` (new)
- `frontend/apps/child/src/pages/ChildTasksPage.vue` (modify — replace `showFailToast` calls)
- `frontend/apps/child/src/pages/ChildWishesPage.vue` (modify — replace `showFailToast` calls)
- `frontend/apps/child/src/pages/ChildHomePage.vue` (modify — replace `showFailToast` calls)
- `frontend/apps/child/src/pages/ChildLedgerPage.vue` (modify — replace `showFailToast` calls)
- `frontend/apps/child/src/pages/ChildBlindBoxPage.vue` (modify — replace `showFailToast` calls)
- `frontend/apps/child/src/pages/ChildWishCreatePage.vue` (modify — replace `showFailToast` calls)
- `frontend/apps/child/src/pages/ChildScenarioPage.vue` (modify — replace `showFailToast` calls)
- `frontend/apps/child/src/pages/ChildWishDetailPage.vue` (modify — replace `showFailToast` calls)
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (modify — add gentle error messages)
- `frontend/apps/child/src/i18n/locales/en-US.ts` (modify — add gentle error messages)
- `frontend/apps/child/src/components/__tests__/ChildInlineError.spec.ts` (new)

**Approach:**
1. Create `ChildInlineError.vue`:
   - Renders a soft card with `--color-surface-soft` background
   - Shows a gentle icon (not Vant's fail icon — use a custom Clay-style icon or emoji-free illustration)
   - Text in `--color-ink` with a温和 tone
   - Auto-dismisses after 3s (like toast) but appears inline, not as overlay
2. Grep all `showFailToast` calls in child app pages and replace with `<ChildInlineError>`.
3. i18n keys: Replace "错误" / "失败" wording with "出了点小问题" / " Oops" equivalents.
4. **Unified placement: slide-down banner across all 8 pages.** Appears at the top of the page content area, slides in from top, auto-dismisses after 3s. Works with `van-pull-refresh` containers.

**Patterns to follow:** `EmptyState.vue` for Clay-styled inline component pattern; `clay.css` for surface tokens.

**Test scenarios:**
- Component renders with gentle styling (no red/fail colors)
- No "错误" or "失败" text appears in child-facing messages
- Auto-dismisses after 3s
- Accessible: has `role="alert"` and `aria-live="polite"`
- Dark mode: uses Clay dark surface tokens

**Verification:** All `showFailToast` calls replaced in child app; error messages use温和 wording; grep for "错误" in child i18n returns 0 results in user-facing strings.

---

### U7. Dialog Classification — Bottom Sheet for Destructive Ops

**Goal:** Owner destructive operations use bottom sheet instead of center dialog.

**Requirements:** R13, R14

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/components/BottomSheetConfirm.vue` (new)
- `frontend/apps/main/src/components/asset/AssetListPanel.vue` (modify — batch delete → BottomSheetConfirm)
- `frontend/apps/main/src/components/liability/LiabilityListPanel.vue` (modify — delete/settle batch → BottomSheetConfirm, 3 call sites)
- `frontend/apps/main/src/components/wishes/WishSavingsLogDialog.vue` (modify — delete savings log → BottomSheetConfirm)
- `frontend/apps/main/src/pages/BabyChoreTemplatesPage.vue` (modify — delete template → BottomSheetConfirm)
- `frontend/apps/main/src/pages/AssetSellPage.vue` (modify — confirm sale → BottomSheetConfirm)
- `frontend/apps/child/src/pages/ChildSettingsPage.vue` (modify — logout confirm stays as center dialog, non-destructive)
- `frontend/apps/main/src/components/__tests__/BottomSheetConfirm.spec.ts` (new)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add impact preview text)

**Approach:**
1. Create `BottomSheetConfirm.vue`:
   - Uses `van-popup` with `position="bottom"` and `round`
   - Animation: 300ms ease-out slide-up (per interaction-rules §2.1)
   - Content: title, description, "影响预览" section (what will be lost), confirm/cancel buttons
   - Confirm button is red (`--color-error`) for destructive operations
2. In main app: replace `showConfirmDialog` calls in 5 destructive files with `BottomSheetConfirm`: AssetListPanel (batch delete), LiabilityListPanel (delete/settle batch ×3), WishSavingsLogDialog (delete savings log), BabyChoreTemplatesPage (delete template), AssetSellPage (confirm sale).
3. **Stay as center dialog (non-destructive):** LogoutPage, SettingsPage (logout confirms), ChangePasswordPage (password change/reset) — these are auth operations, not destructive data operations.
4. **Deferred:** ChallengeList (cancel challenge) — borderline destructive, evaluate separately.
5. In child app: ChildSettingsPage logout confirm stays as center dialog (non-destructive).
6. "影响预览" text: "删除后，该资产的历史估值记录和关联数据将不可恢复。"

**Patterns to follow:** `van-popup` bottom-sheet pattern; existing `showConfirmDialog` usage in `AssetListPanel.vue` and `LiabilityListPanel.vue`.

**Test scenarios:**
- Bottom sheet slides up on delete action (not center dialog)
- "影响预览" section is displayed
- Confirm button triggers deletion; cancel closes sheet
- Animation duration is 300ms
- Child app wish delete uses inline snackbar (not center dialog)
- `prefers-reduced-motion: reduce` degrades to instant show/hide

**Verification:** Deleting an asset shows bottom sheet with impact preview; child wish delete shows inline undo; no `showConfirmDialog` for destructive ops in either app.

---

### U8. Mystery Bonus Consolation

**Goal:** When mystery bonus doesn't trigger, show consolation message.

**Requirements:** R15, R16

**Dependencies:** U2 (consolation appears in the same reward callback as celebration)

**Files:**
- `frontend/apps/child/src/pages/ChildTasksPage.vue` (modify — add consolation logic)
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (modify — add consolation text)
- `frontend/apps/child/src/i18n/locales/en-US.ts` (modify — add consolation text)

**Approach:**
1. In the task completion flow (`ChildTasksPage.vue`), the existing `checkAutoDraw()` function triggers a blind box draw after auto-approval. The integration point is inside `checkAutoDraw()`: after `getLatestAutoDraw()` returns, if `data` is null (no draw triggered), show the consolation toast. For the `pending_approval` path (background polling), the consolation only fires if the child is still on the tasks page when approval arrives — if they've navigated away, skip it.
   - If bonus was triggered: celebration animation plays (U2 handles this)
   - If bonus was NOT triggered: show `showToast({ message: t('reward.consolation'), duration: 2000 })`
2. Consolation text: "下次一定！继续努力" (i18n key: `reward.consolation`). No emoji per `frontend/CLAUDE.md` i18n rule.
3. The toast uses `showToast` (plain, no icon) — not `showFailToast` — to maintain a neutral/encouraging tone.
4. Ensure the consolation doesn't appear when: the task has no reward configured, or when the blind box draw was not attempted (only when `checkAutoDraw` ran but didn't trigger a bonus).
5. The blind box `base_draw_prob` is currently 0.30 — this is the existing trigger probability, not a new 20% mechanism. The "mystery bonus ~20%" from the manifesto maps to this existing probability system.

**Patterns to follow:** Existing blind box draw flow in `ChildTasksPage.vue`; Vant `showToast` for plain text toast.

**Test scenarios:**
- Non-bonus completion shows consolation toast
- Bonus completion does NOT show consolation (only celebration)
- No-reward task completion shows neither celebration nor consolation
- Consolation text is i18n-resolved (not hardcoded)
- Consolation toast auto-dismisses after 2000ms

**Verification:** Task completion without bonus shows "下次一定！" toast; task completion with bonus shows celebration only; no double-messaging.

---

### U9. Owner Impact Description on Config Page

**Goal:** Family config page items show impact descriptions.

**Requirements:** R17

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/pages/FamilyConfigPage.vue` (modify — add impact descriptions)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add impact description text)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — add impact description text)

**Approach:**
1. Add an `impactDescription` computed mapping for each family config setting:
   - AI cache TTL → "影响所有家庭成员的 AI 建议刷新频率"
   - Economy config → "影响孩子的任务奖励和心愿系统"
   - Member permissions → "影响家庭成员可以看到和操作的内容"
2. Render the impact description as a subtle line below each setting label (using `--color-muted` text, smaller font).
3. The descriptions are static text per setting key (not dynamic counts — O6 numeric display is deferred).

**Patterns to follow:** `FamilyConfigPage.vue` existing layout; `--color-muted` for secondary text.

**Test scenarios:**
- Each config setting shows an impact description below its label
- Impact descriptions are i18n-resolved
- Descriptions use `--color-muted` styling
- Dark mode: descriptions remain readable (contrast ≥ 3:1)

**Verification:** Config page shows impact text for each setting; all text is i18n-resolved; no hardcoded Chinese in component.

---

## Verification Contract

| Gate | Command | Scope |
|------|---------|-------|
| Type check (child) | `cd frontend/apps/child && pnpm typecheck` | Child app |
| Type check (main) | `cd frontend/apps/main && pnpm typecheck` | Main app |
| Unit tests (child) | `cd frontend/apps/child && pnpm test:run` | Child app |
| Unit tests (main) | `cd frontend/apps/main && pnpm test:run` | Main app |
| Cross-app consistency | `grep -rn "showFailToast" frontend/apps/child/src/pages/` | Should return 0 results |
| Animation cap | `grep -rnE "(animation|transition).*(\d+(\.\d+)?s|[2-9][0-9]{3,}ms)" frontend/` | Should return 0 results (>2000ms) |
| No center dialog for destructive | `grep -rn "showConfirmDialog" frontend/apps/child/src/` | Should return only ChildSettingsPage logout confirm (legitimate non-destructive) |

---

## Definition of Done

1. All 9 implementation units pass their test scenarios.
2. `pnpm typecheck` passes in both `frontend/apps/main` and `frontend/apps/child`.
3. `pnpm test:run` passes in both apps with no regressions.
4. No `showFailToast` remains in child app pages (replaced by `ChildInlineError`).
5. No `showConfirmDialog` remains in child app for destructive operations (ChildSettingsPage logout confirm is legitimate non-destructive, excluded).
6. All animation durations ≤ 2000ms hard cap.
7. `prefers-reduced-motion: reduce` degrades all new animations to fade.
8. All new user-facing strings are i18n-resolved (no hardcoded Chinese in components).
9. Cross-app semantic tokens don't drift (`--color-success`, `--color-error` mean the same thing in both apps).
10. No abandoned experimental code remains in the diff.
