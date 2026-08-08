<template>
  <div class="family-page">
    <PageHeader :title="t('family.title')" />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <template v-if="familyStore.family">
        <!-- Family Info -->
        <van-cell-group inset class="section">
          <van-cell :title="t('family.familyName')" :value="familyStore.family.custom_title || familyStore.family.name" />
          <van-cell :title="t('family.inviteCode')" :value="familyStore.family.invite_code" is-link @click="copyInviteCode">
            <template #right-icon>
              <van-icon name="description" />
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Adult Members -->
        <div class="section">
          <h2 class="section-heading"><van-icon name="friends-o" /> {{ t('family.memberManagement') }}</h2>
          <div class="member-cards">
            <div v-for="member in adultMembers" :key="member.id" class="child-mgmt-card" :class="{ 'member-disabled': member.is_active === false }">
              <div class="child-mgmt-header">
                <span
                  class="child-avatar"
                  :style="{ background: member.is_active === false ? 'var(--text-tertiary)' : (member.avatar_color || 'var(--color-primary)') }"
                >{{ member.display_name[0] }}</span>
                <span class="child-name">{{ member.display_name }}</span>
                <span v-if="member.username" class="child-username">@{{ member.username }}</span>
                <van-tag v-if="member.is_active === false" type="danger" size="medium" style="margin-left: auto">
                  {{ t('family.disabledTag') }}
                </van-tag>
                <van-tag v-else :type="getRoleTagType(member)" size="medium" style="margin-left: auto">
                  {{ getRoleLabel(member) }}
                </van-tag>
              </div>
              <div v-if="canShowActions(member)" class="child-mgmt-actions">
                <button
                  v-if="canChangeRole(member) && member.role === 'member'"
                  class="action-btn"
                  @click="onPromoteToAdmin(member)"
                >
                  <van-icon name="manager-o" size="18" />
                  <span>{{ t('family.promoteToOwner') }}</span>
                </button>
                <button
                  v-if="canChangeRole(member) && member.role === 'owner'"
                  class="action-btn"
                  @click="onDemoteToMember(member)"
                >
                  <van-icon name="friends-o" size="18" />
                  <span>{{ t('family.demoteToMember') }}</span>
                </button>
                <button
                  v-if="canManage(member)"
                  class="action-btn action-btn--warn"
                  @click="onToggleStatus(member)"
                >
                  <van-icon :name="member.is_active !== false ? 'close' : 'success'" size="18" />
                  <span>{{ member.is_active !== false ? t('family.disableAccount') : t('family.enableAccount') }}</span>
                </button>
                <button
                  v-if="canManage(member)"
                  class="action-btn action-btn--danger"
                  @click="onRemoveMember(member)"
                >
                  <van-icon name="delete-o" size="18" />
                  <span>{{ t('family.removeMember') }}</span>
                </button>
                <button
                  v-if="canManage(member)"
                  class="action-btn action-btn--edit"
                  @click="onResetPassword(member)"
                >
                  <van-icon name="lock" size="18" />
                  <span>{{ t('family.resetPassword') }}</span>
                </button>
              </div>
            </div>
          </div>
          <div class="section-action">
            <van-button
              v-if="isOwner"
              block
              plain
              type="primary"
              size="small"
              :loading="regenerating"
              @click="onRegenerate"
            >
              {{ t('family.regenerateInviteCode') }}
            </van-button>
          </div>
        </div>

        <!-- Children management dashboard (owner only) -->
        <div v-if="isOwner && childMembers.length > 0" class="section">
          <h2 class="section-heading"><van-icon name="manager-o" /> {{ t('family.childManagement') }}</h2>
          <div class="child-cards">
            <div v-for="child in childMembers" :key="child.id" class="child-mgmt-card">
              <div class="child-mgmt-header">
                <span
                  class="child-avatar"
                  :style="{ background: child.avatar_color || '#f5a623' }"
                >{{ child.display_name[0] }}</span>
                <span class="child-name">{{ child.display_name }}</span>
                <span v-if="child.username" class="child-username">@{{ child.username }}</span>
              </div>
              <div class="child-mgmt-stats">
                <div class="stat">
                  <span class="stat-label">{{ t('family.childBalance') }}</span>
                  <span class="stat-value">{{ childBalances[child.id] ?? '…' }} ⭐</span>
                </div>
                <div class="stat">
                  <span class="stat-label">{{ t('family.childWeeklyChores') }}</span>
                  <span class="stat-value">
                    {{ childChoreStats[child.id]?.completed_this_week ?? '…' }}/{{ childChoreStats[child.id]?.total_this_week ?? '…' }}
                  </span>
                </div>
                <div class="stat">
                  <span class="stat-label">{{ t('family.childActiveWishes') }}</span>
                  <span class="stat-value" :class="{ 'has-pending': (childWishCounts[child.id] ?? 0) > 0 }">
                    {{ childWishCounts[child.id] ?? 0 }}
                  </span>
                </div>
                <div class="stat">
                  <span class="stat-label">{{ t('family.childPendingChores') }}</span>
                  <span class="stat-value" :class="{ 'has-pending': (childPendingChores[child.id] ?? 0) > 0 }">
                    {{ pendingStatsLoaded ? (childPendingChores[child.id] ?? 0) : '—' }}
                  </span>
                </div>
                <div class="stat">
                  <span class="stat-label">{{ t('family.childPendingWishes') }}</span>
                  <span class="stat-value" :class="{ 'has-pending': (childPendingWishes[child.id] ?? 0) > 0 }">
                    {{ pendingStatsLoaded ? (childPendingWishes[child.id] ?? 0) : '—' }}
                  </span>
                </div>
              </div>
              <div class="child-mgmt-actions">
                <button class="action-btn action-btn--edit" @click="openEditSheet(child)">
                  <van-icon name="edit" size="18" />
                  <span>{{ t('family.editChildBtn') }}</span>
                </button>
                <button class="action-btn action-btn--danger" @click="onForceLogout(child)">
                  <van-icon name="revoke" size="18" />
                  <span>{{ t('family.forceLogout') }}</span>
                </button>
                <button class="action-btn action-btn--warn" @click="onUnlockPin(child)">
                  <van-icon name="lock" size="18" />
                  <span>{{ t('family.unlockPin') }}</span>
                </button>
                <button class="action-btn" @click="$router.push({ name: 'ChildReset', params: { childId: child.id }, query: { name: child.display_name } })">
                  <van-icon name="edit" size="18" />
                  <span>{{ t('family.resetCredentials') }}</span>
                </button>
              </div>
            </div>
          </div>
          <!-- Add child button -->
          <div class="section-action section-action--spaced">
            <van-button
              v-if="isOwner"
              block
              plain
              type="primary"
              size="small"
              @click="showAddChildSheet = true"
            >{{ t('family.addChild') }}</van-button>
          </div>
        </div>

        <!-- Add child sheet (also shown when no children yet) -->
        <div v-if="isOwner && childMembers.length === 0" class="section">
          <div class="section-action">
            <van-button
              block
              plain
              type="primary"
              size="small"
              @click="showAddChildSheet = true"
            >{{ t('family.addChild') }}</van-button>
          </div>
        </div>

        <!-- Edit child info bottom sheet -->
        <van-popup v-model:show="editSheetVisible" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">{{ t('family.editChildTitle') }}</p>
          <van-field
            v-model="editForm.display_name"
            :label="t('family.editChildName')"
            :placeholder="t('family.editChildNamePlaceholder')"
            maxlength="20"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <p class="sheet-label">{{ t('family.editChildColor') }}</p>
          <div class="color-swatch-picker">
            <button
              v-for="color in AVATAR_COLORS"
              :key="color"
              class="color-swatch"
              :class="{ selected: editForm.avatar_color === color }"
              :style="{ background: color }"
              @click="editForm.avatar_color = color"
            />
          </div>
          <p class="sheet-label">{{ t('family.editChildBirthday') }}</p>
          <van-date-picker
            v-model="editBirthdayParts"
            :min-date="new Date(2000, 0, 1)"
            :max-date="new Date()"
            style="margin-top: 4px"
          />
          <van-cell :title="t('family.editChildLunar')" style="padding: 8px 0">
            <template #right-icon>
              <van-switch v-model="editForm.birthday_is_lunar" size="20" />
            </template>
          </van-cell>
          <van-button
            block
            type="primary"
            :loading="editSubmitting"
            style="margin-top: 16px; border-radius: 12px"
            @click="submitEdit"
          >{{ t('family.editChildSave') }}</van-button>
        </van-popup>

        <!-- Add child bottom sheet -->
        <van-popup v-model:show="showAddChildSheet" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">{{ t('family.addChildTitle') }}</p>
          <van-field v-model="newChild.display_name" :label="t('family.childNickname')" :placeholder="t('family.childNicknamePlaceholder')" style="margin-top: 8px" />
          <van-field v-model="newChild.username" :label="t('family.childUsername')" :placeholder="t('family.childUsernamePlaceholder')" style="margin-top: 8px" />
          <van-field v-model="newChild.password" type="password" :label="t('family.childPassword')" :placeholder="t('family.childPasswordPlaceholder')" style="margin-top: 8px" />
          <p class="sheet-label">{{ t('family.selectPinEmojis') }}</p>
          <div class="emoji-picker">
            <button
              v-for="emoji in CHILD_EMOJIS"
              :key="emoji"
              class="emoji-pick-btn"
              :class="{ selected: newChild.pin.includes(emoji) }"
              :disabled="newChild.pin.length >= 4 && !newChild.pin.includes(emoji)"
              @click="togglePinEmoji(emoji)"
            >{{ emoji }}</button>
          </div>
          <p class="pin-preview">{{ newChild.pin.length ? t('family.pinSelected', { emojis: newChild.pin.join(' ') }) : t('family.pinSelectedEmpty') }}</p>
          <van-button
            block
            type="primary"
            :loading="addingChild"
            :disabled="!newChild.display_name || !newChild.username || !newChild.password || newChild.pin.length !== 4"
            style="margin-top: 16px; border-radius: 12px"
            @click="doAddChild"
          >{{ t('family.createAccount') }}</van-button>
        </van-popup>

        <!-- Reset member password bottom sheet -->
        <van-popup v-model:show="resetPwdVisible" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">{{ t('family.resetPasswordTitle3', { name: resetPwdTarget?.display_name ?? '' }) }}</p>
          <van-field
            v-model="resetPwdForm.password"
            type="password"
            :label="t('family.newPasswordLabel')"
            :placeholder="t('family.newPasswordPlaceholder')"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <van-field
            v-model="resetPwdForm.confirm"
            type="password"
            :label="t('family.confirmNewPassword')"
            :placeholder="t('family.confirmNewPasswordPlaceholder')"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <van-button
            block
            type="primary"
            :loading="resetPwdSubmitting"
            :disabled="!resetPwdForm.password || resetPwdForm.password.length < 8"
            style="margin-top: 16px; border-radius: 12px"
            @click="submitResetPassword"
          >{{ t('family.confirmResetPassword') }}</van-button>
        </van-popup>


      </template>

      </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Family' })
