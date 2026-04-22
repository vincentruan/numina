<template>
  <div class="asset-sell-page">
    <PageHeader title="出售资产" />

    <template v-if="asset">
      <div class="asset-summary">
        <div class="asset-name">{{ asset.name }}</div>
        <div class="asset-value">当前价值 ¥{{ (asset.current_value || 0).toLocaleString() }}</div>
      </div>

      <van-cell-group inset title="出售信息">
        <van-field
          v-model="form.sell_price"
          type="number"
          label="出售价格"
          placeholder="请输入出售价格"
          required
          input-align="right"
        >
          <template #button>元</template>
        </van-field>
        <van-field
          v-model="form.sell_fee"
          type="number"
          label="手续费"
          placeholder="0"
          input-align="right"
        >
          <template #button>元</template>
        </van-field>
        <van-field
          v-model="form.sell_channel"
          label="出售渠道"
          placeholder="如：闲鱼、转转、自售"
          input-align="right"
        />
        <van-field
          v-model="form.notes"
          label="备注"
          placeholder="可选"
          input-align="right"
        />
      </van-cell-group>

      <!-- Preview -->
      <van-cell-group v-if="sellPrice > 0" inset title="收益预览">
        <van-cell title="净回收金额">
          <template #value>
            <span class="highlight">¥{{ netRecovery.toLocaleString() }}</span>
          </template>
        </van-cell>
        <van-cell title="盈亏">
          <template #value>
            <span :class="profitLoss >= 0 ? 'positive' : 'negative'">
              {{ profitLoss >= 0 ? '+' : '' }}¥{{ profitLoss.toLocaleString() }}
            </span>
          </template>
        </van-cell>
        <van-cell v-if="asset.purchase_date" title="持有天数" :value="`${daysHeld} 天`" />
      </van-cell-group>

      <div class="actions">
        <van-button block type="warning" :loading="submitting" @click="onSubmit">
          确认出售
        </van-button>
        <van-button block plain @click="$router.back()">取消</van-button>
      </div>
    </template>

    <van-loading v-else class="page-loading" />

    <!-- Result Dialog -->
    <van-dialog
      v-model:show="showResult"
      title="出售成功"
      confirm-button-text="返回列表"
      :before-close="onResultClose"
    >
      <div v-if="sellResult" class="result-dialog">
        <div class="result-row">
          <span>净回收</span>
          <span class="highlight">¥{{ sellResult.net_recovery.toLocaleString() }}</span>
        </div>
        <div class="result-row">
          <span>总盈亏</span>
          <span :class="sellResult.total_profit_loss >= 0 ? 'positive' : 'negative'">
            {{ sellResult.total_profit_loss >= 0 ? '+' : '' }}¥{{ sellResult.total_profit_loss.toLocaleString() }}
          </span>
        </div>
        <div class="result-row">
          <span>实际日耗</span>
          <span>¥{{ sellResult.actual_daily_cost }}/天</span>
        </div>
        <div v-if="sellResult.target_daily_cost" class="result-row">
          <span>目标日耗</span>
          <span>¥{{ sellResult.target_daily_cost }}/天</span>
        </div>
        <div class="result-row">
          <span>持有天数</span>
          <span>{{ sellResult.days_held }} 天</span>
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useAssetStore } from '@/stores/asset'
import { useDashboardStore } from '@/stores/dashboard'
import type { AssetSellResponse } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'

const route = useRoute()
const router = useRouter()
const assetStore = useAssetStore()
const dashboardStore = useDashboardStore()
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
  const cost = asset.value?.purchase_price || 0
  return Math.round((netRecovery.value - cost) * 100) / 100
})
const daysHeld = computed(() => {
  if (!asset.value?.purchase_date) return 0
  const ms = Date.now() - new Date(asset.value.purchase_date).getTime()
  return Math.floor(ms / 86400000)
})

async function onSubmit() {
  if (sellPrice.value <= 0) {
    showToast('⚠️ 请输入出售价格')
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
    showToast('❌ 出售失败，请重试')
  } finally {
    submitting.value = false
  }
}

function onResultClose(action: string) {
  if (action === 'confirm') {
    router.push('/assets')
  }
  return true
}

onMounted(() => {
  const id = route.params.id as string
  if (!assetStore.currentAsset || assetStore.currentAsset.id !== id) {
    assetStore.fetchAsset(id)
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
.highlight { color: #1989fa; font-weight: 600; }
.positive { color: #07c160; font-weight: 600; }
.negative { color: #ee0a24; font-weight: 600; }
.page-loading {
  display: flex;
  justify-content: center;
  padding-top: 40vh;
}
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
