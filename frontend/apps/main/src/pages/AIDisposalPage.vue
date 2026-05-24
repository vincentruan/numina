<template>
  <div class="ai-disposal-page">
    <PageHeader :title="t('aiDisposal.title')" />

    <div v-if="loading" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!suggestions.length" class="empty-state">
      <div class="empty-illustration" aria-hidden="true">
        <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="60" cy="60" r="56" fill="var(--empty-bg-outer)" />
          <circle cx="60" cy="60" r="42" fill="var(--empty-bg-inner)" />
          <!-- Box body -->
          <rect x="32" y="46" width="56" height="40" rx="4" fill="var(--empty-icon-fill)" />
          <!-- Box lid -->
          <path d="M28 46h64M44 46V36h32v10" stroke="var(--empty-icon-stroke)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          <!-- Arrow up (export) -->
          <path d="M60 58v18M52 64l8-8 8 8" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <!-- Checkmark badge -->
          <circle cx="84" cy="36" r="10" fill="var(--empty-badge-bg)" />
          <path d="M79 36l3.5 3.5 6-6" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <p class="empty-title">{{ t('aiTask.emptyDisposal') }}</p>
      <p class="empty-desc">{{ t('aiTask.emptyDisposalDesc') }}</p>
      <div class="actions">
        <TaskConsole
          v-model="isConsoleOpen"
          :status="taskStatus"
          :phase="taskPhase"
          :think-content="taskThinkContent"
          :think-done="taskThinkDone"
          :think-seconds="taskThinkSeconds"
          :answer-content="taskAnswerContent"
          :elapsed-seconds="taskElapsed"
          :queue-position="taskQueuePosition"
          :error-code="taskErrorCode"
          @retry="onRefresh"
        />
        <van-button
          v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
          type="primary"
          block
          @click="onRefresh"
        >
          {{ t('aiTask.emptyDisposalBtn') }}
        </van-button>
        <van-button
          v-else
          type="danger"
          block
          class="cancel-btn"
          @click="cancelTask"
        >
          <span class="stop-icon-wrapper">
            <van-icon name="stop-circle-o" class="stop-icon" />
            <van-loading size="14" type="spinner" class="spinning-ring" />
          </span>
          {{ t('aiTask.cancelBtn') }}
        </van-button>
      </div>
    </div>

    <template v-else>
      <div class="summary-bar">
        <span>{{ t('aiDisposal.pendingCount', { count: suggestions.length }) }}</span>
        <van-button
          v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
          size="mini"
          plain
          @click="onRefresh"
        >
          {{ t('aiDisposal.rescan') }}
        </van-button>
        <van-button
          v-else
          size="mini"
          type="danger"
          class="cancel-btn-mini"
          @click="cancelTask"
        >
          <span class="stop-icon-wrapper-mini">
            <van-icon name="stop-circle-o" class="stop-icon-mini" />
            <van-loading size="12" type="spinner" class="spinning-ring-mini" />
          </span>
          {{ t('aiTask.cancelBtn') }}
        </van-button>
      </div>

      <van-swipe-cell v-for="s in suggestions" :key="s.id" class="suggestion-item">
        <div class="suggestion-card">
          <div class="card-top">
            <div class="asset-info">
              <span class="asset-name">{{ s.asset_name }}</span>
              <span class="category-tag">{{ s.category_name }}</span>
            </div>
            <div class="score-badge" :class="scoreClass(s.inefficiency_score)">
              {{ s.inefficiency_score ?? '-' }}
            </div>
          </div>

          <div v-if="s.estimated_resale_range" class="resale-range">
            {{ t('aiDisposal.estimatedResale', { range: s.estimated_resale_range }) }}
          </div>

          <div class="channel-row">
            <van-icon name="shop-o" size="14" />
            <span>{{ t('aiDisposal.suggestedChannel', { channel: s.suggested_channel }) }}</span>
          </div>

          <p v-if="s.suggestion" class="suggestion-text">{{ s.suggestion }}</p>

          <div v-if="s.daily_cost != null" class="daily-cost">
            {{ t('aiDisposal.dailyWaste', { cost: s.daily_cost.toFixed(1) }) }}
          </div>
        </div>
        <template #right>
          <van-button square type="warning" :text="t('aiDisposal.dismiss')" class="dismiss-btn" @click="onDismiss(s.id)" />
        </template>
      </van-swipe-cell>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getDisposalSuggestions, dismissDisposalSuggestion } from '@/api/ai'