import { ref, computed, onMounted, onActivated } from 'vue'
import { showToast, showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import { getAllChildBalances, getChildrenChoreStats, updateMemberInfo, resetMemberPassword, updateMemberStatus, type ChoreStats } from '@/api/family'
import { getPendingApprovals } from '@/api/chores'
import { listParentChildWishes } from '@/api/childWishes'
import { createChild, forceLogoutChild, unlockChildPin } from '@/api/children'
import { usePageLoading } from '@/composables/usePageLoading'
import { useMemberNotify } from '@/composables/useMemberNotify'
import { copyToClipboard } from '@/utils/ai-chat/tableUtils'

const { t } = useI18n()

const familyStore = useFamilyStore()
const authStore = useAuthStore()
const { increment, decrement } = usePageLoading()
const { notifyFamilyEvent, markFamilySnapshot } = useMemberNotify()
// Skip first onActivated — Vue 3 fires both onMounted and onActivated on first
// mount inside <KeepAlive>; onMounted handles initial load.
let hasActivated = false
const refreshing = ref(false)

// Child dashboard data
const childBalances = ref<Record<string, number>>({})
const childChoreStats = ref<Record<string, ChoreStats>>({})
const childWishCounts = ref<Record<string, number>>({})
const childPendingChores = ref<Record<string, number>>({})
const childPendingWishes = ref<Record<string, number>>({})
// False until the pending-chore/pending-wish fetches have run; used to
// show a `—` placeholder instead of a misleading 0 during load.
const pendingStatsLoaded = ref(false)

const AVATAR_COLORS = ['#4F46E5', '#7C3AED', '#DB2777', '#D97706', '#059669', '#0284C7']

// Edit child info sheet state
const editSheetVisible = ref(false)
const editTargetChild = ref<{ id: string; display_name: string } | null>(null)
const editForm = ref({
  display_name: '',
  avatar_color: '#4F46E5',
  birthday_is_lunar: false,
})
const editBirthdayParts = ref<string[]>([])
const editSubmitting = ref(false)
const isOwner = computed(() => authStore.user?.role === 'owner')
const isCurrentUserRoot = computed(() =>
  authStore.user?.id === familyStore.family?.created_by,
)
const isCurrentUserAdmin = computed(() =>
  authStore.user?.role === 'owner' && !isCurrentUserRoot.value,
)
const childMembers = computed(() =>
  familyStore.members.filter(m => m.role === 'child'),
)
const adultMembers = computed(() =>
  familyStore.members.filter(m => m.role !== 'child'),
)
const currentUserId = computed(() => authStore.user?.id)
const regenerating = ref(false)

function canManage(member: { id: string; role: string }): boolean {
  if (member.id === currentUserId.value) return false
  if (member.id === familyStore.family?.created_by) return false
  if (isCurrentUserRoot.value) return true
  if (isCurrentUserAdmin.value && member.role === 'member') return true
  return false
}

function canChangeRole(member: { id: string; role: string }): boolean {
  return isCurrentUserRoot.value && member.id !== familyStore.family?.created_by
}

function canShowActions(member: { id: string; role: string }): boolean {
  return canManage(member) || canChangeRole(member)
}

function getRoleTagType(member: { id: string; role: string }): 'default' | 'primary' | 'success' | 'warning' | 'danger' {
  if (member.id === familyStore.family?.created_by) return 'primary'
  if (member.role === 'owner') return 'success'
  return 'default'
}

function getRoleLabel(member: { id: string; role: string }): string {
  if (member.id === familyStore.family?.created_by) return t('family.rootOwner')
  if (member.role === 'owner') return t('family.owner')
  return t('family.member')
}

const CHILD_EMOJIS = ['🐱', '🐶', '🐸', '🦊', '🐼', '🐨', '🦁', '🐯', '🌟', '🌈', '🍎', '🎈']

// Add child sheet
const showAddChildSheet = ref(false)
const addingChild = ref(false)
const newChild = ref({ display_name: '', username: '', password: '', pin: [] as string[] })

// Reset password sheet
const resetPwdVisible = ref(false)
const resetPwdTarget = ref<{ id: string; display_name: string } | null>(null)
const resetPwdForm = ref({ password: '', confirm: '' })
const resetPwdSubmitting = ref(false)


async function copyInviteCode() {
  const code = familyStore.family?.invite_code
  if (code) {
    const ok = await copyToClipboard(code)
    if (ok) {
      showSuccessToast(t('family.inviteCodeCopied'))
    } else {
      showSuccessToast(t('toast.newInviteCode', { code }))
    }
  }
}

async function loadChildDashboard() {
  if (!isOwner.value || childMembers.value.length === 0) return

  // Load all child balances in a single batch request (avoids N+1)
  try {
    const res = await getAllChildBalances()
    childBalances.value = res.data
  } catch { /* non-critical */ }

  // Load weekly chore completion stats per child
  try {
    const res = await getChildrenChoreStats()
    childChoreStats.value = res.data
  } catch { /* non-critical */ }

  // Load pending chore approvals — compute per-child counts
  try {
    const choreApprovals = await getPendingApprovals()
    const choreCounts: Record<string, number> = {}
    for (const item of choreApprovals) {
      if (!item.child_user_id) continue
      choreCounts[item.child_user_id] = (choreCounts[item.child_user_id] ?? 0) + 1
    }
    childPendingChores.value = choreCounts
  } catch { /* non-critical */ }

  // Load wishes — compute per-child active wish counts and pending wish counts
  try {
    const wishes = await listParentChildWishes()
    const activeCounts: Record<string, number> = {}
    const pendingCounts: Record<string, number> = {}
    for (const w of wishes) {
      if (['pending_review', 'active', 'redemption_requested'].includes(w.status)) {
        activeCounts[w.child_user_id] = (activeCounts[w.child_user_id] ?? 0) + 1
      }
      if (w.status === 'pending_review' || w.status === 'redemption_requested') {
        pendingCounts[w.child_user_id] = (pendingCounts[w.child_user_id] ?? 0) + 1
      }
    }
    childWishCounts.value = activeCounts
    childPendingWishes.value = pendingCounts
  } catch { /* non-critical */ }

  pendingStatsLoaded.value = true
}

async function onPromoteToAdmin(member: { id: string; display_name: string }) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('family.confirmPromoteAdmin', { name: member.display_name }) })
  } catch { return }
  try {
    await familyStore.updateMemberRole(member.id, 'owner')
    showSuccessToast(t('family.memberPromoted'))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  }
}

