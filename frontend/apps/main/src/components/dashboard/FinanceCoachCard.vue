<script setup lang="ts">
import { ref, computed, onMounted, onActivated, onDeactivated, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getFinanceCoach } from '@/api/ai'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import type { FinanceSuggestion } from '@/types'
import { useI18n } from 'vue-i18n'
import { showToast, showFailToast } from 'vant'
import { useTaskResume } from '@/composables/useTaskResume'
import IIcon from '@/components/IIcon.vue'
import AiGatedInline from '@/components/ai/AiGatedInline.vue'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')
const suggestions = ref<FinanceSuggestion[]>([])
const loading = ref(true)
const loaded = ref(false)
const visible = ref(false)
const refreshing = ref(false)
const expanded = ref<string[]>([])
const cancelling = ref(false)

const count = computed(() => suggestions.value.length)

// v3: useTaskResume replaces inline resumeIfRunning + useTaskPolling
const resumeHandle = useTaskResume('coach', {
  onComplete: async () => {
    await load(false)
  },
  onError: () => {
    loading.value = false
    loaded.value = true
    // Don't toast here — the template shows inline error + retry instead
  },
})

async function load(force = false) {
  if (!familyStore.aiEnabled) {
    visible.value = false
    loading.value = false
    loaded.value = true
    return
  }
  try {
    refreshing.value = force
    loading.value = true
    // Clear stale taskId from any previous task
    resumeHandle.taskId.value = null

    const resp = await getFinanceCoach(force)

    // 202 queued: backend created a task but another is running.
    // Set taskId so useTaskPolling picks it up; onComplete re-calls load().
    if (resp.status === 'queued' && resp.task_id) {
      resumeHandle.taskId.value = resp.task_id
      return
    }

    // Advice baseline gate (spec §7.1): schema-validate before display.
    // target_id is optional — when absent the backend has sanitised a
    // hallucinated ID; the suggestion text is still shown and the CTA
    // navigates to the list tab for target_type (assets/liabilities/wishes).
    const valid = (resp.report?.suggestions || []).filter(
      (s) =>
        s &&
        s.id &&
        ['high', 'medium', 'low'].includes(s.severity) &&
        s.title &&
        s.action &&
        s.target_type &&
        s.cta_label,
    )
    if (valid.length === 0) {
      visible.value = false
      return
    }
    suggestions.value = valid.slice(0, 3)
    visible.value = true
    resumeHandle.taskId.value = null
  } catch {
    visible.value = false // silent hide on failure (spec §7.2)
    resumeHandle.taskId.value = null
  } finally {
    loading.value = false
    loaded.value = true
    refreshing.value = false
  }
}

// v3: resume replaced by useTaskResume

async function onCancel() {
  if (!resumeHandle.taskId.value || cancelling.value) return
  cancelling.value = true
  try {
    await resumeHandle.cancel()
    resumeHandle.taskId.value = null
    loading.value = false
    loaded.value = true
    showToast(t('aiTask.cancelled'))
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    cancelling.value = false
  }
}

async function onRetry() {
  await load(true)
}

function onCta(s: FinanceSuggestion) {
  // When target_id is present → navigate to the entity detail page.
  // When target_id was sanitised (hallucinated by LLM) → fall back to the
  // list tab for target_type so the user can locate the entity manually.
  const typeToListTab: Record<string, string> = {
    liability: 'liabilities',
    asset: 'assets',
    wish: 'wishes',
  }
  if (s.target_type === 'liability' && s.target_id) {
    router.push(`/liabilities/${s.target_id}`)
  } else if (s.target_type === 'asset' && s.target_id) {
    router.push(`/assets/${s.target_id}`)
  } else if (s.target_type === 'wish' && s.target_id) {
    router.push(`/wishes/${s.target_id}`)
  } else {
    const tab = typeToListTab[s.target_type]
    if (tab) router.push({ path: '/finance', query: { tab } })
  }
}

async function onToggle(names: string[]) {
  if (names.includes('coach') && !loaded.value) {
    await load(false)
  }
}

// Fix race condition: aiEnabled may still be false when onMounted fires
// because App.vue's loadCoinConfig() hasn't completed yet. Watch for it
// to become true and trigger load() when it does. Use a hasStarted flag to
// avoid double-loading when both onMounted (aiEnabled already true) and this
// watch fire for the same enablement.
let hasStarted = false
function startLoad() {
  if (hasStarted) return
  hasStarted = true
  resumeHandle.resume().then((resumed) => {
    if (!resumed) {
      load(false)
    }
  })
}

onMounted(() => {
  if (familyStore.aiEnabled) {
    startLoad()
  } else {
    loading.value = false
    loaded.value = true
  }
})

watch(
  () => familyStore.aiEnabled,
  (enabled) => {
    if (enabled && !hasStarted) {
      startLoad()
    }
  },
)

// Dashboard is KeepAlive-cached; onActivated re-runs resume logic.
let hasActivated = false
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  await resumeHandle.resume()
})

// Dashboard is KeepAlive-cached — disconnect on deactivate, cleanup on unmount.
onDeactivated(() => {
  resumeHandle.disconnect()
})

onUnmounted(() => {
  resumeHandle.cleanup()
})
</script>

