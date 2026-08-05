<script setup lang="ts">
/**
 * ASRConfigPage — list/manage ASR provider configs
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast, showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useAuthStore } from '@numina/auth'
import { getASRConfigs, deleteASRConfig, testASRConfig, updateASRConfig } from '@/api/asr'
import type { ASRProviderConfig, ASRTestResult, ASRLangTestResult, ASRDiffOp } from '@/api/asr'
import PageHeader from '@/components/common/PageHeader.vue'

defineOptions({ name: 'ASRConfigPage' })

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const isOwner = computed(() => authStore.user?.role === 'owner')
const configs = ref<ASRProviderConfig[]>([])
const loading = ref(true)
const testingId = ref<string | null>(null)
const testResult = ref<ASRTestResult | null>(null)
const testResultConfigId = ref<string | null>(null)

async function loadConfigs() {
  loading.value = true
  try {
    const res = await getASRConfigs()
    configs.value = res.data.configs
  } catch {
    showFailToast(t('common.failed'))
  } finally {
    loading.value = false
  }
}

function goToForm(id?: string) {
  if (id) {
    router.push(`/settings/ai/asr/${id}/edit`)
  } else {
    router.push('/settings/ai/asr/new')
  }
}

async function handleDelete(cfg: ASRProviderConfig) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('asrConfig.deleteConfirm') })
    await deleteASRConfig(cfg.id)
    showSuccessToast(t('common.success'))
    await loadConfigs()
  } catch {
    // cancelled
  }
}

async function handleTest(cfg: ASRProviderConfig) {
  testingId.value = cfg.id
  testResult.value = null
  testResultConfigId.value = null
  try {
    const res = await testASRConfig(cfg.id)
    testResult.value = res.data
    testResultConfigId.value = cfg.id
    if (res.data.success) {
      showSuccessToast(t('asrConfig.testSuccess'))
      await loadConfigs()
    } else {
      showFailToast(res.data.message || t('asrConfig.testFailed'))
    }
  } catch {
    showFailToast(t('asrConfig.testFailed'))
  } finally {
    testingId.value = null
  }
}

async function toggleActive(cfg: ASRProviderConfig) {
  const newActive = !cfg.is_active
  if (newActive && !cfg.test_passed) {
    showToast(t('asrConfig.enableRequiresTest'))
    return
  }
  try {
    await updateASRConfig(cfg.id, { is_active: newActive })
    showSuccessToast(newActive ? t('asrConfig.enableSuccess') : t('asrConfig.disableSuccess'))
    await loadConfigs()
  } catch {
    showFailToast(t('common.failed'))
  }
}

function statusLabel(cfg: ASRProviderConfig): string {
  if (cfg.circuit_state === 'open') return t('asrConfig.circuitOpen')
  if (cfg.is_active) return t('asrConfig.statusActive')
  if (cfg.test_passed === null || cfg.test_passed === undefined) return t('asrConfig.statusNotTested')
  if (cfg.test_passed) return t('asrConfig.statusTestPassed')
  return t('asrConfig.statusTestFailed')
}

function statusClass(cfg: ASRProviderConfig): string {
  if (cfg.circuit_state === 'open') return 'status--danger'
  if (cfg.is_active) return 'status--success'
  if (cfg.test_passed) return 'status--warning'
  return 'status--default'
}

function statusDotClass(cfg: ASRProviderConfig): string {
  if (cfg.circuit_state === 'open') return 'dot--danger'
  if (cfg.is_active) return 'dot--success'
  if (cfg.test_passed) return 'dot--warning'
  return 'dot--default'
}

function providerLabel(provider: string): string {
  if (provider === 'openai') return 'OpenAI'
  if (provider === 'siliconflow') return 'SiliconFlow'
  return 'OpenAI Compatible'
}

function diffTitle(op: ASRDiffOp): string {
  switch (op.op) {
    case 'equal': return ''
    case 'sub': return `替换: "${op.ref}" → "${op.hyp}"`
    case 'del': return `漏识: "${op.ref}"`
    case 'ins': return `多识: "${op.hyp}"`
    default: return ''
  }
}

onMounted(loadConfigs)
</script>

<template>
  <div class="asr-config-page">
    <PageHeader :title="t('asrConfig.pageTitle')" />

    <!-- Description tip -->
    <div class="page-desc">
      {{ t('asrConfig.pageDesc') }}
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-wrapper">
      <van-loading size="24" />
    </div>

    <!-- Empty state -->
    <div v-else-if="configs.length === 0" class="empty-state">
      <van-icon name="volume-o" size="48" color="var(--text-secondary)" />
      <p class="empty-title">{{ t('asrConfig.emptyTitle') }}</p>
      <p class="empty-desc">{{ t('asrConfig.emptyDesc') }}</p>
      <van-button v-if="isOwner" plain icon="plus" size="small" @click="goToForm()">
        {{ t('asrConfig.addProvider') }}
      </van-button>
    </div>

    <!-- Config list -->
    <div v-else class="config-list">
      <div v-for="cfg in configs" :key="cfg.id" class="provider-card">
        <!-- Card header: logo + info + switch -->
        <div class="card-header">
          <div class="card-logo" :class="`logo--${cfg.provider}`">
            <svg v-if="cfg.provider === 'openai'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365 2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" fill="currentColor" />
            </svg>
            <svg v-else-if="cfg.provider === 'siliconflow'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 4h6v6H4V4zm10 0h6v6h-6V4zM4 14h6v6H4v-6zm10 0h6v6h-6v-6z" fill="currentColor" opacity="0.2" />
              <path d="M7 7h10M7 17h10M7 7v10M17 7v10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              <circle cx="12" cy="12" r="2.5" fill="currentColor" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" />
              <path d="M12 7v5l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
          </div>
          <div class="card-header-info">
            <div class="card-title-row">
              <span class="card-name">{{ cfg.name }}</span>
              <span class="card-provider-fmt">{{ providerLabel(cfg.provider) }}</span>
            </div>
            <div class="card-status-row">
              <span class="health-dot" :class="statusDotClass(cfg)" />
              <span class="status-label" :class="statusClass(cfg)">{{ statusLabel(cfg) }}</span>
            </div>
          </div>
          <van-switch
            v-if="isOwner"
            :model-value="cfg.is_active"
            size="20"
            @update:model-value="toggleActive(cfg)"
          />
        </div>

        <!-- Card body: model + API key + test result -->
        <div class="card-body">
          <!-- Model row with test button -->
          <div v-if="cfg.model_id" class="model-row">
            <span class="model-id">{{ cfg.model_id }}</span>
            <button
              v-if="isOwner"
              class="test-btn"
              :class="{ 'test-btn--testing': testingId === cfg.id }"
              :disabled="testingId === cfg.id"
              @click="handleTest(cfg)"
            >
              <span v-if="testingId === cfg.id" class="test-btn__icon test-btn__icon--spinning">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" opacity="0.3" />
                  <path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                </svg>
              </span>
              <van-icon v-else name="play-circle-o" size="15" />
              <span>{{ t('asrConfig.test') }}</span>
            </button>
          </div>

          <!-- API Key -->
          <div class="info-row">
            <span class="info-label">{{ t('asrConfig.apiKey') }}</span>
            <span class="info-value info-value--mono">{{ cfg.ai_api_key_masked || '—' }}</span>
          </div>

          <!-- Base URL -->
          <div v-if="cfg.base_url" class="info-row">
            <span class="info-label">{{ t('asrConfig.baseUrl') }}</span>
            <span class="info-value info-value--mono">{{ cfg.base_url }}</span>
          </div>

          <!-- Failure count warning -->
          <div v-if="cfg.failure_count > 0" class="warn-row">
            <van-icon name="warning-o" size="14" />
            <span>{{ t('asrConfig.failureCount', { count: cfg.failure_count }) }}</span>
          </div>

          <!-- Test result with per-language WER diff -->
          <div v-if="testResultConfigId === cfg.id && testResult" class="test-result">
            <div v-for="lr in testResult.language_results" :key="lr.language" class="lang-result">
              <div class="lang-header">
                <span class="lang-label">{{ lr.language === 'zh' ? '中文' : 'English' }}</span>
                <span :class="lr.passed ? 'text-success' : 'text-danger'">
                  {{ lr.error ? lr.error : `字错率 ${lr.error_rate_pct}%` }}
                </span>
              </div>
              <div v-if="!lr.error && lr.ops.length" class="diff-display">
                <span
                  v-for="(op, idx) in lr.ops"
                  :key="idx"
                  :class="`diff-${op.op}`"
                  :title="diffTitle(op)"
                >{{ op.ref ?? op.hyp ?? '' }}</span>
              </div>
              <div v-if="lr.transcribed" class="transcribed-text">
                <span class="info-label">ASR: </span>{{ lr.transcribed }}
              </div>
              <div v-if="lr.latency_ms" class="test-latency">{{ lr.latency_ms }}ms</div>
            </div>
          </div>

          <!-- Test message from config -->
          <div v-else-if="cfg.test_message" class="test-result">
            <span :class="cfg.test_passed ? 'text-success' : 'text-danger'">
              {{ cfg.test_message }}
            </span>
            <span v-if="cfg.test_latency_ms" class="test-latency">{{ cfg.test_latency_ms }}ms</span>
          </div>
        </div>

        <!-- Card actions: edit / delete — AIConfigPage style -->
        <div v-if="isOwner" class="card-actions">
          <button class="action-btn action-btn--edit" @click="goToForm(cfg.id)">
            <van-icon name="edit" size="18" />
            <span>{{ t('common.edit') }}</span>
          </button>
          <button class="action-btn action-btn--danger" @click="handleDelete(cfg)">
            <van-icon name="delete-o" size="18" />
            <span>{{ t('common.delete') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Add provider button -->
    <div v-if="isOwner && configs.length > 0" class="page-actions">
      <van-button block plain icon="plus" @click="goToForm()">
        {{ t('asrConfig.addProvider') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.asr-config-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 8px 16px 4px;
  line-height: 1.5;
}

.loading-wrapper {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 20px;
  color: var(--text-secondary);
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 4px 0 0;
}

.empty-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
  line-height: 1.5;
}

/* ── Config list ── */
.config-list {
  padding: 12px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Card — matches AIConfigPage .provider-card ── */
.provider-card {
  background: var(--bg-card, var(--card-bg));
  border-radius: 16px;
  border: 1px solid var(--border-light);
  overflow: hidden;
}

/* ── Card header ── */
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 14px 12px;
  border-bottom: 1px solid var(--border-light);
}