async function onDemoteToMember(member: { id: string; display_name: string }) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('family.confirmDemoteMember', { name: member.display_name }) })
  } catch { return }
  try {
    await familyStore.updateMemberRole(member.id, 'member')
    showSuccessToast(t('family.memberDemoted'))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  }
}

async function onToggleStatus(member: { id: string; display_name: string; is_active?: boolean }) {
  const willDisable = member.is_active !== false
  const msg = willDisable
    ? t('family.confirmDisableAccount', { name: member.display_name })
    : t('family.confirmEnableAccount', { name: member.display_name })
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: msg })
  } catch { return }
  try {
    await updateMemberStatus(member.id, !willDisable)
    showSuccessToast(willDisable ? t('family.memberDisabled') : t('family.memberEnabled'))
    await familyStore.fetchFamily()
    if (willDisable) {
      notifyFamilyEvent('memberDeactivated', { name: member.display_name })
    }
    markFamilySnapshot()
  } catch {
    showFailToast(t('toast.operationFailed2'))
  }
}

async function onRemoveMember(member: { id: string; display_name: string }) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('family.confirmRemoveMember2', { name: member.display_name }) })
  } catch { return }
  try {
    await familyStore.removeMember(member.id)
    showSuccessToast(t('toast.memberRemoved'))
    markFamilySnapshot()
  } catch {
    showFailToast(t('toast.operationFailed2'))
  }
}

