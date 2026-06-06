<template>
  <div class="category-grid">
    <div v-if="physicalCategories.length" class="category-group">
      <div class="group-label">{{ t('categoryGrid.physical') }}</div>
      <div class="grid">
        <div
          v-for="cat in physicalCategories"
          :key="cat.id"
          class="grid-item"
          :class="{ selected: modelValue === cat.id }"
          @click="$emit('update:modelValue', cat.id)"
        >
          <SvgIcon :name="getIconId(cat.icon)" class="icon" />
          <span class="name">{{ cat.name }}</span>
        </div>
      </div>
    </div>
    <div v-if="financialCategories.length" class="category-group">
      <div class="group-label">{{ t('categoryGrid.financial') }}</div>
      <div class="grid">
        <div
          v-for="cat in financialCategories"
          :key="cat.id"
          class="grid-item"
          :class="{ selected: modelValue === cat.id }"
          @click="$emit('update:modelValue', cat.id)"
        >
          <SvgIcon :name="getIconId(cat.icon)" class="icon" />
          <span class="name">{{ cat.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Category } from '@/types'
import { getIconId } from '@/utils/icon'

const { t } = useI18n()

const props = defineProps<{
  modelValue: string
  categories: Category[]
  assetType: string
}>()

defineEmits<{ 'update:modelValue': [value: string] }>()

const physicalCategories = computed(() =>
  props.categories.filter(c => c.asset_type === 'physical')
)
const financialCategories = computed(() =>
  props.categories.filter(c => c.asset_type === 'financial')
)
</script>

<style scoped>
.category-grid { padding: 8px 0; }
.category-group { margin-bottom: 8px; }
.group-label {
  font-size: 11px;
  color: var(--van-text-color-3);
  padding: 0 16px 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 0 16px;
}
.grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--van-background-2);
  border: 1.5px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
}
.grid-item:active {
  transform: scale(0.95);
}
.grid-item:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
}
.grid-item.selected {
  border-color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 12%, transparent);
}
.icon {
  width: 22px;
  height: 22px;
  fill: currentColor;
}
.name {
  font-size: 10px;
  color: var(--van-text-color-2);
  margin-top: 4px;
  text-align: center;
  line-height: 1.2;
}
.grid-item.selected .name { color: var(--van-primary-color); }
</style>
