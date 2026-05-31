<template>
  <div class="ai-hub-page">
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
      <p class="report-generating-text">{{ ws.progressMessage || t('aiHub.reportGenerating') }}</p>
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

    <!-- Agent grid: system agents → time-machine app card → custom agents -->
    <div class="feature-section">
      <AgentGrid
        :system-agents="agentStore.systemAgents.filter(a => a.is_enabled)"
        :custom-agents="agentStore.customAgents.filter(a => a.is_enabled)"
        :show-create="isOwner"
        @consult="handleAgentConsult"
        @edit="handleAgentEdit"
        @create="router.push({ name: 'AgentCreate' })"
      >
        <template #between>
          <!-- 应用区 (Apps): fixed-rule applications, not chat agents.
               Rendered between system and custom zones per R1 + R13.
               Hardcoded constant — not sourced from ai_agents table. -->
          <div class="agent-section">
            <div class="agent-section__title">{{ t('agents.apps') }}</div>
            <div class="agent-grid">
              <div
                class="agent-card app-card"
                role="button"
                tabindex="0"
                @click="router.push('/ai/time-machine')"
                @keydown.enter="router.push('/ai/time-machine')"
                @keydown.space.prevent="router.push('/ai/time-machine')"
              >
                <div class="agent-card__icon">⏰</div>
                <div class="agent-card__body">
                  <div class="agent-card__name">{{ t('aiHub.timeMachineCardTitle') }}</div>
                  <div class="agent-card__desc">{{ t('aiHub.timeMachineCardDesc') }}</div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </AgentGrid>
    </div>

    <!-- Chat input -->
    <div class="chat-entry">
      <!-- Recipient chip (U11): which agent the bottom input sends to.
           Default is 数鸣; tap to pick a different system or custom agent. -->
      <div class="recipient-chip-row">
        <button
          class="recipient-chip"
          :disabled="!selectedRecipient"
          :aria-label="t('aiHub.changeRecipient')"
          @click="showRecipientPicker = true"
        >
          <template v-if="!agentStore.systemAgents.length && !agentStore.customAgents.length">
            <van-skeleton :row="1" row-width="80px" />
          </template>
          <template v-else>
            <span class="recipient-chip__label">{{ t('aiHub.sendTo') }}</span>
            <span class="recipient-chip__icon" aria-hidden="true">
              <NuminaLogo
                v-if="selectedRecipient?.agent_name === NUMINA_AGENT_NAME"
                :width="32"
              />
              <span v-else>{{ selectedRecipient?.icon || '🤖' }}</span>
            </span>
            <span class="recipient-chip__name">
              {{ selectedRecipient?.display_name || t('aiHub.recipientFallback') }}
            </span>
            <svg
              class="recipient-chip__chevron"
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </template>
        </button>
      </div>

      <AIChatInput
        v-model="chatInput"
        v-model:deep-think="deepThink"
        v-model:web-search="webSearch"
        :placeholder="t('aiHub.chatPlaceholder')"
        :disabled="!selectedRecipient"
        @submit="startChat"
      />
    </div>

    <!-- Recipient picker action sheet -->
    <van-action-sheet
      v-model:show="showRecipientPicker"
      :title="t('aiHub.changeRecipient')"
      :description="recipientPickerHint"
    >
      <div v-if="!recipientChoices.length" class="recipient-empty">
        <p class="recipient-empty__text">{{ t('aiHub.noEnabledAgents') }}</p>
        <van-button size="small" plain @click="onManageAgentsClicked">
          {{ t('aiHub.manageAgents') }}
        </van-button>
      </div>
      <van-cell-group v-else inset>
        <van-cell
          v-for="agent in recipientChoices"
          :key="agent.id"
          :title="agent.display_name"
          :label="agent.description || ''"
          clickable
          :class="{ 'recipient-row--active': agent.id === selectedRecipient?.id }"
          @click="onSelectRecipient(agent)"
        >
          <template #icon>
            <span class="recipient-row__icon" aria-hidden="true">
              <NuminaLogo v-if="agent.agent_name === NUMINA_AGENT_NAME" :width="24" />
              <span v-else>{{ agent.icon || '🤖' }}</span>
            </span>
          </template>
        </van-cell>
      </van-cell-group>
    </van-action-sheet>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getUser } from '@/utils/storage'
import { getAIReport } from '@/api/ai'
import { useAIStore } from '@/stores/ai'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAIReportWS } from '@/composables/useAIReportWS'
import AIChatInput from '@/components/common/AIChatInput.vue'
import AgentGrid from '@/components/agent/AgentGrid.vue'
import NuminaLogo from '@/components/common/NuminaLogo.vue'
import type { Agent } from '@/types/agent'
import type { AIReport } from '@/types'

const NUMINA_AGENT_NAME = 'numina'

const { t } = useI18n()

const router = useRouter()
const aiStore = useAIStore()
const agentStore = useAgentStore()
const authStore = useAuthStore()
const ws = useAIReportWS()
const isOwner = authStore.user?.role === 'owner'

const currentReport = ref<AIReport | null>(null)
const reportGeneratedAt = ref<string | null>(null)
const reportLoading = ref(false)
const chatInput = ref('')
const deepThink = ref(false)
const webSearch = ref(false)

// Recipient chip state (U11): which agent the bottom chat input talks to.
// Defaults to 数鸣 once agents load; user can switch via action sheet.
const selectedRecipient = ref<Agent | null>(null)
const showRecipientPicker = ref(false)

