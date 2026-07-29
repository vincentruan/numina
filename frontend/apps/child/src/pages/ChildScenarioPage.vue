<template>
  <div class="scenario-page">
    <PageHeader :title="t('scenario.title')" />
    <van-pull-refresh
      v-model="refreshing"
      :pulling-text="t('common.pullRefresh.pulling')"
      :loosing-text="t('common.pullRefresh.loosing')"
      :loading-text="t('common.pullRefresh.loading')"
      :success-text="t('common.pullRefresh.success')"
      @refresh="onRefresh"
    >
      <van-skeleton v-if="loading && !refreshing && !scenario" title :row="3" :row-width="['100%', '80%', '60%']" />

      <div v-else-if="error && !scenario" class="error-msg">
        {{ error }}
      </div>

      <template v-else-if="scenario">
        <ScenarioCard
          :story="scenario.story"
          :choices="scenario.choices"
          :age-group="scenario.age_group"
          :completed="scenario.completed"
          @choose="onChoose"
        />

        <p v-if="scenario.completed" class="already-completed">
          {{ t('scenario.alreadyCompleted') }}
        </p>
      </template>
    </van-pull-refresh>

    <ScenarioFeedback
      :visible="feedbackVisible"
      :feedback-text="feedback.feedbackText"
      :dimension-hint="feedback.dimensionHint"
      :badges-unlocked="feedback.badgesUnlocked"
      @close="onFeedbackClose"
    />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildScenario' })

import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showFailToast } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import { getWeeklyScenario, submitChoice, type ScenarioResponse } from '@/api/literacy'
import ScenarioCard from '@/components/literacy/ScenarioCard.vue'
import ScenarioFeedback from '@/components/literacy/ScenarioFeedback.vue'

const { t } = useI18n()
const { increment, decrement } = usePageLoading()

const scenario = ref<ScenarioResponse | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')

const feedbackVisible = ref(false)
const feedback = reactive({
  feedbackText: '',
  dimensionHint: '',
  badgesUnlocked: [] as string[],
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    scenario.value = await getWeeklyScenario()
  } catch {
    error.value = t('scenario.loadFailed')
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

async function onChoose(index: number) {
  if (!scenario.value) return
  try {
    const res = await submitChoice(index)
    feedback.feedbackText = res.feedback_text
    feedback.dimensionHint = res.dimension_hint
    feedback.badgesUnlocked = res.badges_unlocked
    feedbackVisible.value = true
    // Mark scenario completed locally
    scenario.value = { ...scenario.value, completed: true }
  } catch {
    showFailToast(t('scenario.submitFailed'))
  }
}

function onFeedbackClose() {
  feedbackVisible.value = false
}

onMounted(async () => {
  increment()
  try {
    await load()
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.scenario-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

.loading-state {
  text-align: center;
  margin-top: 60px;
  color: var(--color-muted-soft);
  font-family: Inter, sans-serif;
  font-size: 15px;
}

.error-msg {
  background: var(--color-brand-coral);
  color: var(--color-on-primary);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin: 0 0 16px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  text-align: center;
}

.already-completed {
  text-align: center;
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  margin-top: var(--space-md);
}
</style>
