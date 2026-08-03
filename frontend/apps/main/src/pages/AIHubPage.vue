<template>
  <div class="ai-hub-page">
    <!-- AI-first tooltip (shown once on first visit) -->
    <div v-if="showAiTip" class="feature-tip">{{ t('featureHints.aiFirst') }}</div>

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
          <span class="hub-greeting-hi"><ShimmerText :text="t('aiHub.greeting', { userName })" :duration="3" /></span>
        </div>
        <!-- Health score ring -->
        <div class="hub-score-ring" role="img" :aria-label="scoreAriaLabel">
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
        <template v-for="stat in statItems" :key="stat.type">
          <div class="hub-stat-item">
            <div class="hub-stat-num-wrap">
              <span class="hub-stat-num" :class="{ warn: stat.warn }">{{ stat.value }}</span>
              <van-popover
                :show="activePopover === stat.type"
                :placement="stat.type === 'alerts' ? 'bottom-end' : 'bottom'"
                :offset="[0, 8]"
                :teleport="null"
                @update:show="(v) => (activePopover = v ? stat.type : null)"
              >
                <div class="stat-popover-content">
                  <div class="stat-popover-header">
                    <span class="stat-popover-value" :class="{ warn: stat.warn }">{{ stat.value }}</span>
                    <span class="stat-popover-label">{{ stat.label }}</span>
                  </div>
                  <p class="stat-popover-desc">{{ stat.tip }}</p>
                  <button class="stat-popover-action" type="button" @click="goToReport">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                    </svg>
                    {{ t('aiHub.viewFullReport') }}
                  </button>
                </div>
                <template #reference>
                  <button class="hub-stat-info" type="button" :aria-label="t('aiHub.viewDetail')">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <circle cx="12" cy="12" r="10"/>
                      <line x1="12" y1="7" x2="12" y2="13"/>
                      <line x1="12" y1="16.5" x2="12.01" y2="16.5"/>
                    </svg>
                  </button>
                </template>
              </van-popover>
            </div>
            <span class="hub-stat-label">{{ stat.label }}</span>
          </div>
          <div class="hub-stat-divider" aria-hidden="true"></div>
        </template>
        <div class="hub-stat-meta" aria-live="polite">
          <template v-if="reportLoading">
            <span>{{ t('aiHub.generating') }}</span>
            <button class="refresh-btn refresh-btn--loading" disabled :aria-label="t('aiHub.refreshReport')">
              <van-loading size="11" color="var(--text-tertiary)" />
            </button>
          </template>
          <template v-else-if="reportGeneratedAt">
            <span>{{ reportAge }}</span>
            <button class="refresh-btn" :aria-label="t('aiHub.refreshReport')" @click="() => refreshReport()">
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
      <!-- eslint-disable vue/no-v-html -->
      <p class="report-summary-text" v-html="renderedSummary" />
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
    <AiGatedCard v-else-if="!aiStore.aiEnabled" :is-owner="isOwner" />

    <div v-else class="report-empty-card" role="button" tabindex="0" :aria-label="t('aiHub.generateFirstReport')" @click="generateReport" @keydown.enter="$router.push('/ai/report')" @keydown.space.prevent="$router.push('/ai/report')">
      <div class="report-empty-icon" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
      </div>
      <p class="report-empty-text"><ShimmerText :text="t('aiHub.generateFirstReport')" :duration="3" /></p>
      <p class="report-empty-sub">{{ t('aiHub.generateFirstReportSub') }}</p>
    </div>

    <!-- Agent sections: 小鸣 featured card → My Agents → Analysis Apps -->
    <div class="feature-section">
      <!-- 小鸣 featured card (full width) -->
      <NuminaAgentCard @consult="handleNuminaConsult" />

      <!-- 我的智能体 Section -->
      <div class="agent-section">
        <div class="agent-section__header" role="button" tabindex="0" @click="toggleMyAgents" @keydown.enter="toggleMyAgents" @keydown.space.prevent="toggleMyAgents">
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
            <van-button v-if="isOwner" size="small" type="primary" plain @click="navigateToAgentCreate">
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
            <div v-if="isOwner" class="agent-card agent-card--create" role="button" tabindex="0" @click="navigateToAgentCreate" @keydown.enter="navigateToAgentCreate" @keydown.space.prevent="navigateToAgentCreate">
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
        <div class="agent-section__header" role="button" tabindex="0" @click="toggleAnalysisApps" @keydown.enter="toggleAnalysisApps" @keydown.space.prevent="toggleAnalysisApps">
          <span class="agent-section__title">{{ t('aiHub.analysisApps') }}</span>
          <span class="agent-section__count">{{ t('aiHub.analysisAppsCount', { count: analysisApps.length }) }}</span>
          <van-icon :name="analysisAppsCollapsed ? 'arrow-down' : 'arrow-up'" class="agent-section__icon" />
        </div>
        <div class="agent-section__content" :class="{ collapsed: analysisAppsCollapsed }">
          <!-- Analysis apps list -->
          <div class="app-list">
            <!-- Trend Analysis app card -->
            <div
              class="app-list-item"
              role="button"
              tabindex="0"
              @click="goToAnalytics('trend')"
              @keydown.enter="goToAnalytics('trend')"
              @keydown.space.prevent="goToAnalytics('trend')"
            >
              <div class="app-list-item__icon">
                <SvgIcon name="trend" class="icon-svg" />
              </div>
              <div class="app-list-item__body">
                <div class="app-list-item__name">{{ t('aiHub.trendAnalysisCardTitle') }}</div>
                <div class="app-list-item__desc">{{ t('aiHub.trendAnalysisCardDesc') }}</div>
              </div>
              <van-icon name="arrow" class="app-list-item__arrow" />
            </div>

            <!-- Asset Insights app card -->
            <div
              class="app-list-item"
              role="button"
              tabindex="0"
              @click="goToAnalytics('insight')"
              @keydown.enter="goToAnalytics('insight')"
              @keydown.space.prevent="goToAnalytics('insight')"
            >
              <div class="app-list-item__icon">
                <SvgIcon name="insight" class="icon-svg" />
              </div>
              <div class="app-list-item__body">
                <div class="app-list-item__name">{{ t('aiHub.insightAnalysisCardTitle') }}</div>
                <div class="app-list-item__desc">{{ t('aiHub.insightAnalysisCardDesc') }}</div>
              </div>
              <van-icon name="arrow" class="app-list-item__arrow" />
            </div>

            <!-- Time Machine app card -->
            <div
              class="app-list-item"
              role="button"
              tabindex="0"
              @click="navigateToTimeMachine"
              @keydown.enter="navigateToTimeMachine"
              @keydown.space.prevent="navigateToTimeMachine"
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

    <!-- Chat input directly rendered (InputBox handles its own fixed bottom positioning) -->
    <!-- Hidden when AI assistant is not enabled — the AiGatedCard above explains why. -->
    <InputBox
      v-if="aiStore.aiEnabled"
      v-model="chatInput"
      v-model:web-search="webSearch"
      :disabled="!selectedAgent"
      :agents="agentChoices"
      :agent-id="selectedAgent?.id"
      :is-welcome-mode="true"
      :status="'ready'"
      :agent-icon="selectedAgent?.icon"
      :agent-label="selectedAgent?.display_name"
      @submit="submitChatFromInput"
      @select-agent="showAgentPicker = true"
    />

    <!-- Agent picker action sheet (only shows actual agents, not Time Machine) -->
    <van-action-sheet
      v-model:show="showAgentPicker"
      :title="t('aiHub.selectAgent')"
      safe-area-inset-bottom
    >
      <van-cell-group inset class="agent-picker-group">
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
              <span v-else-if="isEmoji(getAgentIcon(agent.icon))" class="agent-row__emoji">
                {{ getAgentIcon(agent.icon) || '🤖' }}
              </span>
              <IIcon v-else :icon="getAgentIcon(agent.icon)" size="24" :color="agent.color || 'var(--van-primary-color)'" />
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </van-action-sheet>
    </template>
  </div>
