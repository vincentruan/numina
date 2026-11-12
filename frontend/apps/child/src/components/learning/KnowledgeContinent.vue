<template>
  <div class="knowledge-continent">
    <!-- Continent grid — each subject rendered as a continent card -->
    <div class="continent-grid">
      <button
        v-for="continent in continents"
        :key="continent.subject"
        class="continent-card"
        :class="[
          getTerrainClass(continent.subject),
          { 'continent-card--active': selectedSubject === continent.subject },
        ]"
        :style="continentStyle(continent)"
        :disabled="continent.itemCount === 0"
        @click="$emit('select', continent.subject)"
      >
        <!-- Continent marker icon -->
        <div class="continent-card__icon">
          <span class="continent-card__emoji">{{ continent.icon }}</span>
        </div>

        <!-- Continent name -->
        <h3 class="continent-card__name">
          {{ continent.displayName }}
        </h3>

        <!-- Mastery progress -->
        <div class="continent-card__progress">
          <div
            class="continent-card__progress-fill"
            :style="{ width: continent.masteryPercent + '%' }"
          />
        </div>
        <span class="continent-card__stats">
          {{ t('continent.mastered', { mastered: continent.masteredCount, total: continent.itemCount }) }}
        </span>

        <!-- Fog overlay — opacity driven by mastery ratio -->
        <div
          class="continent-card__fog"
          :style="{ opacity: computeFogOpacity(continent.masteryRatio) }"
        />

        <!-- Frontier badge — for unexplored continents with available content -->
        <span v-if="continent.isFrontier" class="continent-card__frontier-badge">
          📍
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CONTINENT_THEMES, getTerrainClass, type ContinentTheme } from '@/data/continentThemes'

export interface ContinentSummary {
  /** Subject key */
  subject: string
  /** Display name (already translated) */
  displayName: string
  /** Emoji marker icon */
  icon: string
  /** Total topic count in this continent */
  itemCount: number
  /** Number of mastered topics */
  masteredCount: number
  /** Mastery ratio 0-1 */
  masteryRatio: number
  /** Mastery percentage 0-100 */
  masteryPercent: number
  /** Whether this continent has frontier (next-to-explore) topics */
  isFrontier: boolean
}

const props = defineProps<{
  /** List of continents to render */
  continents: ContinentSummary[]
  /** Currently selected subject */
  selectedSubject: string
}>()

defineEmits<{
  select: [subject: string]
}>()

const { t } = useI18n()

/**
 * Compute fog opacity based on mastery ratio (matches ContinentFog.vue logic).
 *
 * 0% mastered → 0.7 (mostly obscured — unexplored continent)
 * 1-49% → 0.4 (dimmed)
 * 50-79% → 0.15 (lightly veiled)
 * 80%+ → 0 (fully clear — mastered continent)
 */
function computeFogOpacity(ratio: number): number {
  const clamped = Math.max(0, Math.min(1, ratio))
  if (clamped >= 0.8) return 0
  if (clamped >= 0.5) return 0.15
  if (clamped > 0) return 0.4
  return 0.7
}

/** Inline style for each continent card — accent background from theme */
function continentStyle(continent: ContinentSummary): Record<string, string> {
  const theme = CONTINENT_THEMES[continent.subject]
  if (!theme) return {}
  return {
    '--continent-accent': theme.accent,
    '--continent-color': theme.color,
  }
}
</script>

<style scoped>
.knowledge-continent {
  padding: 8px 0 16px;
}

.continent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  padding: 0 4px;
}

.continent-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 12px;
  border: 2px solid var(--continent-color, var(--color-border));
  border-radius: 16px;
  background: var(--continent-accent, var(--color-surface-card));
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  overflow: hidden;
  min-height: 120px;
  text-align: center;
}

.continent-card:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.continent-card--active {
  border-color: var(--continent-color);
  box-shadow: 0 0 0 3px var(--continent-accent);
}

.continent-card:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.continent-card__icon {
  font-size: 32px;
  margin-bottom: 8px;
  z-index: 1;
}

.continent-card__emoji {
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1));
}

.continent-card__name {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #1a1a1a);
  margin: 0 0 8px;
  line-height: 1.3;
  z-index: 1;
}

.continent-card__progress {
  width: 100%;
  height: 4px;
  background: rgba(0, 0, 0, 0.08);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 6px;
  z-index: 1;
}

.continent-card__progress-fill {
  height: 100%;
  background: var(--continent-color);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.continent-card__stats {
  font-size: 11px;
  color: var(--color-text-muted, #888);
  z-index: 1;
}

/* Fog overlay — sits on top, pointer-events: none */
.continent-card__fog {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at 50% 40%,
    transparent 30%,
    rgba(180, 180, 200, 0.6) 100%
  );
  pointer-events: none;
  transition: opacity 0.4s ease;
  border-radius: 14px;
}

/* Frontier badge — marks the next continent to explore */
.continent-card__frontier-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 14px;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.2));
  z-index: 2;
}

/* Terrain-specific border styling */
.territory--math { border-style: solid; }
.territory--science { border-style: dashed; }
.territory--language { border-style: solid; }
.territory--social { border-style: dotted; }
.territory--arts { border-style: double; }

/* Dark mode adjustments */
[data-theme="dark"] .continent-card {
  background: var(--color-surface-card);
  border-color: var(--color-border);
}

[data-theme="dark"] .continent-card--active {
  border-color: var(--continent-color);
}

[data-theme="dark"] .continent-card__fog {
  background: radial-gradient(
    circle at 50% 40%,
    transparent 30%,
    rgba(40, 40, 60, 0.7) 100%
  );
}

/* Mobile: smaller cards, 2-column grid */
@media (max-width: 480px) {
  .continent-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  .continent-card {
    padding: 12px 8px;
    min-height: 100px;
  }
  .continent-card__icon {
    font-size: 28px;
  }
  .continent-card__name {
    font-size: 12px;
  }
}
</style>
