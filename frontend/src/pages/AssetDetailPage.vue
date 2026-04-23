<template>
  <div class="asset-detail-page">
    <PageHeader title="资产详情" />

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
            <svg class="icon-svg-hero" aria-hidden="true">
              <use :href="`#${getIconId(asset.category?.icon)}`" />
            </svg>
          </div>
          <div class="hero-info">
            <div class="hero-name">{{ asset.name }}</div>
            <div class="hero-category">{{ asset.category?.name || '未分类' }}</div>
            <div class="hero-usage">
              <span v-if="daysUsed > 0" class="usage-badge">已使用 {{ daysUsed }} 天</span>
              <span v-if="asset.expected_lifespan_days" class="usage-badge lifespan">预计 {{ asset.expected_lifespan_days }} 天</span>
            </div>
          </div>
        </div>
        <div class="hero-values">
          <div class="hero-value-item">
            <div class="hero-value-label">{{ asset.status === 'sold' ? '出售价格' : '当前价值' }}</div>
            <MoneyDisplay
            :amount="asset.status === 'sold' ? (asset.sell_price || 0) : (asset.current_value || 0)"
            size="large"
            :source-currency="asset.currency"
            :original-value="asset.status === 'sold' ? (asset.sell_price || 0) : (asset.current_value || 0)"
          />
          </div>
          <div class="hero-value-item">
            <div class="hero-value-label">购入价格</div>
            <MoneyDisplay
              :amount="asset.purchase_price"
              :source-currency="asset.currency"
              :original-value="asset.purchase_price"
            />
          </div>
          <div v-if="asset.daily_cost != null && asset.daily_cost > 0" class="hero-value-item">
            <div class="hero-value-label">日均成本</div>
            <div class="hero-daily-cost">¥{{ asset.daily_cost.toFixed(2) }}</div>
          </div>
        </div>
        <div v-if="asset.status !== 'sold'" class="hero-change" :class="returnClass">
          {{ returnText }}
        </div>
        <div v-if="asset.status === 'sold'" class="sell-summary">
          净回收 ¥{{ (asset.sell_price! - (asset.sell_fee || 0)).toLocaleString() }}
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
      <van-cell-group inset title="基本信息">
        <van-cell title="名称" :value="asset.name" />
        <van-cell title="类型" :value="typeText" />
        <van-cell title="分类" :value="asset.category?.name || '未分类'">
          <template #icon>
            <svg class="cat-icon-svg" aria-hidden="true">
              <use :href="`#${getIconId(asset.category?.icon)}`" />
            </svg>
          </template>
        </van-cell>
        <van-cell title="购入价格">
          <template #value>
            <MoneyDisplay
              :amount="asset.purchase_price"
              :source-currency="asset.currency"
              :original-value="asset.purchase_price"
            />
          </template>
        </van-cell>
        <van-cell title="购入日期" :value="asset.purchase_date" />
        <van-cell title="状态">
          <template #value>
            <van-tag :type="statusType">{{ statusText }}</van-tag>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Physical Info -->
      <van-cell-group v-if="asset.asset_type === 'physical'" inset title="实物信息">
        <van-cell v-if="asset.location" title="存放位置" :value="asset.location" />
        <van-cell v-if="asset.expected_lifespan_days" title="预期寿命" :value="`${asset.expected_lifespan_days} 天`" />
        <van-cell v-if="asset.annual_maintenance_cost" title="年维护费">
          <template #value><MoneyDisplay :amount="asset.annual_maintenance_cost" /></template>
        </van-cell>
        <van-cell v-if="asset.usage_frequency" title="使用频率" :value="usageText" />
        <van-cell v-if="asset.daily_cost" title="日耗">
          <template #value>
            <span class="daily-cost">¥{{ asset.daily_cost.toFixed(2) }}/天</span>
          </template>
        </van-cell>
        <van-cell v-if="asset.target_daily_cost" title="目标日耗">
          <template #value>
            <span class="target-cost">¥{{ asset.target_daily_cost.toFixed(2) }}/天</span>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Financial Info -->
      <van-cell-group v-if="asset.asset_type === 'financial'" inset title="金融信息">
        <van-cell v-if="asset.institution" title="金融机构" :value="asset.institution" />
        <van-cell v-if="asset.interest_rate" title="利率" :value="`${asset.interest_rate}%`" />
        <van-cell v-if="asset.maturity_date" title="到期日期" :value="asset.maturity_date" />
        <van-cell v-if="asset.return_rate !== undefined" title="收益率">
          <template #value>
            <span :class="(asset.return_rate || 0) >= 0 ? 'positive' : 'negative'">
              {{ (asset.return_rate || 0) >= 0 ? '+' : '' }}{{ (asset.return_rate || 0).toFixed(2) }}%
            </span>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Sell Info (when sold) -->
      <van-cell-group v-if="asset.status === 'sold'" inset title="出售信息">
        <van-cell title="出售价格">
          <template #value><MoneyDisplay :amount="asset.sell_price || 0" /></template>
        </van-cell>
        <van-cell v-if="asset.sell_fee" title="手续费">
          <template #value><MoneyDisplay :amount="asset.sell_fee" /></template>
        </van-cell>
        <van-cell v-if="asset.sell_channel" title="出售渠道" :value="asset.sell_channel" />
        <van-cell v-if="asset.sell_date" title="出售日期" :value="asset.sell_date" />
      </van-cell-group>

      <!-- Tags -->
      <van-cell-group v-if="asset.tags?.length" inset title="标签">
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
      <van-cell-group v-if="asset.notes" inset title="备注">
        <van-cell :title="asset.notes" />
      </van-cell-group>

      <!-- Valuation History -->
      <van-cell-group v-if="valuations.length" inset title="估值历史">
        <van-cell
          v-for="v in valuations"
          :key="v.id"
          :title="`¥${v.value.toLocaleString()}`"
          :value="v.valued_at.slice(0, 10)"
        />
      </van-cell-group>

      <!-- Actions -->
      <div class="actions">
        <template v-if="asset.status === 'in_use' || asset.status === 'idle'">
          <van-button block type="primary" :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : $router.push(`/assets/${asset.id}/edit`)">
            编辑
          </van-button>
          <van-button block type="warning" plain :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : $router.push(`/assets/${asset.id}/sell`)">
            出售资产
          </van-button>
          <van-button block type="default" plain :loading="acting" :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : onRetire">
            报废/退役
          </van-button>
        </template>
        <template v-else-if="asset.status === 'retired'">
          <van-button block type="success" plain :loading="acting" :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : onReactivate">
            恢复服役
          </van-button>
          <van-button block type="primary" plain :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : $router.push(`/assets/${asset.id}/edit`)">
            编辑
          </van-button>
        </template>
        <template v-else-if="asset.status === 'sold'">
          <van-button block type="primary" plain :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" @click="syncing ? null : $router.push(`/assets/${asset.id}/edit`)">
            编辑
          </van-button>
        </template>
        <van-button block type="danger" plain :loading="deleting" :disabled="syncing" :aria-disabled="syncing ? 'true' : undefined" class="delete-btn" @click="syncing ? null : onDelete">
          删除
        </van-button>
      </div>
    </template>

    <van-loading v-else class="page-loading" />
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

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const assetStore = useAssetStore()
const deleting = ref(false)
const acting = ref(false)
const valuations = ref<AssetValuation[]>([])
const imageError = ref(false)

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