</template>

<script setup lang="ts">
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ref, computed, onMounted, onActivated, onDeactivated, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getUser, isGuideDone, markGuideDone } from '@/utils/storage'
import { parseApiDate } from '@/utils/format'
import { getAIReport, getAITask } from '@/api/ai'
import { getSystemDefaultSession } from '@/api/sessions'
import { useAIStore } from '@/stores/ai'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import { showToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useReportStream } from '@/composables/useReportStream'
import AgentCard from '@/components/agent/AgentCard.vue'
import NuminaAgentCard from '@/components/agent/NuminaAgentCard.vue'
import AIBrainIcon from '@/components/common/AIBrainIcon.vue'
import IIcon from '@/components/IIcon.vue'
import { getAgentIcon, isEmoji } from '@/utils/agent'
import InputBox from '@/components/ai-chat/InputBox.vue'
import ShimmerText from '@/components/ai-chat/ShimmerText.vue'
import AIHubSkeleton from '@/components/ai/AIHubSkeleton.vue'
import AiGatedCard from '@/components/ai/AiGatedCard.vue'
import { XIAOMING_DEFAULT_PROMPT, SYSTEM_DEFAULT_SESSION_MAX_AGE_HOURS } from '@/constants/agentDefaultPrompt'
import type { Agent } from '@/types/agent'
import type { AIReport } from '@/types'
import type { SubmitPayload } from '@/types/ai-chat/input-mode'
import { usePageLoading } from '@/composables/usePageLoading'

