<template>
  <div class="ai-config-page">
    <PageHeader title="AI 智能助手" />

    <!-- AI Enable Toggle (owner only) -->
    <van-cell-group inset title="AI 功能">
      <van-cell title="启用 AI 助手" center>
        <template #value>
          <van-switch
            v-model="aiEnabled"
            :disabled="!isOwner || saving"
            @change="onToggleAI"
          />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Provider Config (owner only, shown when enabled) -->
    <template v-if="isOwner">
      <van-cell-group inset title="服务商配置" class="section">
        <van-cell title="AI 服务商" :value="providerLabel" is-link @click="showProviderPicker = true" />
        <van-field
          v-model="apiKeyInput"
          label="API Key"
          :placeholder="maskedKey || '请输入 API Key'"
          :type="showApiKey ? 'text' : 'password'"
          clearable
          :disabled="saving"
        >
          <template #right-icon>
            <van-icon
              :name="showApiKey ? 'eye-o' : 'closed-eye'"
              style="cursor: pointer"
              :aria-label="showApiKey ? '隐藏 API Key' : '显示 API Key'"
              @click="showApiKey = !showApiKey"
            />
          </template>
        </van-field>
        <van-field
          v-model="baseUrlInput"
          label="Base URL"
          :placeholder="selectedProvider === 'anthropic' ? '如: https://api.anthropic.com' : '如: https://api.openai.com'"
          clearable
          :disabled="saving"
        />
        <van-field
          v-model="modelIdInput"
          label="模型 ID"
          :placeholder="selectedProvider === 'anthropic' ? '如: claude-3-5-haiku-20241022' : '如: gpt-4o-mini'"
          :required="!!selectedProvider"
          clearable
          :disabled="saving"
        >
          <template #right-icon>
            <div style="display: flex; gap: 8px; align-items: center;">
              <van-icon
                v-if="testStatusIcon"
                :name="testStatusIcon"
                :color="testStatusColor"
                style="cursor: pointer; font-size: 18px"
                :aria-label="testStatusLabel"
                @click="showTestDetails = true"
              />
              <van-icon
                v-if="thinkingStatusIcon"
                :name="thinkingStatusIcon"
                :color="thinkingStatusColor"
                style="cursor: pointer; font-size: 18px"
                :aria-label="thinkingStatusLabel"
                @click="showThinkingDetails = true"
              />
            </div>
          </template>
        </van-field>
        <van-field
          v-model="visionModelIdInput"
          label="图像模型 ID"
          :placeholder="selectedProvider === 'anthropic' ? '如: claude-3-5-sonnet-20241022' : '如: gpt-4o'"
          clearable
          :disabled="saving"
        >
          <template #right-icon>
            <van-icon
              v-if="visionTestStatusIcon"
              :name="visionTestStatusIcon"
              :color="visionTestStatusColor"
              style="cursor: pointer; font-size: 18px"
              :aria-label="visionTestStatusLabel"
              @click="showVisionTestDetails = true"
            />
          </template>
        </van-field>
      </van-cell-group>

      <div class="actions">
        <van-button
          block
          type="primary"
          :loading="saving"
          :disabled="!canSave"
          @click="onSave"
        >
          保存配置
        </van-button>
        <div
          v-if="validationError"
          class="tip"
        >
          <van-icon name="info-o" />
          <span>{{ validationError }}</span>
        </div>
      </div>
    </template>

    <!-- Non-owner view -->
    <template v-else>
      <van-cell-group inset class="section">
        <van-cell
          title="当前状态"
          :value="aiStore.config?.ai_enabled ? '已启用' : '未启用'"
        />
        <van-cell
          v-if="aiStore.config?.ai_provider"
          title="服务商"
          :value="providerLabel"
        />
        <van-cell
          v-if="aiStore.config?.ai_base_url"
          title="Base URL"
          :value="aiStore.config.ai_base_url"
        />
        <van-cell
          v-if="aiStore.config?.ai_model_id"
          title="模型 ID"
          :value="aiStore.config.ai_model_id"
        />
        <van-cell
          v-if="aiStore.config?.ai_vision_model_id"
          title="图像模型 ID"
          :value="aiStore.config.ai_vision_model_id"
        />
      </van-cell-group>
      <div class="tip">
        <van-icon name="info-o" />
        <span>AI 功能由家庭管理员配置</span>
      </div>
    </template>

    <!-- Provider Picker -->
    <van-popup v-model:show="showProviderPicker" round position="bottom">
      <van-picker
        :columns="providerOptions"
        @confirm="onProviderConfirm"
        @cancel="showProviderPicker = false"
      />
    </van-popup>

    <!-- Connection Test Details Popup -->
    <van-popup v-model:show="showTestDetails" round position="bottom" style="padding: 20px">
      <div class="test-details">
        <h3 style="margin-bottom: 16px; font-size: 16px">主模型连接测试</h3>
        <van-cell-group inset>
          <van-cell title="连接状态" :value="aiStore.config?.ai_test_connected ? '✅ 成功' : '❌ 失败'" />
          <van-cell v-if="aiStore.config?.ai_test_message" title="消息" :value="aiStore.config.ai_test_message" />
          <van-cell v-if="aiStore.config?.ai_test_latency_ms" title="延迟" :value="`${aiStore.config.ai_test_latency_ms}ms`" />
          <van-cell v-if="aiStore.config?.ai_test_timestamp" title="测试时间" :value="formatTimestamp(aiStore.config.ai_test_timestamp)" />
        </van-cell-group>
        <van-button
          block
          type="primary"
          style="margin-top: 16px"
          :loading="testingMain"
          :disabled="!aiStore.config?.ai_enabled || !modelIdInput.trim()"
          @click="onTestMain"
        >
          测试连接
        </van-button>
        <van-button block plain style="margin-top: 10px" @click="showTestDetails = false">
          关闭
        </van-button>
      </div>
    </van-popup>

    <!-- Thinking Test Details Popup -->
    <van-popup v-model:show="showThinkingDetails" round position="bottom" style="padding: 20px">
      <div class="test-details">
        <h3 style="margin-bottom: 16px; font-size: 16px">思考能力测试</h3>
        <van-cell-group inset>
          <van-cell title="测试结果" :value="aiStore.config?.ai_test_thinking_success ? '🧠 支持思考' : '❌ 不支持'" />
          <van-cell v-if="aiStore.config?.ai_test_thinking_message" title="消息" :value="aiStore.config.ai_test_thinking_message" />
          <van-cell v-if="aiStore.config?.ai_test_thinking_latency_ms" title="延迟" :value="`${aiStore.config.ai_test_thinking_latency_ms}ms`" />
          <van-cell v-if="aiStore.config?.ai_test_thinking_timestamp" title="测试时间" :value="formatTimestamp(aiStore.config.ai_test_thinking_timestamp)" />
        </van-cell-group>
        <van-button
          block
          type="primary"
          style="margin-top: 16px"
          :loading="testingThinking"
          :disabled="!aiStore.config?.ai_enabled || !modelIdInput.trim()"
          @click="onTestThinking"
        >
          测试思考能力
        </van-button>
        <van-button block plain style="margin-top: 10px" @click="showThinkingDetails = false">
          关闭
        </van-button>
      </div>
    </van-popup>

    <!-- Vision Test Details Popup -->
    <van-popup v-model:show="showVisionTestDetails" round position="bottom" style="padding: 20px">
      <div class="test-details">
        <h3 style="margin-bottom: 16px; font-size: 16px">图像模型测试结果</h3>
        <van-cell-group inset>
          <van-cell title="连接状态" :value="aiStore.config?.ai_vision_test_success ? '✅ 成功' : '❌ 失败'" />
          <van-cell v-if="aiStore.config?.ai_vision_test_message" title="消息" :value="aiStore.config.ai_vision_test_message" />
          <van-cell v-if="aiStore.config?.ai_vision_test_latency_ms" title="延迟" :value="`${aiStore.config.ai_vision_test_latency_ms}ms`" />
          <van-cell v-if="aiStore.config?.ai_vision_test_timestamp" title="测试时间" :value="formatTimestamp(aiStore.config.ai_vision_test_timestamp)" />
        </van-cell-group>
        <van-button
          block
          type="primary"
          style="margin-top: 16px"
          :loading="testingVision"
          :disabled="!aiStore.config?.ai_enabled || !visionModelIdInput.trim()"
          @click="onTestVision"
        >
          测试图像模型
        </van-button>
        <van-button block plain style="margin-top: 10px" @click="showVisionTestDetails = false">
          关闭
        </van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useAIStore } from '@/stores/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const authStore = useAuthStore()
