<script setup lang="ts">
/**
 * CapabilityCard — displays an AICapability as a clickable card on the AI Hub.
 *
 * Renders the capability's icon, color, name, description, and example questions.
 * Clicking the card navigates to the AI chat page with the capability ID.
 */
import type { AICapability } from '@/api/ai'
import IIcon from '@/components/IIcon.vue'
import { isEmoji } from '@/utils/agent'

const props = defineProps<{
  capability: AICapability
}>()

const emit = defineEmits<{
  click: [capability: AICapability]
}>()

function iconIsEmoji(): boolean {
  return isEmoji(props.capability.ui.icon)
}
</script>

<template>
  <div
    class="capability-card"
    :style="{ '--cap-color': capability.ui.color }"
    @click="emit('click', capability)"
  >
    <div class="capability-card__icon" :class="`capability-card__icon--${capability.id}`">
      <!-- Emoji icon -->
      <span v-if="iconIsEmoji()" class="capability-card__emoji">{{ capability.ui.icon }}</span>
      <!-- Iconify / SVG icon -->
      <IIcon v-else :icon="capability.ui.icon" size="28" :color="'var(--cap-color)'" />
    </div>
    <div class="capability-card__body">
      <div class="capability-card__name">{{ capability.name }}</div>
      <div class="capability-card__desc">{{ capability.description }}</div>
      <!-- Example questions as chips (max 2 to avoid card overflow) -->
      <div v-if="capability.ui.example_questions.length > 0" class="capability-card__examples">
        <span
          v-for="q in capability.ui.example_questions.slice(0, 2)"
          :key="q"
          class="example-chip"
        >
          {{ q }}
        </span>
      </div>
    </div>
    <div class="capability-card__arrow" aria-hidden="true">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="9 18 15 12 9 6" />
      </svg>
    </div>
  </div>
</template>

<style scoped>
.capability-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 12px;
  background: var(--van-background-2);
  border: 1px solid var(--van-border-color);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
  position: relative;
}

.capability-card:active {
  transform: scale(0.97);
}

.capability-card:hover {
  border-color: var(--cap-color);
  box-shadow: 0 4px 16px color-mix(in srgb, var(--cap-color) 15%, transparent);
}

/* Icon slot */
.capability-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: color-mix(in srgb, var(--cap-color) 12%, transparent);
}

.capability-card__emoji {
  font-size: 24px;
  line-height: 1;
}

/* Body */
.capability-card__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.capability-card__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--van-text-color);
  letter-spacing: -0.15px;
}

.capability-card__desc {
  font-size: 12px;
  color: var(--van-text-color-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
}

/* Example question chips */
.capability-card__examples {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.example-chip {
  font-size: 11px;
  color: var(--cap-color);
  background: color-mix(in srgb, var(--cap-color) 8%, transparent);
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* Arrow indicator */
.capability-card__arrow {
  position: absolute;
  top: 16px;
  right: 16px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
</style>
