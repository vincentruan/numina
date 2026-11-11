<template>
  <div v-if="displayConnections.length" class="rwc-section">
    <h3 class="rwc-title">
      <IIcon icon="lucide:globe" size="18" />
      {{ t('learning.realWorld.title') }}
    </h3>
    <div class="rwc-list">
      <div
        v-for="(item, idx) in displayConnections"
        :key="idx"
        class="rwc-card"
      >
        <div class="rwc-card__icon">
          <IIcon :icon="iconFor(item, idx)" size="24" :color="iconColor(idx)" />
        </div>
        <div class="rwc-card__body">
          <p class="rwc-card__context">{{ item.context }}</p>
          <p class="rwc-card__explanation">{{ item.explanation }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import IIcon from '@/components/IIcon.vue'
import type { RealWorldConnection } from '@/api/learning'

const props = defineProps<{
  connections: RealWorldConnection[]
}>()

const { t } = useI18n()

const displayConnections = computed(() => props.connections.slice(0, 3))

const defaultIcons = [
  'lucide:shopping-cart',
  'lucide:chef-hat',
  'lucide:music',
  'lucide:palette',
  'lucide:football',
  'lucide:building',
  'lucide:leaf',
  'lucide:gamepad-2',
  'lucide:wrench',
  'lucide:heart-pulse',
]

const iconColors = [
  'var(--color-brand-ochre)',
  'var(--color-brand-teal)',
  'var(--color-brand-coral)',
  'var(--color-brand-sage)',
  'var(--color-brand-lavender)',
]

function iconFor(item: RealWorldConnection, idx: number): string {
  if (item.icon) return item.icon
  return defaultIcons[idx % defaultIcons.length]
}

function iconColor(idx: number): string {
  return iconColors[idx % iconColors.length]
}
</script>

<style scoped>
.rwc-section {
  margin-bottom: 24px;
}

.rwc-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 12px;
}

.rwc-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rwc-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  transition: transform 0.15s;
}

.rwc-card:active {
  transform: scale(0.98);
}

.rwc-card__icon {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--color-surface-soft);
}

.rwc-card__body {
  flex: 1 1 auto;
  min-width: 0;
}

.rwc-card__context {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 4px;
  line-height: 1.4;
}

.rwc-card__explanation {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
  margin: 0;
  line-height: 1.5;
}

/* Dark mode */
[data-theme="dark"] .rwc-card__icon {
  background: rgba(255, 255, 255, 0.06);
}
</style>
