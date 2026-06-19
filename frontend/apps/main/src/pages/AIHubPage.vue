<template>
  <div class="ai-hub-page">
    <!-- Skeleton for initial loading -->
    <AIHubSkeleton v-if="initialLoading" />

    <!-- Actual Content -->
    <template v-else>
    <!-- Header -->
    <div class="hub-header">
      <div class="hub-header-blob" aria-hidden="true"></div>
      <div class="hub-header-main">
        <div class="hub-greeting">
          <span class="hub-greeting-label">{{ t('aiHub.title') }}</span>
          <span class="hub-greeting-hi">{{ t('aiHub.greeting', { userName }) }}</span>
        </div>
        <!-- Health score ring -->
        <div class="hub-score-ring" :class="scoreClass" role="img" :aria-label="scoreAriaLabel">
          <svg viewBox="0 0 64 64" class="score-svg" aria-hidden="true">
            <circle class="score-track" cx="32" cy="32" r="26" />
            <circle
              class="score-fill"
              cx="32" cy="32" r="26"
              :stroke-dasharray="`${scoreArc} 163.36`"
            />
          </svg>
          <div class="score-inner">
            <span class="score-number">{{ displayScore }}</span>
            <span class="score-label">{{ t('aiHub.scoreUnit') }}</span>
          </div>
        </div>
      </div>
      <!-- Stats row -->
      <div class="hub-stats">
        <div class="hub-stat-item">
          <span class="hub-stat-num">{{ suggestionCount }}</span>
          <span class="hub-stat-label">{{ t('aiHub.suggestionsCount') }}</span>
        </div>
        <div class="hub-stat-divider" aria-hidden="true"></div>
        <div class="hub-stat-item">
          <span class="hub-stat-num warn">{{ alertCount }}</span>
          <span class="hub-stat-label">{{ t('aiHub.alertsCount') }}</span>
        </div>
        <div class="hub-stat-divider" aria-hidden="true"></div>
        <div class="hub-stat-item">
          <span class="hub-stat-num">{{ currentReport?.data_completeness_score != null ? currentReport.data_completeness_score.toFixed(0) : '-' }}%</span>
          <span class="hub-stat-label">{{ t('aiHub.dataCompleteness') }}</span>
        </div>
        <div class="hub-stat-divider" aria-hidden="true"></div>
        <div class="hub-stat-meta" aria-live="polite">
          <template v-if="reportLoading">
            <van-loading size="10" />
            <span>{{ t('aiHub.generating') }}</span>
          </template>
          <template v-else-if="reportGeneratedAt">
            <span>{{ reportAge }}</span>
            <button class="refresh-btn" :disabled="reportLoading" :aria-label="t('aiHub.refreshReport')" @click="() => refreshReport()">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
              </svg>
            </button>
          </template>
          <template v-else>
            <span>{{ t('aiHub.noReport') }}</span>
          </template>
        </div>
      </div>
    </div>

    <!-- Report summary card -->
    <div v-if="currentReport" class="report-summary-card" role="button" tabindex="0" :aria-label="t('aiHub.viewFullReport')" @click="$router.push('/ai/report')" @keydown.enter="$router.push('/ai/report')" @keydown.space.prevent="$router.push('/ai/report')">
      <div class="report-summary-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        {{ t('aiHub.latestReport') }}
      </div>
      <p class="report-summary-text">{{ currentReport.summary }}</p>
      <div class="report-summary-cta">
        {{ t('aiHub.viewFullReport') }}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </div>
    </div>

    <!-- Generating in progress -->
    <div v-else-if="reportLoading" class="report-generating-card" aria-live="polite" :aria-label="t('aiHub.reportGenerating')">
      <van-loading size="28" color="var(--color-primary)" />
      <p class="report-generating-text">{{ stream.progressMessage || t('aiHub.reportGenerating') }}</p>
      <p class="report-generating-sub">{{ t('aiHub.reportGeneratingSub') }}</p>
    </div>

    <!-- AI disabled state: shown when family has not enabled AI -->
    <div v-else-if="!aiStore.aiEnabled" class="ai-disabled-card" role="status" :aria-label="t('aiHub.disabledTitle')">
      <div class="ai-disabled-icon" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9.663 17h4.673M12 3a6 6 0 0 1 6 6c0 2.22-1.2 4.16-3 5.2V16a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-1.8A6 6 0 0 1 12 3z"/>
          <path d="M9 21h6"/>
          <line x1="2" y1="2" x2="22" y2="22" stroke-width="1.8"/>
        </svg>
      </div>
      <p class="ai-disabled-title">{{ t('aiHub.disabledTitle') }}</p>
      <p class="ai-disabled-desc">{{ t('aiHub.disabledDesc') }}</p>
      <button class="ai-disabled-action" @click="$router.push('/settings/ai')">
        {{ t('aiHub.disabledAction') }}
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </button>
    </div>

    <div v-else class="report-empty-card" role="button" tabindex="0" :aria-label="t('aiHub.generateFirstReport')" @click="generateReport">
      <div class="report-empty-icon" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
      </div>
      <p class="report-empty-text">{{ t('aiHub.generateFirstReport') }}</p>
      <p class="report-empty-sub">{{ t('aiHub.generateFirstReportSub') }}</p>
    </div>

    <!-- Agent sections: 数鸣 featured card → My Agents → Analysis Apps -->
    <div class="feature-section">
      <!-- 数鸣 featured card (full width) -->
      <NuminaAgentCard @consult="handleNuminaConsult" />

      <!-- 我的智能体 Section -->
      <div class="agent-section">
        <div class="agent-section__header" @click="toggleMyAgents">
          <span class="agent-section__title">{{ t('aiHub.myAgents') }}</span>
          <span class="agent-section__count">{{ t('aiHub.myAgentsCount', { count: enabledCustomAgents.length }) }}</span>
          <van-icon :name="myAgentsCollapsed ? 'arrow-down' : 'arrow-up'" class="agent-section__icon" />
        </div>
        <div class="agent-section__content" :class="{ collapsed: myAgentsCollapsed }">
          <!-- Empty state for custom agents -->
          <div v-if="enabledCustomAgents.length === 0" class="agent-empty-state">
            <div class="agent-empty-icon" aria-hidden="true">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
              </svg>
            </div>
            <p class="agent-empty-text">{{ t('aiHub.myAgentsEmpty') }}</p>
            <p class="agent-empty-hint">{{ t('aiHub.myAgentsEmptyHint') }}</p>
            <van-button v-if="isOwner" size="small" type="primary" plain @click="router.push({ name: 'AgentCreate' })">
              {{ t('aiHub.myAgentsCreate') }}
            </van-button>
          </div>
          <!-- Custom agents grid -->
          <div v-else class="agent-grid">
            <AgentCard
              v-for="agent in enabledCustomAgents"
              :key="agent.id"
              :agent="agent"
              :show-actions="true"
              @consult="handleAgentConsult"
              @edit="handleAgentEdit"
            />
            <!-- Create agent card -->
            <div v-if="isOwner" class="agent-card agent-card--create" @click="router.push({ name: 'AgentCreate' })">
              <div class="agent-card__icon">＋</div>
              <div class="agent-card__body">
                <div class="agent-card__name">{{ t('agents.createAgent') }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 分析应用 Section -->
      <div class="agent-section">
        <div class="agent-section__header" @click="toggleAnalysisApps">
          <span class="agent-section__title">{{ t('aiHub.analysisApps') }}</span>
          <span class="agent-section__count">{{ t('aiHub.analysisAppsCount', { count: analysisApps.length }) }}</span>
          <van-icon :name="analysisAppsCollapsed ? 'arrow-down' : 'arrow-up'" class="agent-section__icon" />
        </div>
        <div class="agent-section__content" :class="{ collapsed: analysisAppsCollapsed }">
          <!-- Analysis apps list -->
          <div class="app-list">
            <!-- Time Machine app card -->
            <div
              class="app-list-item"
              role="button"
              tabindex="0"
              @click="router.push('/ai/time-machine')"
              @keydown.enter="router.push('/ai/time-machine')"
              @keydown.space.prevent="router.push('/ai/time-machine')"
            >
              <div class="app-list-item__icon">
                <SvgIcon name="time-machine" class="icon-svg" />
              </div>
              <div class="app-list-item__body">
                <div class="app-list-item__name">{{ t('aiHub.timeMachineCardTitle') }}</div>
                <div class="app-list-item__desc">{{ t('aiHub.timeMachineCardDesc') }}</div>
              </div>
              <van-icon name="arrow" class="app-list-item__arrow" />
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- Chat input with integrated toolbar -->
    <div class="chat-entry">
      <AIChatInput
        v-model="chatInput"
        v-model:mode="chatMode"
        v-model:web-search="webSearch"
        :disabled="!selectedAgent"
        :placeholder="chatPlaceholder"
        :agents="agentChoices"
        :selected-agent-id="selectedAgent?.id"
        @submit="submitChatFromInput"
        @action="onInputAction"
        @select-agent="showAgentPicker = true"
      />
      <!-- Hidden file inputs (kept here so the page owns the upload state) -->
      <input ref="fileInputRef" type="file" accept=".pdf,.doc,.docx,.txt,.md" hidden @change="handleFileSelect" />
      <input ref="photoInputRef" type="file" accept="image/*" hidden @change="handlePhotoSelect" />
    </div>

    <!-- Agent picker action sheet (only shows actual agents, not Time Machine) -->
    <van-action-sheet
      v-model:show="showAgentPicker"
      :title="t('aiHub.selectAgent')"
    >
      <van-cell-group inset>
        <van-cell
          v-for="agent in agentChoices"
          :key="agent.id"
          :title="agent.display_name"
          :label="agent.description || ''"
          clickable
          :class="{ 'agent-row--active': agent.id === selectedAgent?.id }"
          @click="selectAgent(agent)"
        >
          <template #icon>
            <div class="agent-row__icon">
              <AIBrainIcon v-if="agent.agent_name === NUMINA_AGENT_NAME" :active="true" />
              <span v-else class="agent-row__emoji">{{ agent.icon || '🤖' }}</span>
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </van-action-sheet>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getUser } from '@/utils/storage'
import { getAIReport } from '@/api/ai'
import { getSystemDefaultSession } from '@/api/sessions'
import { useAIStore } from '@/stores/ai'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import { showToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAIReportStream } from '@/composables/useAIReportStream'
import AgentCard from '@/components/agent/AgentCard.vue'
import NuminaAgentCard from '@/components/agent/NuminaAgentCard.vue'
import AIBrainIcon from '@/components/common/AIBrainIcon.vue'
import AIChatInput from '@/components/common/AIChatInput.vue'
import AIHubSkeleton from '@/components/ai/AIHubSkeleton.vue'
import { SHUMING_DEFAULT_PROMPT, SYSTEM_DEFAULT_SESSION_MAX_AGE_HOURS } from '@/constants/agentDefaultPrompt'
import type { Agent } from '@/types/agent'
import type { AIReport } from '@/types'

