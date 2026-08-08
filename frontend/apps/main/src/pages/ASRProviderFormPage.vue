<script setup lang="ts">
/**
 * ASRProviderFormPage — create/edit ASR provider config
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { getASRConfigs, createASRConfig, updateASRConfig, testASRConfig } from '@/api/asr'
import type { ASRProviderConfig, ASRTestResult, ASRDiffOp } from '@/api/asr'
import PageHeader from '@/components/common/PageHeader.vue'
import ASRProviderPickerSheet from '@/components/ai/ASRProviderPickerSheet.vue'

defineOptions({ name: 'ASRProviderFormPage' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const configId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => !!configId.value)

// Form fields
const name = ref('')
const provider = ref<'openai' | 'openai_compatible' | 'siliconflow'>('openai')
const apiKey = ref('')
const baseUrl = ref('')
const modelId = ref('')
const model2Id = ref('')
const model3Id = ref('')

// State
const saving = ref(false)
const testing = ref(false)
const testResult = ref<ASRTestResult | null>(null)
const existingConfig = ref<ASRProviderConfig | null>(null)

// Provider picker
const showProviderPicker = ref(false)

// Auto-fill base URL and model when switching provider
const PROVIDER_DEFAULTS: Record<string, { baseUrl: string; modelId: string }> = {
  openai: { baseUrl: 'https://api.openai.com/v1', modelId: 'whisper-1' },
  siliconflow: { baseUrl: 'https://api.siliconflow.cn/v1', modelId: 'FunAudioLLM/SenseVoiceSmall' },
}

watch(provider, (newProvider, oldProvider) => {
  const defaults = PROVIDER_DEFAULTS[newProvider]
  if (defaults && !configId.value) {
    const oldDefaults = oldProvider ? PROVIDER_DEFAULTS[oldProvider] : undefined
    // Only reset baseUrl if it still matches the previous provider's default
    if (!oldDefaults || baseUrl.value === oldDefaults.baseUrl) {
      baseUrl.value = defaults.baseUrl
    }
    // Only set modelId if it's empty or still matches previous provider's default
    if (!modelId.value || (oldDefaults && modelId.value === oldDefaults.modelId)) {
      modelId.value = defaults.modelId
    }
  }
}, { immediate: true })

function providerLabel(p: string): string {
  if (p === 'openai') return t('asrConfig.providerOpenAI')
  if (p === 'openai_compatible') return t('asrConfig.providerOpenAICompatible')
  if (p === 'siliconflow') return t('asrConfig.providerSiliconFlow')
  return p
}

const canSubmit = computed(() => name.value.trim() && apiKey.value.trim())

async function loadExisting() {
  if (!configId.value) return
  try {
    const res = await getASRConfigs()
    const cfg = res.data.configs.find(c => c.id === configId.value)
    if (cfg) {
      existingConfig.value = cfg
      name.value = cfg.name
      provider.value = cfg.provider as 'openai' | 'openai_compatible' | 'siliconflow'
      baseUrl.value = cfg.base_url || ''
      modelId.value = cfg.model_id || ''
      model2Id.value = cfg.model_2_id || ''
      model3Id.value = cfg.model_3_id || ''
    }
  } catch {
    showFailToast(t('common.failed'))
    router.back()
  }
}

async function handleSave() {
  if (!canSubmit.value) return
  saving.value = true
  testResult.value = null
  try {
    if (isEdit.value && configId.value) {
      const payload: Record<string, unknown> = {
        name: name.value.trim(),
        provider: provider.value,
        base_url: baseUrl.value.trim() || null,
        model_id: modelId.value.trim() || null,
        model_2_id: model2Id.value.trim() || null,
        model_3_id: model3Id.value.trim() || null,
      }
      if (apiKey.value.trim()) {
        payload.ai_api_key = apiKey.value.trim()
      }
      await updateASRConfig(configId.value, payload as Parameters<typeof updateASRConfig>[1])
    } else {
      await createASRConfig({
        name: name.value.trim(),
        provider: provider.value,
        ai_api_key: apiKey.value.trim(),
        base_url: baseUrl.value.trim() || null,
        model_id: modelId.value.trim() || null,
        model_2_id: model2Id.value.trim() || null,
        model_3_id: model3Id.value.trim() || null,
      })
    }
    showSuccessToast(t('toast.aiConfigSaved'))
    router.push('/settings/ai/asr')
  } catch {
    showFailToast(t('common.failed'))
  } finally {
    saving.value = false
  }
}

async function handleTestAndEnable() {
  if (!existingConfig.value) return
  testing.value = true
  testResult.value = null
  try {
    const res = await testASRConfig(existingConfig.value.id)
    testResult.value = res.data
    if (res.data.success) {
      // Auto-enable after successful test
      await updateASRConfig(existingConfig.value.id, { is_active: true })
      showSuccessToast(t('asrConfig.testSuccess'))
      router.push('/settings/ai/asr')
    } else {
      showFailToast(res.data.message || t('asrConfig.testFailed'))
    }
  } catch {
    showFailToast(t('asrConfig.testFailed'))
  } finally {
    testing.value = false
  }
}

onMounted(loadExisting)
</script>

<template>
  <div class="asr-form-page">
    <PageHeader :title="isEdit ? t('asrConfig.editProvider') : t('asrConfig.addProvider')" />

    <div class="page-body">
      <van-cell-group inset>
        <!-- Provider type -->
        <van-cell
          :title="t('asrConfig.provider')"
          is-link
          class="provider-select-cell"
          @click="showProviderPicker = true"
        >
          <template #value>
            <div class="provider-cell-value">
              <div class="provider-cell-logo" :class="`logo--${provider}`">
                <!-- OpenAI -->
                <svg v-if="provider === 'openai'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365 2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" fill="currentColor" />
                </svg>
                <!-- OpenAI Compatible -->
                <svg v-else-if="provider === 'openai_compatible'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365 2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" fill="currentColor" opacity="0.85" />
                  <circle cx="18" cy="6" r="4" fill="currentColor" opacity="0.15" />
                  <path d="M17 5v2M18 4v4M19 5v2" stroke="currentColor" stroke-width="1" stroke-linecap="round" opacity="0.6" />
                </svg>
                <!-- SiliconFlow -->
                <svg v-else-if="provider === 'siliconflow'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M4 4h6v6H4V4zm10 0h6v6h-6V4zM4 14h6v6H4v-6zm10 0h6v6h-6v-6z" fill="currentColor" opacity="0.2" />
                  <path d="M7 7h10M7 17h10M7 7v10M17 7v10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                  <circle cx="12" cy="12" r="2.5" fill="currentColor" />
                </svg>
              </div>
              <span class="provider-cell-text">{{ providerLabel(provider) }}</span>
            </div>
          </template>
        </van-cell>

        <!-- Name -->
        <van-field
          v-model="name"
          :label="t('asrConfig.providerName')"
          :placeholder="t('asrConfig.providerNamePlaceholder')"
          maxlength="100"
          show-word-limit
        />

        <!-- API Key -->
        <van-field
          v-model="apiKey"
          type="password"
          :label="t('asrConfig.apiKey')"
          :placeholder="isEdit ? '••••••••' : t('asrConfig.apiKeyPlaceholder')"
          autocomplete="off"
        />

        <!-- Base URL -->
        <van-field
          v-model="baseUrl"
          :label="t('asrConfig.baseUrl')"
          :placeholder="t('asrConfig.baseUrlPlaceholder')"
          clearable
        />

        <!-- Model ID (primary) -->
        <van-field
          v-model="modelId"
          :label="t('asrConfig.modelId')"
          :placeholder="t('asrConfig.modelIdPlaceholder')"
          clearable
        />

        <!-- Model ID 2 -->
        <van-field
          v-model="model2Id"
          :label="t('asrConfig.modelId2')"
          placeholder="whisper-1"
          clearable
        />

        <!-- Model ID 3 -->
        <van-field
          v-model="model3Id"
          :label="t('asrConfig.modelId3')"
          placeholder="whisper-1"
          clearable
        />
      </van-cell-group>

      <!-- Test result with per-language WER diff -->
      <div v-if="testResult" class="test-result-card">
        <div class="test-result-header" :class="testResult.success ? 'text-success' : 'text-danger'">
          {{ testResult.message }}
        </div>
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
            >{{ op.ref ?? op.hyp ?? '' }}</span>
          </div>
          <div v-if="lr.transcribed" class="transcribed-text">
            ASR: {{ lr.transcribed }}
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="form-actions">
        <van-button
          type="primary"
          block
          :loading="saving"
          :disabled="!canSubmit"
          @click="handleSave"
        >
          {{ t('common.save') }}
        </van-button>

        <van-button
          v-if="isEdit && existingConfig"
          plain
          block
          :loading="testing"
          :loading-text="t('asrConfig.testRunning')"
          class="mt-12"
          @click="handleTestAndEnable"
        >
          {{ t('asrConfig.testAndEnable') }}
        </van-button>
      </div>

      <!-- Provider picker -->
      <ASRProviderPickerSheet
        v-model:show="showProviderPicker"
        v-model="provider"
      />
    </div>
  </div>
</template>

<style scoped>
.asr-form-page {
  min-height: 100vh;
  background: var(--bg-secondary);
}

.page-body {
  padding: 12px 0;
}

.test-result-card {
  margin: 16px;
  padding: 12px;
  background: var(--bg-card, var(--card-bg));
  border-radius: 12px;
  border: 1px solid var(--border-light);
}

.test-result-header {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 12px;
}

.lang-result {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.lang-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.lang-label {
  font-weight: 600;
  color: var(--text-primary);
}

.diff-display {
  font-size: 14px;
  line-height: 1.8;
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
}

.text-success {
  color: #16a34a;
}

.text-danger {
  color: #ef4444;
}

.form-actions {
  padding: 16px;
}

.mt-12 {
  margin-top: 12px;
}

/* Provider cell with logo */
.provider-select-cell :deep(.van-cell__title) {
  flex: none;
  width: var(--van-field-label-width, 6.2em);
  margin-right: var(--van-field-label-margin-right, 12px);
}

.provider-select-cell :deep(.van-cell__value) {
  flex: 1;
  min-width: 0;
}

.provider-cell-value {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.provider-cell-logo {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.provider-cell-logo svg {
  width: 16px;
  height: 16px;
}

/* OpenAI: green */
.logo--openai {
  background: color-mix(in srgb, #10a37f 12%, transparent);
  color: #10a37f;
}

[data-theme='dark'] .logo--openai {
  background: rgba(16, 163, 127, 0.15);
  color: #34d399;
}

/* OpenAI Compatible: blue-gray */
.logo--openai_compatible {
  background: color-mix(in srgb, #64748b 12%, transparent);
  color: #64748b;
}

[data-theme='dark'] .logo--openai_compatible {
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
}

/* SiliconFlow: indigo */
.logo--siliconflow {
  background: color-mix(in srgb, #6366f1 12%, transparent);
  color: #6366f1;
}

[data-theme='dark'] .logo--siliconflow {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
}

.provider-cell-text {
  font-size: 13px;
  color: var(--text-secondary);
  flex: 1;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
