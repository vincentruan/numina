<template>
  <div class="baby-page">
    <PageHeader :title="t('baby.title')" :show-back="false" />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- No Children State -->
      <van-empty v-if="childMembers.length === 0" :description="t('baby.noChildren')">
        <van-button type="primary" size="small" @click="$router.push('/family/members')">
          {{ t('baby.addChildren') }}
        </van-button>
      </van-empty>

      <!-- Child Selector + Content -->
      <template v-else>
        <!-- Child Tabs -->
        <van-tabs v-model:active="activeChildIndex" scrollable class="child-tabs">
          <van-tab :title="t('baby.tabAll')" />
          <van-tab v-for="child in childMembers" :key="child.id">
            <template #title>
              <div class="child-tab-title">
                <div class="child-tab-avatar" :style="{ background: child.avatar_color || '#FF6B6B' }">
                  {{ (child.display_name ?? '?').charAt(0) }}
                </div>
                <span class="child-tab-name">{{ child.display_name }}</span>
              </div>
            </template>
          </van-tab>
        </van-tabs>

        <!-- Pending Approvals (filtered by selected child) -->
        <PendingApprovalsSection
          v-if="authStore.user?.role === 'owner'"
          :child-id="selectedChildId ? String(selectedChildId) : null"
        />

        <!-- Summary Card -->
        <van-cell-group inset class="summary-card">
          <van-cell :title="t('baby.balance')">
            <template #value>
              <div class="balance-row">
                <span>{{ currentBalance }} ⭐</span>
                <van-button
                  size="mini"
                  type="warning"
                  plain
                  class="grant-btn"
                  @click="openGrantSheet"
                >{{ t('baby.grantBtn') }}</van-button>
              </div>
            </template>
          </van-cell>
          <van-cell :title="t('baby.weeklyChores')" :value="`${currentChoreStats.completed_this_week ?? 0}/${currentChoreStats.total_this_week ?? 0}`" />
          <van-cell :title="t('baby.activeWishes')" :value="`${currentWishCount}`" />
          <van-cell :title="t('baby.blindBoxGifts')" is-link @click="$router.push('/blind-box/gifts')" />
          <van-cell :title="t('baby.blindBoxDraws')" is-link @click="$router.push('/blind-box/draws')">
            <template v-if="pendingDrawCount > 0" #value>
              <van-badge :content="pendingDrawCount" />
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Content Tabs -->
        <van-tabs v-model:active="activeContentTab" class="content-tabs">
          <van-tab :title="t('baby.tabDiary')">
            <van-cell-group inset>
              <van-cell :title="t('baby.weeklyRate')" :value="`${weeklyCompletionRate}%`" />
            </van-cell-group>
            <div class="calendar-wrap">
              <ChildCalendar
                v-if="calendarChildId"
                :key="calendarChildId"
                :fetch-month="fetchCalendarMonth"
                day-route="/baby/calendar/day"
                :extra-query="{ child_id: calendarChildId }"
                variant="parent"
                :show-completion-rate="true"
              />
            </div>
          </van-tab>

          <van-tab :title="t('baby.tabWishes')">
            <div class="wish-list">
              <div
                v-for="wish in filteredWishes"
                :key="wish.id"
                class="wish-item"
                @click="$router.push('/family/wish-review')"
              >
                <div class="wish-header">
                  <span class="wish-emoji-icon">{{ wish.emoji || '🌟' }}</span>
                  <span class="wish-name">{{ wish.name }}</span>
                  <van-tag :type="getWishStatusType(wish.status)">{{ getWishStatusLabel(wish.status) }}</van-tag>
                </div>
                <div v-if="wish.star_coin_cost" class="wish-cost">{{ wish.star_coin_cost }} ⭐</div>
                <van-progress
                  v-if="wish.status === 'active' && wish.star_coin_cost"
                  :percentage="Math.min(Math.round(((childBalances[wish.child_user_id] ?? 0) / wish.star_coin_cost) * 100), 100)"
                  stroke-width="6"
                  color="#f5a623"
                />
              </div>
              <van-empty v-if="filteredWishes.length === 0" :description="t('baby.noWishes')" image-size="60" />
            </div>
          </van-tab>

          <van-tab :title="t('baby.tabChores')">
            <div class="chore-list">
              <van-cell
                v-for="chore in filteredChores"
                :key="chore.id"
                :title="chore.chore_name"
                :label="t('baby.choreReward', { reward: chore.coin_reward })"
              >
                <template #right-icon>
                  <van-tag :type="chore.status === 'approved' ? 'success' : 'default'">
                    {{ chore.status === 'approved' ? t('baby.choreCompleted') : t('baby.chorePending') }}
                  </van-tag>
                </template>
              </van-cell>
              <van-empty v-if="filteredChores.length === 0" :description="t('baby.noChores')" image-size="60" />
            </div>
          </van-tab>
        </van-tabs>

        <!-- Child picker popup (shown when on 全部 tab) -->
        <van-popup v-model:show="showChildPicker" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">{{ t('baby.grantSelectChild') }}</p>
          <van-cell
            v-for="child in childMembers"
            :key="child.id"
            :title="child.display_name"
            is-link
            @click="selectChildAndGrant(child)"
          >
            <template #icon>
              <div class="child-tab-avatar" :style="{ background: child.avatar_color || '#FF6B6B', marginRight: '8px' }">
                {{ (child.display_name ?? '?').charAt(0) }}
              </div>
            </template>
          </van-cell>
        </van-popup>

        <!-- Grant stars bottom sheet -->
        <van-popup v-model:show="showGrantSheet" position="bottom" round style="padding: 24px 16px 40px">
          <p class="sheet-title">{{ t('baby.grantSheetTitle', { name: grantTargetChild?.display_name }) }}</p>
          <van-field
            v-model="grantAmountStr"
            type="digit"
            :label="t('baby.grantAmountLabel')"
            :placeholder="t('baby.grantAmountPlaceholder')"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <van-field
            v-model="grantReason"
            :label="t('baby.grantReasonLabel')"
            :placeholder="t('baby.grantReasonPlaceholder')"
            style="margin-top: 8px; border-radius: 8px; background: #f9f9f9"
          />
          <van-button
            block
            type="primary"
            :disabled="!grantAmountStr || parseInt(grantAmountStr, 10) <= 0"
            :loading="grantingCoins"
            style="margin-top: 16px; border-radius: 12px; background: #f5a623; border: none"
            @click="doGrant"
          >{{ t('baby.grantConfirm') }}</van-button>
        </van-popup>
      </template>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { useChoreStore } from '@/stores/chore'
