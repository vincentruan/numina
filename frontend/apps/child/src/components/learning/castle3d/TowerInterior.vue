<template>
  <div class="tower-interior">
    <!-- Floor list: HTML overlay on the 3D view (accessible, cheap) -->
    <div class="tower-interior__floors" role="list">
      <section
        v-for="floor in reversedFloors"
        :key="floor.domain || '__root'"
        role="listitem"
        class="tower-floor"
        :class="`tower-floor--${floorState(floor)}`"
      >
        <header class="tower-floor__header">
          <span class="tower-floor__domain">{{ floor.domain || t('learning.castle.rootFloor') }}</span>
          <span class="tower-floor__count">
            {{ t('learning.castle.towers', { mastered: floor.mastered_count, total: floor.total_count }) }}
          </span>
        </header>

        <!-- Bricks mirror the 3D count, so the 2 states never disagree -->
        <div class="tower-floor__bricks" :aria-label="floorA11y(floor)">
          <i
            v-for="n in brickCount(floor)"
            :key="n"
            class="tower-floor__brick"
            :class="{ 'tower-floor__brick--new': isNewFloor(floor) }"
          />
        </div>

        <!-- Windows for this domain -->
        <div v-if="windowsFor(floor).length > 0" class="tower-floor__windows">
          <button
            v-for="win in windowsFor(floor)"
            :key="win.topic_id"
            type="button"
            class="tower-window"
            :class="`tower-window--${win.reason === '复习到期' ? 'review' : 'recommended'}`"
            :aria-label="windowA11y(win)"
            @click="emit('windowSelect', win)"
          >
            <span aria-hidden="true">{{ win.reason === '复习到期' ? '🔁' : '✨' }}</span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'TowerInterior' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CastleFloor, CastleTower, CastleWindow } from '@/api/learning'

const props = defineProps<{
  tower: CastleTower
  windows: CastleWindow[]
  /** Topic id from `?new=` — only that floor animates. */
  newTopicId?: string | null
  newDomain?: string | null
  newSubject?: string | null
}>()

const emit = defineEmits<{
  windowSelect: [window: CastleWindow]
}>()

const { t } = useI18n()

const MAX_BRICKS_PER_FLOOR = 8

/** Bottom-up so the tower grows visually. */
const reversedFloors = computed<CastleFloor[]>(() => [...props.tower.floors].reverse())

function floorState(floor: CastleFloor): 'mastered' | 'decayed' | 'learning' | 'empty' {
  if (floor.review_due_count > 0) return 'decayed'
  if (floor.total_count > 0 && floor.mastered_count === floor.total_count) return 'mastered'
  if (floor.mastered_count > 0 || floor.learning_count > 0) return 'learning'
  return 'empty'
}

function brickCount(floor: CastleFloor): number {
  if (floor.total_count === 0) return 0
  const ratio = (floor.mastered_count + floor.learning_count) / floor.total_count
  return ratio === 0 ? 0 : Math.max(1, Math.round(ratio * MAX_BRICKS_PER_FLOOR))
}

function windowsFor(floor: CastleFloor): CastleWindow[] {
  const anchor = floor.domain || ''
  return props.windows.filter((w) => (w.domain || '') === anchor)
}

function isNewFloor(floor: CastleFloor): boolean {
  if (!props.newTopicId || !props.newSubject) return false
  if (props.newSubject !== props.tower.subject) return false
  return (floor.domain || '') === (props.newDomain ?? '')
}

function floorA11y(floor: CastleFloor): string {
  return t('learning.castle.floorA11y', {
    domain: floor.domain || t('learning.castle.rootFloor'),
    mastered: floor.mastered_count,
    total: floor.total_count,
  })
}

function windowA11y(win: CastleWindow): string {
  const reason =
    win.reason === '复习到期'
      ? t('learning.castle.windowReview')
      : t('learning.castle.windowRecommended')
  return t('learning.castle.windowA11y', {
    topic: win.topic_name_zh || win.topic_name,
    reason,
  })
}
</script>

<style scoped>
.tower-interior {
  /* Flex child of .castle3d-tower: must be allowed to shrink below its
     min-content width, or long domain names push the list past the viewport. */
  flex: 1;
  min-width: 0;
  min-height: 0;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-md);
  box-sizing: border-box;
  -webkit-overflow-scrolling: touch;
}

.tower-interior__floors {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tower-floor {
  min-width: 0;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md, 10px);
  background: var(--color-surface-card);
  padding: 10px 12px;
  box-sizing: border-box;
}

.tower-floor--empty {
  opacity: 0.5;
}

.tower-floor--mastered {
  border-color: var(--color-primary);
}

.tower-floor--decayed {
  border-style: dashed;
  border-color: var(--color-brand-coral, #ff6b5a);
}

.tower-floor__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.tower-floor__domain {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}

.tower-floor__count {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--color-muted);
}

.tower-floor__bricks {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.tower-floor__brick {
  width: 18px;
  height: 12px;
  border-radius: 2px;
  background: var(--color-primary);
  opacity: 0.75;
}

.tower-floor__brick--new {
  animation: brick-drop 520ms cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

@keyframes brick-drop {
  from {
    transform: translateY(-14px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 0.75;
  }
}

.tower-floor__windows {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.tower-window {
  /* 56x56 minimum hit area (R12) */
  min-width: 56px;
  min-height: 56px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--color-hairline);
  border-radius: var(--radius-pill, 999px);
  background: var(--color-canvas);
  font-size: 18px;
  cursor: pointer;
}

.tower-window:active {
  transform: scale(0.96);
}

.tower-window--review {
  border-color: var(--color-brand-coral, #ff6b5a);
}

.tower-window--recommended {
  border-color: var(--color-brand-teal, #1a3a3a);
}

@media (prefers-reduced-motion: reduce) {
  .tower-floor__brick--new {
    animation: none;
  }
}
</style>