const aiStore = useAIStore()

const saving = ref(false)
const testingMain = ref(false)
const testingThinking = ref(false)
const testingVision = ref(false)
const showProviderPicker = ref(false)
const showTestDetails = ref(false)
const showThinkingDetails = ref(false)
const showVisionTestDetails = ref(false)
const apiKeyInput = ref('')
const baseUrlInput = ref('')
const modelIdInput = ref('')
const visionModelIdInput = ref('')
const selectedProvider = ref<string>('anthropic')
const aiEnabled = ref(false)
const showApiKey = ref(false)

const isOwner = computed(() => authStore.user?.role === 'owner')

const maskedKey = computed(() => aiStore.config?.ai_api_key_masked ?? null)

const testStatusIcon = computed(() => {
  if (aiStore.config?.ai_test_connected === null) return null
  return aiStore.config?.ai_test_connected ? 'success' : 'cross'
})

const testStatusColor = computed(() => {
  if (aiStore.config?.ai_test_connected === null) return '#999'
  return aiStore.config?.ai_test_connected ? '#07c160' : '#ee0a24'
})

const testStatusLabel = computed(() => {
  if (aiStore.config?.ai_test_connected === null) return '未测试'
  return aiStore.config?.ai_test_connected ? '连接成功' : '连接失败'
})

