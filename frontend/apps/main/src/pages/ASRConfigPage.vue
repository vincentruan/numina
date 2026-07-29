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

function providerLabel(provider: string): string {
  return provider === 'openai' ? 'OpenAI' : 'OpenAI Compatible'
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

    <div class="page-body">
      <!-- Description -->
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
        <van-button v-if="isOwner" type="primary" size="small" @click="goToForm()">
          {{ t('asrConfig.addProvider') }}
        </van-button>
      </div>

      <!-- Config list -->
      <div v-else class="config-list">
        <div v-for="cfg in configs" :key="cfg.id" class="config-card">
          <div class="config-header">
            <div class="config-name">
              {{ cfg.name }}
              <span class="config-provider">{{ providerLabel(cfg.provider) }}</span>
            </div>
            <span class="config-status" :class="statusClass(cfg)">
              {{ statusLabel(cfg) }}
            </span>
          </div>

          <div class="config-body">
            <div v-if="cfg.model_id" class="config-row">
              <span class="config-label">{{ t('asrConfig.modelId') }}</span>
              <span class="config-value">{{ cfg.model_id }}</span>
            </div>
            <div v-if="cfg.base_url" class="config-row">
              <span class="config-label">{{ t('asrConfig.baseUrl') }}</span>
              <span class="config-value config-value--mono">{{ cfg.base_url }}</span>
            </div>
            <div class="config-row">
              <span class="config-label">{{ t('asrConfig.apiKey') }}</span>
              <span class="config-value">{{ cfg.ai_api_key_masked || '—' }}</span>
            </div>
            <div v-if="cfg.failure_count > 0" class="config-row config-row--warn">
              {{ t('asrConfig.failureCount', { count: cfg.failure_count }) }}
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
                  <span class="config-label">ASR: </span>{{ lr.transcribed }}
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

          <div v-if="isOwner" class="config-actions">
            <van-button
              size="small"
              :loading="testingId === cfg.id"
              :loading-text="t('asrConfig.testRunning')"
              @click="handleTest(cfg)"
            >
              {{ t('asrConfig.testAndEnable') }}
            </van-button>
            <van-switch
              :model-value="cfg.is_active"
              size="20"
              @update:model-value="toggleActive(cfg)"
            />
            <van-button size="small" plain @click="goToForm(cfg.id)">
              {{ t('common.edit') }}
            </van-button>
            <van-button size="small" plain type="danger" @click="handleDelete(cfg)">
              {{ t('common.delete') }}
            </van-button>
          </div>
        </div>
      </div>

      <!-- Add button -->
      <div v-if="isOwner && configs.length > 0" class="add-btn-wrapper">
        <van-button type="primary" plain block @click="goToForm()">
          {{ t('asrConfig.addProvider') }}
        </van-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.asr-config-page {
  min-height: 100vh;
  background: var(--bg-primary);
}

.page-body {
  padding: 12px 16px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 16px;
  line-height: 1.5;
}

.loading-wrapper {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 12px 0 8px;
}

.empty-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 16px;
  line-height: 1.5;
}

.config-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-card {
  background: var(--card-bg, #f5f5ff);
  border-radius: 12px;
  padding: 14px;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.config-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.config-provider {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-secondary);
  margin-left: 6px;
}

.config-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}

.status--success {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.status--danger {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.status--warning {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.status--default {
  background: rgba(107, 114, 128, 0.12);
  color: var(--text-secondary);
}

.config-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.config-label {
  color: var(--text-secondary);
}

.config-value {
  color: var(--text-primary);
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-value--mono {
  font-family: monospace;
  font-size: 12px;
}

.config-row--warn {
  color: #d97706;
  font-size: 12px;
}

.test-result {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 8px;
  background: rgba(99, 102, 241, 0.06);
  border-radius: 6px;
  margin-top: 4px;
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

.diff-equal {
  color: var(--text-primary);
}

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

.text-success {
  color: #16a34a;
}

.text-danger {
  color: #ef4444;
}

.test-latency {
  color: var(--text-secondary);
  font-size: 11px;
}

.config-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.add-btn-wrapper {
  margin-top: 16px;
}
</style>
