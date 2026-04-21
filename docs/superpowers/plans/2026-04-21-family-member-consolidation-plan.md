# Family Member Management Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate FamilyPage and MemberManagePage into a single unified page at `/family`, move coin rate settings to SettingsPage, and delete MemberManagePage.

**Architecture:** Refactor FamilyPage.vue as the base — it already owns all child management logic. Merge adult member swipe actions (remove, set owner, regenerate invite code) from MemberManagePage directly into FamilyPage. Split the member list into two sections: adult members and child members. Move coin rate settings to SettingsPage. No new components, no backend changes.

**Tech Stack:** Vue 3 + TypeScript, Vant 4 (van-swipe-cell, van-cell-group, van-button), Pinia (useFamilyStore, useAuthStore), Vue Router

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `frontend/src/pages/FamilyPage.vue` | Modify | Add adult swipe actions + regenerate button; split members into adult/child sections; remove coin rate fields |
| `frontend/src/pages/SettingsPage.vue` | Modify | Add coin rate settings section (owner only) |
| `frontend/src/router/index.ts` | Modify | Remove `/family/members` route |
| `frontend/src/pages/MemberManagePage.vue` | Delete | Replaced by consolidated FamilyPage |

---

## Task 1: Add adult member swipe actions to FamilyPage

**Files:**
- Modify: `frontend/src/pages/FamilyPage.vue`

Replace the existing adult member display (the `van-cell-group` with `MemberCard`) with a `van-swipe-cell` list that includes set-owner and remove actions. Also add the regenerate invite code button and the `onSetOwner` / `onRemove` / `onRegenerate` functions from MemberManagePage.

- [ ] **Step 1: Replace the members section template**

In `FamilyPage.vue`, find the `<!-- Members -->` section (lines 22–31) and replace it with:

```html
<!-- Adult Members -->
<van-cell-group inset title="家庭成员" class="section">
  <van-swipe-cell v-for="member in adultMembers" :key="member.id">
    <van-cell :title="member.display_name" :label="'@' + member.username">
      <template #icon>
        <div class="avatar" :style="{ background: member.avatar_color || '#1989fa' }">
          {{ member.display_name.charAt(0) }}
        </div>
      </template>
      <template #value>
        <van-tag :type="member.role === 'owner' ? 'primary' : 'default'" size="medium">
          {{ member.role === 'owner' ? '管理员' : '成员' }}
        </van-tag>
      </template>
    </van-cell>
    <template v-if="isOwner" #right>
      <van-button
        v-if="member.id !== currentUserId && member.role !== 'owner'"
        square
        type="primary"
        text="设为管理员"
        class="swipe-btn"
        @click="onSetOwner(member.id)"
      />
      <van-button
        v-if="member.id !== currentUserId"
        square
        type="danger"
        text="移除"
        class="swipe-btn"
        @click="onRemoveMember(member)"
      />
    </template>
  </van-swipe-cell>
  <van-cell v-if="isOwner">
    <template #title>
      <van-button
        block
        plain
        type="primary"
        size="small"
        :loading="regenerating"
        @click="onRegenerate"
      >
        重新生成邀请码
      </van-button>
    </template>
  </van-cell>
</van-cell-group>
```

- [ ] **Step 2: Add computed `adultMembers` and `currentUserId`**

In the `<script setup>` section, add after the existing `childMembers` computed:

```ts
const adultMembers = computed(() =>
  familyStore.members.filter(m => m.role !== 'child'),
)
const currentUserId = computed(() => authStore.user?.id)
const regenerating = ref(false)
```

- [ ] **Step 3: Add `onSetOwner`, `onRemoveMember`, `onRegenerate` functions**

Add after the existing `openGrantSheet` function:

```ts
async function onSetOwner(userId: string) {
  try {
    await showConfirmDialog({ title: '确认', message: '确定要将该成员设为管理员吗？' })
    await familyStore.updateMemberRole(userId, 'owner')
    showToast('已设为管理员')
  } catch {
    // cancelled
  }
}

async function onRemoveMember(member: { id: string; display_name: string }) {
  try {
    await showConfirmDialog({ title: '确认移除', message: `确定要移除「${member.display_name}」吗？` })
    await familyStore.removeMember(member.id)
    showToast('已移除')
  } catch {
    // cancelled
  }
}

async function onRegenerate() {
  try {
    await showConfirmDialog({ title: '确认', message: '重新生成邀请码后，旧邀请码将失效' })
    regenerating.value = true
    const code = await familyStore.regenerateInviteCode()
    showToast(`新邀请码: ${code}`)
  } catch {
    // cancelled
  } finally {
    regenerating.value = false
  }
}
```

