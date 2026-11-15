<template>
  <div class="knowledge-castle">
    <!-- Skeleton: distinct from the zero-progress castle (U5) -->
    <RoleShimmer
      v-if="state === 'loading'"
      variant="clay-pulse"
      data-test="castle-skeleton"
    />

    <!-- Error: retry, never rendered as an empty castle -->
    <div v-else-if="state === 'error'" class="castle-error" data-test="castle-error">
      <span class="castle-error__icon" aria-hidden="true">🏰</span>
      <p class="castle-error__title">{{ t('learning.castle.errorTitle') }}</p>
      <button
        type="button"
        class="castle-error__retry"
        data-test="castle-retry"
        @click="emit('retry')"
      >
        {{ t('learning.castle.errorRetry') }}
      </button>
    </div>

    <!-- Content (zero-progress children still land here: full foundation + empty floors) -->
    <div v-else class="castle-body" data-test="castle-content">
      <header class="castle-header">
        <h1 class="castle-header__title">{{ t('learning.castle.title') }}</h1>
        <p class="castle-header__subtitle">{{ t('learning.castle.subtitle') }}</p>
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
              :class="[
                `floor--${floorState(floor)}`,
                { 'floor--brick-drop': isNewFloor(tower.subject, floor) },
              ]"
              :aria-label="floorA11y(tower.subject, floor)"
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

          <!-- Unlit windows: only for review-due / recommended topics -->
          <div
            v-if="windowsFor(tower.subject).length"
            class="tower__windows"
          >
            <button
              v-for="win in windowsFor(tower.subject)"
              :key="win.topic_id"
              type="button"
              class="window"
              :class="`window--${win.reason === '复习到期' ? 'review' : 'recommended'}`"
              :aria-label="windowA11y(win)"
              data-test="castle-window"
              @click="onWindowClick(win)"
            >
              <span class="window__glyph" aria-hidden="true">
                {{ win.reason === '复习到期' ? '🔁' : '✨' }}
              </span>
            </button>
          </div>
        </section>
      </div>

      <p v-if="towers.length === 0" class="castle-empty">
        {{ t('learning.empty') }}
      </p>
    </div>

    <CastleCelebration
      v-if="celebrating"
      @done="celebrating = false"
    />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'KnowledgeCastle' })

import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CastleFloor, CastleIndex, CastleTower, CastleWindow } from '@/api/learning'
import { CONTINENT_THEMES, getContinentTheme } from '@/data/continentThemes'
import RoleShimmer from '@/components/RoleShimmer.vue'
import CastleCelebration from '@/components/learning/CastleCelebration.vue'

const props = defineProps<{
  castle: CastleIndex | null
  state: 'loading' | 'error' | 'content'
  /** Topic id from `?new=` — the only brick that animates (F1). */
  newTopicId?: string | null
  /** Subject/domain of that topic, resolved by the page, so we can find its floor. */
  newSubject?: string | null
  newDomain?: string | null
}>()

const emit = defineEmits<{
  retry: []
  windowSelect: [window: CastleWindow]
}>()

const { t } = useI18n()

const towers = computed<CastleTower[]>(() => props.castle?.towers ?? [])
const windows = computed<CastleWindow[]>(() => props.castle?.windows ?? [])
const streakDays = computed(() => props.castle?.streak_days ?? 0)

const celebrating = ref(false)
/** Fires at most once per arrival with `?new=` — pull-to-refresh must not replay (F3). */
const celebrationConsumed = ref(false)

// --- theme helpers -------------------------------------------------------

function towerStyle(subject: string): Record<string, string> {
  const theme = CONTINENT_THEMES[subject]
  if (!theme) return {}
  return { '--tower-color': theme.color, '--tower-accent': theme.accent }
}

function towerIcon(subject: string): string {
  return getContinentTheme(subject).icon
}

// --- state derivation (never regresses; decay = cracks + fading) ---------

function floorState(floor: CastleFloor): 'mastered' | 'decayed' | 'learning' | 'empty' {
  if (floor.review_due_count > 0) return 'decayed'
  if (floor.total_count > 0 && floor.mastered_count === floor.total_count) return 'mastered'
  if (floor.mastered_count > 0 || floor.learning_count > 0) return 'learning'
  return 'empty'
}

/** Aggregated bricks: capped so a 200-topic floor does not emit 200 nodes (R11). */
const MAX_BRICKS_PER_FLOOR = 8

function brickCount(floor: CastleFloor): number {
  if (floor.total_count === 0) return 0
  const ratio = (floor.mastered_count + floor.learning_count) / floor.total_count
  // A floor with *any* progress must show at least one brick — otherwise the
  // brick-drop animation on `?new=` has nothing to animate for large floors.
  return ratio === 0 ? 0 : Math.max(1, Math.round(ratio * MAX_BRICKS_PER_FLOOR))
}

function reversedFloors(tower: CastleTower): CastleFloor[] {
  return [...tower.floors].reverse()
}

// --- windows -------------------------------------------------------------

