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

    <!-- Small bubble tooltip -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="popoverVisible"
          class="conversion-bubble"
          :style="bubbleStyle"
          @click.stop
        >
          <div class="bubble-row">
            <span class="bubble-label">原始金额</span>
            <span class="bubble-value">{{ originalAmountDisplay }}</span>
          </div>
          <div class="bubble-row">
            <span class="bubble-label">汇率</span>
            <span class="bubble-value">{{ rateDisplay }}</span>
          </div>
          <div class="bubble-time">
            汇率更新: {{ formattedFetchTime }}
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Overlay to close bubble -->
    <Teleport to="body">
      <div
        v-if="popoverVisible"
        class="conversion-overlay"
        @click="popoverVisible = false"
      ></div>
    </Teleport>
  </span>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useCurrency } from '@/composables/useCurrency'
import { useExchangeRate } from '@/composables/useExchangeRate'

const props = withDefaults(defineProps<{
  amount: number
  size?: 'small' | 'normal' | 'large'
  showSign?: boolean
  colorful?: boolean
  sourceCurrency?: string
  originalValue?: number
}>(), {
  size: 'normal',
  showSign: false,
  colorful: false,
  sourceCurrency: 'CNY',
  originalValue: 0
})

const { currency } = useCurrency()
const { getRateInfo } = useExchangeRate()

const popoverVisible = ref(false)
const rateInfo = ref<{ rate: number; fetched_at: string } | null>(null)
const bubbleStyle = ref<Record<string, string>>({})
const _iconElement = ref<HTMLElement | null>(null)

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

const currencySymbol = computed(() => CURRENCY_SYMBOLS[currency.value] || currency.value)
const locale = computed(() => CURRENCY_LOCALES[currency.value] || 'zh-CN')

// Show conversion info only when actual currency conversion is happening
const showConversionInfo = computed(() => {
  return props.sourceCurrency &&
    props.sourceCurrency !== currency.value &&
    props.originalValue > 0
})

// Source currency symbol for popover
const sourceCurrencySymbol = computed(() =>
  CURRENCY_SYMBOLS[props.sourceCurrency] || props.sourceCurrency
)

// Format original amount display
const originalAmountDisplay = computed(() => {
  if (!props.originalValue) return ''
  const formatted = Math.abs(props.originalValue).toLocaleString(
    CURRENCY_LOCALES[props.sourceCurrency] || 'zh-CN',
    { minimumFractionDigits: 2, maximumFractionDigits: 2 }
  )
  return `${sourceCurrencySymbol.value}${formatted}`
})

// Format rate display
const rateDisplay = computed(() => {
  if (!rateInfo.value) return '-'
  // Rate is stored as "1 CNY = rate foreign_currency"
  // For display, we need "1 foreign_currency = (1/rate) CNY"
  const invertedRate = 1 / rateInfo.value.rate
  return `1 ${props.sourceCurrency} = ${invertedRate.toFixed(2)} ${currency.value}`
})

// Format fetch time - compact format
const formattedFetchTime = computed(() => {
  if (!rateInfo.value?.fetched_at) return '-'
  const date = new Date(rateInfo.value.fetched_at)
  const month = date.getMonth() + 1
  const day = date.getDate()
  const hour = date.getHours().toString().padStart(2, '0')
  const min = date.getMinutes().toString().padStart(2, '0')
  return `${month}/${day} ${hour}:${min}`
})

const displayValue = computed(() => {
  const abs = Math.abs(props.amount)

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
  return props.amount >= 0 ? '+' : '-'
})

const colorClass = computed(() => {
  if (!props.colorful) return ''
  return props.amount >= 0 ? 'money-positive' : 'money-negative'
})

const sizeClass = computed(() => `money-${props.size}`)

function togglePopover(event: MouseEvent) {
  popoverVisible.value = !popoverVisible.value

  if (popoverVisible.value) {
    const target = event.target as HTMLElement
    const rect = target.getBoundingClientRect()

    // Position bubble above the icon
    bubbleStyle.value = {
      position: 'fixed',
      left: `${Math.max(10, Math.min(rect.left - 40, window.innerWidth - 180))}px`,
      top: `${rect.top - 95}px`,
    }
  }
}

// Close on escape key
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && popoverVisible.value) {
    popoverVisible.value = false
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
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
.conversion-bubble {
  position: fixed;
  background: rgba(0, 0, 0, 0.85);
  color: #fff;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  min-width: 150px;
  max-width: 200px;
  z-index: 2001;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}
.conversion-bubble::after {
  content: '';
  position: absolute;
  bottom: -6px;
  left: 50px;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid rgba(0, 0, 0, 0.85);
}
.bubble-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.bubble-label {
  color: #aaa;
  flex-shrink: 0;
}
.bubble-value {
  font-weight: 500;
  text-align: right;
  word-break: break-all;
}
.bubble-time {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 11px;
  color: #888;
}
.conversion-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>