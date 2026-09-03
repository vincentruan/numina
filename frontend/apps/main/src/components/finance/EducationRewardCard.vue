<template>
  <!-- B1 教育奖励支出专项统计（方案 B：只读聚合，不动资产/净资产） -->
  <!-- 归位于负债 tab 内：教育奖励是家庭支出流水，与负债同属「钱出去」域。 -->
  <!-- 空状态折叠：未开启/无数据时整张卡不渲染，避免永久噪音（不占视觉空间）。 -->
  <div
    v-if="educationRewardCount > 0"
    class="education-reward-card"
    role="button"
    tabindex="0"
    :aria-label="t('financeHub.educationReward')"
    @click="openDetail"
    @keydown.enter="openDetail"
    @keydown.space.prevent="openDetail"
  >
    <div class="er-header">
      <span class="er-title">{{ t('financeHub.educationReward') }}</span>
      <van-icon name="arrow" class="er-chevron" />
    </div>
    <div class="er-row">
      <div class="er-cell">
        <div class="er-cell-label">{{ t('financeHub.educationRewardTotal') }}</div>
        <div class="er-cell-value">
          <MoneyDisplay :amount="educationRewardSummary?.total ?? 0" />
        </div>
      </div>
      <div class="er-cell">
        <div class="er-cell-label">{{ t('financeHub.educationRewardMonth') }}</div>
        <div class="er-cell-value">
          <MoneyDisplay :amount="educationRewardSummary?.month_total ?? 0" />
        </div>
      </div>
      <div class="er-cell er-cell-count-wrap">
        <span class="er-cell-count">{{ t('financeHub.educationRewardCount', { count: educationRewardCount }) }}</span>
      </div>
    </div>

    <!-- 下钻：education_reward 活动流水明细（bottom sheet，无新路由） -->
    <van-popup
      v-model:show="showDetail"
      position="bottom"
      round
      closeable
      :aria-label="t('financeHub.educationRewardDetailTitle')"
    >
      <div class="er-detail">
        <div class="er-detail-title">{{ t('financeHub.educationRewardDetailTitle') }}</div>
        <div v-if="detailLoading" class="er-detail-loading">
          <van-loading size="20px" />
        </div>
        <div v-else-if="detailItems.length === 0" class="er-detail-empty">
          {{ t('financeHub.educationRewardDetailEmpty') }}
        </div>
        <ul v-else class="er-detail-list">
          <li v-for="item in detailItems" :key="item.id" class="er-detail-item">
            <div class="er-detail-item-main">
              <div class="er-detail-item-title">{{ item.title }}</div>
              <div class="er-detail-item-time">{{ formatTime(item.created_at) }}</div>
            </div>
            <div class="er-detail-item-amount">
              <MoneyDisplay :amount="item.amount ?? 0" />
            </div>
          </li>
        </ul>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { getRecentActivities } from '@/api/dashboard'
import { parseApiDate } from '@/utils/format'
import type { ActivityItem } from '@/api/dashboard'

defineOptions({ name: 'EducationRewardCard' })

const { t, locale } = useI18n()
const dashboardStore = useDashboardStore()

const educationRewardSummary = computed(() => dashboardStore.educationRewardSummary)
const educationRewardCount = computed(() => educationRewardSummary.value?.count ?? 0)

// --- drill-down: fetch recent activities, client-filter education_reward ---
const showDetail = ref(false)
const detailLoading = ref(false)
const detailItems = ref<ActivityItem[]>([])

async function loadDetail() {
  detailLoading.value = true
  try {
    const res = await getRecentActivities(50)
    detailItems.value = (res.data || []).filter((a) => a.type === 'education_reward')
  } catch {
    detailItems.value = []
  } finally {
    detailLoading.value = false
  }
}

async function openDetail() {
  showDetail.value = true
  await loadDetail()
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = parseApiDate(iso)
  if (Number.isNaN(d.getTime())) return iso
  // Locale-aware date+time; follows user language without hard-coding a format.
  return d.toLocaleString(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.education-reward-card {
  margin: 0 0 12px;
  padding: 10px 14px;
  background: var(--bg-primary, #fff);
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: background 0.15s ease;
}

.education-reward-card:active {
  background: var(--bg-secondary, #f7f8fa);
}

.er-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.er-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #323233);
}

.er-chevron {
  color: var(--text-secondary, #969799);
  font-size: 14px;
}

.er-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.er-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.er-cell-label {
  font-size: 11px;
  color: var(--text-secondary, #969799);
}

.er-cell-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #323233);
}

.er-cell-count-wrap {
  align-items: flex-end;
}

.er-cell-count {
  font-size: 12px;
  color: var(--text-secondary, #969799);
}

/* --- drill-down popup --- */
.er-detail {
  padding: 20px 16px calc(20px + env(safe-area-inset-bottom));
  max-height: 60vh;
  overflow-y: auto;
}

.er-detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #323233);
  text-align: center;
  margin-bottom: 16px;
}

.er-detail-loading,
.er-detail-empty {
  padding: 32px 0;
  text-align: center;
  color: var(--text-secondary, #969799);
  font-size: 13px;
}

.er-detail-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.er-detail-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color, #ebedf0);
}

.er-detail-item:last-child {
  border-bottom: none;
}

.er-detail-item-main {
  flex: 1;
  min-width: 0;
}

.er-detail-item-title {
  font-size: 14px;
  color: var(--text-primary, #323233);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.er-detail-item-time {
  font-size: 12px;
  color: var(--text-secondary, #969799);
  margin-top: 2px;
}

.er-detail-item-amount {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #323233);
  flex-shrink: 0;
}
</style>