import { useBlindBoxStore } from '@/stores/blindBox'
import PageHeader from '@/components/common/PageHeader.vue'
import PendingApprovalsSection from '@/components/dashboard/PendingApprovalsSection.vue'
import ChildCalendar from '@/components/calendar/ChildCalendar.vue'
import { getAllChildBalances, getChildrenChoreStats, type ChoreStats } from '@/api/family'
import { listParentChildWishes, type ParentWish } from '@/api/childWishes'
import { getFamilyChildCalendar } from '@/api/calendar'
import { grantCoins } from '@/api/coins'
import { getChildrenChores, type ChoreInstance } from '@/api/chores'

const { t } = useI18n()
const authStore = useAuthStore()
const familyStore = useFamilyStore()
const choreStore = useChoreStore()
const blindBoxStore = useBlindBoxStore()

const pendingDrawCount = computed(
  () => blindBoxStore.draws.filter((d) => d.status === 'pending_fulfillment').length,
)

const refreshing = ref(false)
const activeChildIndex = ref(0)
const activeContentTab = ref(0)

// Grant stars state
const showChildPicker = ref(false)
const showGrantSheet = ref(false)
const grantTargetChild = ref<{ id: string; display_name: string } | null>(null)
const grantAmountStr = ref('')
const grantReason = ref('')
const grantingCoins = ref(false)

const childBalances = ref<Record<string, number>>({})
const childChoreStats = ref<Record<string, ChoreStats>>({})
const allWishes = ref<ParentWish[]>([])

const allChores = ref<ChoreInstance[]>([])

const childMembers = computed(() => familyStore.members.filter(m => m.role === 'child'))

const selectedChildId = computed(() => {
  if (activeChildIndex.value === 0) return null // "全部"
  const child = childMembers.value[activeChildIndex.value - 1]
  return child?.id ?? null
})

const currentBalance = computed(() => {
  if (!selectedChildId.value) {
    return Object.values(childBalances.value).reduce((sum, val) => sum + val, 0)
  }
  return childBalances.value[selectedChildId.value] ?? 0
})

const currentChoreStats = computed(() => {
  if (!selectedChildId.value) {
    const all = Object.values(childChoreStats.value)
    return {
      completed_this_week: all.reduce((sum, s) => sum + (s.completed_this_week ?? 0), 0),
      total_this_week: all.reduce((sum, s) => sum + (s.total_this_week ?? 0), 0),
    }
  }
  return childChoreStats.value[selectedChildId.value] ?? { completed_this_week: 0, total_this_week: 0 }
})

const currentWishCount = computed(() => {
  const wishes = selectedChildId.value
    ? allWishes.value.filter(w => w.child_user_id === selectedChildId.value)
    : allWishes.value
  return wishes.filter(w => ['pending_review', 'active', 'redemption_requested'].includes(w.status)).length
})

const filteredWishes = computed(() => {
  if (!selectedChildId.value) return allWishes.value
  return allWishes.value.filter(w => w.child_user_id === selectedChildId.value)
})

const filteredChores = computed(() => {
  if (!selectedChildId.value) return allChores.value
  return allChores.value.filter(c => c.child_user_id === String(selectedChildId.value))
})

const weeklyCompletionRate = computed(() => {
  const stats = currentChoreStats.value
  if (!stats.total_this_week) return 0
  return Math.round((stats.completed_this_week / stats.total_this_week) * 100)
})

