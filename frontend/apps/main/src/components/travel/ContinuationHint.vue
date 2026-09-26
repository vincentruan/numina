<template>
  <div
    class="continuation-hint"
    role="button"
    :aria-label="t('travel.itinerary.continuationDay', { day: dayNumber })"
    @click="$emit('scrollToStart')"
  >
    <van-icon :name="icon" size="14" />
    <span class="continuation-text">{{ t('travel.itinerary.continuationDay', { day: dayNumber }) }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const ICON_MAP: Record<string, string> = {
  accommodation: 'hotel-o',
  dining: 'restaurant-o',
  transport: 'car-o',
  activity: 'fire-o',
  custom: 'star-o',
}

const props = defineProps<{
  type: string
  dayNumber: number
}>()

defineEmits<{
  scrollToStart: []
}>()

const { t } = useI18n()

const icon = computed(() => ICON_MAP[props.type] || 'star-o')
</script>

<style scoped>
.continuation-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  margin: 4px 12px;
  border-radius: 8px;
  background: var(--bg-secondary, #f5f5f5);
  cursor: pointer;
  opacity: 0.7;
  transition: opacity 0.15s;
}

.continuation-hint:active {
  opacity: 1;
}

.continuation-text {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
