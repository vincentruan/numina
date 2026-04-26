<template>
  <div class="ai-hub-page">
    <!-- Header -->
    <div class="hub-header">
      <div class="hub-header-bg" aria-hidden="true"></div>
      <div class="hub-header-content">
        <div class="hub-greeting">
          <span class="hub-greeting-hi">你好，{{ userName }}</span>
          <span class="hub-greeting-sub">家庭资产智能助手</span>
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
      <!-- Report freshness -->
      <div class="hub-meta" aria-live="polite">
        <template v-if="reportLoading">
          <van-loading size="12" color="rgba(255,255,255,0.7)" />
          <span>正在生成报告…</span>
        </template>
        <template v-else-if="reportGeneratedAt">
          <span>报告生成于 {{ reportAge }}</span>
          <button class="refresh-btn" :disabled="reportLoading" aria-label="刷新报告" @click="() => refreshReport()">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
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

    <!-- Report summary card -->
    <div v-if="currentReport" class="report-summary-card" role="button" tabindex="0" aria-label="查看完整资产体检报告" @click="$router.push('/ai/report')" @keydown.enter="$router.push('/ai/report')" @keydown.space.prevent="$router.push('/ai/report')">
      <div class="report-summary-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        最新资产体检报告
      </div>
      <p class="report-summary-text">{{ currentReport.summary }}</p>
      <div class="report-summary-stats">
        <div class="report-stat">
          <span class="report-stat-num">{{ suggestionCount }}</span>
          <span class="report-stat-label">项建议</span>
        </div>
        <div class="report-stat-divider" aria-hidden="true"></div>
        <div class="report-stat">
          <span class="report-stat-num warn">{{ alertCount }}</span>
          <span class="report-stat-label">项预警</span>
        </div>
        <div class="report-stat-divider" aria-hidden="true"></div>
        <div class="report-stat">
          <span class="report-stat-num">{{ currentReport.data_completeness_score?.toFixed(0) ?? '-' }}%</span>
          <span class="report-stat-label">数据完整度</span>
        </div>
      </div>
      <div class="report-summary-cta">
        查看完整报告
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </div>
    </div>

    <div v-else-if="!reportLoading" class="report-empty-card" role="button" tabindex="0" aria-label="立即生成资产体检报告" @click="generateReport">
      <div class="report-empty-icon" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
      </div>
      <p class="report-empty-text">立即生成首份资产体检报告</p>
      <p class="report-empty-sub">AI 将综合分析资产配置、负债压力和资产效率</p>
    </div>

    <!-- Spending leaks -->
    <div class="leaks-section">
      <h2 class="feature-section-title">资金泄漏检测</h2>
      <SpendingLeaksCard />
    </div>

    <!-- Feature grid -->
    <div class="feature-section">
      <h2 class="feature-section-title">AI 功能</h2>
      <div class="feature-grid" role="list">
        <button
          v-for="feat in features"
          :key="feat.route"
          class="feature-card"
          role="listitem"
          :aria-label="feat.title + '：' + feat.desc"
          @click="$router.push(feat.route)"
        >
          <div class="feature-icon" aria-hidden="true" v-html="feat.svg"></div>
          <span class="feature-title">{{ feat.title }}</span>
          <span class="feature-desc">{{ feat.desc }}</span>
        </button>
      </div>
    </div>

    <!-- Chat input -->
    <div class="chat-entry">
      <AIChatInput
        v-model="chatInput"
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
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAIReportWS } from '@/composables/useAIReportWS'
import AIChatInput from '@/components/common/AIChatInput.vue'
import SpendingLeaksCard from '@/components/ai/SpendingLeaksCard.vue'

const { t } = useI18n()

const router = useRouter()
const aiStore = useAIStore()
const ws = useAIReportWS()

const currentReport = ref<Record<string, any> | null>(null)
const reportGeneratedAt = ref<string | null>(null)
const reportLoading = ref(false)
const chatInput = ref('')

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
  router.push({ path: '/ai/chat' })
}

