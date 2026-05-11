<template>
  <div class="freq-selector">
    <div
      v-for="opt in options"
      :key="opt.value"
      class="freq-item"
      :class="{ selected: modelValue === opt.value }"
      @click="$emit('update:modelValue', opt.value)"
    >
      <van-icon :name="opt.icon" class="icon" aria-hidden="true" />
      <span class="label">{{ opt.label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

defineProps<{ modelValue: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()

const { t } = useI18n()

const options = computed(() => [
  { value: 'daily',   icon: 'clock-o',        label: t('usageFreq.daily') },
  { value: 'weekly',  icon: 'calendar-o',     label: t('usageFreq.weekly') },
  { value: 'monthly', icon: 'notes-o',        label: t('usageFreq.monthly') },
  { value: 'rarely',  icon: 'pause-circle-o', label: t('usageFreq.rarely') },
  { value: 'idle',    icon: 'bag-o',          label: t('usageFreq.idle') },
])
</script>

<style scoped>
.freq-selector {
  display: flex;
  gap: 6px;
  padding: 8px 16px;
}
.freq-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--van-background-2);
  border: 1.5px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.freq-item.selected {
  border-color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 12%, transparent);
}
.icon { font-size: 20px; color: var(--van-text-color); }
.label {
  font-size: 10px;
  color: var(--van-text-color-2);
  margin-top: 4px;
}
.freq-item.selected .label { color: var(--van-primary-color); }
</style>
