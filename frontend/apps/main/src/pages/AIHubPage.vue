<template>
  <div class="ai-hub-page">
    <!-- Header -->
    <div class="hub-header">
      <div class="hub-header-blob" aria-hidden="true"></div>
      <div class="hub-header-main">
        <div class="hub-greeting">
          <span class="hub-greeting-label">AI 智能助手</span>
          <span class="hub-greeting-hi">你好，{{ userName }}</span>
        </div>
        <!-- Health score ring -->
        <div class="hub-score-ring" :class="scoreClass" role="img" :aria-label="`资产健康评分 ${displayScore} 分`">
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
            <span class="score-label">分</span>
          </div>
        </div>
      </div>
      <!-- Stats row -->
      <div class="hub-stats">
        <div class="hub-stat-item">
          <span class="hub-stat-num">{{ suggestionCount }}</span>
          <span class="hub-stat-label">项建议</span>
        </div>
        <div class="hub-stat-divider" aria-hidden="true"></div>
        <div class="hub-stat-item">
          <span class="hub-stat-num warn">{{ alertCount }}</span>
          <span class="hub-stat-label">项预警</span>
        </div>
        <div class="hub-stat-divider" aria-hidden="true"></div>
        <div class="hub-stat-item">
          <span class="hub-stat-num">{{ currentReport?.data_completeness_score?.toFixed(0) ?? '-' }}%</span>
          <span class="hub-stat-label">数据完整度</span>
        </div>
        <div class="hub-stat-divider" aria-hidden="true"></div>
        <div class="hub-stat-meta" aria-live="polite">
          <template v-if="reportLoading">
            <van-loading size="10" />
            <span>生成中…</span>
          </template>
          <template v-else-if="reportGeneratedAt">
            <span>{{ reportAge }}</span>
            <button class="refresh-btn" :disabled="reportLoading" aria-label="刷新报告" @click="() => refreshReport()">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
              </svg>
            </button>
          </template>
          <template v-else>
            <span>暂无报告</span>
          </template>
        </div>
      </div>
    </div>

    <!-- Report summary card -->
    <div v-if="currentReport" class="report-summary-card" role="button" tabindex="0" aria-label="查看完整资产体检报告" @click="$router.push('/ai/report')" @keydown.enter="$router.push('/ai/report')" @keydown.space.prevent="$router.push('/ai/report')">
      <div class="report-summary-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        最新资产体检报告
      </div>
      <p class="report-summary-text">{{ currentReport.summary }}</p>
      <div class="report-summary-cta">
        查看完整报告
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </div>
    </div>

    <!-- Generating in progress -->
    <div v-else-if="reportLoading" class="report-generating-card" aria-live="polite" aria-label="正在生成报告">
      <van-loading size="28" color="var(--color-primary)" />
      <p class="report-generating-text">{{ ws.progressMessage || '正在生成报告…' }}</p>
      <p class="report-generating-sub">AI 正在综合分析，请稍候</p>
    </div>

    <div v-else class="report-empty-card" role="button" tabindex="0" aria-label="立即生成资产体检报告" @click="generateReport">
      <div class="report-empty-icon" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
      </div>
      <p class="report-empty-text">立即生成首份资产体检报告</p>
      <p class="report-empty-sub">AI 将综合分析资产配置、负债压力和资产效率</p>
    </div>

    <!-- Feature grid -->
    <div class="feature-section">
      <h2 class="feature-section-title">{{ t('aiHub.capabilities') }}</h2>
      <div class="feature-grid" role="list">
        <button
          v-for="cap in capabilities"
          :key="cap.id"
          class="feature-card"
          role="listitem"
          :data-testid="`capability-${cap.id}`"
          :aria-label="cap.name + '：' + cap.description"
          @click="startCapability(cap)"
        >
          <span class="feature-icon" aria-hidden="true">{{ capabilityEmoji(cap.id) }}</span>
          <span class="feature-title">{{ cap.name }}</span>
          <span class="feature-desc">{{ cap.description }}</span>
        </button>
      </div>
    </div>

    <!-- Chat input -->
    <div class="chat-entry">
      <AIChatInput
        v-model="chatInput"
        v-model:deep-think="deepThink"
        v-model:web-search="webSearch"
        placeholder="问我任何关于家庭资产的问题…"
        @submit="startChat"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getUser } from '@/utils/storage'
import { getAIReport } from '@/api/ai'
import { useAIStore } from '@/stores/ai'
import { useCapabilityStore } from '@/stores/capability'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAIReportWS } from '@/composables/useAIReportWS'
import AIChatInput from '@/components/common/AIChatInput.vue'

const { t } = useI18n()

const router = useRouter()
const aiStore = useAIStore()
const capabilityStore = useCapabilityStore()
const ws = useAIReportWS()

