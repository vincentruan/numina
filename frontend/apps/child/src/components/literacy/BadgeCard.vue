<template>
  <div :class="['badge-card', `variant-${variant}`, `dim-${dimensionIcon}`]">
    <!-- Current / History variants -->
    <template v-if="variant !== 'locked'">
      <div class="badge-icon-wrap">
        <span class="badge-emoji">{{ dimensionIcon }}</span>
      </div>
      <div class="badge-body">
        <p class="badge-name">{{ badge.name }}</p>
        <p class="badge-level">
          <span v-for="i in badgeLevel" :key="i" class="star">&#9733;</span>
          <span v-if="badgeLevel" class="level-label">
            {{ t('badges.level') }} {{ badgeLevel }}
          </span>
        </p>
        <p v-if="'description' in badge && badge.description" class="badge-desc">
          {{ badge.description }}
        </p>
      </div>
      <!-- History overlay ribbon -->
      <span v-if="variant === 'history'" class="surpassed-ribbon">
        {{ t('badges.surpassed') }}
      </span>
    </template>

    <!-- Locked variant -->
    <template v-else>
      <div class="badge-icon-wrap locked-silhouette">
        <span class="badge-emoji locked-emoji">🔒</span>
      </div>
      <div class="badge-body">
        <p class="badge-name locked-name">{{ badgeName }}</p>
        <p class="badge-criteria" v-if="criteriaSummary">
          {{ t('badges.criteria') }}: {{ criteriaSummary }}
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'BadgeCard' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { BadgeInfo, BadgeHistoryItem, BadgeDefinitionInfo } from '@/api/literacy'

const { t } = useI18n()

const props = defineProps<{
  badge: BadgeInfo | BadgeHistoryItem | BadgeDefinitionInfo
  variant: 'current' | 'history' | 'locked'
  dimensionIcon: string
  badgeName?: string
  criteriaSummary?: string
}>()

const badgeLevel = computed(() => 'level' in props.badge ? props.badge.level : 0)
</script>

<style scoped>
.badge-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  border: 1px solid var(--color-hairline);
  overflow: hidden;
  transition: transform 0.15s;
}

/* Current variant — warm ochre accent */
.variant-current {
  border-color: var(--color-brand-ochre);
  background: linear-gradient(
    135deg,
    var(--color-surface-card) 0%,
    rgba(var(--color-brand-ochre-rgb), 0.08) 100%
  );
}

/* History variant — dimmed */
.variant-history {
  opacity: 0.6;
}

/* Surpassed ribbon */
.surpassed-ribbon {
  position: absolute;
  top: 6px;
  right: -24px;
  background: var(--color-brand-coral);
  color: var(--color-on-dark);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  padding: 2px 28px;
  transform: rotate(35deg);
  border-radius: 2px;
}

/* Locked variant */
.variant-locked {
  opacity: 0.45;
}

.badge-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(var(--color-brand-ochre-rgb), 0.12);
}

.variant-history .badge-icon-wrap {
  background: var(--color-surface-soft);
}

.variant-locked .badge-icon-wrap {
  background: var(--color-surface-soft);
}

.locked-silhouette {
  opacity: 0.5;
}

.badge-emoji {
  font-size: 22px;
}

.locked-emoji {
  font-size: 18px;
}

.badge-body {
  flex: 1;
  min-width: 0;
}

.badge-name {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.variant-current .badge-name {
  color: var(--color-brand-ochre);
}

.locked-name {
  color: var(--color-muted);
  font-style: italic;
}

.badge-level {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-brand-ochre);
  margin: 0;
  font-weight: 500;
}

.variant-history .badge-level {
  color: var(--color-muted-soft);
}

.star {
  font-size: 14px;
}

.level-label {
  margin-left: 4px;
  font-size: 14px;
  color: var(--color-muted);
}

.badge-desc {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  margin: 2px 0 0;
  line-height: 1.4;
}

.badge-criteria {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
  margin: 2px 0 0;
  line-height: 1.4;
}
</style>