defineOptions({ name: 'AIHub' })

const NUMINA_AGENT_NAME = 'numina'

const { t } = useI18n()

const router = useRouter()
const route = useRoute()
const aiStore = useAIStore()
const agentStore = useAgentStore()
const authStore = useAuthStore()
const stream = useReportStream()
const { increment, decrement } = usePageLoading()
const isOwner = authStore.user?.role === 'owner'

// AI-first tooltip: show on first visit for 3s
const showAiTip = ref(false)

const currentReport = ref<AIReport | null>(null)
const reportGeneratedAt = ref<string | null>(null)
const reportLoading = ref(false)
const initialLoading = ref(true)
const chatInput = ref('')
const chatMode = ref<'flash' | 'thinking' | 'pro' | 'ultra'>('pro')
// `undefined` (not `false`) so the InputBox's auto-enable logic runs when the
// family has web search configured. A literal `false` would be treated as an
// explicit user choice and short-circuit auto-enable. Once the user toggles
// (or auto-enable fires), this becomes a definite boolean via v-model.
const webSearch = ref<boolean | undefined>(undefined)
const showAgentPicker = ref(false)
const selectedAgent = ref<Agent | null>(null)

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

// Analysis apps list (trend / insight / time-machine)
const analysisApps = computed(() => [
  { id: 'trend-analysis', name: t('aiHub.trendAnalysisCardTitle'), desc: t('aiHub.trendAnalysisCardDesc'), route: '/dashboard/analytics', tab: 'trend' },
  { id: 'insight-analysis', name: t('aiHub.insightAnalysisCardTitle'), desc: t('aiHub.insightAnalysisCardDesc'), route: '/dashboard/analytics', tab: 'insight' },
  { id: 'time-machine', name: t('aiHub.timeMachineCardTitle'), desc: t('aiHub.timeMachineCardDesc'), route: '/ai/time-machine' },
])

// Guard: show toast and return true when AI is not enabled, so callers can
// bail out of navigation early.  Keeps the message in one place.
function guardAiEnabled(): boolean {
  if (aiStore.aiEnabled) return false
  showToast({ message: t('aiHub.aiNotEnabled'), icon: 'warning-o' })
  return true
}

function goToAnalytics(tab: 'trend' | 'insight') {
  if (guardAiEnabled()) return
  router.push({
    path: '/dashboard/analytics',
    query: { tab },
    state: { from: route.path },
  })
}

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
// Built-in agents: only 小鸣 (numina) is suitable for chat; ignore other system agents.
const agentChoices = computed<Agent[]>(() => [
  ...agentStore.systemAgents.filter((a) => a.is_enabled && a.agent_name === NUMINA_AGENT_NAME),
  ...agentStore.customAgents.filter((a) => a.is_enabled),
])

// Default selected agent to 小鸣 once loaded
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