function windowsFor(subject: string): CastleWindow[] {
  return windows.value.filter((w) => w.subject === subject)
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

function towerA11y(tower: CastleTower): string {
  return t('learning.castle.towerA11y', {
    subject: t(`learning.subject.${tower.subject}`, tower.subject),
    mastered: tower.mastered_count,
    total: tower.total_count,
  })
}

function floorA11y(subject: string, floor: CastleFloor): string {
  return t('learning.castle.floorA11y', {
    domain: floor.domain,
    mastered: floor.mastered_count,
    total: floor.total_count,
  })
}

function onWindowClick(win: CastleWindow): void {
  emit('windowSelect', win)
}

// --- brick-drop animation + celebration (F1, R6) -------------------------

/** True only for the floor that owns the `?new` topic — nothing else animates. */
function isNewFloor(subject: string, floor: CastleFloor): boolean {
  if (!props.newTopicId || !props.newSubject) return false
  // Backend emits floor.domain as `topic.domain or ""` (empty string when
  // the topic's domain is null); match against the normalized anchor.
  const anchor = props.newDomain ?? ''
  return subject === props.newSubject && (floor.domain || '') === anchor
}

/**
 * Tiered celebration (KD6): a completed subject tower gets the full fireworks.
 * Only checked when the child arrived via `?new` — a spontaneous open must not
 * replay a celebration for a tower that was already finished (F3).
 */
watch(
  () => [props.newTopicId, props.newSubject, props.castle] as const,
  ([topicId, subject, castle]) => {
    if (!topicId || !subject || !castle) {
      celebrating.value = false
      return
    }
    // Fire exactly once per arrival with `?new=` — pull-to-refresh must not
    // replay the fireworks for a tower that was already completed (F3).
    if (celebrationConsumed.value) {
      celebrating.value = false
      return
    }
    const tower = castle.towers.find((tw) => tw.subject === subject)
    if (!tower || tower.total_count === 0 || tower.mastered_count !== tower.total_count) {
      return
    }
    celebrating.value = true
    celebrationConsumed.value = true
  },
  { immediate: true },
)
</script>

<style scoped>
.knowledge-castle {
  padding: var(--space-md);
}

/* --- header --- */
.castle-header {
  margin-bottom: var(--space-lg);
  text-align: center;
}
.castle-header__title {
  margin: 0;
  font-size: 22px;
  color: var(--color-ink);
}
.castle-header__subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-muted);
}
.castle-header__streak {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--color-muted);
}

/* --- horizontal strip (native overflow + scroll-snap, per plan) --- */
.castle-strip {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: var(--space-md);
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
  border-radius: 0 0 var(--radius-sm, 6px) var(--radius-sm, 6px);
  background: var(--tower-color, var(--color-border));
  opacity: 0.5;
}
.tower__summary {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--color-muted);
  white-space: nowrap;
}

/* --- floor --- */
.floor {
  min-height: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm, 6px);
  background: var(--color-surface-card);
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
  background: var(--tower-color, var(--color-primary));
}

.floor--empty {
  opacity: 0.45;
}
.floor--learning .brick {
  opacity: 0.7;
}
.floor--mastered {
  border-color: var(--tower-color, var(--color-primary));
  background: var(--tower-accent, var(--color-surface-card));
}

/* Decay: cracks are a dashed outline + fading, never removal, and never
   colour-only (R3 colour-blind requirement). */
.floor--decayed {
  border-style: dashed;
  border-color: var(--color-brand-coral, #ff6b5a);
  background: repeating-linear-gradient(
    45deg,
    var(--color-surface-card),
    var(--color-surface-card) 4px,
    var(--color-border) 4px,
    var(--color-border) 6px
  );
  opacity: 0.75;
}
.floor--decayed .brick {
  opacity: 0.5;
}

/* Brick-drop: only the floor owning the `?new` topic animates (F1) */
.floor--brick-drop .brick {
  animation: brick-drop 520ms cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
.floor--brick-drop {
  animation: floor-glow 900ms ease-out;
}

@keyframes brick-drop {
  from {
    transform: translateY(-14px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes floor-glow {
  0%,
  100% {
    box-shadow: none;
  }
  40% {
    box-shadow: 0 0 10px var(--tower-color, var(--color-primary));
  }
}

/* --- windows --- */
.tower__windows {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 8px;
}
.window {
  /* 44px minimum touch target (R7) */
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-pill, 999px);
  background: var(--color-surface-card);
  cursor: pointer;
  font-size: 18px;
}
.window:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.window:active {
  transform: scale(0.96);
}
.window--review {
  border-color: var(--color-brand-coral, #ff6b5a);
}
.window--recommended {
  border-color: var(--color-brand-teal, #1a3a3a);
}

/* --- error --- */
.castle-error {
  text-align: center;
  padding: var(--space-xl) var(--space-md);
}
.castle-error__icon {
  font-size: 40px;
  display: block;
}
.castle-error__title {
  margin: var(--space-sm) 0;
  color: var(--color-body);
}
.castle-error__retry {
  min-height: 44px;
  padding: 0 var(--space-lg);
  border: none;
  border-radius: var(--radius-pill, 999px);
  background: var(--color-primary);
  color: var(--color-on-dark, #fff);
  cursor: pointer;
}

.castle-empty {
  text-align: center;
  color: var(--color-muted);
  margin-top: var(--space-lg);
}

/* --- dark mode --- */
[data-theme='dark'] .floor {
  background: var(--color-surface-card);
}
[data-theme='dark'] .floor--decayed {
  background: repeating-linear-gradient(
    45deg,
    var(--color-surface-card),
    var(--color-surface-card) 4px,
    var(--color-border) 4px,
    var(--color-border) 6px
  );
}

/* --- reduced motion --- */
@media (prefers-reduced-motion: reduce) {
  .window,
  .floor,
  .brick,
  .floor--brick-drop,
  .floor--brick-drop .brick {
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
