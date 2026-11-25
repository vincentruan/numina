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
      <p class="challenge-3d-stub__notice">3D Distribute — coming soon</p>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DistributeChallenge, ChallengeVerdict } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'

defineOptions({ name: 'DistributeChallenge3D' })

const props = defineProps<{ config: DistributeChallenge }>()
const emit = defineEmits<{ complete: []; requestTutor: [] }>()
const { t } = useI18n()

const completed = ref(false)
const feedbackMessage = ref('')
const feedbackVerdict = ref<ChallengeVerdict | null>(null)
const attemptCount = ref(0)
const hasAnyPlacement = ref(false)

const showTutorSuggestion = computed(() => attemptCount.value >= 2 && !completed.value)
const allowEarlyContinue = computed(() => attemptCount.value >= 2 && !completed.value)
const statusText = computed(() => `${props.config.objects.length} items, ${props.config.zones.length} zones`)

function checkAnswer() { attemptCount.value++ }
function onContinue() { completed.value = false; emit('complete') }
</script>

<style scoped>
.challenge-3d-stub { padding: 32px; text-align: center; }
.challenge-3d-stub__notice { color: var(--color-muted); font-size: 14px; }
</style>