async function onResetPassword(member: { id: string; display_name: string }) {
  resetPwdTarget.value = member
  resetPwdForm.value = { password: '', confirm: '' }
  resetPwdVisible.value = true
}

async function submitResetPassword() {
  if (!resetPwdTarget.value) return
  if (resetPwdForm.value.password.length < 8) {
    showToast(t('family.newPasswordPlaceholder'))
    return
  }
  if (resetPwdForm.value.password !== resetPwdForm.value.confirm) {
    showToast(t('family.passwordMismatch'))
    return
  }
  resetPwdSubmitting.value = true
  try {
    await resetMemberPassword(resetPwdTarget.value.id, resetPwdForm.value.password)
    showSuccessToast(t('family.memberPasswordReset'))
    resetPwdVisible.value = false
  } catch {
    showFailToast(t('toast.operationFailed2'))
  } finally {
    resetPwdSubmitting.value = false
  }
}

async function onRegenerate() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmRegenerateCode') })
  } catch { return }
  regenerating.value = true
  try {
    const code = await familyStore.regenerateInviteCode()
    showToast(t('toast.newInviteCode', { code }))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  } finally {
    regenerating.value = false
  }
}

function openEditSheet(child: { id: string; display_name: string; avatar_color?: string; birthday?: string | null; birthday_is_lunar?: boolean }) {
  editTargetChild.value = child
  editForm.value.display_name = child.display_name
  editForm.value.avatar_color = child.avatar_color || '#4F46E5'
  editForm.value.birthday_is_lunar = child.birthday_is_lunar ?? false
  if (child.birthday) {
    const parts = child.birthday.split('-')
    editBirthdayParts.value = parts
  } else {
    const today = new Date()
    editBirthdayParts.value = [
      String(today.getFullYear()),
      String(today.getMonth() + 1).padStart(2, '0'),
      String(today.getDate()).padStart(2, '0'),
    ]
  }
  editSheetVisible.value = true
}