- [ ] **Step 4: Add `showConfirmDialog` to imports**

Find the existing import line:
```ts
import { showToast } from 'vant'
```
Replace with:
```ts
import { showToast, showConfirmDialog } from 'vant'
```

- [ ] **Step 5: Add avatar and swipe-btn styles**

In the `<style scoped>` section, add:

```css
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  margin-right: 10px;
}
.swipe-btn {
  height: 100%;
}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend && npx vue-tsc -b --noEmit
```
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/FamilyPage.vue
git commit -m "feat(family): add adult member swipe actions and regenerate invite code to FamilyPage"
```

---

## Task 2: Remove coin rate settings from FamilyPage

**Files:**
- Modify: `frontend/src/pages/FamilyPage.vue`

- [ ] **Step 1: Remove the coin tier settings section from template**

Find and delete the entire `<!-- Coin tier settings (owner only) -->` block (the `van-cell-group` with `v-if="isOwner"` containing the two `van-field` elements and save button, roughly lines 35–57 in the original file).

- [ ] **Step 2: Remove coin-related script refs and functions**

Remove these lines from `<script setup>`:

```ts
const copperToSilverStr = ref(String(familyStore.coinCopperToSilver))
const silverToGoldStr = ref(String(familyStore.coinSilverToGold))
const savingRates = ref(false)
```

And remove the `validateRate` and `saveCoinRates` functions entirely.

- [ ] **Step 3: Remove coin config sync from `onMounted`**

In `onMounted`, remove these two lines:
```ts
copperToSilverStr.value = String(familyStore.coinCopperToSilver)
silverToGoldStr.value = String(familyStore.coinSilverToGold)
```

The `onMounted` block should now look like:
```ts
onMounted(async () => {
  await familyStore.fetchFamily()
  if (isOwner.value) {
    await loadChildDashboard()
  }
})
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx vue-tsc -b --noEmit
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/FamilyPage.vue
git commit -m "refactor(family): remove coin rate settings from FamilyPage"
```

---

## Task 3: Add coin rate settings to SettingsPage

**Files:**
- Modify: `frontend/src/pages/SettingsPage.vue`

- [ ] **Step 1: Add coin rate section to template**

In `SettingsPage.vue`, find the "家庭管理" section:
```html
<van-cell-group
  v-if="authStore.user?.role === 'owner' || authStore.user?.role === 'member'"
  inset
  title="家庭管理"
  class="section"
>
  <van-cell title="家庭成员管理" icon="friends-o" is-link to="/family" />
</van-cell-group>
```

Insert the following block **after** it (before the `账户信息` section):

```html
<!-- Coin rate settings (owner only) -->
<van-cell-group v-if="authStore.user?.role === 'owner'" inset title="⭐ 星星币兑换比例" class="section">
  <van-field
    v-model="copperToSilverStr"
    label="铜→银"
    type="digit"
    placeholder="默认 10"
  />
  <van-field
    v-model="silverToGoldStr"
    label="银→金"
    type="digit"
    placeholder="默认 10"
  />
  <van-cell>
    <template #title>
      <van-button size="small" type="primary" :loading="savingRates" @click="saveCoinRates">
        保存
      </van-button>
    </template>
  </van-cell>
</van-cell-group>
```

- [ ] **Step 2: Add coin rate script logic**

In `SettingsPage.vue` `<script setup>`, add the following imports and refs. First, add `updateFamilySettings` to the family API import — find:
```ts
import { useFamilyStore } from '@/stores/family'
```
Replace with:
```ts
import { useFamilyStore } from '@/stores/family'
import { updateFamilySettings } from '@/api/family'
```

Then add these refs and functions after the existing `showTitleDialog` ref block:

```ts
const copperToSilverStr = ref(String(familyStore.coinCopperToSilver))
const silverToGoldStr = ref(String(familyStore.coinSilverToGold))
const savingRates = ref(false)

