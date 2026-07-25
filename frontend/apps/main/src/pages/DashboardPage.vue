<template>
  <div class="dashboard-page" role="main" :aria-label="t('dashboard.aria.pageTitle')">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Skeleton Loading State -->
      <DashboardSkeleton v-if="dashboardStore.loading && !overview?.asset_count" />

      <!-- Empty State for new users -->
      <div v-else-if="!dashboardStore.loading && overview?.asset_count === 0" class="empty-dashboard">
        <van-empty :description="t('dashboard.emptyState.startRecording')">
          <van-button type="primary" size="small" @click="$router.push('/assets/new')">
            {{ t('dashboard.emptyState.addAssetBtn') }}
          </van-button>
        </van-empty>
      </div>

      <template v-else>
        <!-- Hero section: unified stat card (net worth + drill-down sub-stats) -->
        <div class="hero-section">
          <OverviewStatCard />
        </div>

        <!-- D2/A1a: finance_coach proactive suggestions card (Plan B T5) -->
        <FinanceCoachCard />

        <!-- Smart Reminders (includes expiring soon + upcoming payments + idle + AI reminders) -->
        <SmartRemindersCard
          :idle-assets="dashboardStore.lowUsageAssets.filter((a) => a.usage_frequency === 'idle')"
          :expiring-assets="dashboardStore.expiringSoonAssets"
          :upcoming-payments="upcomingPayments"
          @select-status="onStatusSelect"
        />

        <!-- D1: Pending approvals (owner-only; component self-gates on non-empty list) -->
        <PendingApprovalsSection v-if="authStore.user?.role === 'owner'" />

        <!-- Focus top-3 preview across assets/liabilities/wishes -->
        <FocusTop3Card />
      </template>

      <div class="bottom-spacer" />
    </van-pull-refresh>

    <!-- New User Onboarding Overlay -->
    <OnboardingOverlay :visible="showOnboarding" @complete="onOnboardingComplete" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { useChoreStore } from '@/stores/chore'
import { getUpcomingPayments } from '@/api/dashboard'
import type { UpcomingPaymentItem } from '@/api/dashboard'
import { usePageLoading } from '@/composables/usePageLoading'

import OverviewStatCard from '@/components/dashboard/OverviewStatCard.vue'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton.vue'
import SmartRemindersCard from '@/components/dashboard/SmartRemindersCard.vue'
import FinanceCoachCard from '@/components/dashboard/FinanceCoachCard.vue'
import PendingApprovalsSection from '@/components/dashboard/PendingApprovalsSection.vue'
import OnboardingOverlay from '@/components/common/OnboardingOverlay.vue'
import FocusTop3Card from '@/components/dashboard/FocusTop3Card.vue'

const { t } = useI18n()
const router = useRouter()

const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const choreStore = useChoreStore()
const { increment, decrement } = usePageLoading()
const refreshing = ref(false)

// Upcoming payments
const upcomingPayments = ref<UpcomingPaymentItem[]>([])

// Onboarding overlay
const showOnboarding = ref(false)

function onOnboardingComplete() {
  showOnboarding.value = false
  localStorage.setItem('onboarding_completed', 'true')
}

function maybeShowOnboarding() {
  if (localStorage.getItem('onboarding_completed') === 'true') return
  // Only show when there are no assets yet
  if ((overview.value?.asset_count ?? 0) === 0) {
    showOnboarding.value = true
  }
}

const overview = computed(() => dashboardStore.overview)

// Smart-reminder status taps now deep-link into the finance assets tab (the full
// asset list no longer lives on the overview page).
function onStatusSelect(_status: string | null) {
  router.push({ path: '/finance', query: { tab: 'assets' } })
}

async function onRefresh() {
  dashboardStore.resetAssetPagination()
  await dashboardStore.fetchAll()
  if (authStore.user?.role === 'owner') {
    await choreStore.fetchPendingApprovals()
  }
  refreshing.value = false
}

onMounted(async () => {
  increment()
  try {
    await Promise.all([
      dashboardStore.fetchAll().then(() => {
        maybeShowOnboarding()
      }),
      authStore.user?.role === 'owner' ? choreStore.fetchPendingApprovals() : Promise.resolve(),
      getUpcomingPayments()
        .then((res) => {
          upcomingPayments.value = res.data.items
        })
        .catch(() => {
          // Non-critical: silently ignore if endpoint not available
        }),
    ])
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.dashboard-page {
  background: var(--card-bg);
  min-height: 100vh;
}

.hero-section {
  background: var(--bg-secondary);
}

.empty-dashboard {
  padding: 40px 0;
}

.bottom-spacer {
  height: 80px;
}
</style>
