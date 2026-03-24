<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    close-on-popstate
    @update:show="$emit('update:show', $event)"
  >
    <div class="currency-picker">
      <van-search
        v-model="searchQuery"
        :placeholder="t('currency.searchPlaceholder')"
        shape="round"
      />

      <!-- Favorites section -->
      <div v-if="favoriteCurrencies.length > 0" class="currency-section">
        <div class="section-title">{{ t('currency.favorites') }}</div>
        <van-cell-group inset>
          <van-cell
            v-for="currency in favoriteCurrencies"
            :key="currency.code"
            :title="formatCurrencyLabel(currency)"
            clickable
            @click="selectCurrency(currency.code)"
          >
            <template #right-icon>
              <van-icon v-if="modelValue === currency.code" name="success" color="#1988f1" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>

      <!-- All currencies section -->
      <div v-if="filteredAllCurrencies.length > 0" class="currency-section">
        <div class="section-title">{{ t('currency.all') }}</div>
        <van-cell-group inset>
          <van-cell
            v-for="currency in filteredAllCurrencies"
            :key="currency.code"
            :title="formatCurrencyLabel(currency)"
            clickable
            @click="selectCurrency(currency.code)"
          >
            <template #right-icon>
              <van-icon v-if="modelValue === currency.code" name="success" color="#1988f1" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrencyStore } from '@/stores/currency'
import type { Currency } from '@/types'

const props = defineProps<{
  modelValue: string
  show: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:show': [value: boolean]
}>()

const { t, locale } = useI18n()
const currencyStore = useCurrencyStore()

const searchQuery = ref('')

const favoriteCurrencies = computed(() => {
  const query = searchQuery.value.toLowerCase()
  return currencyStore.currencies
    .filter(c => c.is_favorite)
    .filter(c => {
      if (!query) return true
      return (
        c.code.toLowerCase().includes(query) ||
        c.name_zh.toLowerCase().includes(query) ||
        c.name_en.toLowerCase().includes(query)
      )
    })
    .sort((a, b) => a.sort_order - b.sort_order)
})

const filteredAllCurrencies = computed(() => {
  const query = searchQuery.value.toLowerCase()
  return currencyStore.currencies
    .filter(c => !c.is_favorite)
    .filter(c => {
      if (!query) return true
      return (
        c.code.toLowerCase().includes(query) ||
        c.name_zh.toLowerCase().includes(query) ||
        c.name_en.toLowerCase().includes(query)
      )
    })
    .sort((a, b) => a.code.localeCompare(b.code))
})

function formatCurrencyLabel(currency: Currency): string {
  const name = locale.value === 'zh-CN' ? currency.name_zh : currency.name_en
  return `${currency.flag_emoji} ${name}（${currency.code}）${currency.symbol}`
}

function selectCurrency(code: string) {
  emit('update:modelValue', code)
  emit('update:show', false)
}
</script>

<style scoped>
.currency-picker {
  max-height: 70vh;
  overflow-y: auto;
  padding-bottom: env(safe-area-inset-bottom);
}
.section-title {
  padding: 12px 16px 8px;
  font-size: 13px;
  color: var(--van-text-color-3);
}
</style>