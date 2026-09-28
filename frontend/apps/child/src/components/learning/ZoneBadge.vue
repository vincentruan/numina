<template>
  <span class="zone-badge" :class="`zone-badge--${zone}`">
    <span class="zone-badge__icon">{{ icon }}</span>
    <span class="zone-badge__label">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  zone: string
}>()

const { t } = useI18n()

const icon = computed(() => {
  switch (props.zone) {
    case 'growth': return '🌟'
    case 'comfort': return '🌱'
    case 'challenge': return '⚡'
    default: return '📍'
  }
})

const label = computed(() => {
  return t(`learning.zone.${props.zone}`)
})
</script>

<style scoped>
.zone-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 10px;
  font-family: Inter, sans-serif;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
}

.zone-badge--growth {
  background: #e8f5e9;
  color: #2e7d32;
}

[data-theme="dark"] .zone-badge--growth {
  background: #1b5e20;
  color: #a5d6a7;
}

.zone-badge--comfort {
  background: #e3f2fd;
  color: #1565c0;
}

[data-theme="dark"] .zone-badge--comfort {
  background: #0d47a1;
  color: #90caf9;
}

.zone-badge--challenge {
  background: #fff3e0;
  color: #e65100;
}

[data-theme="dark"] .zone-badge--challenge {
  background: #bf360c;
  color: #ffcc80;
}

.zone-badge__icon {
  font-size: 10px;
}

.zone-badge__label {
  line-height: 1;
}
</style>
