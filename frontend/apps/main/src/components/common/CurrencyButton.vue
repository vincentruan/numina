<template>
  <div class="currency-button" role="button" tabindex="0" @click="showPicker = true" @keydown.enter="showPicker = true" @keydown.space.prevent="showPicker = true">
    <span class="currency-flag">{{ flag }}</span>
    <span class="currency-symbol">{{ symbol }}</span>
    <van-icon name="arrow-down" size="10" />
  </div>

  <CurrencyPicker
    v-model="selectedCurrency"
    v-model:show="showPicker"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import CurrencyPicker from './CurrencyPicker.vue'
import { useCurrencyStore } from '@/stores/currency'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const authStore = useAuthStore()
const currencyStore = useCurrencyStore()

const showPicker = ref(false)
const selectedCurrency = ref(props.modelValue || authStore.user?.default_currency || 'CNY')

const flag = computed(() => currencyStore.flagMap[selectedCurrency.value] || '🏳️')
const symbol = computed(() => currencyStore.symbolMap[selectedCurrency.value] || selectedCurrency.value)

watch(selectedCurrency, (newCurrency) => {
  emit('update:modelValue', newCurrency)
})

// Sync external changes
watch(() => props.modelValue, (newVal) => {
  if (newVal && newVal !== selectedCurrency.value) {
    selectedCurrency.value = newVal
  }
})
</script>

<style scoped>
.currency-button {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 6px;
  background: var(--van-active-color);
  border-radius: 4px;
  cursor: pointer;
  margin-right: 4px;
}
.currency-flag {
  font-size: 14px;
  line-height: 1;
}
.currency-symbol {
  font-weight: 500;
  font-size: 14px;
  line-height: 1;
}
</style>