.card-logo {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.card-logo svg {
  width: 26px;
  height: 26px;
}

.logo--openai {
  background: color-mix(in srgb, #10a37f 10%, transparent);
  color: #10a37f;
}
[data-theme='dark'] .logo--openai {
  background: rgba(16, 163, 127, 0.15);
  color: #34d399;
}

.logo--siliconflow {
  background: color-mix(in srgb, #6366f1 10%, transparent);
  color: #6366f1;
}
[data-theme='dark'] .logo--siliconflow {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
}

.logo--openai_compatible {
  background: color-mix(in srgb, #64748b 10%, transparent);
  color: #64748b;
}
[data-theme='dark'] .logo--openai_compatible {
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
}

.card-header-info {
  flex: 1;
  min-width: 0;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-provider-fmt {
  font-size: 12px;
  color: var(--text-tertiary);
  font-family: monospace;
  flex-shrink: 0;
}

.card-status-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot--success { background: var(--van-success-color, #16a34a); }
.dot--danger { background: var(--van-danger-color, #ef4444); }
.dot--warning { background: var(--van-warning-color, #d97706); }
.dot--default { background: var(--text-tertiary, #93939f); }

.status-label {
  font-size: 12px;
  flex-shrink: 0;
}
.status--success { color: #16a34a; }
.status--danger { color: #ef4444; }
.status--warning { color: #d97706; }
.status--default { color: var(--text-secondary); }

/* ── Card body ── */
.card-body {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.model-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-id {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  gap: 8px;
}

.info-label {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.info-value {
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
}

.info-value--mono {
  font-family: monospace;
  font-size: 12px;
}

.warn-row {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #d97706;
  font-size: 12px;
}

/* ── Test button — matches AIConfigPage .test-btn ── */
.test-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  min-height: 36px;
  border-radius: 8px;
  border: 1px solid var(--van-primary-color);
  background: transparent;
  color: var(--van-primary-color);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s, opacity 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.test-btn:active {
  background: color-mix(in srgb, var(--van-primary-color) 10%, transparent);
}
.test-btn--testing {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: var(--text-tertiary);
  color: var(--text-tertiary);
}
.test-btn__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.test-btn__icon--spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* ── Test result ── */
.test-result {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 8px;
  background: color-mix(in srgb, var(--van-primary-color) 6%, transparent);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.lang-result {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.lang-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.lang-label {
  font-weight: 600;
  color: var(--text-primary);
}

.diff-display {
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
  padding: 4px 0;
}

.diff-equal { color: var(--text-primary); }
.diff-sub {
  background: #fef3c7;
  color: #92400e;
  text-decoration: line-through;
  border-radius: 2px;
  padding: 0 1px;
}
.diff-del {
  background: #fee2e2;
  color: #991b1b;
  text-decoration: line-through;
  border-radius: 2px;
  padding: 0 1px;
}
.diff-ins {
  background: #dcfce7;
  color: #166534;
  border-radius: 2px;
  padding: 0 1px;
}

.transcribed-text {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.text-success { color: #16a34a; }
.text-danger { color: #ef4444; }

.test-latency {
  color: var(--text-secondary);
  font-size: 11px;
}

/* ── Card actions — matches AIConfigPage ── */
.card-actions {
  display: flex;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  margin: 0;
  border-radius: 0 0 16px 16px;
  overflow: hidden;
}

[data-theme='dark'] .card-actions {
  border-color: rgba(255, 255, 255, 0.08);
}

.action-btn {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 10px 4px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
  -webkit-tap-highlight-color: transparent;
}

.action-btn + .action-btn::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  height: 60%;
  width: 1px;
  background: rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .action-btn + .action-btn::before {
  background: rgba(255, 255, 255, 0.08);
}

.action-btn:active {
  background: rgba(0, 0, 0, 0.04);
}

[data-theme='dark'] .action-btn:active {
  background: rgba(255, 255, 255, 0.06);
}

.action-btn--edit {
  color: #4f46e5;
}
[data-theme='dark'] .action-btn--edit {
  color: #818cf8;
}

.action-btn--danger {
  color: #ee0a24;
}

/* ── Page actions ── */
.page-actions {
  padding: 16px 16px 0;
}
</style>
