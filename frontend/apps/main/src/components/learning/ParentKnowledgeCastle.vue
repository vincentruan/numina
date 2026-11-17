<template>
  <div class="parent-knowledge-castle">
    <!-- Loading skeleton -->
    <van-skeleton v-if="state === 'loading'" :rows="5" :round="true" />

    <!-- Error: retry -->
    <div v-else-if="state === 'error'" class="castle-error">
      <span class="castle-error__icon" aria-hidden="true">🏰</span>
      <p class="castle-error__title">{{ t('learning.castle.errorTitle') }}</p>
      <van-button type="primary" size="small" @click="emit('retry')">
        {{ t('learning.castle.errorRetry') }}
      </van-button>
    </div>

    <!-- Content (zero-progress children still land here: full foundation + empty floors) -->
    <div v-else class="castle-body">
      <header class="castle-header">
        <h1 class="castle-header__title">{{ t('learning.castle.parentTitle') }}</h1>
        <p class="castle-header__subtitle">{{ t('learning.castle.parentSubtitle') }}</p>
        <p v-if="streakDays > 0" class="castle-header__streak">
          <span aria-hidden="true">🔥</span>
          {{ t('learning.castle.decoStreak', { days: streakDays }) }}
        </p>
      </header>

      <!-- Horizontally scrollable strip of towers -->
      <div class="castle-strip" role="list">
        <section
          v-for="tower in towers"
          :key="tower.subject"
          role="listitem"
          class="tower"
          :class="`tower--${tower.subject}`"
          :style="towerStyle(tower.subject)"
        >
          <div class="tower__cap" aria-hidden="true">{{ towerIcon(tower.subject) }}</div>

          <!-- Floor stack: bottom-up so the tower grows visually -->
          <div class="tower__floors">
            <div
              v-for="floor in reversedFloors(tower)"
              :key="floor.domain"
              class="floor"
              :class="`floor--${floorState(floor)}`"
              :aria-label="floorA11y(floor)"
            >
              <span class="floor__bricks" aria-hidden="true">
                <i
                  v-for="n in brickCount(floor)"
                  :key="n"
                  class="brick"
                />
              </span>
            </div>
          </div>

          <div class="tower__plinth" aria-hidden="true" />

          <p class="tower__summary">
            {{ t('learning.castle.towers', {
              mastered: tower.mastered_count,
              total: tower.total_count,
            }) }}
          </p>
          <span class="sr-only">{{ towerA11y(tower) }}</span>

          <!-- Windows: display-only in parent view (no click action) -->
          <div
            v-if="windowsFor(tower.subject).length"
            class="tower__windows"
          >
            <span
              v-for="win in windowsFor(tower.subject)"
              :key="win.topic_id"
              class="window"
              :class="`window--${isReviewDue(win) ? 'review' : 'recommended'}`"
              :title="windowTooltip(win)"
              :aria-label="windowA11y(win)"
            >
              <span class="window__glyph" aria-hidden="true">
                {{ isReviewDue(win) ? '🔁' : '✨' }}
              </span>
            </span>
          </div>
        </section>
      </div>

      <p v-if="towers.length === 0" class="castle-empty">
        {{ t('learning.castle.parentEmpty') }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ParentKnowledgeCastle' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CastleFloor, CastleIndex, CastleTower, CastleWindow } from '@/api/learning'
import { CONTINENT_THEMES, getContinentTheme } from '@/data/continentThemes'
import { subjectLabel } from '@/utils/domainLabel'

const props = defineProps<{
  castle: CastleIndex | null
  state: 'loading' | 'error' | 'content'
}>()

const emit = defineEmits<{
  retry: []
}>()

const { t } = useI18n()

const towers = computed<CastleTower[]>(() => props.castle?.towers ?? [])
const windows = computed<CastleWindow[]>(() => props.castle?.windows ?? [])
const streakDays = computed(() => props.castle?.streak_days ?? 0)

// --- theme helpers -------------------------------------------------------

function towerStyle(subject: string): Record<string, string> {
  const theme = CONTINENT_THEMES[subject]
  if (!theme) return {}
  return { '--tower-color': theme.color, '--tower-accent': theme.accent }
}

function towerIcon(subject: string): string {
  return getContinentTheme(subject).icon
}

// --- state derivation ----------------------------------------------------

function floorState(floor: CastleFloor): 'mastered' | 'decayed' | 'learning' | 'empty' {
  if (floor.review_due_count > 0) return 'decayed'
  if (floor.total_count > 0 && floor.mastered_count === floor.total_count) return 'mastered'
  if (floor.mastered_count > 0 || floor.learning_count > 0) return 'learning'
  return 'empty'
}

const MAX_BRICKS_PER_FLOOR = 8

function brickCount(floor: CastleFloor): number {
  if (floor.total_count === 0) return 0
  const ratio = (floor.mastered_count + floor.learning_count) / floor.total_count
  return ratio === 0 ? 0 : Math.max(1, Math.round(ratio * MAX_BRICKS_PER_FLOOR))
}

function reversedFloors(tower: CastleTower): CastleFloor[] {
  return [...tower.floors].reverse()
}

// --- windows (display-only) ----------------------------------------------

/**
 * Backend sends `reason` as the Chinese display string ('复习到期' /
 * '推荐学习'). Centralised here so the component compares in one place and a
 * future machine code only needs changing in this helper.
 */
const REASON_REVIEW_DUE = '复习到期'

function isReviewDue(win: CastleWindow): boolean {
  return win.reason === REASON_REVIEW_DUE
}

function windowReasonLabel(win: CastleWindow): string {
  return isReviewDue(win)
    ? t('learning.castle.windowReview')
    : t('learning.castle.windowRecommended')
}

function windowsFor(subject: string): CastleWindow[] {
  return windows.value.filter((w) => w.subject === subject)
}

function windowTooltip(win: CastleWindow): string {
  const name = win.topic_name_zh || win.topic_name
  return `${name} — ${windowReasonLabel(win)}`
}

function windowA11y(win: CastleWindow): string {
  return t('learning.castle.windowA11y', {
    topic: win.topic_name_zh || win.topic_name,
    reason: windowReasonLabel(win),
  })
}

function towerA11y(tower: CastleTower): string {
  return t('learning.castle.towerA11y', {
    subject: subjectLabel(t, tower.subject),
    mastered: tower.mastered_count,
    total: tower.total_count,
  })
}

function floorA11y(floor: CastleFloor): string {
  return t('learning.castle.floorA11y', {
    domain: floor.domain,
    mastered: floor.mastered_count,
    total: floor.total_count,
  })
}
</script>

<style scoped>
.parent-knowledge-castle {
  padding: 16px;
}

/* --- header --- */
.castle-header {
  margin-bottom: 20px;
  text-align: center;
}
.castle-header__title {
  margin: 0;
  font-size: 22px;
  color: var(--text-primary);
}
.castle-header__subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.castle-header__streak {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

/* --- horizontal strip --- */
.castle-strip {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 16px;
  scroll-snap-type: x proximity;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.castle-strip::-webkit-scrollbar {
  display: none;
}

/* --- tower --- */
.tower {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 0 0 auto;
  min-width: 120px;
  scroll-snap-align: start;
}
.tower__cap {
  font-size: 26px;
  line-height: 1;
  margin-bottom: 4px;
}
.tower__floors {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 100%;
}
.tower__plinth {
  width: 100%;
  height: 10px;
  border-radius: 0 0 6px 6px;
  background: var(--tower-color, var(--separator));
  opacity: 0.5;
}
.tower__summary {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

/* --- floor --- */
.floor {
  min-height: 16px;
  border: 1px solid var(--separator);
  border-radius: 6px;
  background: var(--card-bg);
  padding: 2px 3px;
}
.floor__bricks {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}
.brick {
  width: 10px;
  height: 8px;
  border-radius: 2px;
  background: var(--tower-color, var(--van-primary-color));
}

.floor--empty {
  opacity: 0.45;
}
.floor--learning .brick {
  opacity: 0.7;
}
.floor--mastered {
  border-color: var(--tower-color, var(--van-primary-color));
  background: var(--tower-accent, var(--card-bg));
}

/* Decay: dashed outline + fading, never removal */
.floor--decayed {
  border-style: dashed;
  border-color: #ff6b5a;
  background: repeating-linear-gradient(
    45deg,
    var(--card-bg),
    var(--card-bg) 4px,
    var(--separator) 4px,
    var(--separator) 6px
  );
  opacity: 0.75;
}
.floor--decayed .brick {
  opacity: 0.5;
}

/* --- windows (display-only) --- */
.tower__windows {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 8px;
}
.window {
  min-width: 36px;
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--separator);
  border-radius: 999px;
  background: var(--card-bg);
  font-size: 16px;
  cursor: default;
}
.window--review {
  border-color: #ff6b5a;
}
.window--recommended {
  border-color: #2a9d8f;
}

/* --- error --- */
.castle-error {
  text-align: center;
  padding: 40px 16px;
}
.castle-error__icon {
  font-size: 40px;
  display: block;
}
.castle-error__title {
  margin: 8px 0;
  color: var(--text-secondary);
}

.castle-empty {
  text-align: center;
  color: var(--text-secondary);
  margin-top: 20px;
}

/* --- reduced motion --- */
@media (prefers-reduced-motion: reduce) {
  .window,
  .floor,
  .brick {
    transition: none !important;
    animation: none !important;
  }
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
