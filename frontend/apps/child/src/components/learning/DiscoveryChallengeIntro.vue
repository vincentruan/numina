<template>
  <div class="discovery-intro">
    <!-- Scenario presentation -->
    <div v-if="step === 'scenario'" class="discovery-scenario">
      <div class="scenario-icon">🤔</div>
      <h2 class="scenario-title">{{ t('discovery.challengeTitle') }}</h2>
      <p class="scenario-text">{{ displayScenario }}</p>
      <p class="scenario-hint">{{ t('discovery.noWorry') }}</p>
      <button class="btn-primary discovery-start-btn" @click="startChallenge">
        {{ t('discovery.tryIt') }}
      </button>
    </div>

    <!-- Challenge interaction (delegates to ManipulateObserveReflect) -->
    <div v-else-if="step === 'challenge'" class="discovery-challenge">
      <ManipulateObserveReflect
        :config="config"
        :show-hint="showHint"
        @complete="onChallengeComplete"
        @request-tutor="$emit('request-tutor')"
      />
      <button
        v-if="!challengeCompleted"
        class="btn-secondary hint-btn"
        @click="showHint = !showHint"
      >
        {{ showHint ? t('discovery.hideHint') : t('discovery.giveHint') }} 💡
      </button>
    </div>

    <!-- Discovery moment: reveal concept name -->
    <div v-else-if="step === 'discovery'" class="discovery-reveal">
      <div class="reveal-celebration">✨</div>
      <p class="reveal-message">{{ displayDiscoveryMessage }}</p>
      <div v-if="displayConceptName" class="reveal-concept">
        <p class="reveal-concept-text">
          {{ t('discovery.whatYouDidIs', { concept: displayConceptName }) }}
        </p>
      </div>
      <button class="btn-primary discovery-continue-btn" @click="continueToPractice">
        {{ t('discovery.keepGoing') }} →
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ManipulateObserveReflect from '@/components/learning/ManipulateObserveReflect.vue'
import type { ChallengeConfig } from '@/types/learning-challenge'

const props = defineProps<{
  config: ChallengeConfig
}>()

const emit = defineEmits<{
  complete: []
  'request-tutor': []
}>()

const { t, locale } = useI18n()

type Step = 'scenario' | 'challenge' | 'discovery'
const step = ref<Step>('scenario')
const showHint = ref(false)
const challengeCompleted = ref(false)

const displayScenario = computed(() => {
  if (locale.value.startsWith('zh') && props.config.scenarioZh) {
    return props.config.scenarioZh
  }
  return props.config.scenario
})

const displayDiscoveryMessage = computed(() => {
  if (locale.value.startsWith('zh') && props.config.discoveryMessageZh) {
    return props.config.discoveryMessageZh
  }
  return props.config.discoveryMessage
})

const displayConceptName = computed(() => {
  if (locale.value.startsWith('zh') && props.config.conceptNameZh) {
    return props.config.conceptNameZh
  }
  return props.config.conceptName
})

function startChallenge() {
  step.value = 'challenge'
}

function onChallengeComplete() {
  challengeCompleted.value = true
  step.value = 'discovery'
}

function continueToPractice() {
  emit('complete')
}
</script>

<style scoped>
.discovery-intro {
  padding: 24px 16px;
  text-align: center;
}

/* Scenario phase */
.discovery-scenario {
  animation: fadeIn 0.4s ease-out;
}

.scenario-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.scenario-title {
  font-family: 'Inter', sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text-primary, #1a1a1a);
  margin: 0 0 16px;
}

.scenario-text {
  font-size: 16px;
  line-height: 1.6;
  color: var(--color-text-secondary, #4a4a4a);
  margin: 0 0 12px;
  padding: 16px;
  background: var(--color-surface-card, #fff);
  border-radius: 12px;
  border: 2px solid var(--color-brand-ochre, #e8a835);
}

.scenario-hint {
  font-size: 14px;
  color: var(--color-text-muted, #888);
  font-style: italic;
  margin: 0 0 24px;
}

.discovery-start-btn {
  min-width: 160px;
  padding: 14px 32px;
  font-size: 16px;
  font-weight: 600;
}

/* Challenge phase */
.discovery-challenge {
  animation: fadeIn 0.3s ease-out;
}

.hint-btn {
  margin-top: 16px;
  font-size: 14px;
}

/* Discovery reveal phase */
.discovery-reveal {
  animation: scaleIn 0.5s ease-out;
}

.reveal-celebration {
  font-size: 56px;
  margin-bottom: 16px;
  animation: bounce 0.6s ease-out;
}

.reveal-message {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-brand-teal, #2ba89f);
  margin: 0 0 20px;
}

.reveal-concept {
  padding: 20px;
  background: linear-gradient(135deg, var(--color-brand-ochre-light, #fef3d9), var(--color-brand-teal-light, #e6f7f5));
  border-radius: 16px;
  margin: 0 0 24px;
}

.reveal-concept-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary, #1a1a1a);
  margin: 0;
}

.discovery-continue-btn {
  min-width: 160px;
  padding: 14px 32px;
  font-size: 16px;
  font-weight: 600;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.9); }
  to { opacity: 1; transform: scale(1); }
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}
</style>