const NUMINA_AGENT_NAME = 'numina'

const { t } = useI18n()

const router = useRouter()
const aiStore = useAIStore()
const agentStore = useAgentStore()
const authStore = useAuthStore()
const stream = useAIReportStream()
const isOwner = authStore.user?.role === 'owner'

const currentReport = ref<AIReport | null>(null)
const reportGeneratedAt = ref<string | null>(null)
const reportLoading = ref(false)
const initialLoading = ref(true)
const chatInput = ref('')
const chatMode = ref<'normal' | 'smart'>('normal')
const webSearch = ref(false)
const showAgentPicker = ref(false)
const selectedAgent = ref<Agent | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const photoInputRef = ref<HTMLInputElement | null>(null)

// Enabled custom agents for the grid
const enabledCustomAgents = computed(() =>
  agentStore.customAgents.filter((a) => a.is_enabled),
)

// Collapsible section states — my agents expands when content first loads
const myAgentsCollapsed = ref(true)
const analysisAppsCollapsed = ref(true)

// Set initial collapse state once agents are loaded
const myAgentsInitialized = ref(false)
watch(
  () => enabledCustomAgents.value.length,
  (len) => {
    if (!myAgentsInitialized.value) {
      myAgentsCollapsed.value = len === 0
      if (len > 0) myAgentsInitialized.value = true
    }
  },
  { immediate: true },
)