const thinkingStatusIcon = computed(() => {
  if (aiStore.config?.ai_test_thinking_success === null) return null
  return aiStore.config?.ai_test_thinking_success ? 'success' : 'cross'
})

const thinkingStatusColor = computed(() => {
  if (aiStore.config?.ai_test_thinking_success === null) return '#999'
  return aiStore.config?.ai_test_thinking_success ? '#07c160' : '#ee0a24'
})

const thinkingStatusLabel = computed(() => {
  if (aiStore.config?.ai_test_thinking_success === null) return '未测试'
  return aiStore.config?.ai_test_thinking_success ? '支持思考' : '不支持'
})

const visionTestStatusIcon = computed(() => {
  if (aiStore.config?.ai_vision_test_success === null) return null
  return aiStore.config?.ai_vision_test_success ? 'success' : 'cross'
})

const visionTestStatusColor = computed(() => {
  if (aiStore.config?.ai_vision_test_success === null) return '#999'
  return aiStore.config?.ai_vision_test_success ? '#07c160' : '#ee0a24'
})

const visionTestStatusLabel = computed(() => {
  if (aiStore.config?.ai_vision_test_success === null) return '未测试'
  return aiStore.config?.ai_vision_test_success ? '测试成功' : '测试失败'
})

function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const providerOptions = [
  { text: 'Anthropic (Claude)', value: 'anthropic', icon: '💬' },
  { text: 'OpenAI (GPT)', value: 'openai', icon: '🤖' },
]

const providerLabel = computed(() => {
  if (selectedProvider.value === 'anthropic') return '💬 Anthropic (Claude)'
  if (selectedProvider.value === 'openai') return '🤖 OpenAI (GPT)'
  return '未选择'
})

