<template>
  <div class="asset-detail-page">
    <PageHeader :title="t('assetDetail.pageTitle')" />

    <template v-if="asset">
      <!-- Hero Card -->
      <div class="hero-card" :class="asset.status === 'sold' ? 'sold' : ''">
        <van-tag v-if="asset.status !== 'in_use'" class="status-badge" :type="statusType" size="medium">
          {{ statusText }}
        </van-tag>
        <div class="hero-top">
          <div v-if="asset.image_url && !imageError" class="hero-image">
            <img :src="imageUrl" :alt="asset.name" @error="onImageError" />
          </div>
          <div v-else class="hero-icon" :style="{ background: 'rgba(255,255,255,0.15)' }">
            <SvgIcon :name="getIconId(asset.category?.icon)" class="icon-svg-hero" />
          </div>
          <div class="hero-info">
            <div class="hero-name">{{ asset.name }}</div>
            <div class="hero-category">{{ asset.category?.name || t('asset.uncategorized') }}</div>
            <div class="hero-usage">
              <span v-if="daysUsed > 0" class="usage-badge">{{ t('asset.daysUsed', { days: daysUsed }) }}</span>
              <span v-if="asset.expected_lifespan_days" class="usage-badge lifespan">{{ t('asset.expectedLifespan', { days: asset.expected_lifespan_days }) }}</span>
            </div>
          </div>
        </div>
        <div class="hero-values">
          <div class="hero-value-item">
            <div class="hero-value-label">{{ asset.status === 'sold' ? t('assetDetail.sellPrice') : t('asset.currentValue') }}</div>
            <MoneyDisplay
            :amount="asset.status === 'sold' ? (asset.sell_price || 0) : (asset.current_value || 0)"
            size="large"
            :source-currency="asset.currency"
            :original-value="asset.status === 'sold' ? (asset.sell_price || 0) : (asset.current_value || 0)"
          />
          </div>
          <div class="hero-value-item">
            <div class="hero-value-label">{{ t('asset.purchasePrice') }}</div>
            <MoneyDisplay
              :amount="asset.purchase_price"
              :source-currency="asset.currency"
              :original-value="asset.purchase_price"
            />
          </div>
          <div v-if="asset.daily_cost != null && asset.daily_cost > 0" class="hero-value-item">
            <div class="hero-value-label">{{ t('asset.dailyCostLabel') }}</div>
            <div class="hero-daily-cost">¥{{ asset.daily_cost.toFixed(2) }}</div>
          </div>
        </div>
        <div v-if="asset.status !== 'sold'" class="hero-change" :class="returnClass">
          {{ returnText }}
        </div>
        <div v-if="asset.status === 'sold'" class="sell-summary">
          {{ t('assetDetail.netRecovery', { amount: (asset.sell_price! - (asset.sell_fee || 0)).toLocaleString() }) }}
          <span v-if="asset.sell_date"> · {{ asset.sell_date }}</span>
        </div>
      </div>

      <!-- Daily Cost Chart -->
      <DailyCostChart
        v-if="asset.purchase_price && asset.purchase_date"
        :purchase-price="asset.purchase_price"
        :purchase-date="asset.purchase_date"
        :target-daily-cost="asset.target_daily_cost"
      />

      <!-- Basic Info -->
      <van-cell-group inset :title="t('assetDetail.sectionBasicInfo')">
        <van-cell :title="t('assetDetail.fieldName')" :value="asset.name" />
        <van-cell :title="t('assetDetail.fieldType')" :value="typeText" />
        <van-cell :title="t('assetDetail.fieldCategory')" :value="asset.category?.name || t('asset.uncategorized')">
          <template #icon>
            <SvgIcon :name="getIconId(asset.category?.icon)" class="cat-icon-svg" />
          </template>
        </van-cell>
        <van-cell :title="t('assetDetail.fieldPurchasePrice')">
          <template #value>
            <MoneyDisplay
              :amount="asset.purchase_price"
              :source-currency="asset.currency"
              :original-value="asset.purchase_price"
            />
          </template>
        </van-cell>
        <van-cell :title="t('assetDetail.fieldPurchaseDate')" :value="asset.purchase_date" />
        <van-cell :title="t('assetDetail.fieldStatus')">
          <template #value>
            <van-tag :type="statusType">{{ statusText }}</van-tag>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Wish Origin -->
      <van-cell-group v-if="asset.from_wish_id" inset :title="t('assetDetail.sectionWishOrigin')">
        <van-cell :title="t('assetDetail.fromWish')" is-link :to="`/wishes/${asset.from_wish_id}`" />
      </van-cell-group>

      <!-- Physical Info -->
      <van-cell-group v-if="asset.asset_type === 'physical'" inset :title="t('assetDetail.sectionPhysicalInfo')">
        <van-cell v-if="asset.location" :title="t('assetDetail.fieldLocation')" :value="asset.location" />
        <van-cell v-if="asset.expected_lifespan_days" :title="t('assetDetail.fieldExpectedLifespan')" :value="t('assetDetail.lifespanDays', { days: asset.expected_lifespan_days })" />
        <van-cell v-if="asset.annual_maintenance_cost" :title="t('assetDetail.fieldAnnualMaintenance')">
          <template #value><MoneyDisplay :amount="asset.annual_maintenance_cost" /></template>
        </van-cell>
        <van-cell v-if="asset.usage_frequency" :title="t('assetDetail.fieldUsageFrequency')" :value="usageText" />
        <van-cell v-if="asset.daily_cost" :title="t('assetDetail.fieldDailyCost')">
          <template #value>
            <span class="daily-cost">¥{{ asset.daily_cost.toFixed(2) }}{{ t('assetDetail.perDay') }}</span>
          </template>
        </van-cell>
        <van-cell v-if="asset.target_daily_cost" :title="t('assetDetail.fieldTargetDailyCost')">
          <template #value>
            <span class="target-cost">¥{{ asset.target_daily_cost.toFixed(2) }}{{ t('assetDetail.perDay') }}</span>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Financial Info -->
      <van-cell-group v-if="asset.asset_type === 'financial'" inset :title="t('assetDetail.sectionFinancialInfo')">
        <van-cell v-if="asset.institution" :title="t('assetDetail.fieldInstitution')" :value="asset.institution" />
        <van-cell v-if="asset.interest_rate" :title="t('assetDetail.fieldInterestRate')" :value="`${asset.interest_rate}%`" />
        <van-cell v-if="asset.maturity_date" :title="t('assetDetail.fieldMaturityDate')" :value="asset.maturity_date" />
        <van-cell v-if="asset.return_rate !== undefined" :title="t('assetDetail.fieldReturnRate')">
          <template #value>
            <span :class="(asset.return_rate || 0) >= 0 ? 'positive' : 'negative'">
              {{ (asset.return_rate || 0) >= 0 ? '+' : '' }}{{ (asset.return_rate || 0).toFixed(2) }}%
            </span>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Sell Info (when sold) -->
      <van-cell-group v-if="asset.status === 'sold'" inset :title="t('assetDetail.sectionSellInfo')">
        <van-cell :title="t('assetDetail.fieldSellPrice')">
          <template #value><MoneyDisplay :amount="asset.sell_price || 0" /></template>
        </van-cell>
        <van-cell v-if="asset.sell_fee" :title="t('assetDetail.fieldSellFee')">
          <template #value><MoneyDisplay :amount="asset.sell_fee" /></template>
        </van-cell>
        <van-cell v-if="asset.sell_channel" :title="t('assetDetail.fieldSellChannel')" :value="asset.sell_channel" />
        <van-cell v-if="asset.sell_date" :title="t('assetDetail.fieldSellDate')" :value="asset.sell_date" />
      </van-cell-group>

      <!-- Tags -->
      <van-cell-group v-if="asset.tags?.length" inset :title="t('assetDetail.sectionTags')">
        <van-cell>
          <template #value>
            <div class="tags">
              <van-tag v-for="tag in asset.tags" :key="tag.id" :color="tag.color" size="medium" class="tag">
                {{ tag.name }}
              </van-tag>
            </div>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Notes -->
      <van-cell-group v-if="asset.notes" inset :title="t('assetDetail.sectionNotes')">
        <van-cell :title="asset.notes" />
      </van-cell-group>

      <!-- Valuation History -->
      <van-cell-group v-if="valuations.length" inset :title="t('assetDetail.sectionValuationHistory')">
        <van-cell
          v-for="v in valuations"
          :key="v.id"
          :title="`¥${v.value.toLocaleString()}`"
          :value="v.valued_at.slice(0, 10)"
        />
      </van-cell-group>

      <!-- Buy vs Rent Calculator -->
      <BuyVsRentCalculator :initial-price="asset.purchase_price ?? undefined" />

      <!-- Cost Equivalence -->
      <CostEquivalenceCard :asset-id="asset.id" />

      <!-- Actions -->
      <div class="actions">
        <template v-if="asset.status === 'in_use' || asset.status === 'idle'">
          <van-button block type="primary" :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : $router.push(`/assets/${asset.id}/edit`)">
            {{ t('assetDetail.btnEdit') }}
          </van-button>
          <van-button block type="warning" plain :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : $router.push(`/assets/${asset.id}/sell`)">
            {{ t('assetDetail.btnSell') }}
          </van-button>
          <van-button block type="default" plain :loading="acting" :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : onRetire">
            {{ t('assetDetail.btnRetire') }}
          </van-button>
        </template>
        <template v-else-if="asset.status === 'retired'">
          <van-button block type="success" plain :loading="acting" :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : onReactivate">
            {{ t('assetDetail.btnReactivate') }}
          </van-button>
          <van-button block type="primary" plain :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : $router.push(`/assets/${asset.id}/edit`)">
            {{ t('assetDetail.btnEdit') }}
          </van-button>
        </template>
        <template v-else-if="asset.status === 'sold'">
          <van-button block type="primary" plain :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : $router.push(`/assets/${asset.id}/edit`)">
            {{ t('assetDetail.btnEdit') }}
          </van-button>
        </template>
        <van-button block type="danger" plain :loading="deleting" :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" class="delete-btn" @click="syncing ? null : onDelete">
          {{ t('assetDetail.btnDelete') }}
        </van-button>
      </div>
    </template>

    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAssetStore } from '@/stores/asset'