function submitChat() {
  const q = chatInput.value.trim()
  if (!q || !selectedAgent.value) return

  const deepThink = chatMode.value === 'thinking' || chatMode.value === 'ultra'
  aiStore.draftQuery = q
  aiStore.deepThinkEnabled = deepThink
  aiStore.webSearchEnabled = webSearch.value ?? false

  router.push({
    path: '/ai/chat',
    query: {
      q,
      agentId: selectedAgent.value.id,
      newSession: '1',
      deepThink: deepThink ? '1' : undefined,
      // Carry the web search state ONLY when the user made an explicit choice
      // (toggled on or off). When it's still `undefined` (auto-enable hasn't
      // resolved or the user never touched it), omit it so the chat page
      // runs its own auto-default logic instead of treating '0' as "off".
      webSearch: webSearch.value === undefined ? undefined : webSearch.value ? '1' : '0',
    },
  })

  chatInput.value = ''
}

function submitChatFromInput(payload: SubmitPayload) {
  chatInput.value = payload.text
  submitChat()
}


const userName = computed(() => getUser()?.display_name || t('aiHub.defaultUserName'))

const displayScore = computed(() => currentReport.value?.overall_score ?? '?')

const scoreArc = computed(() => {
  const s = currentReport.value?.overall_score ?? 0
  return ((s / 100) * 163.36).toFixed(2)
})

const scoreAriaLabel = computed(() => {
  const score = displayScore.value
  return t('aiHub.scoreAriaLabel', { score })
})

// Generate short summary (120-200 chars) for display in the summary card
const renderedSummary = computed(() => {
  if (!currentReport.value?.summary) return ''
  // Parse markdown to plain text
  const raw = marked.parse(currentReport.value.summary, { async: false }) as string
  const plainText = DOMPurify.sanitize(raw, { ALLOWED_TAGS: [] }).trim()
  // Truncate to ~180 chars (middle of 120-200 range) at word boundary
  const maxLength = 180
  if (plainText.length <= maxLength) return plainText
  const truncated = plainText.slice(0, maxLength)
  const lastSpace = truncated.lastIndexOf(' ')
  return (lastSpace > maxLength * 0.7 ? truncated.slice(0, lastSpace) : truncated) + '...'
})

const reportAge = computed(() => {
  if (!reportGeneratedAt.value) return ''
  const diff = Date.now() - parseApiDate(reportGeneratedAt.value).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return t('aiHub.justNow')
  if (mins < 60) return t('aiHub.minutesAgo', { minutes: mins })
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return t('aiHub.hoursAgo', { hours: hrs })
  return t('aiHub.daysAgo', { days: Math.floor(hrs / 24) })
})

type HubStatType = 'suggestions' | 'alerts' | 'completeness'

const activePopover = ref<HubStatType | null>(null)

const suggestionCount = computed(() => {
  const r = currentReport.value
  if (!r) return 0
  // New format: indicators array - sum of suggestions across all indicators
  if (r.indicators?.length) {
    return r.indicators.reduce((sum, ind) => sum + (ind.suggestions?.length ?? 0), 0)
  }
  // Legacy format fallback: count populated sections
  return [r.net_worth_health, r.allocation_analysis, r.liability_pressure, r.asset_efficiency]
    .filter(Boolean).length
})

const alertCount = computed(() => {
  const r = currentReport.value
  if (!r) return 0
  // New format: indicators with 1-5 score scale; alerts = score <= 2 (poor/critical)
  if (r.indicators?.length) {
    return r.indicators.filter(ind => typeof ind.score === 'number' && ind.score <= 2).length
  }
  // Legacy format fallback: score < 60 on 0-100 scale
  const sections = [r.net_worth_health, r.allocation_analysis, r.liability_pressure, r.asset_efficiency]
  return sections.filter(s => s && typeof s.score === 'number' && s.score < 60).length
})

const dataCompletenessDisplay = computed(() => {
  const score = currentReport.value?.data_completeness_score
  return score != null ? `${score.toFixed(0)}%` : '-'
})

const statItems = computed<Array<{ type: HubStatType; value: string; label: string; tip: string; warn: boolean }>>(() => [
  {
    type: 'suggestions',
    value: String(suggestionCount.value),
    label: t('aiHub.suggestionsCount'),
    tip: t('aiHub.suggestionCountTip'),
    warn: false,
  },
  {
    type: 'alerts',
    value: String(alertCount.value),
    label: t('aiHub.alertsCount'),
    tip: t('aiHub.alertCountTip'),
    warn: true,
  },
  {
    type: 'completeness',
    value: dataCompletenessDisplay.value,
    label: t('aiHub.dataCompleteness'),
    tip: t('aiHub.dataCompletenessTip'),
    warn: false,
  },
])