const validationError = computed(() => {
  if (saving.value) return null
  if (aiEnabled.value && !selectedProvider.value) return '请选择 AI Provider'
  if (aiEnabled.value && !apiKeyInput.value.trim() && !aiStore.config?.ai_api_key_masked) return '请填写 API Key'
  if (aiEnabled.value && selectedProvider.value && !modelIdInput.value.trim()) return '请填写模型 ID'
  return null
})

const canSave = computed(() => !saving.value && !validationError.value)

onMounted(async () => {
  await aiStore.fetchConfig()
  aiEnabled.value = aiStore.config?.ai_enabled ?? false
  selectedProvider.value = aiStore.config?.ai_provider ?? 'anthropic'
  baseUrlInput.value = aiStore.config?.ai_base_url ?? ''
  modelIdInput.value = aiStore.config?.ai_model_id ?? ''
  visionModelIdInput.value = aiStore.config?.ai_vision_model_id ?? ''
})

async function onToggleAI(val: boolean) {
  saving.value = true
  try {
    await aiStore.updateConfig({ ai_enabled: val })
    showToast(val ? t('toast.aiEnabled') : t('toast.aiDisabled'))
  } catch {
    aiEnabled.value = !val
    showToast(t('toast.operationFailed2'))
  } finally {
    saving.value = false
  }
}

function onProviderConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  selectedProvider.value = selectedOptions[0].value
  showProviderPicker.value = false
}

async function onSave() {
  saving.value = true
  try {
    const payload: { ai_provider?: string; ai_api_key?: string; ai_base_url?: string | null; ai_model_id?: string | null; ai_vision_model_id?: string | null } = {}
    payload.ai_provider = selectedProvider.value
    if (apiKeyInput.value.trim()) payload.ai_api_key = apiKeyInput.value.trim()
    payload.ai_base_url = baseUrlInput.value.trim() || null
    payload.ai_model_id = modelIdInput.value.trim() || null
    payload.ai_vision_model_id = visionModelIdInput.value.trim() || null
    await aiStore.updateConfig(payload)
    apiKeyInput.value = ''
    showToast(t('toast.aiConfigSaved'))
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : t('toast.saveFailedGeneric')
    showToast(msg.includes('API Key') ? msg : t('toast.saveFailedGeneric'))
  } finally {
    saving.value = false
  }
}

async function onTestMain() {
  testingMain.value = true
  try {
    await aiStore.testMainModel()
    await aiStore.fetchConfig()
    showToast(aiStore.config?.ai_test_connected ? '✅ 主模型连接成功' : `❌ ${aiStore.config?.ai_test_message || '连接失败'}`)
  } catch {
    showToast(t('toast.aiTestFailed'))
  } finally {
    testingMain.value = false
  }
}

async function onTestThinking() {
  testingThinking.value = true
  try {
    await aiStore.testThinking()
    await aiStore.fetchConfig()
    showToast(aiStore.config?.ai_test_thinking_success ? '🧠 支持思考能力' : `❌ ${aiStore.config?.ai_test_thinking_message || '不支持'}`)
  } catch {
    showToast(t('toast.aiTestFailed'))
  } finally {
    testingThinking.value = false
  }
}

async function onTestVision() {
  testingVision.value = true
  try {
    await aiStore.testVisionModel()
    await aiStore.fetchConfig()
    showToast(aiStore.config?.ai_vision_test_success ? '✅ 图像模型测试成功' : `❌ ${aiStore.config?.ai_vision_test_message || '测试失败'}`)
  } catch {
    showToast(t('toast.aiTestFailed'))
  } finally {
    testingVision.value = false
  }
}
</script>

<style scoped>
.ai-config-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}
.section {
  margin-top: 12px;
}
.actions {
  padding: 16px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.test-btn {
  margin-top: 0;
}
.tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 16px;
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
