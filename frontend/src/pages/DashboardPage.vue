<template>
  <div class="dashboard-page">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Empty State for new users -->
      <div v-if="!dashboardStore.loading && overview?.asset_count === 0" class="empty-dashboard">
        <van-empty description="开始记录你的第一项资产">
          <van-button type="primary" size="small" @click="$router.push('/assets/new')">
            添加资产
          </van-button>
        </van-empty>
      </div>

      <template v-else>
        <!-- Net Worth Card -->
        <NetWorthCard
          :net-worth="overview?.net_worth || 0"
          :total-assets="overview?.total_assets || 0"
          :total-liabilities="overview?.total_liabilities || 0"
          :month-over-month-change="overview?.month_over_month_change"
        />

        <!-- Status Summary Grid -->
        <StatusSummaryGrid
          :summary="dashboardStore.statesSummary"
          :active-status="activeStatus"
          @select="onStatusSelect"
        />

        <!-- Status Tabs -->
        <StatusTabs v-model="activeStatus" />

        <!-- Asset List by Status -->
        <van-cell-group v-if="filteredAssets.length" inset title="资产列表" class="section">
          <AssetCard
            v-for="asset in filteredAssets.slice(0, 5)"
            :key="asset.id"
            :asset="asset"
            clickable
            @click="$router.push(`/assets/${asset.id}`)"
          />
          <van-cell
            v-if="filteredAssets.length > 5"
            title="查看全部"
            is-link
            @click="$router.push('/assets')"
          />
        </van-cell-group>

        <van-cell-group v-else inset class="section">
          <van-empty description="暂无资产" image-size="60" />
        </van-cell-group>

        <!-- Charts Section (Collapsible) -->
        <van-collapse v-model="activeCollapse" class="section">
          <van-collapse-item title="趋势分析" name="trend">
            <TrendLineChart :data="dashboardStore.trend" @period-change="onPeriodChange" />
          </van-collapse-item>
          <van-collapse-item title="资产配置" name="allocation">
            <AllocationPieChart :data="dashboardStore.allocation" />
          </van-collapse-item>
        </van-collapse>

        <!-- Daily Cost Ranking -->
        <van-cell-group v-if="dashboardStore.dailyCostRanking.length" inset title="日耗排行" class="section">
          <van-cell
            v-for="item in dashboardStore.dailyCostRanking.slice(0, 5)"
            :key="item.id"
            :title="`${item.icon} ${item.name}`"
            clickable
            @click="$router.push(`/assets/${item.id}`)"
          >
            <template #value>
              <span class="daily-cost-value">¥{{ item.daily_cost.toFixed(2) }}/天</span>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Investment Returns -->
        <van-cell-group v-if="dashboardStore.investmentReturns.length" inset title="投资收益排行" class="section">
          <van-cell
            v-for="item in dashboardStore.investmentReturns.slice(0, 5)"
            :key="item.id"
            :title="item.name"
            :label="`本金 ¥${item.purchase_price.toLocaleString()}`"
            clickable
            @click="$router.push(`/assets/${item.id}`)"
          >
            <template #value>
              <div class="return-value">
                <span :class="item.return_rate >= 0 ? 'positive' : 'negative'">
                  {{ item.return_rate >= 0 ? '+' : '' }}{{ item.return_rate.toFixed(2) }}%
                </span>
              </div>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Recent Activities -->
        <van-cell-group v-if="dashboardStore.recentActivities.length" inset title="最近动态" class="section">
          <van-cell
            v-for="activity in dashboardStore.recentActivities.slice(0, 5)"
            :key="activity.id"
            :title="activity.title"
            :label="activity.created_at.slice(0, 10)"
            :icon="activityIcon(activity.type)"
          >
            <template v-if="activity.amount" #value>
              <span class="activity-amount">¥{{ activity.amount.toLocaleString() }}</span>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Settings Link -->
        <van-cell-group inset class="section">
          <van-cell title="设置" icon="setting-o" is-link to="/settings" />
        </van-cell-group>
      </template>

      <div class="bottom-spacer" />
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import NetWorthCard from '@/components/dashboard/NetWorthCard.vue'
import StatusSummaryGrid from '@/components/dashboard/StatusSummaryGrid.vue'
import StatusTabs from '@/components/dashboard/StatusTabs.vue'
import AssetCard from '@/components/asset/AssetCard.vue'
import TrendLineChart from '@/components/charts/TrendLineChart.vue'
import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'

const dashboardStore = useDashboardStore()
const refreshing = ref(false)
const activeStatus = ref<string | null>(null)
const activeCollapse = ref<string[]>(['trend', 'allocation'])

const overview = computed(() => dashboardStore.overview)

// Computed property to get filtered assets from homeAssets
const filteredAssets = computed(() => {
  if (!activeStatus.value) {
    // Return all assets from all groups
    const allAssets = Object.values(dashboardStore.homeAssets).flat()
    // Sort by updated_at desc
    return allAssets.sort((a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
  }
  return dashboardStore.homeAssets[activeStatus.value] || []
})

function onStatusSelect(status: string | null) {
  activeStatus.value = status
}

function onPeriodChange(period: 'month' | 'quarter' | 'year') {
  dashboardStore.fetchTrend(period)
}

async function onRefresh() {
  await dashboardStore.fetchAll()
  refreshing.value = false
}

function activityIcon(type: string) {
  const map: Record<string, string> = {
    create: 'plus',
    update: 'edit',
    delete: 'delete-o',
    sell: 'gold-coin-o',
    retire: 'close',
    reactivate: 'replay',
    payment: 'balance-pay',
  }
  return map[type] || 'notes-o'
}

onMounted(() => {
  dashboardStore.fetchAll()
})
</script>

<style scoped>
.dashboard-page {
  background: #f7f8fa;
  min-height: 100vh;
}
.section {
  margin-top: 12px;
}
.daily-cost-value {
  color: #ff976a;
  font-size: 13px;
}
.return-value {
  text-align: right;
}
.return-value .positive {
  color: #07c160;
  font-weight: 500;
}
.return-value .negative {
  color: #ee0a24;
  font-weight: 500;
}
.bottom-spacer {
  height: 20px;
}
.activity-amount {
  color: #1989fa;
  font-size: 13px;
}
:deep(.van-collapse-item__content) {
  padding: 0;
}
</style>