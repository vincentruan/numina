<template>
  <div :class="['scenario-card', `age-${ageTier}`]">
    <!-- Completed badge -->
    <div v-if="completed" class="completed-banner">{{ t('scenario.completed') }}</div>

    <!-- Story -->
    <div class="story">
      <p class="story-text">{{ story }}</p>
    </div>

    <!-- Choices prompt -->
    <p v-if="!completed" class="choose-prompt">{{ t('scenario.choosePrompt') }}</p>

    <!-- Choice cards -->
    <div class="choices">
      <button
        v-for="(choice, idx) in choices"
        :key="idx"
        :class="['choice-card', { disabled: completed }]"
        :disabled="completed"
        @click="onChoose(idx)"
      >
        <span class="choice-text">{{ choice.text }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ScenarioCard' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

interface Choice {
  text: string
}

const props = defineProps<{
  story: string
  choices: Choice[]
  ageGroup: string
  completed: boolean
}>()

const emit = defineEmits<{
  (e: 'choose', index: number): void
}>()

const { t } = useI18n()

const ageTier = computed<'low' | 'mid' | 'high'>(() => {
  if (props.ageGroup === 'low') return 'low'
  if (props.ageGroup === 'high') return 'high'
  return 'mid'
})

function onChoose(idx: number) {
  if (!props.completed) {
    emit('choose', idx)
  }
}
</script>

<style scoped>
.scenario-card {
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  border: 1px solid var(--color-hairline);
}

.completed-banner {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  text-align: center;
  margin-bottom: var(--space-md);
  padding: 6px 12px;
  background: rgba(var(--color-brand-ochre-rgb, 200, 150, 50), 0.12);
  border-radius: var(--radius-md);
}

.story {
  margin-bottom: var(--space-md);
}

.story-text {
  font-family: Inter, sans-serif;
  font-size: 16px;
  line-height: 1.65;
  color: var(--color-ink);
  margin: 0;
}

.age-low .story-text {
  font-size: 18px;
  line-height: 1.75;
}

.choose-prompt {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-body);
  margin: 0 0 var(--space-md);
}

.choices {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.choice-card {
  display: block;
  width: 100%;
  text-align: left;
  padding: 14px 16px;
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 15px;
  color: var(--color-ink);
  cursor: pointer;
  transition: transform 0.15s, background 0.15s;
  -webkit-tap-highlight-color: transparent;
}

.age-low .choice-card {
  font-size: 17px;
  padding: 16px 18px;
}

.choice-card:active:not(.disabled) {
  transform: scale(0.98);
  background: var(--color-brand-ochre);
  color: var(--color-on-primary);
}

.choice-card.disabled {
  opacity: 0.5;
  cursor: default;
}

.choice-text {
  display: block;
}
</style>
