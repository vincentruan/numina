<template>
  <div v-if="config" class="manipulate-challenge">
    <!-- Scenario text -->
    <div class="challenge-scenario">
      <p class="challenge-scenario__text">{{ scenarioText }}</p>
    </div>

    <!-- Interaction area (provided by child component) -->
    <slot />

    <!-- Feedback bar -->
    <div class="challenge-feedback">
      <div
        v-if="feedbackMessage"
        class="challenge-feedback__message"
        :class="feedbackClass"
      >
        <span class="challenge-feedback__glyph" aria-hidden="true">{{ feedbackGlyph }}</span>
        <span>{{ feedbackMessage }}</span>
      </div>
      <div v-else class="challenge-feedback__status">
        {{ statusText }}
      </div>
      <button
        v-if="!completed"
        class="challenge-check-btn"
        :disabled="!hasAnyPlacement"
        @click="$emit('check')"
      >
        {{ t('learning.challenge.check') }}
      </button>
      <button
        v-if="showTutorSuggestion"
        class="challenge-tutor-btn"
        @click="$emit('requestTutor')"
      >
        {{ t('learning.challenge.askTutor') }}
      </button>
      <button
        v-if="completed || allowEarlyContinue"
        class="challenge-next-btn"
        @click="$emit('continue')"
      >
        {{ t('learning.challenge.continue') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ChallengeConfig, ChallengeVerdict } from '@/types/learning-challenge'

defineOptions({ name: 'ChallengeShell' })

const props = defineProps<{
  config: ChallengeConfig
  feedbackMessage: string
  /** Three-state verdict. `correct` completes; `close` and `wrong` allow retry. */
  feedbackVerdict: ChallengeVerdict | null
  hasAnyPlacement: boolean
  completed: boolean
  showTutorSuggestion: boolean
  /**
   * True once the child has retried enough times that continuing without a
   * correct verdict should be allowed. Keeps a child who keeps landing `close`
   * from being stuck on the challenge with no way forward.
   */
  allowEarlyContinue?: boolean
  statusText: string
}>()

defineEmits<{
  check: []
  continue: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

const isZh = computed(() => locale.value.startsWith('zh'))
const scenarioText = computed(() =>
  isZh.value ? props.config.scenarioZh : props.config.scenario,
)

const feedbackClass = computed(() => {
  switch (props.feedbackVerdict) {
    case 'correct':
      return 'challenge-feedback__message--correct'
    case 'close':
      return 'challenge-feedback__message--close'
    case 'wrong':
      return 'challenge-feedback__message--wrong'
    default:
      return ''
  }
})

/**
 * Non-color cue so close/wrong stay distinguishable for a child with
 * color-vision deficiency. Each verdict has its own glyph.
 */
const feedbackGlyph = computed(() => {
  switch (props.feedbackVerdict) {
    case 'correct':
      return '✓'
    case 'close':
      return '≈'
    case 'wrong':
      return '✗'
    default:
      return ''
  }
})
</script>

<style scoped>
.manipulate-challenge {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

/* Scenario */
.challenge-scenario {
  padding: 12px 16px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
}

.challenge-scenario__text {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0;
  line-height: 1.5;
}

/* Feedback bar */
.challenge-feedback {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.challenge-feedback__message {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  padding: 10px 16px;
  border-radius: var(--radius-md);
  text-align: center;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.challenge-feedback__glyph {
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
}

.challenge-feedback__message--correct {
  background: rgba(var(--color-brand-mint-rgb), 0.2);
  color: var(--color-ink);
}

/* Close: a near miss, deliberately distinct from both success and failure.
   Uses an ochre tint plus the ≈ glyph so it stays readable without color. */
.challenge-feedback__message--close {
  background: rgba(var(--color-brand-ochre-rgb), 0.16);
  color: var(--color-ink);
  border: 1px dashed var(--color-brand-ochre);
}

.challenge-feedback__message--wrong {
  background: rgba(var(--color-brand-coral-rgb), 0.12);
  color: var(--color-ink);
}

.challenge-feedback__status {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted);
}

.challenge-check-btn,
.challenge-next-btn {
  min-height: 48px;
  min-width: 120px;
  padding: 12px 24px;
  border: none;
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.challenge-check-btn {
  background: var(--color-primary);
  color: var(--color-on-primary);
}

.challenge-check-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.challenge-next-btn {
  background: var(--color-brand-mint);
  color: var(--color-ink);
}

.challenge-tutor-btn {
  background: var(--color-surface-card);
  color: var(--color-brand-ochre);
  border: 1px solid var(--color-brand-ochre);
}
</style>