import * as assetApi from '@/api/assets'
import type { AssetValuation } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import DailyCostChart from '@/components/charts/DailyCostChart.vue'
import BuyVsRentCalculator from '@/components/asset/BuyVsRentCalculator.vue'
import CostEquivalenceCard from '@/components/asset/CostEquivalenceCard.vue'
import { usePageLoading } from '@/composables/usePageLoading'
import { getIconId } from '@/utils/icon'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const assetStore = useAssetStore()
const deleting = ref(false)
const acting = ref(false)
const valuations = ref<AssetValuation[]>([])
const imageError = ref(false)
const { increment, decrement } = usePageLoading()

const asset = computed(() => assetStore.currentAsset)

// Check if this asset is currently syncing
const syncing = computed(() => asset.value ? assetStore.isSyncing(asset.value.id) : false)

const imageUrl = computed(() => {
  if (!asset.value?.image_url) return ''
  if (asset.value.image_url.startsWith('/')) {
    return `/api/v1${asset.value.image_url}`
  }
  return asset.value.image_url
})

function onImageError() {
  imageError.value = true
}

const daysUsed = computed(() => {
  if (!asset.value?.purchase_date) return 0
  const purchase = new Date(asset.value.purchase_date)
  const now = new Date()
  const diff = Math.floor((now.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : 0
})

const statusText = computed(() => {
  const status = asset.value?.status || ''
  const map: Record<string, string> = {
    in_use: t('asset.inUse'),
    idle: t('asset.idle'),
    sold: t('asset.sold'),
    retired: t('asset.retired'),
  }
  return map[status] || ''
})
const statusType = computed(() => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'default'> = {
    in_use: 'success',
    idle: 'warning',
    sold: 'default',
    retired: 'danger',
  }
  return map[asset.value?.status || ''] || 'default'
})

const typeText = computed(() => {
  const map: Record<string, string> = {
    physical: t('asset.typePhysical'),
    financial: t('asset.typeFinancial'),
  }
  return map[asset.value?.asset_type || ''] || ''
})

const usageText = computed(() => {
  const map: Record<string, string> = {
    daily: t('asset.usageDaily'),
    weekly: t('asset.usageWeekly'),
    monthly: t('asset.usageMonthly'),
    rarely: t('asset.usageRarely'),
    idle: t('asset.usageIdle'),
  }
  return map[asset.value?.usage_frequency || ''] || ''
})

const returnClass = computed(() => {
  const rate = asset.value?.return_rate || 0
  return rate >= 0 ? 'positive' : 'negative'
})

const returnText = computed(() => {
  if (!asset.value?.purchase_price || !asset.value?.current_value) return ''
  const diff = asset.value.current_value - asset.value.purchase_price
  const sign = diff >= 0 ? '+' : ''
  return `${sign}¥${diff.toLocaleString()} (${sign}${(asset.value.return_rate || 0).toFixed(2)}%)`
})

async function onRetire() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmRetireAsset', { name: asset.value?.name }) })
    acting.value = true
    await assetStore.retireAsset(asset.value!.id)
    showToast(t('toast.assetRetired'))
  } catch {
    // cancelled
  } finally {
    acting.value = false
  }
}