const features = [
  {
    route: '/ai/report',
    title: '资产体检',
    desc: '综合健康评分',
    svg: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
  },
  {
    route: '/ai/alerts',
    title: '老化预警',
    desc: '即将到期资产',
    svg: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  },
  {
    route: '/ai/disposal',
    title: '闲置清仓',
    desc: '建议处置资产',
    svg: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="7.5 4.21 12 6.81 16.5 4.21"/><polyline points="7.5 19.79 7.5 14.6 3 12"/><polyline points="21 12 16.5 14.6 16.5 19.79"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
  },
  {
    route: '/ai/liability',
    title: '负债优化',
    desc: '还款策略建议',
    svg: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>`,
  },
  {
    route: '/ai/allocation',
    title: '配置漂移',
    desc: '资产配置偏离检测',
    svg: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 010 8.49m-8.48-.01a6 6 0 010-8.49m11.31-2.82a10 10 0 010 14.14m-14.14 0a10 10 0 010-14.14"/></svg>`,
  },
  {
    route: '/ai/chat',
    title: 'AI 问答',
    desc: '自由对话助手',
    svg: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>`,
  },
  {
    route: '/ai/time-machine',
    title: '资产时光机',
    desc: 'What-if 模拟、财务推演',
    svg: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  },
]

onMounted(async () => {
  await aiStore.fetchConfig()
  await loadReport()
})
</script>

<style scoped>
.ai-hub-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 140px;
}

/* ── Header ── */
.hub-header {
  position: relative;
  padding: 20px 20px 16px;
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  overflow: hidden;
}

.hub-header-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 80% 20%, rgba(255,255,255,0.08) 0%, transparent 50%),
    radial-gradient(circle at 20% 80%, rgba(255,255,255,0.05) 0%, transparent 40%);
  pointer-events: none;
}

.hub-header-content {
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

.hub-greeting-hi {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.3px;
}

.hub-greeting-sub {
  font-size: 13px;
  color: rgba(255,255,255,0.92);
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
  stroke: rgba(255,255,255,0.2);
  stroke-width: 4;
}

.score-fill {
  fill: none;
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}

.score-excellent .score-fill { stroke: #4ade80; }
.score-good      .score-fill { stroke: #60a5fa; }
.score-fair      .score-fill { stroke: #fbbf24; }
.score-poor      .score-fill { stroke: #f87171; }
.score-empty     .score-fill { stroke: rgba(255,255,255,0.3); }

.score-inner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 0;
}

.score-number {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}

.score-label {
  font-size: 12px;
  color: rgba(255,255,255,0.9);
  line-height: 1;
}

/* Meta row */
.hub-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  font-size: 12px;
  color: rgba(255,255,255,0.92);
  position: relative;
}

.refresh-btn {
  background: none;
  border: none;
  padding: 10px;
  min-width: 44px;
  min-height: 44px;
  color: rgba(255,255,255,0.92);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: color 0.15s;
}

.refresh-btn:hover { color: #fff; }
.refresh-btn:disabled { opacity: 0.4; cursor: default; }

/* ── Report summary card ── */
.report-summary-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  cursor: pointer;
  transition: box-shadow 0.15s;
}

.report-summary-card:active {
  box-shadow: 0 0 0 1px rgba(99,102,241,0.3);
}

.report-summary-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.report-summary-title svg { color: #6366f1; }

.report-summary-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.report-summary-stats {
  display: flex;
  align-items: center;
  gap: 0;
  margin-bottom: 12px;
}

.report-stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.report-stat-num {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.report-stat-num.warn { color: #f59e0b; }

.report-stat-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.report-stat-divider {
  width: 1px;
  height: 28px;
  background: var(--separator);
}

.report-summary-cta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  font-size: 12px;
  color: #6366f1;
  font-weight: 500;
}

/* Empty report card */
.report-empty-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 24px 16px;
  text-align: center;
  cursor: pointer;
  border: 1.5px dashed rgba(99,102,241,0.3);
  transition: border-color 0.15s;
}

.report-empty-card:active { border-color: #6366f1; }

.report-empty-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(99,102,241,0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  color: #6366f1;
}

.report-empty-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.report-empty-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

/* ── Spending leaks ── */
.leaks-section {
  padding: 0 0 4px;
}

.leaks-section .feature-section-title {
  padding: 0 16px;
  margin: 12px 0 0;
}

/* ── Feature grid ── */
.feature-section {
  padding: 0 16px;
  margin-top: 4px;
}

.feature-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.feature-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 14px 10px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  border: none;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.1s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  min-height: 88px;
}

.feature-card:active {
  transform: scale(0.96);
  box-shadow: 0 0 0 1.5px rgba(99,102,241,0.25);
}

.feature-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(124,58,237,0.12) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6366f1;
  flex-shrink: 0;
}

[data-theme='dark'] .feature-icon {
  background: linear-gradient(135deg, rgba(99,102,241,0.2) 0%, rgba(124,58,237,0.2) 100%);
  color: #a5b4fc;
}

.feature-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.2;
}

.feature-desc {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.3;
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
  border-top: 1px solid var(--border-color, #eee);
}

/* Dark mode */
[data-theme='dark'] .hub-header {
  background: linear-gradient(135deg, #3730a3 0%, #5b21b6 100%);
}

/* Focus rings for interactive cards */
.report-summary-card:focus-visible,
.report-empty-card:focus-visible,
.feature-card:focus-visible,
.chat-send:focus-visible {
  outline: 2px solid #6366f1;
  outline-offset: 2px;
}

.report-stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
