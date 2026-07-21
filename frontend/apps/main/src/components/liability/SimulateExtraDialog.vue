<script setup lang="ts">
import { ref, watch } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { simulateLiability } from '@/api/liabilities'
import type { Liability, LiabilitySimResult } from '@/types'

const props = defineProps<{ show: boolean; liability: Liability; baseline: LiabilitySimResult | null }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void }>()
const { t } = useI18n()
const { format } = useCurrency()

const extraStr = ref('')
const result = ref<LiabilitySimResult | null>(null)
const loading = ref(false)

watch(
  () => props.show,
  (v) => {
    if (v) {
      extraStr.value = ''
      result.value = null
    }
  },
)

async function onSimulate() {
  const extra = extraStr.value.trim()
  const extraNum = Number(extra)
  if (!extra || !Number.isFinite(extraNum) || extraNum < 0) {
    showFailToast(t('liability.interest.invalidExtra'))
    return
  }
  loading.value = true
  try {
    const r = await simulateLiability({
      remaining: String(props.liability.remaining_amount),
      annual_rate: String(props.liability.interest_rate),
      monthly_payment: props.liability.monthly_payment ? String(props.liability.monthly_payment) : undefined,
      extra_monthly: extra,
    })
    result.value = r.data
    if (r.data.warning) {
      showSuccessToast(r.data.warning)
    }
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:show', false)
}
</script>

<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    @update:show="emit('update:show', $event)"
  >
    <div class="sim-dialog">
      <div class="dialog-title">{{ t('liability.interest.simulateTitle') }}</div>
      <van-field
        v-model="extraStr"
        type="number"
        inputmode="decimal"
        :label="t('liability.interest.extraLabel')"
        :placeholder="t('liability.interest.extraPlaceholder')"
      />
      <van-button block type="primary" :loading="loading" class="sim-btn" @click="onSimulate">
        {{ t('liability.interest.simulate') }}
      </van-button>

      <div v-if="result" class="sim-result">
        <div class="sim-row">
          <span>{{ t('liability.interest.totalInterest') }}</span>
          <span>{{ format(Number(result.total_interest)) }}</span>
        </div>
        <div class="sim-row">
          <span>{{ t('liability.interest.monthsLeft') }}</span>
          <span>{{ result.months }} {{ t('liability.interest.monthsUnit') }}</span>
        </div>
        <template v-if="result.savings_vs_baseline && props.baseline">
          <div class="sim-row sim-highlight">
            <span>{{ t('liability.interest.savings', { amount: '' }).trim() }}</span>
            <span>{{ format(Number(result.savings_vs_baseline)) }}</span>
          </div>
          <div v-if="result.months_saved" class="sim-row">
            <span>{{ t('liability.interest.monthsSaved', { n: result.months_saved }) }}</span>
          </div>
        </template>
        <div v-if="result.warning" class="sim-warning">{{ result.warning }}</div>
      </div>

      <van-button block plain class="sim-close" @click="close">{{ t('common.close') }}</van-button>
    </div>
  </van-popup>
</template>

<style scoped>
.sim-dialog {
  padding: 16px;
}
.dialog-title {
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 12px;
}
.sim-btn {
  margin: 12px 0;
}
.sim-result {
  padding: 10px 0;
  font-size: 13px;
}
.sim-row {
  display: flex;
  justify-content: space-between;
  margin: 4px 0;
}
.sim-highlight {
  color: #07c160;
  font-weight: 600;
}
.sim-warning {
  font-size: 12px;
  color: #ee0a24;
  margin-top: 4px;
}
.sim-close {
  margin-top: 8px;
}
</style>
