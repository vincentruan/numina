<template>
  <span class="money-display" :class="[colorClass, sizeClass]">
    <span class="money-sign">{{ sign }}</span>
    <span class="money-prefix">{{ currencySymbol }}</span>
    <span class="money-value">{{ displayValue }}</span>
    <span
      v-if="showConversionInfo"
      class="conversion-info-icon"
      @click.stop="togglePopover"
    >ⓘ</span>

    <!-- Conversion detail bottom sheet -->
    <van-popup
      :show="popoverVisible"
      position="bottom"
      round
      :style="{ maxHeight: '40vh' }"
      @close="popoverVisible = false"
      @click-overlay="popoverVisible = false"
    >
      <div class="conversion-popup-content">
        <div class="bubble-row">
          <span class="bubble-label">{{ t('currency.originalAmount') }}</span>
          <span class="bubble-value">{{ originalAmountDisplay }}</span>
        </div>
        <div class="bubble-row">
          <span class="bubble-label">{{ t('currency.exchangeRate') }}</span>
          <span class="bubble-value">{{ rateDisplay }}</span>
        </div>
        <div class="bubble-time">
          {{ t('currency.rateUpdatedAt', { time: formattedFetchTime }) }}
        </div>
      </div>
    </van-popup>
  </span>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { parseApiDate } from '@/utils/format'
import { useExchangeRate } from '@/composables/useExchangeRate'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  // Money is str on the wire (money-as-str); coerced to number below. Accept both.
  amount: number | string
  size?: 'small' | 'normal' | 'large'
  showSign?: boolean
  colorful?: boolean
  sourceCurrency?: string
  originalValue?: number | string
}>(), {
  size: 'normal',
  showSign: false,
  colorful: false,
  sourceCurrency: undefined,
  originalValue: 0
})

// Numeric coercions of the wire (possibly string) money props. Number() is
// runtime-benign for numeric strings; null/undefined/'' -> 0.
const numAmount = computed(() => Number(props.amount) || 0)
const numOriginalValue = computed(() => Number(props.originalValue) || 0)

const { currency, convertAmount } = useCurrency()
const { getCachedRate, getRateInfo } = useExchangeRate()

const popoverVisible = ref(false)
const rateInfo = ref<{ rate: number; fetched_at: string } | null>(null)

// Fetch rate info when source currency differs from display currency
watch(
  () => props.sourceCurrency,
  async (sourceCurrency) => {
    if (sourceCurrency && sourceCurrency !== currency.value) {
      rateInfo.value = await getRateInfo(sourceCurrency)
    } else {
      rateInfo.value = null
    }
  },
  { immediate: true }
)

// Also update when display currency changes
watch(currency, async () => {
  if (props.sourceCurrency && props.sourceCurrency !== currency.value) {
    rateInfo.value = await getRateInfo(props.sourceCurrency)
  } else {
    rateInfo.value = null
  }
})

const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: '¥',
  USD: '$',
  EUR: '€',
  GBP: '£',
  JPY: '¥',
  HKD: 'HK$',
}

const CURRENCY_LOCALES: Record<string, string> = {
  CNY: 'zh-CN',
  USD: 'en-US',
  EUR: 'de-DE',
  GBP: 'en-GB',
  JPY: 'ja-JP',
  HKD: 'zh-HK',
}

// Display currency: when sourceCurrency differs from user's default currency,
// convert using the cached exchange rate so the UI is consistent across pages.
const needsConversion = computed(() => {
  return props.sourceCurrency && props.sourceCurrency !== currency.value
})

const convertedAmount = computed(() => {
  if (!needsConversion.value) return numAmount.value
  return convertAmount(numAmount.value, props.sourceCurrency!)
})

const currencySymbol = computed(() => CURRENCY_SYMBOLS[currency.value] || currency.value)
const locale = computed(() => CURRENCY_LOCALES[currency.value] || 'zh-CN')

// Show conversion info only when actual currency conversion is happening
const showConversionInfo = computed(() => {
  return needsConversion.value &&
    numOriginalValue.value > 0
})

// Source currency symbol for popover
const sourceCurrencySymbol = computed(() => {
  if (!props.sourceCurrency) return ''
  return CURRENCY_SYMBOLS[props.sourceCurrency] || props.sourceCurrency
})