<template>
  <van-cell-group inset class="chart-section finance-coach-card" data-test="finance-coach-card">
    <van-collapse v-model="expanded" @change="onToggle">
      <van-collapse-item name="coach">
        <template #title>
          <div class="coach-header">
            <span class="coach-title">
              <span class="coach-icon">
                <van-loading v-if="loading" size="16px" type="spinner" color="#1989fa" />
                <IIcon v-else :icon="'lucide:lightbulb'" size="18" class="coach-icon__svg" />
              </span>
              <span class="coach-title__text">{{ t('dashboard.financeCoach.title') }}</span>
            </span>
            <span v-if="loading" class="coach-summary coach-summary--loading">
              <!-- U21: cancel button visible when AITask is running -->
              <van-button
                v-if="resumeHandle.taskId"
                plain
                type="danger"
                size="mini"
                :loading="cancelling"
                :disabled="cancelling"
                class="coach-cancel-btn"
                @click.stop="onCancel"
              >
                {{ t('aiTask.cancelBtn') }}
              </van-button>
              <van-loading v-else size="12px" type="spinner" />
            </span>
            <span v-else-if="count > 0" class="coach-summary">
              {{ t('dashboard.financeCoach.count', { count }) }}
            </span>
            <span v-else class="coach-summary coach-summary--empty">
              {{ t('dashboard.financeCoach.empty') }}
            </span>
          </div>
        </template>

        <!-- Loading skeleton inside expanded area -->
        <template v-if="loading">
          <div v-for="i in 3" :key="i" class="fc-skeleton-item">
            <div class="fc-skeleton-bar" />
            <div class="fc-skeleton-body">
              <van-skeleton title :row="2" animate />
            </div>
          </div>
        </template>

        <!-- AI disabled teaser -->
        <div v-else-if="!familyStore.aiEnabled" class="fc-ai-gated">
          <AiGatedInline
            :title="t('dashboard.financeCoach.title')"
            :is-owner="isOwner"
          />
        </div>

        <!-- Loaded suggestions -->
        <template v-else-if="visible">
          <div
            v-for="s in suggestions"
            :key="s.id"
            :class="['fc-suggestion', `severity-${s.severity}`]"
            :data-test="`suggestion-${s.id}`"
          >
            <div class="fc-severity-bar" />
            <div class="fc-body">
              <div class="fc-s-title">{{ s.title }}</div>
              <div class="fc-s-action">{{ s.action }}</div>
            </div>
            <van-button size="small" type="primary" @click="onCta(s)">{{ s.cta_label }}</van-button>
          </div>
          <div class="fc-footer">
            <span class="fc-disclaimer">{{ t('dashboard.financeCoach.disclaimer') }}</span>
            <van-button size="mini" plain icon="replay" :loading="refreshing" @click.stop="load(true)" />
          </div>
        </template>

        <!-- Empty / error state inside expanded area -->
        <template v-else-if="loaded">
          <div v-if="resumeHandle.status.value === 'failed'" class="fc-error-state">
            <p class="fc-error-text">
              {{ resumeHandle.task.value?.error_message || t('aiTask.error.generic') }}
            </p>
            <van-button size="small" type="primary" plain @click.stop="onRetry">
              {{ t('aiTask.retry') }}
            </van-button>
          </div>
          <van-empty
            v-else
            :description="t('dashboard.financeCoach.empty')"
            image-size="60"
            class="section-empty"
          />
        </template>
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<style scoped>
.finance-coach-card {
  display: block;
  margin: 8px 0;
}
.finance-coach-card :deep(.van-collapse-item__title) {
  justify-content: flex-start;
}
.finance-coach-card :deep(.van-cell__title) {
  flex: 1;
  display: flex;
  min-width: 0;
}
.finance-coach-card :deep(.van-cell__value) {
  flex: none;
  width: 0;
}
.coach-header {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
}
.coach-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.coach-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4em;
  height: 1.4em;
  flex-shrink: 0;
}
.coach-icon__svg {
  color: #1989fa;
}
.coach-title__text {
  font-weight: 600;
}
.coach-summary {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
}
.coach-summary--loading {
  display: inline-flex;
  align-items: center;
}
/* U21: cancel button inside coach header */
.coach-cancel-btn {
  margin-left: 4px;
}
.coach-summary--empty {
  color: var(--van-text-color-3);
}

/* Skeleton items inside expanded area */
.fc-skeleton-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid var(--separator, #eee);
}
.fc-skeleton-bar {
  width: 4px;
  align-self: stretch;
  border-radius: 2px;
  background: var(--van-skeleton-row-background, #f2f3f5);
}
.fc-skeleton-body {
  flex: 1;
}
.fc-skeleton-body :deep(.van-skeleton) {
  padding: 0;
}

/* Loaded suggestion items */
.fc-suggestion {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid var(--separator, #eee);
}
.fc-severity-bar {
  width: 4px;
  align-self: stretch;
  border-radius: 2px;
}
.severity-high .fc-severity-bar {
  background: #ee0a24;
}
.severity-medium .fc-severity-bar {
  background: #ff976a;
}
.severity-low .fc-severity-bar {
  background: #1989fa;
}
.fc-body {
  flex: 1;
}
.fc-s-title {
  font-weight: 500;
}
.fc-s-action {
  font-size: 12px;
  color: var(--text-secondary, #969799);
}
.fc-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.fc-disclaimer {
  font-size: 11px;
  color: var(--van-text-color-3, #c8c9cc);
}
.section-empty {
  padding: 12px 0;
}
.fc-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 0;
}
.fc-error-text {
  font-size: 13px;
  color: var(--van-danger-color, #ee0a24);
  margin: 0;
  text-align: center;
}
</style>