// Analysis apps list (currently only Time Machine)
const analysisApps = computed(() => [
  { id: 'time-machine', name: t('aiHub.timeMachineCardTitle'), desc: t('aiHub.timeMachineCardDesc'), route: '/ai/time-machine' },
])

function toggleMyAgents() {
  myAgentsCollapsed.value = !myAgentsCollapsed.value
}

function toggleAnalysisApps() {
  analysisAppsCollapsed.value = !analysisAppsCollapsed.value
}

const numinaAgent = computed(() =>
  agentStore.systemAgents.find((a) => a.agent_name === NUMINA_AGENT_NAME) || null,
)

// Agent choices for picker - only actual agents, not apps like Time Machine
const agentChoices = computed<Agent[]>(() => [
  ...agentStore.systemAgents.filter((a) => a.is_enabled),
  ...agentStore.customAgents.filter((a) => a.is_enabled),
])

// Dynamic placeholder based on selected agent
const chatPlaceholder = computed(() => {
  if (!selectedAgent.value) return t('aiHub.chatPlaceholderNoAgent')
  return t('aiHub.chatPlaceholderWithAgent', { name: selectedAgent.value.display_name })
})

// Default selected agent to 数鸣 once loaded
watch(
  () => agentStore.systemAgents,
  () => {
    if (selectedAgent.value) return
    if (numinaAgent.value && numinaAgent.value.is_enabled) {
      selectedAgent.value = numinaAgent.value
    } else {
      const fallback = agentChoices.value[0] || null
      selectedAgent.value = fallback
    }
  },
  { deep: true, immediate: true },
)

