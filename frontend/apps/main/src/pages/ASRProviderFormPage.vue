<script setup lang="ts">
/**
 * ASRProviderFormPage — create/edit ASR provider config
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { getASRConfigs, createASRConfig, updateASRConfig, testASRConfig } from '@/api/asr'
import type { ASRProviderConfig, ASRTestResult, ASRDiffOp } from '@/api/asr'
import PageHeader from '@/components/common/PageHeader.vue'

defineOptions({ name: 'ASRProviderFormPage' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const configId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => !!configId.value)

// Form fields
const name = ref('')
const provider = ref<'openai' | 'openai_compatible'>('openai')
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

// Provider options
const providerOptions = [
  { text: 'OpenAI', value: 'openai' },
  { text: 'OpenAI Compatible', value: 'openai_compatible' },
]
const showProviderPicker = ref(false)

const canSubmit = computed(() => name.value.trim() && apiKey.value.trim())

async function loadExisting() {
  if (!configId.value) return
  try {
    const res = await getASRConfigs()
    const cfg = res.data.configs.find(c => c.id === configId.value)
    if (cfg) {
      existingConfig.value = cfg
      name.value = cfg.name
      provider.value = cfg.provider as 'openai' | 'openai_compatible'
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
    showSuccessToast(t('aiConfig.aiConfigSaved'))
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

function onProviderConfirm({ selectedOptions }: { selectedOptions: { text: string; value: string }[] }) {
  if (selectedOptions[0]) {
    provider.value = selectedOptions[0].value as 'openai' | 'openai_compatible'
  }
  showProviderPicker.value = false
}

onMounted(loadExisting)
</script>

<template>
  <div class="asr-form-page">
    <PageHeader :title="isEdit ? t('asrConfig.editProvider') : t('asrConfig.addProvider')" />

    <div class="page-body">
      <van-cell-group inset>
        <!-- Provider type -->
        <van-field
          :model-value="provider === 'openai' ? 'OpenAI' : 'OpenAI Compatible'"
          is-link
          readonly
          :label="t('asrConfig.provider')"
          :placeholder="t('asrConfig.provider')"
          @click="showProviderPicker = true"
        />

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
      <van-popup v-model:show="showProviderPicker" position="bottom" round>
        <van-picker
          :columns="providerOptions"
          @confirm="onProviderConfirm"
          @cancel="showProviderPicker = false"
        />
      </van-popup>
    </div>
  </div>
</template>

<style scoped>
.asr-form-page {
  min-height: 100vh;
  background: var(--bg-primary);
}

.page-body {
  padding: 12px 0;
}

.test-result-card {
  margin: 16px;
  padding: 12px;
  background: var(--card-bg, #f5f5ff);
  border-radius: 8px;
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
</style>