async function onReactivate() {
  acting.value = true
  try {
    await assetStore.reactivateAsset(asset.value!.id)
    showToast(t('toast.assetReactivated'))
  } finally {
    acting.value = false
  }
}

async function onDelete() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmDelete', { name: asset.value?.name }) })
    deleting.value = true
    await assetStore.deleteAsset(asset.value!.id)
    showToast(t('toast.deleteSuccess'))
    router.replace('/')
  } catch {
    // cancelled
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  increment()
  try {
    const id = route.params.id as string
    await assetStore.fetchAsset(id)
    try {
      const res = await assetApi.getValuations(id)
      valuations.value = res.data
    } catch {
      // non-critical
    }
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.asset-detail-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}

/* ── Hero Card: Pastel Cloud Gradient (light mode) ── */
.hero-card {
  background:
    linear-gradient(135deg,
      rgba(239, 44, 193, 0.10) 0%,
      rgba(189, 187, 255, 0.18) 45%,
      rgba(160, 195, 255, 0.14) 100%),
    #ffffff;
  padding: 20px 16px 16px;
  color: #000000;
  position: relative;
  overflow: hidden;
}

/* Decorative soft blob */
.hero-card::before {
  content: '';
  position: absolute;
  top: -40px;
  right: -30px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(189, 187, 255, 0.22) 0%, transparent 70%);
  pointer-events: none;
}