function selectAgent(agent: Agent) {
  selectedAgent.value = agent
  showAgentPicker.value = false
}

function triggerFileUpload() {
  fileInputRef.value?.click()
}

function triggerPhotoUpload() {
  photoInputRef.value?.click()
}

function handleFileSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    showToast(t('toast.fileSelected', { name: file.name }))
    // TODO: implement file upload to chat
  }
  ;(e.target as HTMLInputElement).value = ''
}

function handlePhotoSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    showToast(t('toast.photoSelected'))
    // TODO: implement photo upload to chat
  }
  ;(e.target as HTMLInputElement).value = ''
}

function submitChat() {
  const q = chatInput.value.trim()
  if (!q || !selectedAgent.value) return

  const deepThink = chatMode.value === 'smart'
  aiStore.draftQuery = q
  aiStore.deepThinkEnabled = deepThink
  aiStore.webSearchEnabled = webSearch.value

  router.push({
    path: '/ai/chat',
    query: {
      q,
      agentId: selectedAgent.value.id,
      newSession: '1',
      deepThink: deepThink ? '1' : undefined,
      webSearch: webSearch.value ? '1' : undefined,
    },
  })

  chatInput.value = ''
}

function submitChatFromInput(value: string) {
  chatInput.value = value
  submitChat()
}

function onInputAction(type: 'file' | 'image' | 'link' | 'clear' | 'camera' | 'ocr' | 'webpage' | 'history') {
  if (type === 'camera') triggerPhotoUpload()
  else if (type === 'file') triggerFileUpload()
  else if (type === 'image') triggerPhotoUpload()
}

const userName = computed(() => getUser()?.display_name || t('aiHub.defaultUserName'))

const displayScore = computed(() => currentReport.value?.overall_score ?? '?')

const scoreArc = computed(() => {
  const s = currentReport.value?.overall_score ?? 0
  return ((s / 100) * 163.36).toFixed(2)
})

const scoreClass = computed(() => {
  const s = currentReport.value?.overall_score ?? 0
  if (s >= 80) return 'score-excellent'
  if (s >= 60) return 'score-good'
  if (s >= 40) return 'score-fair'
  return s > 0 ? 'score-poor' : 'score-empty'
})

const scoreAriaLabel = computed(() => {
  const score = displayScore.value
  return t('aiHub.scoreAriaLabel', { score })
})

const reportAge = computed(() => {
  if (!reportGeneratedAt.value) return ''
  const diff = Date.now() - new Date(reportGeneratedAt.value).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return t('aiHub.justNow')
  if (mins < 60) return t('aiHub.minutesAgo', { minutes: mins })
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return t('aiHub.hoursAgo', { hours: hrs })
  return t('aiHub.daysAgo', { days: Math.floor(hrs / 24) })
})

const suggestionCount = computed(() => {
  const r = currentReport.value
  if (!r) return 0
  return [r.net_worth_health, r.allocation_analysis, r.liability_pressure, r.asset_efficiency]
    .filter(Boolean).length
})

