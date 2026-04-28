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

        <!-- Children management dashboard (owner only) -->
        <div v-if="isOwner && childMembers.length > 0" class="section">
          <p class="section-heading">👧 孩子管理</p>
          <div class="child-cards">
            <div v-for="child in childMembers" :key="child.id" class="child-mgmt-card">
              <div class="child-mgmt-header">
                <span
                  class="child-avatar"
                  :style="{ background: child.avatar_color || '#f5a623' }"
                >{{ child.display_name[0] }}</span>
                <span class="child-name">{{ child.display_name }}</span>
              </div>
              <div class="child-mgmt-stats">
                <div class="stat">
                  <span class="stat-label">余额</span>
                  <span class="stat-value">{{ childBalances[child.id] ?? '…' }} ⭐</span>
                </div>
                <div class="stat">
                  <span class="stat-label">本周家务</span>
                  <span class="stat-value">
                    {{ childChoreStats[child.id]?.completed_this_week ?? '…' }}/{{ childChoreStats[child.id]?.total_this_week ?? '…' }}
                  </span>
                </div>
                <div class="stat">
                  <span class="stat-label">进行中心愿</span>
                  <span class="stat-value" :class="{ 'has-pending': (childWishCounts[child.id] ?? 0) > 0 }">
                    {{ childWishCounts[child.id] ?? 0 }}
                  </span>
                </div>
                <div class="stat">
                  <span class="stat-label">待审家务</span>
                  <span class="stat-value" :class="{ 'has-pending': totalPendingChores > 0 }">
                    {{ totalPendingChores }}
                  </span>
                </div>
                <div class="stat">
                  <span class="stat-label">待审心愿</span>
                  <span class="stat-value" :class="{ 'has-pending': totalPendingWishes > 0 }">
                    {{ totalPendingWishes }}
                  </span>
                </div>
              </div>
              <div class="child-mgmt-actions">
                <button class="action-btn" @click="$router.push('/family/chore-approvals')">
                  <van-icon name="todo-list-o" size="18" />
                  <span>审批家务</span>
                </button>
                <button class="action-btn" @click="$router.push('/family/wish-review')">
                  <van-icon name="gift-o" size="18" />
                  <span>审批心愿</span>
                </button>
                <button class="action-btn action-btn--star" @click="openGrantSheet(child)">
                  <van-icon name="star-o" size="18" />
                  <span>赠送星星</span>
                </button>
                <button class="action-btn action-btn--switch" @click="switchToChildView(child)">
                  <van-icon name="exchange" size="18" />
                  <span>切换视角</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Manual coin grant bottom sheet -->
        <van-popup v-model:show="showGrantSheet" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">⭐ 赠送星星币给 {{ grantTargetChild?.display_name }}</p>
          <van-field
            v-model="grantAmountStr"
            type="digit"
            label="数量"
            placeholder="输入星星币数量"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <van-field
            v-model="grantReason"
            label="原因"
            placeholder="例：今天表现很棒！"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <van-button
            block
            type="primary"
            :disabled="!grantAmountStr || parseInt(grantAmountStr) <= 0"
            :loading="grantingCoins"
            style="margin-top: 16px; border-radius: 12px; background: #f5a623; border: none"
            @click="doGrant"
          >确认赠送</van-button>
        </van-popup>
      </template>

      <van-loading v-else class="page-loading" />
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import { getAllChildBalances, getChildrenChoreStats, type ChoreStats } from '@/api/family'
import { grantCoins } from '@/api/coins'
import { getPendingApprovals } from '@/api/chores'
import { listParentChildWishes } from '@/api/childWishes'
import { adminSwitchToChild } from '@/api/auth'
import { setUser, clearAuth } from '@/utils/storage'
import type { ChildUser } from '@/types'

const { t } = useI18n()

const familyStore = useFamilyStore()
const authStore = useAuthStore()
const refreshing = ref(false)

// Child dashboard data
const childBalances = ref<Record<string, number>>({})
const childChoreStats = ref<Record<string, ChoreStats>>({})
const childWishCounts = ref<Record<string, number>>({})
const totalPendingChores = ref(0)
const totalPendingWishes = ref(0)