import { useAITask } from '@/composables/useAITask'
import PageHeader from '@/components/common/PageHeader.vue'
import TaskConsole from '@/components/ai/TaskConsole.vue'
import type { DisposalSuggestion } from '@/types'

const { t } = useI18n()

const loading = ref(false)
const suggestions = ref<DisposalSuggestion[]>([])

function scoreClass(score: number | null) {
  if (score == null) return 'score-low'
  if (score >= 70) return 'score-high'
  if (score >= 40) return 'score-medium'
  return 'score-low'
}

async function loadSuggestions() {
  loading.value = true
  try {
    const res = await getDisposalSuggestions()
    suggestions.value = res.data as DisposalSuggestion[]
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onScanComplete() {
  await loadSuggestions()
  showToast(t('toast.aiScanComplete'))
}

const {
  status: taskStatus,
  phase: taskPhase,
  thinkContent: taskThinkContent,
  thinkDone: taskThinkDone,
  thinkSeconds: taskThinkSeconds,
  answerContent: taskAnswerContent,
  elapsedSeconds: taskElapsed,
  isConsoleOpen,
  queuePosition: taskQueuePosition,
  errorCode: taskErrorCode,
  startStream,
  cancelTask,
} = useAITask('disposal', '/ai/disposal-suggestions/refresh/events', onScanComplete)

async function onRefresh() {
  await startStream()
}

async function onDismiss(id: string) {
  try {
    await dismissDisposalSuggestion(id)
    suggestions.value = suggestions.value.filter(s => s.id !== id)
  } catch {
    showToast(t('toast.operationFailed'))
  }
}

onMounted(loadSuggestions)
</script>

<style scoped>
.ai-disposal-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}
.loading-state { display: flex; justify-content: center; padding: 60px; }
.empty-state {
  padding: 48px 24px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  --empty-bg-outer: rgba(25, 137, 250, 0.08);
  --empty-bg-inner: rgba(25, 137, 250, 0.12);
  --empty-icon-fill: var(--van-primary-color, #1989fa);
  --empty-icon-stroke: var(--van-primary-color, #1989fa);
  --empty-badge-bg: #34c759;
}
.empty-illustration {
  margin-bottom: 20px;
  filter: drop-shadow(0 4px 12px rgba(1, 1, 32, 0.1));
}
.empty-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: -0.2px;
}
.empty-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 24px;
  max-width: 260px;
}
.actions { padding: 0; width: 100%; }
.summary-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--text-secondary);
}
.suggestion-item { margin: 8px 16px; border-radius: 12px; overflow: hidden; }
.suggestion-card { background: var(--bg-primary); padding: 14px 16px; }
.card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.asset-info { display: flex; flex-direction: column; gap: 4px; }
.asset-name { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.category-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: var(--bg-secondary); color: var(--text-secondary);
  align-self: flex-start;
}
.score-badge {
  width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700;
}
.score-high { background: #fce4ec; color: #c62828; }
.score-medium { background: #fff8e1; color: #92400e; }
.score-low { background: #e8f5e9; color: #2e7d32; }
.resale-range { font-size: 13px; color: var(--text-primary); font-weight: 500; margin-bottom: 6px; }
.channel-row {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text-secondary); margin-bottom: 6px;
}
.suggestion-text { font-size: 13px; color: var(--text-secondary); margin: 0 0 6px; line-height: 1.5; }
.daily-cost { font-size: 12px; color: #f44336; }
.dismiss-btn { height: 100%; }
.cancel-btn {
  position: relative;
}
.stop-icon-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: 6px;
}
.stop-icon { font-size: 16px; }
.spinning-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(255, 255, 255, 0.6);
}
.cancel-btn-mini {
  position: relative;
}
.stop-icon-wrapper-mini {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: 4px;
}
.stop-icon-mini { font-size: 14px; }
.spinning-ring-mini {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(244, 67, 54, 0.4);
}
</style>