const alertCount = computed(() => {
  const r = currentReport.value
  if (!r) return 0
  // count sections with score < 60
  const sections = [r.net_worth_health, r.allocation_analysis, r.liability_pressure, r.asset_efficiency]
  return sections.filter(s => s && typeof s.score === 'number' && s.score < 60).length
})

const CACHE_TTL_MS = 24 * 60 * 60 * 1000 // 24h

async function loadReport() {
  try {
    const res = await getAIReport()
    if (res.data.report) {
      currentReport.value = res.data.report as unknown as AIReport
      reportGeneratedAt.value = res.data.generated_at ?? null
      // Trigger background refresh if cache is stale (>24h)
      if (reportGeneratedAt.value) {
        const age = Date.now() - new Date(reportGeneratedAt.value).getTime()
        if (age > CACHE_TTL_MS) {
          refreshReport(true)
        }
      }
    }
  } catch {
    // no report yet
  }
}

async function generateReport() {
  reportLoading.value = true
  stream.reset()
  try {
    await stream.connect()
    if (stream.report.value) {
      currentReport.value = stream.report.value as unknown as AIReport
      reportGeneratedAt.value = stream.generatedAt.value
    }
  } catch {
    showToast(stream.errorMessage.value || t('toast.aiGenerateFailed'))
  } finally {
    reportLoading.value = false
  }
}

async function refreshReport(silent?: boolean) {
  if (reportLoading.value) return // avoid duplicate with scheduler
  if (!aiStore.aiEnabled) return
  if (!silent) reportLoading.value = true
  stream.reset()
  try {
    await stream.connect()
    if (stream.report.value) {
      currentReport.value = stream.report.value as unknown as AIReport
      reportGeneratedAt.value = stream.generatedAt.value
    }
  } catch {
    if (!silent) showFailToast(t('toast.refreshFailed'))
  } finally {
    if (!silent) reportLoading.value = false
  }
}

function handleAgentConsult(agent: Agent) {
  // R4: unified agentId routing — every agent card lands in AIChatBox with
  // the agent's id in the query string. AIChatBox loads the matching
  // agent's soul/skills based on agentId. No more agent_name special cases
  // (the old ai-assistant / time-machine branches were architectural
  // accidents from before agentId routing existed) and no more skills-based
  // dead routing (the builtin agents that those branches targeted were
  // deleted by migration b6745e8a2c14).
  router.push({ name: 'AIChat', query: { agentId: agent.id } })
}

function handleNuminaConsult() {
  if (!numinaAgent.value) return
  const agentId = numinaAgent.value.id
  getSystemDefaultSession(SYSTEM_DEFAULT_SESSION_MAX_AGE_HOURS)
    .then((res) => {
      const cached = res.data.session
      if (cached) {
        router.push({ name: 'AIChat', query: { agentId, sessionId: cached.session_id } })
      } else {
        aiStore.draftQuery = SHUMING_DEFAULT_PROMPT
        router.push({ name: 'AIChat', query: { agentId, newSession: '1', source: 'system_default' } })
      }
    })
    .catch(() => {
      router.push({ name: 'AIChat', query: { agentId } })
    })
}

function handleAgentEdit(agent: Agent) {
  router.push({ name: 'AgentEdit', params: { id: agent.id } })
}

onMounted(async () => {
  await aiStore.fetchConfig()
  await agentStore.loadAgents()
  await loadReport()
  initialLoading.value = false
})

// Expose refs and functions for testing purposes
defineExpose({
  chatInput,
  chatMode,
  webSearch,
  selectedAgent,
  initialLoading,
  selectAgent,
})
</script>

<style scoped>
.ai-hub-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 140px;
}

/* ── Header: Pastel Cloud Gradient (mirrors NetWorthCard) ── */
.hub-header {
  position: relative;
  padding: 20px 16px 16px;
  background:
    linear-gradient(135deg,
      rgba(239, 44, 193, 0.10) 0%,
      rgba(189, 187, 255, 0.18) 45%,
      rgba(160, 195, 255, 0.14) 100%),
    #ffffff;
  color: #000000;
  overflow: hidden;
}