// Format original amount display (the value in sourceCurrency)
const originalAmountDisplay = computed(() => {
  if (!props.sourceCurrency) return ''
  const raw = numOriginalValue.value || numAmount.value
  if (!raw) return ''
  const formatted = Math.abs(raw).toLocaleString(
    CURRENCY_LOCALES[props.sourceCurrency] || 'zh-CN',
    { minimumFractionDigits: 2, maximumFractionDigits: 2 }
  )
  return `${sourceCurrencySymbol.value}${formatted}`
})

// Format rate display
const rateDisplay = computed(() => {
  if (!rateInfo.value) return '-'
  const sourceRate = rateInfo.value.rate // 1 CNY = sourceRate sourceCurrency
  const targetRate = getCachedRate(currency.value)

  // When target is CNY or target rate not available, show source-to-CNY rate
  if (!targetRate || currency.value === 'CNY') {
    const invertedRate = 1 / sourceRate
    return `1 ${props.sourceCurrency} = ${invertedRate.toFixed(4)} CNY`
  }

  // Show effective cross-rate: 1 source = (targetRate / sourceRate) target
  const crossRate = targetRate.rate / sourceRate
  return `1 ${props.sourceCurrency} = ${crossRate.toFixed(4)} ${currency.value}`
})

// Format fetch time - compact format
const formattedFetchTime = computed(() => {
  if (!rateInfo.value?.fetched_at) return '-'
  const date = parseApiDate(rateInfo.value.fetched_at)
  const month = date.getMonth() + 1
  const day = date.getDate()
  const hour = date.getHours().toString().padStart(2, '0')
  const min = date.getMinutes().toString().padStart(2, '0')
  return `${month}/${day} ${hour}:${min}`
})

const displayValue = computed(() => {
  const abs = Math.abs(convertedAmount.value)

  // CNY使用万/亿单位
  if (currency.value === 'CNY') {
    if (abs >= 100000000) {
      return `${(abs / 100000000).toFixed(2)}亿`
    } else if (abs >= 10000) {
      return `${(abs / 10000).toFixed(2)}万`
    }
  }

  // 其他货币使用标准格式
  if (abs >= 1000) {
    return abs.toLocaleString(locale.value, { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  }
  return abs.toLocaleString(locale.value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
})

const sign = computed(() => {
  if (!props.showSign) return ''
  return convertedAmount.value >= 0 ? '+' : '-'
})

const colorClass = computed(() => {
  if (!props.colorful) return ''
  return convertedAmount.value >= 0 ? 'money-positive' : 'money-negative'
})

const sizeClass = computed(() => `money-${props.size}`)

function togglePopover() {
  popoverVisible.value = !popoverVisible.value
}

onMounted(() => {
  // Pre-fetch target currency rate on mount
  if (currency.value && currency.value !== 'CNY') {
    void getRateInfo(currency.value)
  }
  // Also pre-fetch source rate when present and non-CNY
  if (props.sourceCurrency && props.sourceCurrency !== 'CNY' && props.sourceCurrency !== currency.value) {
    void getRateInfo(props.sourceCurrency)
  }
})

</script>

<style scoped>
.money-display {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.money-prefix {
  margin-right: 1px;
}
.money-small {
  font-size: 12px;
}
.money-normal {
  font-size: 14px;
}
.money-large {
  font-size: 24px;
  font-weight: 600;
}
.money-positive {
  color: #07c160;
}
.money-negative {
  color: #ee0a24;
}
.conversion-info-icon {
  margin-left: 2px;
  font-size: 11px;
  color: #969799;
  cursor: pointer;
  user-select: none;
}
.conversion-popup-content {
  padding: 16px;
  font-size: 13px;
  line-height: 1.5;
}
.bubble-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.bubble-label {
  color: var(--text-secondary, #969799);
  flex-shrink: 0;
}
.bubble-value {
  font-weight: 500;
  text-align: right;
  word-break: break-all;
  color: var(--text-primary);
}
.bubble-time {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color, rgba(0, 0, 0, 0.06));
  font-size: 12px;
  color: var(--text-secondary, #969799);
}
</style>