function goToReport() {
  activePopover.value = null
  router.push('/ai/report')
}

async function loadReport() {
  try {
    const res = await getAIReport()
    if (res.data.report) {
      currentReport.value = res.data.report as unknown as AIReport
      reportGeneratedAt.value = res.data.generated_at ?? null
    }
  } catch {
    // no report yet
  }
}

async function generateReport() {
  reportLoading.value = true
  stream.reset()
  let registered = false
  async function registerBgTask() {
    if (registered) return
    try {
      const task = await getAITask('report')
      if (task.task_id && ['running', 'queued', 'post_processing'].includes(task.status)) {
        aiStore.registerBackgroundTask({
          capability: 'report',
          taskId: task.task_id,
          sessionId: task.session_id || '',
          startedAt: task.started_at || new Date().toISOString(),
          status: task.status,
        })
        registered = true
      }
    } catch {
      // best-effort; task polling on return will catch up
    }
  }
  try {
    const connectPromise = stream.connect()
    await registerBgTask()
    if (!registered) {
      setTimeout(registerBgTask, 500)
    }
    const started = await connectPromise
    if (!started) {
      showToast({ message: t('aiReport.alreadyGenerating'), icon: 'warning-o' })
      return
    }
    // Stream completed — reload from API to get the persisted report
    // (stream.report is only populated on cache hit, not fresh generation)
    await loadReport()
    aiStore.clearBackgroundTask('report')
  } catch {
    showToast(stream.errorMessage.value || t('toast.aiGenerateFailed'))
  } finally {
    reportLoading.value = false
  }
}

async function refreshReport(silent?: boolean) {
  if (reportLoading.value) return // avoid duplicate with scheduler

  // 1-hour cooldown: prevent unnecessary regenerations if report is fresh
  if (reportGeneratedAt.value && !silent) {
    const ageMs = Date.now() - parseApiDate(reportGeneratedAt.value).getTime()
    const oneHourMs = 60 * 60 * 1000
    if (ageMs < oneHourMs) {
      showFailToast(t('toast.reportTooFrequent'))
      return
    }
  }

  if (!silent) reportLoading.value = true
  stream.reset()
  let registered = false
  async function registerBgTask() {
    if (registered) return
    try {
      const task = await getAITask('report')
      if (task.task_id && ['running', 'queued', 'post_processing'].includes(task.status)) {
        aiStore.registerBackgroundTask({
          capability: 'report',
          taskId: task.task_id,
          sessionId: task.session_id || '',
          startedAt: task.started_at || new Date().toISOString(),
          status: task.status,
        })
        registered = true
      }
    } catch {
      // best-effort; task polling on return will catch up
    }
  }
  try {
    // force=true bypasses the 8h cache (plan step 6) — the refresh button
    // means the user wants a fresh report, not the cached one.
    const connectPromise = stream.connect(true)
    await registerBgTask()
    if (!registered) {
      setTimeout(registerBgTask, 500)
    }
    const started = await connectPromise
    if (!started) {
      if (!silent) {
        showToast({ message: t('aiReport.alreadyGenerating'), icon: 'warning-o' })
      }
      return
    }
    // Stream completed — reload from API to get the persisted report
    // (stream.report is only populated on cache hit, not fresh generation)
    await loadReport()
    aiStore.clearBackgroundTask('report')
  } catch (err) {
    if (!silent) {
      // Check if it's a timeout or connection error
      const isTimeout = err instanceof Error && err.message.includes('timeout')
      const isConnectionError = err instanceof Error &&
        (err.message.includes('Failed to fetch') || err.message.includes('NetworkError'))
      if (isTimeout) {
        showFailToast(t('toast.reportTimeout'))
      } else if (isConnectionError) {
        showFailToast(t('toast.refreshFailed'))
      } else {
        showFailToast(stream.errorMessage.value || t('toast.refreshFailed'))
      }
    }
  } finally {
    if (!silent) reportLoading.value = false
  }
}