const numinaAgent = computed(() =>
  agentStore.systemAgents.find((a) => a.agent_name === NUMINA_AGENT_NAME) || null,
)

// All agents the chip's action sheet can switch to: enabled system + custom.
const recipientChoices = computed<Agent[]>(() => [
  ...agentStore.systemAgents.filter((a) => a.is_enabled),
  ...agentStore.customAgents.filter((a) => a.is_enabled),
])

const recipientPickerHint = computed(() =>
  recipientChoices.value.length ? t('aiHub.changeRecipientHint') : '',
)

// Default the recipient to 数鸣 once the agent store finishes loading.
// Defensive fallback: any other enabled system agent (e.g. time-machine), then
// any enabled custom agent. 数鸣 should always exist after migration b6745e8a2c14.
watch(
  () => [agentStore.systemAgents, agentStore.customAgents] as const,
  () => {
    if (selectedRecipient.value) return // user already picked something
    if (numinaAgent.value && numinaAgent.value.is_enabled) {
      selectedRecipient.value = numinaAgent.value
      return
    }
    const fallback =
      agentStore.systemAgents.find((a) => a.is_enabled) ||
      agentStore.customAgents.find((a) => a.is_enabled) ||
      null
    selectedRecipient.value = fallback
  },
  { deep: true, immediate: true },
)

function onSelectRecipient(agent: Agent) {
  selectedRecipient.value = agent
  showRecipientPicker.value = false
}

function onManageAgentsClicked() {
  showRecipientPicker.value = false
  router.push({ name: 'AgentsManage' })
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
  ws.reset()
  try {
    await ws.connect()
    if (ws.report.value) {
      currentReport.value = ws.report.value as unknown as AIReport
      reportGeneratedAt.value = ws.generatedAt.value
    }
  } catch {
    showToast(ws.errorMessage.value || t('toast.aiGenerateFailed'))
  } finally {
    reportLoading.value = false
  }
}

async function refreshReport(silent?: boolean) {
  if (reportLoading.value) return // avoid duplicate with scheduler
  if (!aiStore.aiEnabled) return
  if (!silent) reportLoading.value = true
  ws.reset()
  try {
    await ws.connect()
    if (ws.report.value) {
      currentReport.value = ws.report.value as unknown as AIReport
      reportGeneratedAt.value = ws.generatedAt.value
    }
  } catch {
    if (!silent) showToast(t('toast.refreshFailed'))
  } finally {
    if (!silent) reportLoading.value = false
  }
}

function startChat(q: string) {
  if (!q) return
  if (!selectedRecipient.value) {
    // Defensive — the chat input is disabled when no recipient is set.
    showToast(t('aiHub.noEnabledAgents'))
    return
  }
  aiStore.draftQuery = q
  aiStore.deepThinkEnabled = deepThink.value
  aiStore.webSearchEnabled = webSearch.value
  router.push({
    path: '/ai/chat',
    query: {
      q,
      agentId: selectedRecipient.value.id, // R4: every entry routes by agentId
      newSession: '1', // Signal fresh session from hub
      deepThink: deepThink.value ? '1' : undefined,
      webSearch: webSearch.value ? '1' : undefined,
    },
  })
}

function handleAgentConsult(agent: Agent) {
  // R4: unified agentId routing — every agent card lands in AIChatPage with
  // the agent's id in the query string. AIChatPage loads the matching
  // agent's soul/skills based on agentId. No more agent_name special cases
  // (the old ai-assistant / time-machine branches were architectural
  // accidents from before agentId routing existed) and no more skills-based
  // dead routing (the builtin agents that those branches targeted were
  // deleted by migration b6745e8a2c14).
  router.push({ name: 'AIChat', query: { agentId: agent.id } })
}

function handleAgentEdit(agent: Agent) {
  router.push({ name: 'AgentEdit', params: { id: agent.id } })
}

onMounted(async () => {
  await aiStore.fetchConfig()
  // Enable deep-think by default if model supports thinking capability
  if (aiStore.config?.ai_test_thinking_success === true) {
    deepThink.value = true
  }
  await agentStore.loadAgents()
  await loadReport()
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

/* ── AI disabled card ── */
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

/* ── Recipient chip (U11) ── */
.recipient-chip-row {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 6px;
}

.recipient-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.03);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  min-height: 28px;
}

.recipient-chip:hover {
  background: rgba(0, 0, 0, 0.06);
  border-color: rgba(0, 0, 0, 0.2);
}

.recipient-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

[data-theme='dark'] .recipient-chip {
  border-color: rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
}

[data-theme='dark'] .recipient-chip:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.25);
}

.recipient-chip__label {
  color: var(--text-secondary);
  font-size: 11px;
  letter-spacing: 0.05em;
}

.recipient-chip__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  line-height: 1;
}

.recipient-chip__icon :deep(.numina-logo) {
  height: 14px;
}

.recipient-chip__name {
  font-weight: 600;
}

.recipient-chip__chevron {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.recipient-row__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 24px;
  margin-right: 8px;
  font-size: 18px;
}

.recipient-row--active {
  background-color: rgba(var(--theme-primary-rgb, 0, 122, 255), 0.06);
}

.recipient-empty {
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.recipient-empty__text {
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0;
}

/* ── App card (U9 — time-machine) ── */
.app-card {
  /* Inherits .agent-card base styling; left-border accent distinguishes it
     from chat agents — apps are fixed-rule, not conversational. */
  border-left: 3px solid var(--theme-primary, #007aff);
}
</style>