const statusMap: Record<string, { text: string; type: 'primary' | 'success' | 'warning' | 'danger' | 'default' }> = {
  in_use: { text: '服役中', type: 'success' },
  idle: { text: '闲置', type: 'warning' },
  sold: { text: '已出售', type: 'default' },
  retired: { text: '已退役', type: 'danger' }
}

const statusText = computed(() => statusMap[asset.value?.status || '']?.text || '')
const statusType = computed(() => statusMap[asset.value?.status || '']?.type || 'default')

const typeMap: Record<string, string> = { physical: '实物资产', financial: '金融资产' }
const typeText = computed(() => typeMap[asset.value?.asset_type || ''] || '')

const usageMap: Record<string, string> = {
  daily: '每天', weekly: '每周', monthly: '每月', rarely: '很少', idle: '闲置'
}
const usageText = computed(() => usageMap[asset.value?.usage_frequency || ''] || '')

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

/**
 * Get the icon ID for a category icon.
 * If the icon is already an icon ID (starts with 'icon-'), use it directly.
 * Otherwise, fall back to 'icon-other' for emojis or unknown icons.
 */
function getIconId(icon: string | undefined): string {
  if (!icon) return 'icon-other'
  if (icon.startsWith('icon-')) {
    return icon
  }
  // Fallback for emoji or unknown icons
  return 'icon-other'
}

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
    router.back()
  } catch {
    // cancelled
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  const id = route.params.id as string
  await assetStore.fetchAsset(id)
  try {
    const res = await assetApi.getValuations(id)
    valuations.value = res.data
  } catch {
    // non-critical
  }
})
</script>

<style scoped>
.asset-detail-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}
.hero-card {
  background: linear-gradient(135deg, #1677ff 0%, #0052d9 50%, #2b3a8e 100%);
  padding: 20px 16px 16px;
  color: #fff;
  position: relative;
}
.hero-card.sold {
  background: linear-gradient(135deg, #646566 0%, #969799 100%);
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
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
}
.hero-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.hero-icon {
  width: 72px;
  height: 72px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.icon-svg-hero {
  width: 40px;
  height: 40px;
  fill: white;
  color: white;
}
.hero-info {
  flex: 1;
  min-width: 0;
}
.hero-name {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hero-category {
  font-size: 13px;
  opacity: 0.8;
  margin-bottom: 6px;
}
.hero-usage {
  display: flex;
  gap: 6px;
}
.usage-badge {
  font-size: 11px;
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 8px;
  border-radius: 10px;
  backdrop-filter: blur(4px);
}
.usage-badge.lifespan {
  background: rgba(255, 255, 255, 0.12);
}
.hero-values {
  display: flex;
  align-items: flex-start;
  gap: 0;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 12px 0;
  margin-bottom: 8px;
}
.hero-value-item {
  flex: 1;
  text-align: center;
  border-right: 1px solid rgba(255, 255, 255, 0.15);
}
.hero-value-item:last-child {
  border-right: none;
}
.hero-value-label {
  font-size: 11px;
  opacity: 0.75;
  margin-bottom: 4px;
}
.hero-value-item :deep(.money-display) {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}
.hero-daily-cost {
  font-size: 16px;
  font-weight: 600;
  color: #ffd666;
}
.hero-change {
  font-size: 12px;
  text-align: center;
  opacity: 0.9;
}
.hero-change.positive { color: #7dffa8; }
.hero-change.negative { color: #ffb3b3; }
.sell-summary {
  font-size: 13px;
  opacity: 0.85;
  margin-top: 4px;
}
.status-badge {
  position: absolute;
  top: 12px;
  right: 12px;
}
.cat-icon-svg {
  width: 18px;
  height: 18px;
  margin-right: 4px;
  fill: currentColor;
}
.daily-cost {
  color: #ff976a;
}
.target-cost {
  color: #07c160;
}
.positive { color: #07c160; }
.negative { color: #ee0a24; }
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
.page-loading {
  display: flex;
  justify-content: center;
  padding-top: 40vh;
}
</style>
