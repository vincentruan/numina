<template>
  <van-cell-group inset :title="t('costEquivalence.title')">
    <van-loading v-if="loading" class="card-loading" />
    <template v-else-if="result">
      <van-cell :title="t('costEquivalence.heldDays')" :value="result.held_days != null ? `${result.held_days} ${t('costEquivalence.daysUnit')}` : '--'" />
      <van-cell :title="t('costEquivalence.dailyCost')" :value="result.daily_cost != null ? format(Number(result.daily_cost)) : '--'" />
      <van-cell
        :title="t('costEquivalence.timeCost', { symbol: symbol })"
        :value="result.time_cost_hours != null ? `${result.time_cost_hours.toFixed(1)} ${t('costEquivalence.hoursUnit')}` : '--'"
      />
      <van-cell
        :title="t('costEquivalence.opportunityCost')"
        :value="result.opportunity_cost != null ? format(Number(result.opportunity_cost)) : '--'"
      />
    </template>
    <van-empty v-else :description="t('costEquivalence.noData')" />
  </van-cell-group>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getCostEquivalence, type CostEquivalenceResult } from '@/api/assetsAnalysis'
import { useCurrency } from '@/composables/useCurrency'
import { CURRENCY_SYMBOLS } from '@/utils/format'

const props = defineProps<{ assetId: string }>()

const { t } = useI18n()
const { format, currency } = useCurrency()

const symbol = computed(() => CURRENCY_SYMBOLS[currency.value] || currency.value)

const loading = ref(false)
const result = ref<CostEquivalenceResult | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    result.value = await getCostEquivalence(props.assetId)
  } catch {
    // non-critical, show empty state
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.card-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}
</style>
