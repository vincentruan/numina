<template>
  <div class="parent-continent-overlay">
    <!-- Empty state when no progress -->
    <div v-if="!hasProgress" class="overlay-empty">
      <p class="overlay-empty__text">{{ t('learning.parentOverlay.noProgress') }}</p>
    </div>

    <template v-else>
      <!-- Mastery depth annotations per territory -->
      <div class="overlay-territories">
        <div
          v-for="territory in territoriesWithDepth"
          :key="territory.domain"
          class="overlay-territory"
        >
          <div class="overlay-territory__header">
            <span class="overlay-territory__name">{{ territory.label }}</span>
            <span class="overlay-territory__depth">
              {{ t('learning.parentOverlay.masteredCount', {
                mastered: territory.masteredCount,
                total: territory.totalCount,
              }) }}
            </span>
          </div>
          <!-- Mini progress bar -->
          <div class="overlay-territory__progress">
            <div
              class="overlay-territory__fill"
              :style="{ width: territory.depthPercent + '%' }"
            />
          </div>
          <!-- Recent activity badge -->
          <div v-if="territory.hasRecentActivity" class="overlay-territory__recent">
            {{ t('learning.parentOverlay.exploredToday', { domain: territory.label }) }}
          </div>
        </div>
      </div>

      <!-- Family practice suggestions -->
      <div v-if="suggestions.length > 0" class="overlay-suggestions">
        <h3 class="overlay-suggestions__title">
          {{ t('learning.parentOverlay.suggestionsTitle') }}
        </h3>
        <div
          v-for="suggestion in suggestions"
          :key="suggestion.domain"
          class="overlay-suggestion-card"
        >
          <div class="overlay-suggestion-card__domain">{{ suggestion.domainLabel }}</div>
          <p class="overlay-suggestion-card__text">{{ suggestion.text }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProgressWithTopic } from '@/api/learning'
import { domainLabel } from '@/utils/domainLabel'

defineOptions({ name: 'ParentContinentOverlay' })

const props = defineProps<{
  items: ProgressWithTopic[]
  territories: Array<{
    domain: string
    items: ProgressWithTopic[]
    masteredCount: number
  }>
}>()

const { t } = useI18n()

const hasProgress = computed(() =>
  props.items.some((i) => i.mastery_level !== 'locked' && i.mastery_level !== 'available'),
)

/** Check if a territory has activity in the last 24 hours */
function hasRecentActivity(items: ProgressWithTopic[], dayAgoMs: number): boolean {
  return items.some(
    (i) => i.last_practice_at && Date.parse(i.last_practice_at) > dayAgoMs,
  )
}

const territoriesWithDepth = computed(() => {
  const dayAgoMs = Date.now() - 24 * 60 * 60 * 1000
  return props.territories.map((ter) => ({
    domain: ter.domain,
    label: domainLabel(t, ter.domain),
    masteredCount: ter.masteredCount,
    totalCount: ter.items.length,
    depthPercent: ter.items.length > 0
      ? Math.round((ter.masteredCount / ter.items.length) * 100)
      : 0,
    hasRecentActivity: hasRecentActivity(ter.items, dayAgoMs),
  }))
})

/** Domain keys that have static practice suggestions. */
const SUGGESTION_KEYS: Record<string, string> = {
  Fractions: 'learning.parentOverlay.suggestionFractions',
  Addition: 'learning.parentOverlay.suggestionAddition',
  Multiplication: 'learning.parentOverlay.suggestionMultiplication',
}

const suggestions = computed(() => {
  const frontier = props.territories.filter((ter) =>
    ter.items.some((i) => i.mastery_level === 'learning' || i.mastery_level === 'available'),
  )
  if (frontier.length === 0) {
    return [{
      domain: '__default__',
      domainLabel: '',
      text: t('learning.parentOverlay.suggestionDefault'),
    }]
  }
  return frontier.slice(0, 3).map((ter) => ({
    domain: ter.domain,
    domainLabel: domainLabel(t, ter.domain),
    text: t(SUGGESTION_KEYS[ter.domain] ?? 'learning.parentOverlay.suggestionDefault'),
  }))
})
</script>

<style scoped>
.parent-continent-overlay {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.overlay-empty {
  padding: 24px 16px;
  text-align: center;
}

.overlay-empty__text {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

/* Territory depth annotations */
.overlay-territories {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.overlay-territory {
  padding: 12px;
  background: var(--card-bg);
  border-radius: var(--radius-md, 12px);
}

.overlay-territory__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.overlay-territory__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.overlay-territory__depth {
  font-size: 12px;
  color: var(--text-secondary);
}

.overlay-territory__progress {
  height: 4px;
  background: var(--van-gray-2, #ebedf0);
  border-radius: 2px;
  overflow: hidden;
}

.overlay-territory__fill {
  height: 100%;
  background: var(--van-success-color, #07c160);
  border-radius: 2px;
  transition: width 0.4s ease;
}

.overlay-territory__recent {
  margin-top: 6px;
  font-size: 12px;
  color: var(--van-primary-color, #1989fa);
}

/* Practice suggestions */
.overlay-suggestions {
  margin-top: 8px;
}

.overlay-suggestions__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 10px;
}

.overlay-suggestion-card {
  padding: 12px;
  background: var(--card-bg);
  border-radius: var(--radius-md, 12px);
  border-left: 3px solid var(--van-primary-color, #1989fa);
  margin-bottom: 8px;
}

.overlay-suggestion-card__domain {
  font-size: 12px;
  font-weight: 600;
  color: var(--van-primary-color, #1989fa);
  margin-bottom: 4px;
}

.overlay-suggestion-card__text {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}
</style>