function handleAgentConsult(agent: Agent) {
  if (guardAiEnabled()) return
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
  if (guardAiEnabled()) return
  if (!numinaAgent.value) return
  const agentId = numinaAgent.value.id
  getSystemDefaultSession(SYSTEM_DEFAULT_SESSION_MAX_AGE_HOURS)
    .then((res) => {
      const cached = res.data.session
      if (cached) {
        // 缓存会话存在 → 直接进入查看历史
        router.push({ name: 'AIChat', query: { agentId, thread_id: cached.session_id } })
      } else {
        // 无缓存 → 创建新会话并自动发送默认提示词
        // Pro 模式 + 继承当前 webSearch 配置（根据家庭设置自动决定）
        router.push({
          name: 'AIChat',
          query: {
            agentId,
            q: XIAOMING_DEFAULT_PROMPT,
            newSession: '1',
            source: 'system_default',
            // webSearch 状态继承自 AI Hub 页面的当前选择
            // 如果用户在 hub 页面开启了联网搜索，则传递 '1'
            webSearch: webSearch.value === true ? '1' : undefined,
          },
        })
      }
    })
    .catch(() => {
      router.push({ name: 'AIChat', query: { agentId } })
    })
}

function handleAgentEdit(agent: Agent) {
  router.push({ name: 'AgentEdit', params: { id: agent.id } })
}

function navigateToAgentCreate() {
  if (guardAiEnabled()) return
  router.push({ name: 'AgentCreate' })
}

function navigateToTimeMachine() {
  if (guardAiEnabled()) return
  router.push('/ai/time-machine')
}

async function loadPageData() {
  increment()
  try {
    await aiStore.fetchConfig()
    await agentStore.loadAgents()
    await loadReport()
  } finally {
    decrement()
  }
  initialLoading.value = false
}

onMounted(() => {
  loadPageData()
  if (!isGuideDone('tip_ai-first')) {
    showAiTip.value = true
    setTimeout(() => { showAiTip.value = false; markGuideDone('tip_ai-first') }, 3000)
  }
})

// KeepAlive 缓存页面：返回时触发 onActivated 而非 onMounted
// Skip first onActivated — Vue 3 fires both onMounted and onActivated on first
// mount inside <KeepAlive>; onMounted handles initial load.
let hasActivated = false
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  // If a report task is still running (user navigated away while generation
  // was in progress), resume polling so the page picks up latest progress.
  try {
    const task = await getAITask('report')
    if (task.task_id && ['running', 'queued', 'post_processing'].includes(task.status)) {
      aiStore.registerBackgroundTask({
        capability: 'report',
        taskId: task.task_id,
        sessionId: task.session_id || '',
        startedAt: task.started_at || new Date().toISOString(),
        status: task.status,
      })
      await stream.startPolling()
      await loadReport()
      aiStore.clearBackgroundTask('report')
      return
    } else if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled' || task.status === 'timeout') {
      aiStore.clearBackgroundTask('report')
    }
  } catch {
    // ignore status fetch errors; fall through to normal page load
  }
  loadPageData()
})

// This page is KeepAlive-cached (MainLayout cachedTabs includes 'AIHub'), so
// navigating away DEACTIVATES it rather than unmounting — no unmount hook fires.
// Abort the frontend SSE reader but keep the backend pipeline running so the
// user can navigate back and pick up progress via polling.
onDeactivated(() => {
  stream.abort(true)
})
onUnmounted(() => {
  stream.abort(true)
})

// Expose refs and functions for testing purposes
defineExpose({
  chatInput,
  chatMode,
  webSearch,
  selectedAgent,
  initialLoading,
  selectAgent,
  goToAnalytics,
})
</script>

<style scoped>
.ai-hub-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 180px; /* InputBox + AppTabBar + safe area */
}

/* ── Header: Clean card style ── */
.hub-header {
  position: relative;
  padding: 20px 16px 16px;
  background: var(--card-bg);
  color: var(--text-primary);
  overflow: hidden;
}

/* Decorative blob */
.hub-header-blob {
  position: absolute;
  top: -40px;
  right: -30px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(189, 187, 255, 0.08) 0%, transparent 70%);
  pointer-events: none;
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
  color: var(--text-tertiary);
  font-family: 'Georgia', monospace;
}

/* Display name: tight negative tracking */
.hub-greeting-hi {
  font-size: clamp(20px, 5vw, 24px);
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 1.05;
  color: var(--text-primary);
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
  stroke: var(--separator);
  stroke-width: 4;
}

.score-fill {
  fill: none;
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}