// Manual grant sheet state
const showGrantSheet = ref(false)
const grantTargetChild = ref<{ id: string; display_name: string } | null>(null)
const grantAmountStr = ref('')
const grantReason = ref('')
const grantingCoins = ref(false)
const isOwner = computed(() => authStore.user?.role === 'owner')
const childMembers = computed(() =>
  familyStore.members.filter(m => m.role === 'child'),
)
const adultMembers = computed(() =>
  familyStore.members.filter(m => m.role !== 'child'),
)
const currentUserId = computed(() => authStore.user?.id)
const regenerating = ref(false)

function copyInviteCode() {
  const code = familyStore.family?.invite_code
  if (code) {
    navigator.clipboard.writeText(code).then(() => {
      showToast(t('family.inviteCodeCopied'))
    }).catch(() => {
      showToast(t('toast.newInviteCode', { code }))
    })
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

  // Load total pending chore approvals (family-wide)
  try {
    const choreApprovals = await getPendingApprovals()
    totalPendingChores.value = choreApprovals.length
  } catch { /* non-critical */ }

  // Load wishes — compute per-child active wish counts and total pending
  try {
    const wishes = await listParentChildWishes()
    totalPendingWishes.value = wishes.filter(
      w => w.status === 'pending_review' || w.status === 'redemption_requested',
    ).length
    // Per-child: count active wishes (pending_review + active + redemption_requested)
    const counts: Record<string, number> = {}
    for (const w of wishes) {
      if (['pending_review', 'active', 'redemption_requested'].includes(w.status)) {
        counts[w.child_user_id] = (counts[w.child_user_id] ?? 0) + 1
      }
    }
    childWishCounts.value = counts
  } catch { /* non-critical */ }
}

async function onSetOwner(userId: string) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmPromoteMember') })
  } catch { return }
  try {
    await familyStore.updateMemberRole(userId, 'owner')
    showToast(t('toast.memberPromoted'))
  } catch {
    showToast(t('toast.operationFailed2'))
  }
}

async function onRemoveMember(member: { id: string; display_name: string }) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmRemoveMember', { name: member.display_name }) })
  } catch { return }
  try {
    await familyStore.removeMember(member.id)
    showToast(t('toast.memberRemoved'))
  } catch {
    showToast(t('toast.operationFailed2'))
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
    showToast(t('toast.operationFailed2'))
  } finally {
    regenerating.value = false
  }
}

function openGrantSheet(child: { id: string; display_name: string }) {
  grantTargetChild.value = child
  grantAmountStr.value = ''
  grantReason.value = ''
  showGrantSheet.value = true
}

async function doGrant() {
  const amount = parseInt(grantAmountStr.value)
  if (!grantTargetChild.value || !amount || amount <= 0) return
  grantingCoins.value = true
  try {
    await grantCoins(grantTargetChild.value.id, amount, grantReason.value || '父母奖励')
    showToast(t('toast.childGrantedStars', { amount, name: grantTargetChild.value.display_name }))
    showGrantSheet.value = false
  } catch {
    showToast(t('toast.grantFailed'))
    return
  } finally {
    grantingCoins.value = false
  }
  // Refresh balances separately so a fetch failure doesn't misreport the grant
  try {
    const res = await getAllChildBalances()
    childBalances.value = res.data
  } catch { /* non-critical */ }
}

async function switchToChildView(child: ChildUser) {
  try {
    // 调用管理员专用API获取孩子JWT
    await adminSwitchToChild(child.id)

    // 更新用户状态为孩子
    setUser({
      id: child.id,
      display_name: child.display_name,
      avatar_color: child.avatar_color,
      role: 'child',
    })

    // 标识这是管理员视角切换（用于退出逻辑）— set immediately before navigation
    // so a mid-sequence throw doesn't leave a stale flag with no child session
    localStorage.setItem('admin_child_view', '1')

    // 导航到孩子首页（跨 SPA 全页导航）
    window.location.href = '/child/'
  } catch {
    localStorage.removeItem('admin_child_view')
    clearAuth()
    showToast(t('toast.switchFailed'))
  }
}

async function onRefresh() {
  await familyStore.fetchFamily()
  await loadChildDashboard()
  refreshing.value = false
}

onMounted(async () => {
  await familyStore.fetchFamily()
  if (isOwner.value) {
    await loadChildDashboard()
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
.page-loading {
  display: flex;
  justify-content: center;
  padding-top: 40vh;
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

.action-btn--star {
  color: #f5a623;
}

.action-btn--switch {
  color: #1989fa;
}

.sheet-title {
  font-size: 17px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px;
  text-align: center;
}

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
</style>