async function saveCoinRates() {
  const c2s = parseInt(copperToSilverStr.value)
  const s2g = parseInt(silverToGoldStr.value)
  if (isNaN(c2s) || c2s < 1 || c2s > 100 || isNaN(s2g) || s2g < 1 || s2g > 100) {
    showToast('请输入 1-100 的整数')
    return
  }
  savingRates.value = true
  try {
    await updateFamilySettings({ coinCopperToSilver: c2s, coinSilverToGold: s2g })
    familyStore.coinCopperToSilver = c2s
    familyStore.coinSilverToGold = s2g
    showToast('已保存')
  } catch {
    showToast('保存失败')
  } finally {
    savingRates.value = false
  }
}
```

- [ ] **Step 3: Sync coin refs when store loads**

In `onMounted`, add after `authStore.fetchMe()`:
```ts
if (!familyStore.family) {
  await familyStore.fetchFamily()
}
// Sync coin rate refs from store (loaded by App.vue on mount for adult users)
copperToSilverStr.value = String(familyStore.coinCopperToSilver)
silverToGoldStr.value = String(familyStore.coinSilverToGold)
```

The full `onMounted` should be:
```ts
onMounted(async () => {
  if (!familyStore.family) {
    familyStore.fetchFamily()
  }
  await authStore.fetchMe()
  copperToSilverStr.value = String(familyStore.coinCopperToSilver)
  silverToGoldStr.value = String(familyStore.coinSilverToGold)
  // Initialize theme color from localStorage
  const savedColor = localStorage.getItem('theme-primary')
  if (savedColor) {
    document.documentElement.style.setProperty('--theme-primary', savedColor)
    document.documentElement.style.setProperty('--van-primary-color', savedColor)
  }
})
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx vue-tsc -b --noEmit
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SettingsPage.vue
git commit -m "feat(settings): add coin rate settings section for owner"
```

---

## Task 4: Remove `/family/members` route and delete MemberManagePage

**Files:**
- Modify: `frontend/src/router/index.ts`
- Delete: `frontend/src/pages/MemberManagePage.vue`

- [ ] **Step 1: Remove the route from router**

In `frontend/src/router/index.ts`, find and delete this route entry:
```ts
{
  path: 'family/members',
  name: 'MemberManage',
  component: () => import('@/pages/MemberManagePage.vue')
},
```

- [ ] **Step 2: Delete MemberManagePage.vue**

```bash
rm frontend/src/pages/MemberManagePage.vue
```

- [ ] **Step 3: Verify TypeScript compiles and build succeeds**

```bash
cd frontend && npx vue-tsc -b --noEmit
```
Expected: no errors (no references to MemberManagePage remain)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.ts
git rm frontend/src/pages/MemberManagePage.vue
git commit -m "refactor(router): remove /family/members route and delete MemberManagePage"
```

---

## Task 5: Final build verification

**Files:** none (verification only)

- [ ] **Step 1: Run full production build**

```bash
cd frontend && npm run build
```
Expected: build completes with no TypeScript errors and no missing module errors

- [ ] **Step 2: Manual smoke test checklist**

With the app running (`docker-compose up -d` or `npm run dev` + `uvicorn`):

1. Login as **owner** → navigate to `/family`
   - ✓ Family name and invite code visible
   - ✓ Adult members listed with swipe actions (set owner, remove)
   - ✓ "重新生成邀请码" button visible
   - ✓ Child members section visible (if any children exist)
   - ✓ Child stats (balance, chores, wishes) load correctly
   - ✓ Child action buttons work (grant coins, switch view, approve)
   - ✓ Coin rate settings **not** on this page

2. Login as **owner** → navigate to `/settings`
   - ✓ "⭐ 星星币兑换比例" section visible
   - ✓ Save button updates rates correctly

3. Login as **member** → navigate to `/family`
   - ✓ Adult members visible, no swipe actions
   - ✓ No child section
   - ✓ No regenerate invite code button

4. Navigate to `/family/members`
   - ✓ Route no longer exists (redirects or 404)

- [ ] **Step 3: Commit if any last fixes needed, otherwise done**

```bash
git add -A
git commit -m "fix: post-consolidation cleanup"
```
