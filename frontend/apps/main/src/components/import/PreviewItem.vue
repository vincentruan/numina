<template>
  <div :class="['preview-item', lowConfidence ? 'low-confidence' : '', item.warning ? 'has-warning' : '']">
    <!-- Confidence indicator (R10) -->
    <div class="item-header">
      <van-tag :color="confidenceColor" :text-color="confidenceTextColor" class="confidence-tag">
        <van-icon :name="confidenceIcon" size="12" />
        {{ confidenceLabel }}
      </van-tag>
      <van-button
        size="mini"
        icon="delete-o"
        plain
        type="danger"
        @click="$emit('delete', item.temp_id)"
      />
    </div>

    <!-- Name (always editable) -->
    <van-field
      :model-value="item.name"
      :label="t('importReport.name')"
      :placeholder="t('importReport.name')"
      @update:model-value="(v: string) => emit('update', item.temp_id, { name: v })"
    />

    <!-- Target model switch (R9) -->
    <van-field
      :model-value="modelLabel"
      is-link
      readonly
      :label="t('importReport.targetModel')"
      @click="showModelPicker = true"
    />

    <!-- Asset-specific fields -->
    <template v-if="item.target_model === 'asset'">
      <van-field
        :model-value="item.current_value ?? undefined"
        :label="t('importReport.currentValue')"
        type="number"
        inputmode="decimal"
        :placeholder="t('importReport.enterValue')"
        @update:model-value="(v: string) => emit('update', item.temp_id, { current_value: safeNumber(v) })"
      />
      <van-field
        :model-value="item.asset_type === 'financial' ? t('importReport.financial') : t('importReport.physical')"
        is-link
        readonly
        :label="t('importReport.assetType')"
        @click="showAssetTypePicker = true"
      />
      <van-field
        :model-value="item.currency"
        :label="t('importReport.currency')"
        :placeholder="'CNY'"
        @update:model-value="(v: string) => emit('update', item.temp_id, { currency: v })"
      />
    </template>

    <!-- Liability-specific fields -->
    <template v-if="item.target_model === 'liability'">
      <van-field
        :model-value="item.original_amount ?? undefined"
        :label="t('importReport.originalAmount')"
        type="number"
        inputmode="decimal"
        :placeholder="t('importReport.enterValue')"
        @update:model-value="(v: string) => emit('update', item.temp_id, { original_amount: safeNumber(v) })"
      />
      <van-field
        :model-value="item.remaining_amount ?? undefined"
        :label="t('importReport.remainingAmount')"
        type="number"
        inputmode="decimal"
        :placeholder="t('importReport.enterValue')"
        @update:model-value="(v: string) => emit('update', item.temp_id, { remaining_amount: safeNumber(v) })"
      />
      <van-field
        :model-value="item.monthly_payment ?? undefined"
        :label="t('importReport.monthlyPayment')"
        type="number"
        inputmode="decimal"
        :placeholder="t('importReport.enterValue')"
        @update:model-value="(v: string) => emit('update', item.temp_id, { monthly_payment: safeNumber(v) })"
      />
      <van-field
        :model-value="item.interest_rate ?? undefined"
        :label="t('importReport.interestRate')"
        type="number"
        inputmode="decimal"
        :placeholder="t('importReport.enterValue')"
        @update:model-value="(v: string) => emit('update', item.temp_id, { interest_rate: safeNumber(v) })"
      />
      <van-field
        :model-value="item.currency"
        :label="t('importReport.currency')"
        :placeholder="'CNY'"
        @update:model-value="(v: string) => emit('update', item.temp_id, { currency: v })"
      />
    </template>

    <!-- Matched asset info -->
    <div v-if="item.matched_asset_name" class="item-meta">
      <van-tag type="primary">{{ t('importReport.actionUpdate') }}</van-tag>
      <span class="matched-name">→ {{ item.matched_asset_name }}</span>
    </div>

    <!-- Warning -->
    <div v-if="item.warning" class="item-meta">
      <span class="warning-text">{{ t('importReport.warningAmountMissing') }}</span>
    </div>

    <!-- Model picker popup -->
    <van-popup v-model:show="showModelPicker" position="bottom" round destroy-on-close>
      <van-picker
        :columns="modelColumns"
        @confirm="onModelConfirm"
        @cancel="showModelPicker = false"
      />
    </van-popup>

    <!-- Asset type picker popup -->
    <van-popup v-model:show="showAssetTypePicker" position="bottom" round destroy-on-close>
      <van-picker
        :columns="assetTypeColumns"
        @confirm="onAssetTypeConfirm"
        @cancel="showAssetTypePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ImportPreviewItem } from '@/api/importReport'

