<template>
  <div class="baby-page">
    <PageHeader title="宝贝" :show-back="false" />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Pending Approvals -->
      <PendingApprovalsSection v-if="authStore.user?.role === 'owner'" />

      <!-- No Children State -->
      <van-empty v-if="childMembers.length === 0" description="暂无孩子成员">
        <van-button type="primary" size="small" @click="$router.push('/family/members')">
          添加孩子
        </van-button>
      </van-empty>

      <!-- Child Selector + Content -->
      <template v-else>
        <!-- Child Tabs -->
        <van-tabs v-model:active="activeChildIndex" scrollable>
          <van-tab title="全部" />
          <van-tab v-for="child in childMembers" :key="child.id" :title="child.display_name" />
        </van-tabs>

        <!-- Child Info Cards (one per child, or aggregate) -->
        <div v-if="activeChildIndex === 0" class="child-cards-row">
          <div
            v-for="child in childMembers"
            :key="child.id"
            class="child-info-card"
            @click="activeChildIndex = childMembers.indexOf(child) + 1"
          >
            <div class="child-avatar" :style="{ background: child.avatar_color || '#FF6B6B' }">
              {{ (child.display_name ?? '?').charAt(0) }}
            </div>
            <p class="child-card-name">{{ child.display_name }}</p>
            <p class="child-card-balance">{{ childBalances[child.id] ?? 0 }} ⭐</p>
          </div>
        </div>

        <!-- Summary Card -->
        <van-cell-group inset class="summary-card">
          <van-cell title="余额" :value="`${currentBalance} ⭐`" />
          <van-cell title="本周家务" :value="`${currentChoreStats.completed_this_week ?? 0}/${currentChoreStats.total_this_week ?? 0}`" />
          <van-cell title="进行中心愿" :value="`${currentWishCount}`" />
        </van-cell-group>

        <!-- Content Tabs -->
        <van-tabs v-model:active="activeContentTab" class="content-tabs">
          <van-tab title="心愿">
            <div class="wish-list">
              <div
                v-for="wish in filteredWishes"
                :key="wish.id"
                class="wish-item"
                @click="$router.push('/wish-review')"
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
              <van-empty v-if="filteredWishes.length === 0" description="暂无心愿" image-size="60" />
            </div>
          </van-tab>

          <van-tab title="任务">
            <div class="chore-list">
              <van-cell
                v-for="chore in filteredChores"
                :key="chore.id"
                :title="chore.name"
                :label="`奖励: ${chore.coin_reward}⭐`"
              >
                <template #right-icon>
                  <van-tag :type="chore.status === 'completed' ? 'success' : 'default'">
                    {{ chore.status === 'completed' ? '已完成' : '待完成' }}
                  </van-tag>
                </template>
              </van-cell>
              <van-empty v-if="filteredChores.length === 0" description="暂无任务" image-size="60" />
            </div>
          </van-tab>

          <van-tab title="完成情况">
            <van-cell-group inset>
              <van-cell title="本周完成率" :value="`${weeklyCompletionRate}%`" />
              <van-cell title="本月完成率" :value="`${monthlyCompletionRate}%`" />
            </van-cell-group>
            <div class="calendar-wrap">
              <ChildCalendar
                v-if="calendarChildId"
                :key="calendarChildId"
                :fetch-month="fetchCalendarMonth"
                day-route="/baby/calendar/day"
                :extra-query="calendarChildId ? { child_id: calendarChildId } : undefined"
                variant="parent"
                :show-completion-rate="true"
              />
            </div>
          </van-tab>
        </van-tabs>
      </template>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { useChoreStore } from '@/stores/chore'
import PageHeader from '@/components/common/PageHeader.vue'
import PendingApprovalsSection from '@/components/dashboard/PendingApprovalsSection.vue'
import ChildCalendar from '@/components/calendar/ChildCalendar.vue'
import { getAllChildBalances, getChildrenChoreStats, type ChoreStats } from '@/api/family'
import { listParentChildWishes, type ParentWish } from '@/api/childWishes'
import { getFamilyChildCalendar } from '@/api/calendar'

const authStore = useAuthStore()
const familyStore = useFamilyStore()
const choreStore = useChoreStore()

const refreshing = ref(false)
const activeChildIndex = ref(0)
const activeContentTab = ref(0)

const childBalances = ref<Record<string, number>>({})
const childChoreStats = ref<Record<string, ChoreStats>>({})
const allWishes = ref<ParentWish[]>([])

interface ChildChore {
  id: string
  child_user_id: string
  name: string
  coin_reward: number
  status: 'pending' | 'completed'
}
const allChores = ref<ChildChore[]>([])

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
  return allChores.value.filter(c => c.child_user_id === selectedChildId.value)
})

const weeklyCompletionRate = computed(() => {
  const stats = currentChoreStats.value
  if (!stats.total_this_week) return 0
  return Math.round((stats.completed_this_week / stats.total_this_week) * 100)
})

const monthlyCompletionRate = computed(() => weeklyCompletionRate.value)

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
    pending_review: '待审批',
    active: '进行中',
    redemption_requested: '待兑现',
    fulfilled: '已完成',
    rejected: '已拒绝',
  }
  return map[status] ?? status
}

async function loadData() {
  try {
    const [balances, stats, wishes] = await Promise.all([
      getAllChildBalances(),
      getChildrenChoreStats(),
      listParentChildWishes(),
    ])
    childBalances.value = balances.data
    childChoreStats.value = stats.data
    allWishes.value = wishes
  } catch {
    // non-critical
  }
}

async function onRefresh() {
  await Promise.all([
    familyStore.fetchFamily(),
    choreStore.fetchPendingApprovals(),
    loadData(),
  ])
  refreshing.value = false
}

onMounted(async () => {
  await familyStore.fetchFamily()
  if (authStore.user?.role === 'owner') {
    await choreStore.fetchPendingApprovals()
  }
  await loadData()
})
</script>

<style scoped>
.baby-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}

/* Child info cards row */
.child-cards-row {
  display: flex;
  gap: 10px;
  padding: 12px 16px 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.child-cards-row::-webkit-scrollbar { display: none; }

.child-info-card {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  background: #eeece7;
  border-radius: 8px;
  padding: 12px 16px;
  cursor: pointer;
  min-width: 80px;
  transition: transform 0.1s;
}
.child-info-card:active { transform: scale(0.96); }

.child-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}

.child-card-name {
  font-size: 13px;
  font-weight: 600;
  color: #17171c;
  margin: 0;
}

.child-card-balance {
  font-size: 12px;
  color: #666;
  margin: 0;
}

.summary-card {
  margin-top: 12px;
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