[data-theme='dark'] .hub-header {
  background:
    linear-gradient(135deg,
      rgba(189, 187, 255, 0.08) 0%,
      rgba(189, 187, 255, 0.04) 50%,
      transparent 100%),
    #010120;
  color: #ffffff;
}

/* Decorative blob */
.hub-header-blob {
  position: absolute;
  top: -40px;
  right: -30px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(189, 187, 255, 0.22) 0%, transparent 70%);
  pointer-events: none;
}

[data-theme='dark'] .hub-header-blob {
  background: radial-gradient(circle, rgba(189, 187, 255, 0.10) 0%, transparent 70%);
}

/* Main row: greeting + score ring */
.hub-header-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
}

.hub-greeting {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* Mono label — uppercase, tight tracking */
.hub-greeting-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.45);
  font-family: 'Georgia', monospace;
}

[data-theme='dark'] .hub-greeting-label {
  color: var(--text-tertiary);
}

/* Display name: tight negative tracking */
.hub-greeting-hi {
  font-size: clamp(20px, 5vw, 24px);
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 1.05;
  color: #000000;
}

[data-theme='dark'] .hub-greeting-hi {
  color: #ffffff;
}

/* Score ring */
.hub-score-ring {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
}

.score-svg {
  width: 64px;
  height: 64px;
  transform: rotate(-90deg);
}

.score-track {
  fill: none;
  stroke: rgba(0, 0, 0, 0.12);
  stroke-width: 4;
}

[data-theme='dark'] .score-track {
  stroke: rgba(255, 255, 255, 0.15);
}

.score-fill {
  fill: none;
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}

.score-excellent .score-fill { stroke: #059669; }
.score-good      .score-fill { stroke: #2563eb; }
.score-fair      .score-fill { stroke: #d97706; }
.score-poor      .score-fill { stroke: #dc2626; }
.score-empty     .score-fill { stroke: rgba(0, 0, 0, 0.15); }

[data-theme='dark'] .score-excellent .score-fill { stroke: var(--color-trend-down); }
[data-theme='dark'] .score-good      .score-fill { stroke: #93c5fd; }
[data-theme='dark'] .score-fair      .score-fill { stroke: #fcd34d; }
[data-theme='dark'] .score-poor      .score-fill { stroke: var(--color-trend-up); }
[data-theme='dark'] .score-empty     .score-fill { stroke: rgba(255, 255, 255, 0.15); }

.score-inner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}

.score-number {
  font-size: 18px;
  font-weight: 500;
  letter-spacing: -0.03em;
  color: #000000;
  line-height: 1;
}

[data-theme='dark'] .score-number {
  color: #ffffff;
}

.score-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  color: rgba(0, 0, 0, 0.45);
  font-family: 'Georgia', monospace;
  line-height: 1;
}

[data-theme='dark'] .score-label {
  color: var(--text-tertiary);
}

/* Stats row: frosted glass, 8px radius, dark-blue-tinted shadow */
.hub-stats {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 12px;
  box-shadow: rgba(1, 1, 32, 0.08) 0px 2px 8px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  position: relative;
}

[data-theme='dark'] .hub-stats {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: rgba(1, 1, 32, 0.4) 0px 2px 8px;
}

.hub-stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.hub-stat-num {
  font-size: 16px;
  font-weight: 500;
  letter-spacing: -0.16px;
  color: #000000;
  line-height: 1;
}

[data-theme='dark'] .hub-stat-num {
  color: #ffffff;
}

.hub-stat-num.warn { color: #d97706; }
[data-theme='dark'] .hub-stat-num.warn { color: #fcd34d; }

.hub-stat-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.40);
  font-family: 'Georgia', monospace;
}

[data-theme='dark'] .hub-stat-label {
  color: var(--text-tertiary);
}

.hub-stat-divider {
  width: 1px;
  height: 28px;
  background: rgba(0, 0, 0, 0.10);
  flex-shrink: 0;
}

[data-theme='dark'] .hub-stat-divider {
  background: rgba(255, 255, 255, 0.12);
}

/* Meta (freshness + refresh) — rightmost slot in stats row */
.hub-stat-meta {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  color: rgba(0, 0, 0, 0.40);
  font-family: 'Georgia', monospace;
  letter-spacing: 0.055px;
  flex-shrink: 0;
  padding-left: 8px;
}

[data-theme='dark'] .hub-stat-meta {
  color: var(--text-tertiary);
}

.refresh-btn {
  background: none;
  border: none;
  padding: 8px;
  min-width: 32px;
  min-height: 32px;
  color: rgba(0, 0, 0, 0.40);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: color 0.15s;
}

[data-theme='dark'] .refresh-btn {
  color: var(--text-tertiary);
}

.refresh-btn:hover { color: #000000; }
[data-theme='dark'] .refresh-btn:hover { color: var(--text-primary); }
.refresh-btn:disabled { opacity: 0.4; cursor: default; }

/* ── Report summary card ── */
.report-summary-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 14px 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: rgba(1, 1, 32, 0.06) 0px 2px 8px;
  cursor: pointer;
  transition: box-shadow 0.15s;
}

[data-theme='dark'] .report-summary-card {
  border-color: rgba(255, 255, 255, 0.10);
  box-shadow: rgba(1, 1, 32, 0.3) 0px 2px 8px;
}

.report-summary-card:active {
  box-shadow: rgba(1, 1, 32, 0.12) 0px 4px 12px;
}

.report-summary-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.45);
  font-family: 'Georgia', monospace;
  margin-bottom: 8px;
}

[data-theme='dark'] .report-summary-title {
  color: var(--text-tertiary);
}

.report-summary-title svg { color: rgba(0, 0, 0, 0.35); }
[data-theme='dark'] .report-summary-title svg { color: rgba(255, 255, 255, 0.35); }

.report-summary-text {
  font-size: 13px;
  font-weight: 400;
  letter-spacing: -0.13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.report-summary-cta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: -0.12px;
  color: rgba(0, 0, 0, 0.55);
}

[data-theme='dark'] .report-summary-cta {
  color: rgba(255, 255, 255, 0.55);
}

/* Generating report card */
.report-generating-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 28px 16px;
  text-align: center;
  border: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

[data-theme='dark'] .report-generating-card {
  border-color: rgba(255, 255, 255, 0.10);
}

.report-generating-text {
  font-size: 14px;
  font-weight: 500;
  letter-spacing: -0.14px;
  color: var(--text-primary);
  margin: 0;
}

.report-generating-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  letter-spacing: -0.12px;
}

/* Empty report card */
.report-empty-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 24px 16px;
  text-align: center;
  cursor: pointer;
  border: 1px dashed rgba(0, 0, 0, 0.15);
  transition: border-color 0.15s;
}