async function submitEdit() {
  if (!editTargetChild.value) return
  editSubmitting.value = true
  try {
    const [year, month, day] = editBirthdayParts.value
    await updateMemberInfo(editTargetChild.value.id, {
      display_name: editForm.value.display_name,
      avatar_color: editForm.value.avatar_color,
      birthday: `${year}-${month}-${day}`,
      birthday_is_lunar: editForm.value.birthday_is_lunar,
    })
    showSuccessToast(t('family.editChildSaved'))
    editSheetVisible.value = false
    await familyStore.fetchMembers()
  } catch {
    showFailToast(t('family.editChildFailed'))
  } finally {
    editSubmitting.value = false
  }
}

async function onRefresh() {
  await familyStore.fetchFamily()
  await loadChildDashboard()
  refreshing.value = false
}

function togglePinEmoji(emoji: string) {
  const idx = newChild.value.pin.indexOf(emoji)
  if (idx >= 0) {
    newChild.value.pin.splice(idx, 1)
  } else if (newChild.value.pin.length < 4) {
    newChild.value.pin.push(emoji)
  }
}

async function doAddChild() {
  addingChild.value = true
  try {
    await createChild({
      display_name: newChild.value.display_name,
      username: newChild.value.username,
      password: newChild.value.password,
      pin: [...newChild.value.pin],
    })
    showSuccessToast(t('toast.addSuccess'))
    showAddChildSheet.value = false
    newChild.value = { display_name: '', username: '', password: '', pin: [] }
    await familyStore.fetchFamily()
  } catch (err: unknown) {
    const code = (err as { response?: { data?: { code?: string } } }).response?.data?.code
    const i18nKey = code ? `errors.${code}` : ''
    showFailToast(i18nKey && t(i18nKey) !== i18nKey ? t(i18nKey) : t('toast.operationFailed2'))
  } finally {
    addingChild.value = false
  }
}

