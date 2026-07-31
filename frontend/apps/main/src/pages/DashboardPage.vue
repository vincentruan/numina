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

        <!-- Literacy weekly report status (per-child) -->
        <LiteracyStatusCard ref="literacyStatusRef" />

        <!-- Smart Reminders (includes expiring soon + upcoming payments + idle + AI reminders) -->
        <SmartRemindersCard
          :idle-assets="dashboardStore.lowUsageAssets.filter((a) => a.usage_frequency === 'idle')"
          :expiring-assets="dashboardStore.expiringSoonAssets"
          :upcoming-payments="upcomingPayments"
          @select-status="onStatusSelect"
        />

        <!-- D1: Pending approvals (owner-only; component self-gates on non-empty list) -->
        <PendingApprovalsSection v-if="authStore.user?.role === 'owner'" />

        <!-- Family Manifesto dashboard summary (self-gates when no active manifesto) -->
        <ManifestoDashboardCard />

        <!-- Focus top-3 preview across assets/liabilities/wishes -->
        <FocusTop3Card />
      </template>

      <div class="bottom-spacer" />
    </van-pull-refresh>

    <!-- Step Guide Onboarding Overlay -->
    <StepGuideOverlay
      :visible="guide.isActive.value"
      :steps="guideSteps"
      :current-step="guide.currentStep.value"
      @skip="guide.skip"
      @next="guide.next"
      @complete="guide.complete"
    />

    <!-- Manifesto Signing Popup (P1-2 non-blocking notification) -->
    <ManifestoSigningPopup
      :visible="showManifestoPopup"
      :manifesto-title="unsignedManifestoTitle"
      @update:visible="(val: boolean) => showManifestoPopup = val"
      @navigate="onManifestoNavigate"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { useChoreStore } from '@/stores/chore'
import { useFamilyStore } from '@/stores/family'
import { getUpcomingPayments } from '@/api/dashboard'
import type { UpcomingPaymentItem } from '@/api/dashboard'

defineOptions({ name: 'Dashboard' })
import { usePageLoading } from '@/composables/usePageLoading'
import { useMemberNotify } from '@/composables/useMemberNotify'
import { useStepGuide, type StepGuideStep } from '@/composables/useStepGuide'
import { migrateOldOnboardingKey } from '@/utils/storage'

import OverviewStatCard from '@/components/dashboard/OverviewStatCard.vue'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton.vue'
import SmartRemindersCard from '@/components/dashboard/SmartRemindersCard.vue'
import FinanceCoachCard from '@/components/dashboard/FinanceCoachCard.vue'
import PendingApprovalsSection from '@/components/dashboard/PendingApprovalsSection.vue'
import StepGuideOverlay from '@/components/common/StepGuideOverlay.vue'
import FocusTop3Card from '@/components/dashboard/FocusTop3Card.vue'
import ManifestoDashboardCard from '@/components/dashboard/ManifestoDashboardCard.vue'
import LiteracyStatusCard from '@/components/dashboard/LiteracyStatusCard.vue'
import ManifestoSigningPopup from '@/components/manifesto/ManifestoSigningPopup.vue'
import * as manifestoApi from '@/api/manifesto'

const { t } = useI18n()
const router = useRouter()

const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const choreStore = useChoreStore()
const familyStore = useFamilyStore()
const { increment, decrement } = usePageLoading()
const { checkFamilyChanges } = useMemberNotify()
// Skip first onActivated — Vue 3 fires both onMounted and onActivated on first
// mount inside <KeepAlive>; onMounted handles initial load.
let hasActivated = false
const refreshing = ref(false)
const literacyStatusRef = ref<InstanceType<typeof LiteracyStatusCard> | null>(null)

// Upcoming payments
const upcomingPayments = ref<UpcomingPaymentItem[]>([])

// Step-guide onboarding
const overview = computed(() => dashboardStore.overview)

const guideSteps = computed<StepGuideStep[]>(() => [
  {
    selector: '.empty-dashboard, .hero-section',
    mode: 'spotlight',
    title: (overview.value?.asset_count ?? 0) === 0
      ? t('onboarding.step1.empty.title')
      : t('onboarding.step1.data.title'),
    desc: (overview.value?.asset_count ?? 0) === 0
      ? t('onboarding.step1.empty.desc')
      : t('onboarding.step1.data.desc'),
  },
  {
    selector: '[data-tab="finance"]',
    mode: 'spotlight',
    title: t('onboarding.step2.title'),
    desc: t('onboarding.step2.desc'),
  },
  {
    selector: '[data-tab="settings"]',
    mode: 'spotlight',
    title: t('onboarding.step3.title'),
    desc: t('onboarding.step3.desc'),
  },
])

const guide = useStepGuide({ key: 'guide_main-onboarding-v2', steps: guideSteps.value })

// Manifesto signing popup
const showManifestoPopup = ref(false)
const unsignedManifestoTitle = ref('')

async function checkUnsignedManifesto() {
  try {
    const res = await manifestoApi.getUnsignedCheck()
    if (res.data.has_unsigned && res.data.title) {
      unsignedManifestoTitle.value = res.data.title
      showManifestoPopup.value = true
    }
  } catch {
    // Non-critical: silently ignore
  }
}

function onManifestoNavigate() {
  showManifestoPopup.value = false
  router.push('/manifesto/sign')
}

function maybeShowOnboarding() {
  migrateOldOnboardingKey()
  if (router.currentRoute.value.path !== '/') return
  guide.start()
}

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
  await literacyStatusRef.value?.loadStatuses()
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
      familyStore.fetchFamily().catch(() => { /* non-critical */ }),
    ])
    // Passive check: notify if family state changed since last snapshot.
    checkFamilyChanges()
    // Check for unsigned manifesto
    checkUnsignedManifesto()
  } finally {
    decrement()
  }
})

// KeepAlive 缓存页面：返回时触发 onActivated 而非 onMounted
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
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
      familyStore.fetchFamily().catch(() => { /* non-critical */ }),
    ])
    // Passive check: notify if family state changed since last snapshot.
    checkFamilyChanges()
    // Check for unsigned manifesto
    checkUnsignedManifesto()
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