[data-theme='dark'] .report-empty-card {
  border-color: rgba(255, 255, 255, 0.15);
}

.report-empty-card:active { border-color: rgba(0, 0, 0, 0.35); }
[data-theme='dark'] .report-empty-card:active { border-color: rgba(255, 255, 255, 0.35); }

.report-empty-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  color: rgba(0, 0, 0, 0.40);
}

[data-theme='dark'] .report-empty-icon {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.40);
}

.report-empty-text {
  font-size: 14px;
  font-weight: 500;
  letter-spacing: -0.14px;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.report-empty-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  letter-spacing: -0.12px;
}

/* ── Agent grid section ── */
.feature-section {
  padding: 0 16px;
  margin-top: 4px;
}

/* Collapsible section styles */
.agent-section {
  margin-top: 12px;
}

.agent-section__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--card-bg);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.agent-section__header:active {
  background: var(--van-background-2);
}

.agent-section__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.agent-section__count {
  font-size: 12px;
  color: var(--van-primary-color);
  background: rgba(25, 137, 250, 0.1);
  padding: 2px 8px;
  border-radius: 10px;
}

[data-theme='dark'] .agent-section__count {
  background: rgba(189, 187, 255, 0.15);
}

.agent-section__icon {
  font-size: 14px;
  color: var(--text-tertiary);
  margin-left: auto;
}

.agent-section__content {
  transition: max-height 0.3s ease, opacity 0.3s ease, padding 0.3s ease;
  max-height: 500px;
  opacity: 1;
  overflow: hidden;
}

.agent-section__content.collapsed {
  max-height: 0;
  opacity: 0;
  padding: 0;
  margin-bottom: 0;
}

/* Empty state for my agents */
.agent-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  border: 1px solid var(--van-border-color);
  gap: 8px;
}

.agent-empty-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}

.agent-empty-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}

