<template>
  <div class="currency-selector">
    <van-field
      :model-value="displayAmount"
      type="number"
      :label="label"
      :placeholder="placeholder"
      @update:model-value="onAmountChange"
    >
      <template #button>
        <div class="currency-button" @click="showPicker = true">
          <span class="currency-flag">{{ currencyFlag }}</span>
          <span class="currency-symbol">{{ currencySymbol }}</span>
          <van-icon name="arrow-down" size="12" />
        </div>
      </template>
    </van-field>

    <CurrencyPicker
      v-model="selectedCurrency"
      v-model:show="showPicker"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import CurrencyPicker from './CurrencyPicker.vue'
import { useCurrencyStore } from '@/stores/currency'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()

interface CurrencyAmount {
  amount: number | null
  currency: string
}

const props = withDefaults(defineProps<{
  modelValue: CurrencyAmount
  label?: string
  placeholder?: string
}>(), {
  label: () => t('currency.amountLabel'),
  placeholder: () => t('currency.amountPlaceholder'),
})

const emit = defineEmits<{
  'update:modelValue': [value: CurrencyAmount]
}>()

const authStore = useAuthStore()
const currencyStore = useCurrencyStore()

const showPicker = ref(false)
const selectedCurrency = ref(props.modelValue.currency || authStore.user?.default_currency || 'CNY')

const currencyFlag = computed(() => currencyStore.flagMap[selectedCurrency.value] || '🏳️')
const currencySymbol = computed(() => currencyStore.symbolMap[selectedCurrency.value] || selectedCurrency.value)
const displayAmount = computed(() => props.modelValue.amount?.toString() || '')

// Watch currency change
watch(selectedCurrency, (newCurrency) => {
  emit('update:modelValue', {
    amount: props.modelValue.amount,
    currency: newCurrency,
  })
})

function onAmountChange(value: string) {
  const amount = value ? parseFloat(value) : null
  emit('update:modelValue', {
    amount,
    currency: selectedCurrency.value,
  })
}
</script>

<style scoped>
.currency-selector {
  width: 100%;
}
.currency-button {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: var(--van-gray-2);
  border-radius: 4px;
  cursor: pointer;
}
.currency-flag {
  font-size: 16px;
}
.currency-symbol {
  font-weight: 500;
}
</style>