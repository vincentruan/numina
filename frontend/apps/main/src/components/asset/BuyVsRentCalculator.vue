<template>
  <van-cell-group inset :title="t('buyVsRent.title')">
    <van-field
      v-model="form.purchase_price"
      :label="t('buyVsRent.purchasePrice')"
      type="number"
      :placeholder="t('buyVsRent.purchasePricePlaceholder')"
      input-align="right"
    />
    <van-field
      v-model="form.monthly_rent"
      :label="t('buyVsRent.monthlyRent')"
      type="number"
      :placeholder="t('buyVsRent.monthlyRentPlaceholder')"
      input-align="right"
    />
    <van-field
      v-model="form.usage_months"
      :label="t('buyVsRent.usageMonths')"
      type="number"
      :placeholder="t('buyVsRent.usageMonthsPlaceholder')"
      input-align="right"
    />
    <van-field
      v-model="form.annual_maintenance_cost"
      :label="t('buyVsRent.annualMaintenance')"
      type="number"
      :placeholder="t('buyVsRent.annualMaintenancePlaceholder')"
      input-align="right"
    />
    <van-cell>
      <template #value>
        <van-button type="primary" size="small" :loading="loading" @click="onCalculate">
          {{ t('buyVsRent.calculate') }}
        </van-button>
      </template>
    </van-cell>

    <template v-if="result">
      <van-cell :title="t('buyVsRent.buyTotal')" :value="format(Number(result.buy_total))" />
      <van-cell :title="t('buyVsRent.rentTotal')" :value="format(Number(result.rent_total))" />
      <van-cell
        :title="t('buyVsRent.breakevenMonths')"
        :value="result.breakeven_months != null ? t('buyVsRent.monthsUnit', { n: result.breakeven_months }) : t('buyVsRent.noData')"
      />
      <van-cell :title="t('buyVsRent.recommendation')">
        <template #value>
          <span :class="result.buy_advantage_pct >= 0 ? 'positive' : 'negative'">
            {{ result.recommendation }}
          </span>
        </template>
      </van-cell>
    </template>
  </van-cell-group>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { showToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { calculateBuyVsRent, type BuyVsRentResult } from '@/api/assetsAnalysis'
import { useCurrency } from '@/composables/useCurrency'

const props = defineProps<{ initialPrice?: number }>()

const { t } = useI18n()
const { format } = useCurrency()

const loading = ref(false)
const result = ref<BuyVsRentResult | null>(null)

const form = ref({
  purchase_price: props.initialPrice != null ? String(props.initialPrice) : '',
  monthly_rent: '',
  usage_months: '',
  annual_maintenance_cost: '',
})

async function onCalculate() {
  if (!form.value.purchase_price || !form.value.monthly_rent || !form.value.usage_months) {
    showFailToast(t('toast.buyVsRentFieldsRequired'))
    return
  }
  loading.value = true
  try {
    result.value = await calculateBuyVsRent({
      purchase_price: Number(form.value.purchase_price),
      monthly_rent: Number(form.value.monthly_rent),
      usage_months: Number(form.value.usage_months),
      ...(form.value.annual_maintenance_cost
        ? { annual_maintenance_cost: Number(form.value.annual_maintenance_cost) }
        : {}),
    })
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.positive { color: #07c160; }
.negative { color: #ee0a24; }
</style>
