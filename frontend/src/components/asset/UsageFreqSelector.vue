<template>
  <div class="freq-selector">
    <div
      v-for="opt in options"
      :key="opt.value"
      class="freq-item"
      :class="{ selected: modelValue === opt.value }"
      @click="$emit('update:modelValue', opt.value)"
    >
      <span class="icon">{{ opt.icon }}</span>
      <span class="label">{{ opt.label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ modelValue: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()

const options = [
  { value: 'daily',   icon: '📅', label: '每天' },
  { value: 'weekly',  icon: '📆', label: '每周' },
  { value: 'monthly', icon: '🗓️', label: '每月' },
  { value: 'rarely',  icon: '💤', label: '偶尔' },
  { value: 'idle',    icon: '📦', label: '闲置' },
]
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
.icon { font-size: 18px; }
.label {
  font-size: 10px;
  color: var(--van-text-color-2);
  margin-top: 4px;
}
.freq-item.selected .label { color: var(--van-primary-color); }
</style>