/* Dark mode: midnight blue + subtle lavender overlay */
[data-theme='dark'] .hero-card {
  background:
    linear-gradient(135deg,
      rgba(189, 187, 255, 0.08) 0%,
      rgba(189, 187, 255, 0.04) 50%,
      transparent 100%),
    #010120;
  color: var(--text-primary);
}
[data-theme='dark'] .hero-card::before {
  background: radial-gradient(circle, rgba(189, 187, 255, 0.10) 0%, transparent 70%);
}

/* Sold state: muted overlay on top of gradient */
.hero-card.sold {
  background:
    linear-gradient(135deg,
      rgba(0, 0, 0, 0.04) 0%,
      rgba(0, 0, 0, 0.02) 100%),
    #f5f5f5;
  color: rgba(0, 0, 0, 0.55);
}
[data-theme='dark'] .hero-card.sold {
  background:
    linear-gradient(135deg,
      rgba(255, 255, 255, 0.03) 0%,
      rgba(255, 255, 255, 0.01) 100%),
    #0d0d1a;
  color: rgba(255, 255, 255, 0.50);
}

.status-badge {
  position: absolute;
  top: 12px;
  right: 12px;
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

.hero-image {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  border: 1px solid rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .hero-image {
  border-color: rgba(255, 255, 255, 0.12);
}

.hero-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.hero-icon {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .hero-icon {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.12);
}

.icon-svg-hero {
  width: 40px;
  height: 40px;
  fill: rgba(0, 0, 0, 0.55);
  color: rgba(0, 0, 0, 0.55);
}
[data-theme='dark'] .icon-svg-hero {
  fill: rgba(255, 255, 255, 0.65);
  color: rgba(255, 255, 255, 0.65);
}

.hero-info {
  flex: 1;
  min-width: 0;
}

/* Asset name: display-level, tight negative tracking */
.hero-name {
  font-size: clamp(18px, 5vw, 22px);
  font-weight: 500;
  letter-spacing: -0.22px;
  line-height: 1.15;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #000000;
}
[data-theme='dark'] .hero-name {
  color: var(--text-primary);
}

/* Mono label style for category */
.hero-category {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.45);
  font-family: 'Georgia', monospace;
  margin-bottom: 8px;
}
[data-theme='dark'] .hero-category {
  color: var(--text-tertiary);
}

.hero-usage {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* Badge: sharp 4px radius, glass-dark on light */
.usage-badge {
  font-size: 11px;
  font-weight: 500;
  background: rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(0, 0, 0, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
}
[data-theme='dark'] .usage-badge {
  background: rgba(255, 255, 255, 0.10);
  color: rgba(255, 255, 255, 0.70);
  border-color: rgba(255, 255, 255, 0.12);
}
.usage-badge.lifespan {
  background: rgba(189, 187, 255, 0.12);
  border-color: rgba(189, 187, 255, 0.20);
  color: rgba(0, 0, 0, 0.55);
}
[data-theme='dark'] .usage-badge.lifespan {
  background: rgba(189, 187, 255, 0.10);
  border-color: rgba(189, 187, 255, 0.18);
  color: rgba(255, 255, 255, 0.60);
}

/* Stats row: glass container, 8px radius, dark-blue-tinted shadow */
.hero-values {
  display: flex;
  align-items: flex-start;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  padding: 12px 0;
  margin-bottom: 8px;
  box-shadow: rgba(1, 1, 32, 0.08) 0px 2px 8px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
[data-theme='dark'] .hero-values {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: rgba(1, 1, 32, 0.40) 0px 2px 8px;
}

.hero-value-item {
  flex: 1;
  text-align: center;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .hero-value-item {
  border-right-color: rgba(255, 255, 255, 0.12);
}
.hero-value-item:last-child {
  border-right: none;
}

/* Mono label for value headers */
.hero-value-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.40);
  font-family: 'Georgia', monospace;
  margin-bottom: 4px;
}
[data-theme='dark'] .hero-value-label {
  color: var(--text-tertiary);
}

.hero-value-item :deep(.money-display) {
  color: #000000;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: -0.16px;
}
[data-theme='dark'] .hero-value-item :deep(.money-display) {
  color: var(--text-primary);
}

.hero-daily-cost {
  font-size: 16px;
  font-weight: 500;
  letter-spacing: -0.16px;
  color: #000000;
}
[data-theme='dark'] .hero-daily-cost {
  color: var(--text-primary);
}

.hero-change {
  font-size: 12px;
  font-weight: 500;
  text-align: center;
}
.hero-change.positive {
  color: #059669;
}
[data-theme='dark'] .hero-change.positive {
  color: var(--color-trend-down);
}
.hero-change.negative {
  color: #dc2626;
}
[data-theme='dark'] .hero-change.negative {
  color: var(--color-trend-up);
}

.sell-summary {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.55);
  margin-top: 4px;
  text-align: center;
}
[data-theme='dark'] .sell-summary {
  color: rgba(255, 255, 255, 0.50);
}

.cat-icon-svg {
  width: 18px;
  height: 18px;
  margin-right: 4px;
  fill: currentColor;
}

.daily-cost {
  color: #d97706;
}
[data-theme='dark'] .daily-cost {
  color: var(--color-trend-warn);
}

.target-cost {
  color: #059669;
}
[data-theme='dark'] .target-cost {
  color: var(--color-trend-down);
}

.positive { color: #059669; }
[data-theme='dark'] .positive { color: var(--color-trend-down); }
.negative { color: #dc2626; }
[data-theme='dark'] .negative { color: var(--color-trend-up); }

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.delete-btn {
  margin-top: 4px;
}
</style>
