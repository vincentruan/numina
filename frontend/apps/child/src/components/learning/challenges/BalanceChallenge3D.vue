<template>
  <ChallengeShell
    :config="config"
    :feedback-message="feedbackMessage"
    :feedback-verdict="feedbackVerdict"
    :has-any-placement="hasAnyPlacement"
    :completed="completed"
    :show-tutor-suggestion="showTutorSuggestion"
    :allow-early-continue="allowEarlyContinue"
    :status-text="statusText"
    @check="checkAnswer"
    @continue="onContinue"
    @request-tutor="emit('requestTutor')"
  >
    <div class="challenge-3d-stub">
      <p class="challenge-3d-stub__notice">3D Balance — coming soon</p>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { BalanceChallenge, ChallengeVerdict } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'

defineOptions({ name: 'BalanceChallenge3D' })

const props = defineProps<{ config: BalanceChallenge }>()
const emit = defineEmits<{ complete: []; requestTutor: [] }>()
const { t, locale } = useI18n()

const completed = ref(false)
const feedbackMessage = ref('')
const feedbackVerdict = ref<ChallengeVerdict | null>(null)
const attemptCount = ref(0)
const hasAnyPlacement = ref(false)

const isZh = computed(() => locale.value.startsWith('zh'))
const showTutorSuggestion = computed(() => attemptCount.value >= 2 && !completed.value)
const allowEarlyContinue = computed(() => attemptCount.value >= 2 && !completed.value)
const statusText = computed(() => t('learning.challenge.placedCount', { placed: 0, total: props.config.rightSlots }))

function checkAnswer() { attemptCount.value++ }
function onContinue() { completed.value = false; emit('complete') }
</script>

<style scoped>
.challenge-3d-stub { padding: 32px; text-align: center; }
.challenge-3d-stub__notice { color: var(--color-muted); font-size: 14px; }
</style>
