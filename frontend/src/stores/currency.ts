import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Currency } from '@/types'
import * as currencyApi from '@/api/currencies'

export const useCurrencyStore = defineStore('currency', () => {
  const currencies = ref<Currency[]>([])
  const loading = ref(false)

  const symbolMap = computed(() => {
    const map: Record<string, string> = {}
    for (const c of currencies.value) {
      map[c.code] = c.symbol
    }
    return map
  })

  const flagMap = computed(() => {
    const map: Record<string, string> = {}
    for (const c of currencies.value) {
      map[c.code] = c.flag_emoji
    }
    return map
  })

  const nameMap = computed(() => {
    const map: Record<string, { zh: string; en: string }> = {}
    for (const c of currencies.value) {
      map[c.code] = { zh: c.name_zh, en: c.name_en }
    }
    return map
  })

  async function fetchCurrencies() {
    if (currencies.value.length > 0) return
    loading.value = true
    try {
      const res = await currencyApi.getCurrencies()
      currencies.value = res.data
    } catch (e) {
      console.error('Failed to fetch currencies:', e)
    } finally {
      loading.value = false
    }
  }

  return {
    currencies,
    loading,
    symbolMap,
    flagMap,
    nameMap,
    fetchCurrencies,
  }
})