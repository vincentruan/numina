<template>
  <div class="asset-detail-page">
    <PageHeader title="资产详情" />

    <template v-if="asset">
      <!-- Value Card -->
      <div class="value-card" :class="asset.status === 'sold' ? 'sold' : ''">
        <div class="value-label">{{ asset.status === 'sold' ? '出售价格' : '当前价值' }}</div>
        <MoneyDisplay :amount="asset.status === 'sold' ? (asset.sell_price || 0) : (asset.current_value || 0)" size="large" />
        <div v-if="asset.status !== 'sold'" class="value-change" :class="returnClass">
          {{ returnText }}
        </div>
        <div v-if="asset.status === 'sold'" class="sell-summary">
          净回收 ¥{{ (asset.sell_price! - (asset.sell_fee || 0)).toLocaleString() }}
          <span v-if="asset.sell_date"> · {{ asset.sell_date }}</span>
        </div>
        <van-tag v-if="asset.status !== 'in_use'" class="status-badge" :type="statusType" size="medium">
          {{ statusText }}
        </van-tag>
      </div>

      <!-- Basic Info -->
      <van-cell-group inset title="基本信息">
        <van-cell title="名称" :value="asset.name" />
        <van-cell title="类型" :value="asset.asset_type === 'physical' ? '实物资产' : '金融资产'" />
        <van-cell title="分类" :value="asset.category?.name || '未分类'">
          <template #icon>
            <span class="cat-icon">{{ asset.category?.icon }}</span>
          </template>
        </van-cell>
        <van-cell title="购入价格">
          <template #value><MoneyDisplay :amount="asset.purchase_price" /></template>
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
          <van-button block type="primary" @click="$router.push(`/assets/${asset.id}/edit`)">
            编辑
          </van-button>
          <van-button block type="warning" plain @click="$router.push(`/assets/${asset.id}/sell`)">
            出售资产
          </van-button>
          <van-button block type="default" plain @click="onRetire" :loading="acting">
            报废/退役
          </van-button>
        </template>
        <template v-else-if="asset.status === 'retired'">
          <van-button block type="success" plain @click="onReactivate" :loading="acting">
            恢复服役
          </van-button>
          <van-button block type="primary" plain @click="$router.push(`/assets/${asset.id}/edit`)">
            编辑
          </van-button>
        </template>
        <template v-else-if="asset.status === 'sold'">
          <van-button block type="primary" plain @click="$router.push(`/assets/${asset.id}/edit`)">
            编辑
          </van-button>
        </template>
        <van-button block type="danger" plain @click="onDelete" :loading="deleting" class="delete-btn">
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
import { useAssetStore } from '@/stores/asset'
import * as assetApi from '@/api/assets'
import type { AssetValuation } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'

const route = useRoute()
const router = useRouter()
const assetStore = useAssetStore()
const deleting = ref(false)
const acting = ref(false)
const valuations = ref<AssetValuation[]>([])

const asset = computed(() => assetStore.currentAsset)

const statusMap: Record<string, { text: string; type: 'primary' | 'success' | 'warning' | 'danger' | 'default' }> = {
  in_use: { text: '使用中', type: 'success' },
  idle: { text: '闲置', type: 'warning' },
  sold: { text: '已出售', type: 'default' },
  retired: { text: '已报废', type: 'danger' }
}

const statusText = computed(() => statusMap[asset.value?.status || '']?.text || '')
const statusType = computed(() => statusMap[asset.value?.status || '']?.type || 'default')

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

async function onRetire() {
  try {
    await showConfirmDialog({ title: '确认退役', message: `确定要将「${asset.value?.name}」标记为退役吗？` })
    acting.value = true
    await assetStore.retireAsset(asset.value!.id)
    showToast('已退役')
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
    showToast('已恢复服役')
  } finally {
    acting.value = false
  }
}

async function onDelete() {
  try {
    await showConfirmDialog({ title: '确认删除', message: `确定要删除「${asset.value?.name}」吗？` })
    deleting.value = true
    await assetStore.deleteAsset(asset.value!.id)
    showToast('已删除')
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
  background: #f7f8fa;
  min-height: 100vh;
  padding-bottom: 20px;
}
.value-card {
  background: linear-gradient(135deg, #1989fa 0%, #2b5cff 100%);
  padding: 20px 16px;
  color: #fff;
  text-align: center;
  position: relative;
}
.value-card.sold {
  background: linear-gradient(135deg, #646566 0%, #969799 100%);
}
.value-label {
  font-size: 13px;
  opacity: 0.8;
}
.value-card :deep(.money-display) {
  color: #fff;
}
.value-change {
  font-size: 13px;
  margin-top: 4px;
}
.value-change.positive { color: #a8f0c6; }
.value-change.negative { color: #ffb3b3; }
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
.cat-icon {
  margin-right: 4px;
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