const currentReport = ref<Record<string, unknown> | null>(null)
const reportGeneratedAt = ref<string | null>(null)
const reportLoading = ref(false)
const chatInput = ref('')
const deepThink = ref(false)
const webSearch = ref(false)
const capabilities = computed(() => capabilityStore.capabilities)

const userName = computed(() => getUser()?.display_name || '用户')

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

const reportAge = computed(() => {
  if (!reportGeneratedAt.value) return ''
  const diff = Date.now() - new Date(reportGeneratedAt.value).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} 小时前`
  return `${Math.floor(hrs / 24)} 天前`
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
  return [r.net_worth_health, r.allocation_analysis, r.liability_pressure, r.asset_efficiency]
    .filter(s => s && (s.score ?? 100) < 60).length
})

const CACHE_TTL_MS = 24 * 60 * 60 * 1000 // 24h

async function loadReport() {
  try {
    const res = await getAIReport()
    if (res.data.report) {
      currentReport.value = res.data.report
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

async function loadCapabilities() {
  try {
    await capabilityStore.loadCapabilities()
  } catch {
    // keep empty grid if discovery fails
  }
}

async function generateReport() {
  if (!aiStore.aiEnabled) {
    showToast(t('toast.aiNotEnabled'))
    router.push('/settings/ai')
    return
  }
  reportLoading.value = true
  ws.reset()
  try {
    await ws.connect()
    if (ws.report.value) {
      currentReport.value = ws.report.value
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
      currentReport.value = ws.report.value
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
  aiStore.draftQuery = q
  aiStore.deepThinkEnabled = deepThink.value
  aiStore.webSearchEnabled = webSearch.value
  router.push({
    path: '/ai/chat',
    query: {
      q,
      deepThink: deepThink.value ? '1' : undefined,
      webSearch: webSearch.value ? '1' : undefined,
    },
  })
}

function capabilityEmoji(id: string) {
  const map: Record<string, string> = {
    report: '📊',
    chat: '💬',
    alerts: '🔔',
    allocation: '⚖️',
    disposal: '🗑️',
    liability: '💳',
    spending_leak: '🔍',
    time_machine: '⏰',
  }
  return map[id] ?? '✨'
}

function startCapability(cap: { id: string; ui?: { route?: string | null } }) {
  router.push(cap.ui?.route ?? '/ai/chat')
}

onMounted(async () => {
  await aiStore.fetchConfig()
  await loadCapabilities()
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
  color: rgba(255, 255, 255, 0.45);
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

[data-theme='dark'] .score-excellent .score-fill { stroke: #6ee7a0; }
[data-theme='dark'] .score-good      .score-fill { stroke: #93c5fd; }
[data-theme='dark'] .score-fair      .score-fill { stroke: #fcd34d; }
[data-theme='dark'] .score-poor      .score-fill { stroke: #fca5a5; }
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
  color: rgba(255, 255, 255, 0.45);
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
  color: rgba(255, 255, 255, 0.40);
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
  color: rgba(255, 255, 255, 0.40);
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
  color: rgba(255, 255, 255, 0.40);
}

.refresh-btn:hover { color: #000000; }
[data-theme='dark'] .refresh-btn:hover { color: #ffffff; }
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
  color: rgba(255, 255, 255, 0.45);
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

/* ── Feature grid ── */
.feature-section {
  padding: 0 16px;
  margin-top: 4px;
}

.feature-section-title {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.40);
  font-family: 'Georgia', monospace;
  margin: 0 0 10px;
}

[data-theme='dark'] .feature-section-title {
  color: rgba(255, 255, 255, 0.40);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.feature-card {
  background: var(--card-bg);
  border-radius: 8px;
  padding: 14px 10px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.1s;
  box-shadow: rgba(1, 1, 32, 0.05) 0px 1px 4px;
  min-height: 88px;
}

[data-theme='dark'] .feature-card {
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: rgba(1, 1, 32, 0.3) 0px 1px 4px;
}

.feature-card:active {
  transform: scale(0.96);
  box-shadow: rgba(1, 1, 32, 0.10) 0px 4px 10px;
}

.feature-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(0, 0, 0, 0.55);
  flex-shrink: 0;
}

[data-theme='dark'] .feature-icon {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.60);
}

.feature-title {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: -0.12px;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.2;
}

.feature-desc {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.3;
  letter-spacing: -0.11px;
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

/* Focus rings */
.report-summary-card:focus-visible,
.report-empty-card:focus-visible,
.feature-card:focus-visible {
  outline: 2px solid rgba(0, 0, 0, 0.5);
  outline-offset: 2px;
}

[data-theme='dark'] .report-summary-card:focus-visible,
[data-theme='dark'] .report-empty-card:focus-visible,
[data-theme='dark'] .feature-card:focus-visible {
  outline-color: rgba(255, 255, 255, 0.5);
}
</style>
