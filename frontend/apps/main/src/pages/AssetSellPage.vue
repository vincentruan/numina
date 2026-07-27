<template>
  <div class="asset-sell-page">
    <PageHeader :title="t('assetSell.pageTitle')" />

    <template v-if="asset">
      <div class="asset-summary">
        <div class="asset-name">{{ asset.name }}</div>
        <div class="asset-value">{{ t('assetSell.currentValue', { value: (asset.current_value || 0).toLocaleString() }) }}</div>
      </div>

      <van-cell-group inset :title="t('assetSell.sectionSellInfo')">
        <van-field
          v-model="form.sell_price"
          type="number"
          :label="t('assetSell.sellPrice')"
          :placeholder="t('assetSell.sellPricePlaceholder')"
          required
          input-align="right"
        >
          <template #button>{{ t('assetSell.unit') }}</template>
        </van-field>
        <van-field
          v-model="form.sell_fee"
          type="number"
          :label="t('assetSell.sellFee')"
          :placeholder="t('assetSell.sellFeePlaceholder')"
          input-align="right"
        >
          <template #button>{{ t('assetSell.unit') }}</template>
        </van-field>
        <van-field
          v-model="form.sell_channel"
          :label="t('assetSell.sellChannel')"
          :placeholder="t('assetSell.sellChannelPlaceholder')"
          input-align="right"
        />
        <van-field
          v-model="form.notes"
          :label="t('assetSell.notes')"
          :placeholder="t('assetSell.notesPlaceholder')"
          input-align="right"
        />
      </van-cell-group>

      <!-- Preview -->
      <van-cell-group v-if="sellPrice > 0" inset :title="t('assetSell.sectionPreview')">
        <van-cell :title="t('assetSell.netRecovery')">
          <template #value>
            <span class="highlight">{{ currency.formatIn(netRecovery, asset.currency) }}</span>
          </template>
        </van-cell>
        <van-cell :title="t('assetSell.profitLoss')">
          <template #value>
            <span :class="profitLoss >= 0 ? 'positive' : 'negative'">
              {{ profitLoss >= 0 ? '+' : '-' }}{{ currency.formatIn(Math.abs(profitLoss), asset.currency) }}
            </span>
          </template>
        </van-cell>
        <van-cell v-if="asset.purchase_date" :title="t('assetSell.daysHeld')" :value="t('assetSell.daysUnit', { days: daysHeld })" />
      </van-cell-group>

      <div class="actions">
        <van-button block type="warning" :loading="submitting" @click="onSubmit">
          {{ t('assetSell.confirmBtn') }}
        </van-button>
        <van-button block plain @click="$router.back()">{{ t('assetSell.cancelBtn') }}</van-button>
      </div>
    </template>

    <!-- Result Dialog -->
    <van-dialog
      v-model:show="showResult"
      :title="t('assetSell.resultTitle')"
      :confirm-button-text="t('assetSell.resultConfirmBtn')"
      :before-close="onResultClose"
    >
      <div v-if="sellResult && asset" class="result-dialog">
        <div class="result-row">
          <span>{{ t('assetSell.resultNetRecovery') }}</span>
          <span class="highlight">{{ currency.formatIn(Number(sellResult.net_recovery), asset.currency) }}</span>
        </div>
        <div class="result-row">
          <span>{{ t('assetSell.resultProfitLoss') }}</span>
          <span :class="Number(sellResult.total_profit_loss) >= 0 ? 'positive' : 'negative'">
            {{ Number(sellResult.total_profit_loss) >= 0 ? '+' : '-' }}{{ currency.formatIn(Math.abs(Number(sellResult.total_profit_loss)), asset.currency) }}
          </span>
        </div>
        <div class="result-row">
          <span>{{ t('assetSell.resultDailyCost') }}</span>
          <span>{{ currency.formatIn(Number(sellResult.actual_daily_cost), asset.currency) }}{{ t('assetSell.perDay') }}</span>
        </div>
        <div v-if="sellResult.target_daily_cost" class="result-row">
          <span>{{ t('assetSell.resultTargetDailyCost') }}</span>
          <span>{{ currency.formatIn(Number(sellResult.target_daily_cost), asset.currency) }}{{ t('assetSell.perDay') }}</span>
        </div>
        <div class="result-row">
          <span>{{ t('assetSell.resultDaysHeld') }}</span>
          <span>{{ t('assetSell.daysUnit', { days: sellResult.days_held }) }}</span>
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showFailToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAssetStore } from '@/stores/asset'
import { useDashboardStore } from '@/stores/dashboard'
import type { AssetSellResponse } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'
import { usePageLoading } from '@/composables/usePageLoading'
import { useCurrency } from '@/composables/useCurrency'
import { parseLocalDate } from '@/utils/format'