.agent-empty-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 8px;
  text-align: center;
  line-height: 1.5;
}

/* App list (horizontal card list) */
.app-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.app-list-item {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--card-bg);
  border: 1px solid var(--van-border-color);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.app-list-item:active {
  transform: scale(0.98);
}

.app-list-item__icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(25, 137, 250, 0.08) 0%, rgba(189, 187, 255, 0.12) 100%);
  border-radius: 10px;
  margin-right: 12px;
  flex-shrink: 0;
}

[data-theme='dark'] .app-list-item__icon {
  background: linear-gradient(135deg, rgba(189, 187, 255, 0.14) 0%, rgba(189, 187, 255, 0.08) 100%);
}

.icon-svg {
  width: 22px;
  height: 22px;
  fill: none;
  stroke: var(--van-primary-color);
}

[data-theme='dark'] .icon-svg {
  stroke: #bdbbff;
}

.app-list-item__body {
  flex: 1;
}

.app-list-item__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--van-text-color);
  margin-bottom: 2px;
}

.app-list-item__desc {
  font-size: 12px;
  color: var(--van-text-color-2);
}

.app-list-item__arrow {
  color: var(--van-text-color-3);
  font-size: 16px;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

/* Agent card base styles (for inline cards, not the imported AgentCard component) */
.agent-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 12px;
  background: var(--van-background-2);
  border: 1px solid var(--van-border-color);
  cursor: pointer;
  transition:
    transform 0.15s,
    box-shadow 0.15s;
}

.agent-card:active {
  transform: scale(0.97);
}

.agent-card__icon {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  line-height: 1;
}

.agent-card__body {
  flex: 1;
}

.agent-card__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--van-text-color);
}

.agent-card__desc {
  font-size: 12px;
  color: var(--van-text-color-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Create agent card */
.agent-card--create {
  border: 2px dashed var(--van-border-color);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100px;
  cursor: pointer;
}

.agent-card--create .agent-card__icon {
  font-size: 28px;
  color: var(--van-text-color-3);
}

.agent-card--create .agent-card__name {
  color: var(--van-text-color-3);
  font-size: 13px;
}

/* ── Chat entry ── */
.chat-entry {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  z-index: 10;
  padding: 8px 16px 12px;
  background: var(--bg-primary, #fff);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .chat-entry {
  border-top-color: rgba(255, 255, 255, 0.10);
}

/* ── Agent picker ── */
.agent-row__icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
}

.agent-row__icon :deep(.ai-button-wrapper) {
  transform: translateY(0) scale(0.7);
}

.agent-row__icon :deep(.ai-button-3d) {
  width: 36px;
  height: 36px;
}

.agent-row__emoji {
  font-size: 24px;
}

.agent-row--active {
  background-color: rgba(99, 102, 241, 0.08);
}
</style>
.ai-disabled-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 28px 20px 24px;
  text-align: center;
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: rgba(1, 1, 32, 0.06) 0px 2px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

[data-theme='dark'] .ai-disabled-card {
  border-color: rgba(255, 255, 255, 0.10);
  box-shadow: rgba(1, 1, 32, 0.3) 0px 2px 8px;
}

.ai-disabled-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(0, 0, 0, 0.30);
  margin-bottom: 4px;
}

[data-theme='dark'] .ai-disabled-icon {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.30);
}

.ai-disabled-title {
  font-size: 15px;
  font-weight: 500;
  letter-spacing: -0.15px;
  color: var(--text-primary);
  margin: 0;
}

.ai-disabled-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 8px;
  line-height: 1.5;
  max-width: 260px;
}

.ai-disabled-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.ai-disabled-action:hover {
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.25);
}

[data-theme='dark'] .ai-disabled-action {
  border-color: rgba(255, 255, 255, 0.18);
}

[data-theme='dark'] .ai-disabled-action:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.30);
}

/* Focus rings */
.report-summary-card:focus-visible,
.report-empty-card:focus-visible {
  outline: 2px solid rgba(0, 0, 0, 0.5);
  outline-offset: 2px;
}

[data-theme='dark'] .report-summary-card:focus-visible,
[data-theme='dark'] .report-empty-card:focus-visible {
  outline-color: rgba(255, 255, 255, 0.5);
}

/* ── AI disabled card ── */
