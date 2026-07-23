<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { useAffordBar } from '@/composables/useAffordBar'
import type { Wish } from '@/types'

const props = defineProps<{ wish: Wish; netWorth?: number }>()
const emit = defineEmits<{ (e: 'record'): void; (e: 'showLog'): void }>()
const { t } = useI18n()
const { format } = useCurrency()
const { state, accelerate, purchasingPower, progressPercent, progressColor, price, saved } = useAffordBar(
  () => props.wish,
  () => props.netWorth ?? 0,
)

const savedLabel = computed(() => format(Number(saved.value)))
const priceLabel = computed(() => format(Number(price.value)))
</script>

<template>
  <div v-if="wish.expected_price" class="savings-progress">
    <div class="sp-bar-row">
      {{ t('wish.savings.saved', { saved: savedLabel, price: priceLabel, pct: progressPercent }) }}
    </div>
    <van-progress :percentage="progressPercent" :color="progressColor" :show-pivot="false" stroke-width="8" />
    <div class="sp-eta">
      <span v-if="state.kind === 'unset_monthly'">{{ t('wish.savings.setMonthly') }}</span>
      <span v-else-if="state.kind === 'reached'">{{ t('wish.savings.reached') }}</span>
      <span v-else-if="state.kind === 'progress'">{{ t('wish.savings.eta', { n: state.months }) }}</span>
    </div>
    <div v-if="accelerate" class="sp-accelerate">! {{ t('wish.savings.needAccelerate', { amount: accelerate.requiredMonthly }) }}</div>
    <div class="sp-secondary">
      {{ t('wish.savings.purchasingPower', { net: format(purchasingPower.netWorth), covered: purchasingPower.covered ? t('wish.savings.covered') : t('wish.savings.notCovered') }) }}
    </div>
    <div class="sp-actions">
      <van-button size="small" type="primary" @click="emit('record')">{{ t('wish.savings.record') }}</van-button>
      <van-button size="small" plain @click="emit('showLog')">
        {{ t('wish.savings.log') }} ({{ wish.savings_count ?? 0 }})
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.savings-progress {
  margin: 8px 16px;
  padding: 10px 12px;
  background: var(--card-bg, #fff);
  border-radius: 10px;
}
.sp-bar-row {
  font-size: 13px;
  color: var(--text-primary, #323233);
  margin-bottom: 6px;
}
.sp-eta {
  font-size: 12px;
  color: var(--text-secondary, #969799);
  margin-top: 6px;
}
.sp-accelerate {
  font-size: 12px;
  color: #ff976a;
  font-weight: 600;
  margin-top: 2px;
}
.sp-secondary {
  font-size: 11px;
  color: var(--van-text-color-3, #c8c9cc);
  margin-top: 4px;
}
.sp-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
</style>