const { t } = useI18n()
const currency = useCurrency()

const route = useRoute()
const router = useRouter()
const assetStore = useAssetStore()
const dashboardStore = useDashboardStore()
const { increment, decrement } = usePageLoading()
const submitting = ref(false)
const showResult = ref(false)
const sellResult = ref<AssetSellResponse | null>(null)

const form = ref({
  sell_price: '',
  sell_fee: '',
  sell_channel: '',
  notes: '',
})

const asset = computed(() => assetStore.currentAsset)

const sellPrice = computed(() => parseFloat(form.value.sell_price) || 0)
const sellFee = computed(() => parseFloat(form.value.sell_fee) || 0)
const netRecovery = computed(() => Math.round((sellPrice.value - sellFee.value) * 100) / 100)
const profitLoss = computed(() => {
  const cost = Number(asset.value?.purchase_price) || 0
  return Math.round((netRecovery.value - cost) * 100) / 100
})
const daysHeld = computed(() => {
  if (!asset.value?.purchase_date) return 0
  const ms = Date.now() - parseLocalDate(asset.value.purchase_date).getTime()
  return Math.floor(ms / 86400000)
})

async function onSubmit() {
  if (sellPrice.value <= 0) {
    showToast(t('toast.assetSellPriceRequired'))
    return
  }
  try {
    await showConfirmDialog({
      title: t('assetSell.confirmTitle'),
      message: t('assetSell.confirmMessage', {
        name: asset.value?.name,
        price: sellPrice.value,
      }),
    })
  } catch {
    // User cancelled
    return
  }
  submitting.value = true
  try {
    const result = await assetStore.sellAsset(asset.value!.id, {
      sell_price: sellPrice.value,
      sell_fee: sellFee.value || undefined,
      sell_channel: form.value.sell_channel || undefined,
      notes: form.value.notes || undefined,
    })
    sellResult.value = result
    showResult.value = true
    dashboardStore.fetchAll()
  } catch {
    showFailToast(t('toast.assetSellFailed'))
  } finally {
    submitting.value = false
  }
}

function onResultClose(action: string) {
  if (action === 'confirm') {
    router.push({ path: '/finance', query: { tab: 'assets' } })
  }
  return true
}

defineExpose({ onResultClose })

onMounted(async () => {
  increment()
  try {
    const id = route.params.id as string
    if (!assetStore.currentAsset || assetStore.currentAsset.id !== id) {
      await assetStore.fetchAsset(id)
    }
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.asset-sell-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}
.asset-summary {
  background: linear-gradient(135deg, #ff976a 0%, #ff6034 100%);
  padding: 20px 16px;
  color: #fff;
  text-align: center;
}
.asset-name {
  font-size: 18px;
  font-weight: 600;
}
.asset-value {
  font-size: 13px;
  opacity: 0.85;
  margin-top: 4px;
}
.actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.highlight { color: var(--color-primary); font-weight: 600; }
.positive { color: #07c160; font-weight: 600; }
.negative { color: #ee0a24; font-weight: 600; }
.result-dialog {
  padding: 16px;
}
.result-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--separator);
  font-size: 14px;
}
.result-row:last-child {
  border-bottom: none;
}
</style>