const calendarChildId = computed<string | null>(() => {
  if (selectedChildId.value) return String(selectedChildId.value)
  // 全部视图时取第一个孩子
  const first = childMembers.value[0]
  return first ? String(first.id) : null
})

function fetchCalendarMonth(year: number, month: number) {
  if (!calendarChildId.value) return Promise.reject(new Error('no child'))
  return getFamilyChildCalendar(calendarChildId.value, year, month)
}

function getWishStatusType(status: string): 'primary' | 'success' | 'warning' | 'danger' | 'default' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'default'> = {
    pending_review: 'warning',
    active: 'primary',
    redemption_requested: 'warning',
    fulfilled: 'success',
    rejected: 'danger',
  }
  return map[status] ?? 'default'
}

function getWishStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending_review: t('baby.wishStatusPendingReview'),
    active: t('baby.wishStatusActive'),
    redemption_requested: t('baby.wishStatusRedemptionRequested'),
    fulfilled: t('baby.wishStatusFulfilled'),
    rejected: t('baby.wishStatusRejected'),
  }
  return map[status] ?? status
}

function openGrantSheet() {
  if (!selectedChildId.value) {
    // 全部视图：先选孩子
    showChildPicker.value = true
  } else {
    const child = childMembers.value.find(c => c.id === selectedChildId.value)
    if (!child) return
    grantTargetChild.value = { id: String(child.id), display_name: child.display_name ?? '' }
    grantAmountStr.value = ''
    grantReason.value = ''
    showGrantSheet.value = true
  }
}

function selectChildAndGrant(child: { id: string | number; display_name?: string | null }) {
  showChildPicker.value = false
  grantTargetChild.value = { id: String(child.id), display_name: child.display_name ?? '' }
  grantAmountStr.value = ''
  grantReason.value = ''
  showGrantSheet.value = true
}

async function doGrant() {
  const amount = parseInt(grantAmountStr.value, 10)
  if (!grantTargetChild.value || !amount || amount <= 0) return
  grantingCoins.value = true
  try {
    await grantCoins(grantTargetChild.value.id, amount, grantReason.value || t('baby.grantDefaultReason'))
    showToast(t('toast.childGrantedStars', { amount, name: grantTargetChild.value.display_name }))
    showGrantSheet.value = false
  } catch {
    showToast(t('toast.grantFailed'))
    return
  } finally {
    grantingCoins.value = false
  }
  try {
    const res = await getAllChildBalances()
    childBalances.value = res.data
  } catch { /* non-critical */ }
}

async function loadData() {
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  try {
    const [balances, stats, wishes, chores] = await Promise.all([
      getAllChildBalances(),
      getChildrenChoreStats(),
      listParentChildWishes(),
      getChildrenChores(today),
    ])
    childBalances.value = balances.data
    childChoreStats.value = stats.data
    allWishes.value = wishes
    allChores.value = chores
  } catch {
    // non-critical
  }
}

async function onRefresh() {
  const tasks = [
    familyStore.fetchFamily(),
    loadData(),
  ]
  if (authStore.user?.role === 'owner') {
    tasks.push(choreStore.fetchPendingApprovals())
  }
  await Promise.all(tasks)
  refreshing.value = false
}

onMounted(async () => {
  await familyStore.fetchFamily()
  if (authStore.user?.role === 'owner') {
    await choreStore.fetchPendingApprovals()
  }
  await loadData()
  await blindBoxStore.fetchDraws()
})
</script>

<style scoped>
.baby-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}

/* Child tab custom title */
.child-tab-title {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 5px;
  padding: 2px 2px;
}

.child-tab-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.child-tab-name {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60px;
}

/* Fix tab text visibility in dark mode */
.child-tabs :deep(.van-tab) {
  color: var(--van-gray-6, #969799);
}

.child-tabs :deep(.van-tab--active) {
  color: var(--van-tabs-default-color, var(--van-primary-color, #1989fa));
}

[data-theme='dark'] .child-tabs :deep(.van-tab),
.dark .child-tabs :deep(.van-tab) {
  color: rgba(255, 255, 255, 0.7);
}

[data-theme='dark'] .child-tabs :deep(.van-tab--active),
.dark .child-tabs :deep(.van-tab--active) {
  color: #fff;
}

[data-theme='dark'] .child-tab-name,
.dark .child-tab-name {
  color: inherit;
}

.summary-card {
  margin-top: 12px;
}

.balance-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.grant-btn {
  flex-shrink: 0;
  font-size: 11px;
  padding: 0 8px;
  height: 24px;
  border-radius: 12px;
}

.sheet-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}

.content-tabs {
  margin-top: 12px;
}

.wish-list,
.chore-list {
  padding: 12px;
}

.wish-item {
  background: var(--card-bg);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
}

.wish-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  gap: 6px;
}

.wish-emoji-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.wish-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
}

.wish-cost {
  font-size: 12px;
  color: #f5a623;
  font-weight: 500;
  margin-bottom: 6px;
}

.calendar-wrap {
  margin: 12px 16px 0;
}
</style>