.score-fill { stroke: var(--van-primary-color); }
.score-empty .score-fill { stroke: var(--separator); }

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
  color: var(--text-primary);
  line-height: 1;
}

.score-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  color: var(--text-tertiary);
  font-family: 'Georgia', monospace;
  line-height: 1;
}

/* Stats row */
.hub-stats {
  display: flex;
  align-items: center;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 12px;
  position: relative;
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
  color: var(--text-primary);
  line-height: 1;
}

.hub-stat-num.warn { color: #d97706; }
[data-theme='dark'] .hub-stat-num.warn { color: #fcd34d; }

.hub-stat-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: var(--text-tertiary);
  font-family: 'Georgia', monospace;
}

.hub-stat-divider {
  width: 1px;
  height: 28px;
  background: var(--separator);
  flex-shrink: 0;
}

.hub-stat-num-wrap {
  display: flex;
  align-items: center;
  gap: 3px;
}

.hub-stat-info {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  padding: 0;
  color: var(--text-tertiary);
  cursor: pointer;
  line-height: 1;
}

.hub-stat-info:active {
  color: var(--color-primary, #1989fa);
}

.stat-popover-content {
  padding: 12px 14px;
  max-width: min(220px, calc(100vw - 32px));
  width: max-content;
  box-sizing: border-box;
}

.stat-popover-desc {
  word-break: break-word;
}

.stat-popover-header {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 6px;
}

.stat-popover-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1;
}

.stat-popover-value.warn { color: #d97706; }
[data-theme='dark'] .stat-popover-value.warn { color: #fcd34d; }

.stat-popover-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.stat-popover-desc {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.stat-popover-action {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  background: var(--color-primary, #1989fa);
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}

.stat-popover-action:active {
  opacity: 0.85;
}

/* Meta (freshness + refresh) — rightmost slot in stats row */
.hub-stat-meta {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: 'Georgia', monospace;
  letter-spacing: 0.055px;
  flex-shrink: 0;
  padding-left: 8px;
}

.refresh-btn {
  background: none;
  border: none;
  padding: 8px;
  min-width: 32px;
  min-height: 32px;
  color: var(--text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: color 0.15s;
}

.refresh-btn:hover { color: var(--text-primary); }
.refresh-btn:disabled { opacity: 0.4; cursor: default; }

/* ── Report summary card ── */
.report-summary-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 14px 16px;
  border: 1px solid var(--color-card-border);
  box-shadow: var(--shadow-elevated);
  cursor: pointer;
  transition: box-shadow 0.15s;
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
  color: var(--text-tertiary);
  font-family: 'Georgia', monospace;
  margin-bottom: 8px;
}

.report-summary-title svg { color: var(--text-tertiary); }

.report-summary-text {
  font-size: 13px;
  font-weight: 400;
  letter-spacing: -0.13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
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
  color: var(--text-secondary);
}

/* Generating report card */
.report-generating-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 28px 16px;
  text-align: center;
  border: 1px solid var(--color-card-border);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
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
  border: 1px dashed var(--color-card-border);
  transition: border-color 0.15s;
}

.report-empty-card:active { border-color: var(--text-tertiary); }

.report-empty-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  color: var(--text-tertiary);
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
  line-clamp: 2;
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



/* ── Agent picker ── */
.agent-picker-group {
  padding-bottom: 12px;
}

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

.ai-disabled-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 28px 20px 24px;
  text-align: center;
  border: 1px solid var(--color-card-border);
  box-shadow: var(--shadow-elevated);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.ai-disabled-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  margin-bottom: 4px;
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
  border: 1px solid var(--color-card-border);
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.ai-disabled-action:hover {
  background: var(--bg-secondary);
  border-color: var(--text-tertiary);
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

/* Feature tooltip (auto-dismiss, non-interactive) */
.feature-tip {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--card-bg);
  color: var(--text-secondary);
  padding: 10px 16px;
  text-align: center;
  font-size: 13px;
  border-bottom: 1px solid var(--separator);
  pointer-events: none;
  animation: feature-tip-fade 3s ease-in-out forwards;
}

@keyframes feature-tip-fade {
  0% { opacity: 0; transform: translateY(-4px); }
  10% { opacity: 1; transform: translateY(0); }
  80% { opacity: 1; }
  100% { opacity: 0; }
}
</style>