async function onForceLogout(child: { id: string; display_name: string }) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmForceLogout', { name: child.display_name }) })
  } catch { return }
  try {
    await forceLogoutChild(child.id)
    showSuccessToast(t('toast.childForceLoggedOut'))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  }
}

async function onUnlockPin(child: { id: string; display_name: string }) {
  try {
    await unlockChildPin(child.id)
    showSuccessToast(t('toast.childPinUnlocked'))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  }
}

onMounted(async () => {
  increment()
  try {
    await familyStore.fetchFamily()
    if (isOwner.value) {
      await loadChildDashboard()
    }
  } finally {
    decrement()
  }
})

// KeepAlive 缓存页面：返回时触发 onActivated 而非 onMounted
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  increment()
  try {
    await familyStore.fetchFamily()
    if (isOwner.value) {
      await loadChildDashboard()
    }
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.family-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
.section {
  margin-top: 12px;
}

.section-heading {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 16px 12px;
}

.child-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 16px;
}

.child-mgmt-card {
  background: var(--bg-primary);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.child-mgmt-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.child-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  color: #fff;
}

.child-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.child-username {
  font-size: 12px;
  color: var(--text-tertiary);
  font-weight: 400;
}

.child-mgmt-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-value.has-pending {
  color: #f5a623;
}

.child-mgmt-actions {
  display: flex;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  margin: 12px -16px -16px;
  border-radius: 0 0 12px 12px;
  overflow: hidden;
}

[data-theme='dark'] .child-mgmt-actions {
  border-color: rgba(255, 255, 255, 0.08);
}

.action-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 10px 4px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}

.action-btn + .action-btn::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  height: 60%;
  width: 1px;
  background: rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .action-btn + .action-btn::before {
  background: rgba(255, 255, 255, 0.08);
}

.action-btn:active {
  background: rgba(0, 0, 0, 0.04);
}

.action-btn--edit {
  color: #4F46E5;
}


.member-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 16px;
}

.member-disabled {
  opacity: 0.55;
}

.section-action {
  padding: 12px 16px 0;
}

.section-action--spaced {
  margin-top: 12px;
}

.sheet-title {
  font-size: 17px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px;
  text-align: center;
}

.action-btn--danger {
  color: #ee0a24;
}

.action-btn--warn {
  color: #ff976a;
}

.sheet-label {
  font-size: 14px;
  color: #666;
  margin: 12px 0 8px;
}

.emoji-picker {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin-bottom: 8px;
}

.emoji-pick-btn {
  font-size: 24px;
  padding: 6px;
  border: 2px solid transparent;
  border-radius: 8px;
  background: #f5f5f5;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.emoji-pick-btn.selected {
  border-color: var(--color-primary);
  background: var(--color-soft-stone);
}

.emoji-pick-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.pin-preview {
  font-size: 20px;
  text-align: center;
  margin: 4px 0 0;
  letter-spacing: 4px;
}


.color-swatch-picker {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.color-swatch {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 3px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}

.color-swatch.selected {
  border-color: #333;
  transform: scale(1.15);
}

</style>