const props = defineProps<{ item: ImportPreviewItem }>()
const emit = defineEmits<{
  update: [tempId: string, updates: Partial<ImportPreviewItem>]
  delete: [tempId: string]
}>()

const { t } = useI18n()

const showModelPicker = ref(false)
const showAssetTypePicker = ref(false)

// Safe numeric field conversion — prevents NaN from reaching the backend.
function safeNumber(v: string): number | null {
  if (v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

// Confidence indicator (R10).
const lowConfidence = computed(() => (props.item.confidence ?? 0) < 0.6)
const confidenceColor = computed(() => {
  const c = props.item.confidence ?? 0
  if (c >= 0.8) return '#07c160'
  if (c >= 0.6) return '#ff976a'
  return '#ee0a24'
})
const confidenceTextColor = computed(() => '#fff')
const confidenceIcon = computed(() => {
  const c = props.item.confidence ?? 0
  if (c >= 0.8) return 'success'
  if (c >= 0.6) return 'warning-o'
  return 'cross'
})
const confidenceLabel = computed(() => {
  const c = props.item.confidence
  if (c == null) return t('importReport.confidenceUnknown')
  if (c >= 0.8) return t('importReport.confidenceHigh')
  if (c >= 0.6) return t('importReport.confidenceMedium')
  return t('importReport.confidenceLow')
})

const modelLabel = computed(() =>
  props.item.target_model === 'asset' ? t('importReport.asset') : t('importReport.liability')
)

const modelColumns = computed(() => [
  { text: t('importReport.asset'), value: 'asset' },
  { text: t('importReport.liability'), value: 'liability' },
])

const assetTypeColumns = computed(() => [
  { text: t('importReport.financial'), value: 'financial' },
  { text: t('importReport.physical'), value: 'physical' },
])

function onModelConfirm({ selectedValues }: { selectedValues: string[] }) {
  const newModel = selectedValues[0] as 'asset' | 'liability'
  if (newModel === props.item.target_model) {
    showModelPicker.value = false
    return
  }
  // R9: on model switch, preserve name + currency, reset model-specific fields.
  const updates: Partial<ImportPreviewItem> = {
    target_model: newModel,
    action: 'create',
    matched_asset_id: null,
    matched_asset_name: null,
  }
  if (newModel === 'asset') {
    updates.original_amount = null
    updates.remaining_amount = null
    updates.monthly_payment = null
    updates.interest_rate = null
    updates.liability_category = null
  } else {
    updates.asset_type = ''
    updates.category_hint = ''
    updates.current_value = null
    updates.quantity = null
  }
  emit('update', props.item.temp_id, updates)
  showModelPicker.value = false
}

function onAssetTypeConfirm({ selectedValues }: { selectedValues: string[] }) {
  emit('update', props.item.temp_id, { asset_type: selectedValues[0] })
  showAssetTypePicker.value = false
}
</script>

<style scoped>
.preview-item {
  background: var(--card-bg, var(--van-background-2));
  border-radius: 8px;
  margin: 0 12px 8px;
  padding: 8px 0;
}
.preview-item.low-confidence {
  border-left: 3px solid var(--van-danger-color, #ee0a24);
}
.preview-item.has-warning {
  border-left: 3px solid var(--van-warning-color, #ff976a);
}
.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 12px 8px;
}
.confidence-tag {
  font-size: 11px;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  font-size: 12px;
}
.matched-name {
  color: var(--van-text-color-2);
}
.warning-text {
  color: var(--van-warning-color, #ff976a);
}
</style>
