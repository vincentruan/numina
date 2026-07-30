<template>
  <div class="badge-dimension">
    <!-- Header -->
    <div class="dim-header">
      <span class="dim-icon">{{ icon }}</span>
      <p class="dim-name">{{ label }}</p>
    </div>

    <!-- Current badge -->
    <div v-if="currentBadge" class="dim-current">
      <p class="dim-section-label">{{ t('badges.currentBadge') }}</p>
      <BadgeCard
        :badge="currentBadge"
        variant="current"
        :dimension-icon="icon"
      />
    </div>

    <!-- Locked silhouette when no current badge -->
    <div v-else-if="nextBadge" class="dim-current">
      <p class="dim-section-label">{{ t('badges.locked') }}</p>
      <BadgeCard
        :badge="nextBadge"
        variant="locked"
        :dimension-icon="icon"
        :badge-name="nextBadge.name"
        :criteria-summary="nextBadge.criteria_summary"
      />
    </div>

    <!-- Next badge hint -->
    <div v-if="nextBadge && currentBadge" class="dim-next">
      <p class="dim-next-label">{{ t('badges.nextBadge') }}: <strong>{{ nextBadge.name }}</strong></p>
      <p v-if="nextBadge.criteria_summary" class="dim-next-criteria">
        {{ nextBadge.criteria_summary }}
      </p>
    </div>

    <!-- History section (collapsible) -->
    <div v-if="history.length > 0" class="dim-history">
      <button class="dim-history-toggle" @click="historyOpen = !historyOpen">
        {{ t('badges.history') }} ({{ history.length }})
        <van-icon :name="historyOpen ? 'arrow-up' : 'arrow'" size="12" />
      </button>
      <div v-show="historyOpen" class="dim-history-list">
        <BadgeCard
          v-for="item in history"
          :key="item.id"
          :badge="item"
          variant="history"
          :dimension-icon="icon"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'BadgeDimension' })

import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BadgeCard from './BadgeCard.vue'
import type { BadgeInfo, BadgeHistoryItem, BadgeDefinitionInfo } from '@/api/literacy'

const { t } = useI18n()

const props = defineProps<{
  dimension: string
  currentBadge: BadgeInfo | null
  history: BadgeHistoryItem[]
  nextBadge: BadgeDefinitionInfo | null
}>()

const historyOpen = ref(false)

const DIMENSION_ICONS: Record<string, string> = {
  earning: '💰',
  choosing: '🎯',
  waiting: '⏳',
  caring: '❤️',
}

const icon = computed(() => DIMENSION_ICONS[props.dimension] ?? '🏅')
const label = computed(() => t(`badges.dimensions.${props.dimension}`))
</script>

<style scoped>
.badge-dimension {
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  border: 1px solid var(--color-hairline);
}

.dim-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.dim-icon {
  font-size: 22px;
}

.dim-name {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0;
}

.dim-section-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 6px;
}

.dim-current {
  margin-bottom: 12px;
}

.dim-next {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(var(--color-brand-ochre-rgb), 0.08);
  border-radius: var(--radius-md);
}

.dim-next-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  margin: 0;
}

.dim-next-label strong {
  color: var(--color-brand-ochre);
}

.dim-next-criteria {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
  margin: 2px 0 0;
}

.dim-history {
  border-top: 1px solid var(--color-hairline);
  padding-top: 10px;
}

.dim-history-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  background: none;
  border: none;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-muted);
  cursor: pointer;
  padding: 4px 0;
  -webkit-tap-highlight-color: transparent;
}

.dim-history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
</style>
