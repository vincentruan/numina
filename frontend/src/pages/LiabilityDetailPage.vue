<template>
  <div class="liability-detail-page">
    <PageHeader title="负债详情" />

    <template v-if="liability">
      <!-- Value Card -->
      <div class="value-card">
        <div class="value-label">剩余本金</div>
        <MoneyDisplay :amount="liability.remaining_amount" size="large" />
        <div class="progress-info">
          已还 ¥{{ paidAmount.toLocaleString() }} / 共 ¥{{ liability.original_amount.toLocaleString() }}
        </div>
        <van-progress
          :percentage="paidPercent"
          :stroke-width="8"
          color="#07c160"
          track-color="rgba(255,255,255,0.3)"
          :show-pivot="false"
          class="progress-bar"
        />
      </div>

      <!-- Basic Info -->
      <van-cell-group inset title="基本信息">
        <van-cell title="名称" :value="liability.name" />
        <van-cell title="类型">
          <template #value>
            <span>{{ categoryIcon }} {{ categoryText }}</span>
          </template>
        </van-cell>
        <van-cell title="状态">
          <template #value>
            <van-tag :type="liability.is_active ? 'primary' : 'success'" size="medium">
              {{ liability.is_active ? '还款中' : '已结清' }}
            </van-tag>
          </template>
        </van-cell>
        <van-cell title="原始金额">
          <template #value><MoneyDisplay :amount="liability.original_amount" /></template>
        </van-cell>
        <van-cell v-if="liability.monthly_payment" title="月供">
          <template #value><MoneyDisplay :amount="liability.monthly_payment" /></template>
        </van-cell>
        <van-cell v-if="liability.interest_rate" title="年利率" :value="`${liability.interest_rate}%`" />
      </van-cell-group>

      <!-- Detail Info -->
      <van-cell-group inset title="详细信息">
        <van-cell v-if="liability.institution" title="贷款机构" :value="liability.institution" />
        <van-cell v-if="liability.start_date" title="起始日期" :value="liability.start_date" />
        <van-cell v-if="liability.end_date" title="预计还清" :value="liability.end_date" />
        <van-cell v-if="liability.linked_asset_id" title="关联资产" value="查看关联资产" is-link @click="goToAsset" />
      </van-cell-group>

      <!-- Notes -->
      <van-cell-group v-if="liability.notes" inset title="备注">
        <van-cell :title="liability.notes" />
      </van-cell-group>

      <!-- Actions -->
      <div class="actions">
        <van-button v-if="liability.is_active" block type="success" @click="showPayment = true">
          记录还款
        </van-button>
        <van-button block type="primary" plain @click="$router.push(`/liabilities/${liability.id}/edit`)">
          编辑
        </van-button>
        <van-button block type="danger" plain @click="onDelete" :loading="deleting">
          删除
        </van-button>
      </div>
    </template>

    <van-loading v-else class="page-loading" />

    <!-- Payment Dialog -->
    <van-dialog
      v-model:show="showPayment"
      title="记录还款"
      show-cancel-button
      confirm-button-text="确认还款"
      :before-close="onPaymentConfirm"
    >
      <div class="payment-dialog">
        <div class="payment-hint">剩余本金 ¥{{ liability?.remaining_amount.toLocaleString() }}</div>
        <van-field
          v-model="paymentAmount"
          type="number"
          label="还款金额"
          placeholder="请输入还款金额"
          input-align="right"
        >
          <template #button>元</template>
        </van-field>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useLiabilityStore } from '@/stores/liability'
import PageHeader from '@/components/common/PageHeader.vue'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'

const route = useRoute()
const router = useRouter()
const liabilityStore = useLiabilityStore()
const deleting = ref(false)
const showPayment = ref(false)
const paymentAmount = ref('')

const liability = computed(() => liabilityStore.currentLiability)

const categoryMap: Record<string, { text: string; icon: string }> = {
  mortgage: { text: '房贷', icon: '🏠' },
  car_loan: { text: '车贷', icon: '🚗' },
  credit_card: { text: '信用卡', icon: '💳' },
  personal_loan: { text: '个人贷款', icon: '💰' },
  other: { text: '其他', icon: '📋' }
}

const categoryText = computed(() => categoryMap[liability.value?.category || '']?.text || '')
const categoryIcon = computed(() => categoryMap[liability.value?.category || '']?.icon || '📋')

const paidAmount = computed(() => {
  if (!liability.value) return 0
  return liability.value.original_amount - liability.value.remaining_amount
})

const paidPercent = computed(() => {
  if (!liability.value || liability.value.original_amount === 0) return 0
  return Math.round((paidAmount.value / liability.value.original_amount) * 100)
})

function goToAsset() {
  if (liability.value?.linked_asset_id) {
    router.push(`/assets/${liability.value.linked_asset_id}`)
  }
}

async function onPaymentConfirm(action: string) {
  if (action === 'confirm') {
    const amount = parseFloat(paymentAmount.value)
    if (isNaN(amount) || amount <= 0) {
      showToast('请输入有效金额')
      return false
    }
    if (amount > (liability.value?.remaining_amount || 0)) {
      showToast('还款金额不能超过剩余本金')
      return false
    }
    try {
      await liabilityStore.recordPayment(liability.value!.id, amount)
      showToast('还款成功')
      paymentAmount.value = ''
      return true
    } catch {
      return false
    }
  }
  paymentAmount.value = ''
  return true
}

async function onDelete() {
  try {
    await showConfirmDialog({ title: '确认删除', message: `确定要删除「${liability.value?.name}」吗？` })
    deleting.value = true
    await liabilityStore.deleteLiability(liability.value!.id)
    showToast('已删除')
    router.back()
  } catch {
    // cancelled
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  const id = route.params.id as string
  liabilityStore.fetchLiability(id)
})
</script>

<style scoped>
.liability-detail-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}
.value-card {
  background: linear-gradient(135deg, #ee0a24 0%, #ff6034 100%);
  padding: 20px 16px;
  color: #fff;
  text-align: center;
}
.value-label {
  font-size: 13px;
  opacity: 0.8;
}
.value-card :deep(.money-display) {
  color: #fff;
}
.progress-info {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 8px;
}
.progress-bar {
  margin-top: 8px;
}
.actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.page-loading {
  display: flex;
  justify-content: center;
  padding-top: 40vh;
}
.payment-dialog {
  padding: 16px;
}
.payment-hint {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: 12px;
  text-align: center;
}
</style>
