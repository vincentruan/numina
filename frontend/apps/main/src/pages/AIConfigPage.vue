<template>
  <div class="ai-config-page">
    <PageHeader :title="t('aiConfig.pageTitle')" />

    <!-- AI Enable Toggle (owner only) -->
    <van-cell-group inset :title="t('aiConfig.aiFeatures')">
      <van-cell :title="t('aiConfig.enableAI')" center>
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
      <van-cell-group inset :title="t('aiConfig.providerConfig')" class="section">
        <van-cell :title="t('aiConfig.aiProvider')" :value="providerLabel" is-link @click="showProviderPicker = true" />
        <!-- API Key: shows masked value by default; eye icon toggles plaintext while typing new key -->
        <van-field
          v-model="apiKeyDisplay"
          :label="t('aiConfig.apiKey')"
          :placeholder="t('aiConfig.apiKeyPlaceholder')"
          :type="editingApiKey && !showApiKey ? 'password' : 'text'"
          :disabled="saving"
          autocomplete="off"
          @input="onApiKeyInput"
        >
          <template #right-icon>
            <van-icon
              v-if="maskedKey && !editingApiKey"
              :name="showApiKey ? 'eye-o' : 'closed-eye'"
              style="cursor: pointer"
              :aria-label="showApiKey ? t('aiConfig.hideApiKey') : t('aiConfig.showApiKey')"
              @click="onToggleRevealApiKey"
            />
            <van-icon
              v-else-if="editingApiKey"
              :name="showApiKey ? 'eye-o' : 'closed-eye'"
              style="cursor: pointer"
              :aria-label="showApiKey ? t('aiConfig.hideApiKey') : t('aiConfig.showApiKey')"
              @click="showApiKey = !showApiKey"
            />
          </template>
        </van-field>
        <van-field
          v-model="baseUrlInput"
          :label="t('aiConfig.baseUrl')"
          :placeholder="selectedProvider === 'anthropic' ? t('aiConfig.baseUrlPlaceholderAnthropic') : t('aiConfig.baseUrlPlaceholderOpenAI')"
          clearable
          :disabled="saving"
        />
        <van-field
          v-model="modelIdInput"
          :label="t('aiConfig.modelId')"
          :placeholder="selectedProvider === 'anthropic' ? t('aiConfig.modelIdPlaceholderAnthropic') : t('aiConfig.modelIdPlaceholderOpenAI')"
          :required="!!selectedProvider"
          clearable
          :disabled="saving"
        >
          <template #right-icon>
            <div class="capability-btns" @click="showMainModelPopup = true">
              <span class="capability-emoji" :class="textEmojiClass">📝</span>
              <span class="capability-emoji" :class="thinkingEmojiClass">🧠</span>
            </div>
          </template>
        </van-field>
        <van-field
          v-model="visionModelIdInput"
          :label="t('aiConfig.visionModelId')"
          :placeholder="selectedProvider === 'anthropic' ? t('aiConfig.visionModelIdPlaceholderAnthropic') : t('aiConfig.visionModelIdPlaceholderOpenAI')"
          clearable
          :disabled="saving"
        >
          <template #right-icon>
            <div class="capability-btns" @click="showVisionModelPopup = true">
              <span class="capability-emoji" :class="visionEmojiClass">🖼️</span>
            </div>
          </template>
        </van-field>
        <van-field
          v-model="timeoutInput"
          :label="t('aiConfig.apiTimeout')"
          :placeholder="t('aiConfig.timeoutPlaceholder')"
          type="digit"
          :disabled="saving"
        />
      </van-cell-group>

      <div class="actions">
        <van-button
          block
          type="primary"
          :loading="saving"
          :disabled="!canSave"
          @click="onSave"
        >
          {{ t('aiConfig.saveConfig') }}
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
          :title="t('aiConfig.currentStatus')"
          :value="aiStore.config?.ai_enabled ? t('aiConfig.statusEnabled') : t('aiConfig.statusDisabled')"
        />
        <van-cell
          v-if="aiStore.config?.ai_provider"
          :title="t('aiConfig.providerLabel')"
          :value="providerLabel"
        />
        <van-cell
          v-if="aiStore.config?.ai_base_url"
          :label="t('aiConfig.baseUrl')"
          :value="aiStore.config.ai_base_url"
        />
        <van-cell
          v-if="aiStore.config?.ai_model_id"
          :title="t('aiConfig.modelId')"
          :value="aiStore.config.ai_model_id"
        />
        <van-cell
          v-if="aiStore.config?.ai_vision_model_id"
          :title="t('aiConfig.visionModelId')"
          :value="aiStore.config.ai_vision_model_id"
        />
        <van-cell
          :title="t('aiConfig.apiTimeout')"
          :value="t('aiConfig.timeoutSeconds', { seconds: aiStore.config?.ai_timeout_seconds ?? 60 })"
        />
      </van-cell-group>
      <div class="tip">
        <van-icon name="info-o" />
        <span>{{ t('aiConfig.nonOwnerTip') }}</span>
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

    <!-- Main Model Test Popup (combined) -->
    <van-popup v-model:show="showMainModelPopup" round position="bottom" style="padding: 20px">
      <div class="test-details">
        <h3 style="margin-bottom: 16px; font-size: 16px">{{ t('aiConfig.mainModelTest') }}</h3>

        <!-- Connection Test Section -->
        <div class="test-section">
          <div class="test-header">
            <span class="capability-emoji" :class="textEmojiClass">📝</span>
            <span>{{ t('aiConfig.textConnection') }}</span>
          </div>
          <van-cell-group inset>
            <van-cell :title="t('aiConfig.status')" :value="connectionStatusText" />
            <van-cell v-if="aiStore.config?.ai_test_message" :title="t('aiConfig.message')" :value="aiStore.config.ai_test_message" />
            <van-cell v-if="aiStore.config?.ai_test_latency_ms" :title="t('aiConfig.latency')" :value="t('aiConfig.latencyMs', { ms: aiStore.config.ai_test_latency_ms })" />
            <van-cell v-if="aiStore.config?.ai_test_timestamp" :title="t('aiConfig.testTime')" :value="formatTimestamp(aiStore.config.ai_test_timestamp)" />
          </van-cell-group>
        </div>

        <!-- Thinking Test Section -->
        <div class="test-section">
          <div class="test-header">
            <span class="capability-emoji" :class="thinkingEmojiClass">🧠</span>
            <span>{{ t('aiConfig.thinkingCapability') }}</span>
          </div>
          <van-cell-group inset>
            <van-cell :title="t('aiConfig.status')" :value="thinkingStatusText" />
            <van-cell v-if="aiStore.config?.ai_test_thinking_message" :title="t('aiConfig.message')" :value="aiStore.config.ai_test_thinking_message" />
            <van-cell v-if="aiStore.config?.ai_test_thinking_latency_ms" :title="t('aiConfig.latency')" :value="t('aiConfig.latencyMs', { ms: aiStore.config.ai_test_thinking_latency_ms })" />
            <van-cell v-if="aiStore.config?.ai_test_thinking_timestamp" :title="t('aiConfig.testTime')" :value="formatTimestamp(aiStore.config.ai_test_thinking_timestamp)" />
          </van-cell-group>
        </div>

        <!-- Test Buttons -->
        <div class="test-buttons">
          <van-button
            type="primary"
            :loading="testingConnection"
            :disabled="!aiStore.config?.ai_enabled || !modelIdInput.trim()"
            @click="onTestConnection"
          >
            {{ t('aiConfig.testConnection') }}
          </van-button>
          <van-button
            type="primary"
            :loading="testingThinking"
            :disabled="!aiStore.config?.ai_enabled || !modelIdInput.trim()"
            @click="onTestThinking"
          >
            {{ t('aiConfig.testThinking') }}
          </van-button>
        </div>
        <van-button block plain style="margin-top: 16px" @click="showMainModelPopup = false">
          {{ t('aiConfig.close') }}
        </van-button>
      </div>
    </van-popup>

    <!-- Vision Model Test Popup -->
    <van-popup v-model:show="showVisionModelPopup" round position="bottom" style="padding: 20px">
      <div class="test-details">
        <h3 style="margin-bottom: 16px; font-size: 16px">{{ t('aiConfig.visionModelTest') }}</h3>

        <!-- Image Understanding Test Section -->
        <div class="test-section">
          <div class="test-header">
            <span class="capability-emoji" :class="visionEmojiClass">️</span>
            <span>{{ t('aiConfig.imageUnderstanding') }}</span>
          </div>
          <van-cell-group inset>
            <van-cell :title="t('aiConfig.status')" :value="visionStatusText" />
            <van-cell v-if="aiStore.config?.ai_vision_test_message" :title="t('aiConfig.message')" :value="aiStore.config.ai_vision_test_message" />
            <van-cell v-if="aiStore.config?.ai_vision_test_latency_ms" :title="t('aiConfig.latency')" :value="t('aiConfig.latencyMs', { ms: aiStore.config.ai_vision_test_latency_ms })" />
            <van-cell v-if="aiStore.config?.ai_vision_test_timestamp" :title="t('aiConfig.testTime')" :value="formatTimestamp(aiStore.config.ai_vision_test_timestamp)" />
          </van-cell-group>
        </div>

        <!-- OCR Text Accuracy Test Section -->
        <div class="test-section">
          <div class="test-header">
            <span class="capability-emoji" :class="visionTextEmojiClass">📖</span>
            <span>{{ t('aiConfig.ocrTextRecognition') }}</span>
          </div>
          <van-cell-group inset>
            <van-cell :title="t('aiConfig.status')" :value="visionTextStatusText" />
            <van-cell v-if="aiStore.config?.ai_vision_text_test_message" :title="t('aiConfig.message')" :value="aiStore.config.ai_vision_text_test_message" />
            <van-cell v-if="aiStore.config?.ai_vision_text_test_latency_ms" :title="t('aiConfig.latency')" :value="t('aiConfig.latencyMs', { ms: aiStore.config.ai_vision_text_test_latency_ms })" />
            <van-cell v-if="aiStore.config?.ai_vision_text_test_timestamp" :title="t('aiConfig.testTime')" :value="formatTimestamp(aiStore.config.ai_vision_text_test_timestamp)" />
          </van-cell-group>
        </div>

        <div class="test-buttons">
          <van-button
            type="primary"
            :loading="testingVision"
            :disabled="!aiStore.config?.ai_enabled || !visionModelIdInput.trim()"
            @click="onTestVision"
          >
            {{ t('aiConfig.testImage') }}
          </van-button>
          <van-button
            type="primary"
            :loading="testingVisionText"
            :disabled="!aiStore.config?.ai_enabled || !visionModelIdInput.trim()"
            @click="onTestVisionText"
          >
            {{ t('aiConfig.testOCR') }}
          </van-button>
        </div>
        <van-button block plain style="margin-top: 10px" @click="showVisionModelPopup = false">
          {{ t('aiConfig.close') }}
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
import * as aiApi from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const authStore = useAuthStore()
const aiStore = useAIStore()

const saving = ref(false)
const testingConnection = ref(false)
const testingThinking = ref(false)
const testingVision = ref(false)
const testingVisionText = ref(false)
const revealingApiKey = ref(false)
const showProviderPicker = ref(false)
const showMainModelPopup = ref(false)
const showVisionModelPopup = ref(false)
const apiKeyInput = ref('')       // actual new key typed by user (empty = keep existing)
const apiKeyDisplay = ref('')     // what the field shows (masked key or new input)
const editingApiKey = ref(false)
const baseUrlInput = ref('')
const modelIdInput = ref('')
const visionModelIdInput = ref('')
const timeoutInput = ref('60')
const selectedProvider = ref<string>('anthropic')
const aiEnabled = ref(false)
const showApiKey = ref(false)

const isOwner = computed(() => authStore.user?.role === 'owner')

const maskedKey = computed(() => aiStore.config?.ai_api_key_masked ?? null)

// Emoji classes based on test status
const textEmojiClass = computed(() => {
  if (aiStore.config?.ai_test_connected === null) return 'untested'
  return aiStore.config?.ai_test_connected ? 'success' : 'failed'
})

const thinkingEmojiClass = computed(() => {
  if (aiStore.config?.ai_test_thinking_success === null) return 'untested'
  return aiStore.config?.ai_test_thinking_success ? 'success' : 'failed'
})

const visionEmojiClass = computed(() => {
  if (aiStore.config?.ai_vision_test_success === null) return 'untested'
  return aiStore.config?.ai_vision_test_success ? 'success' : 'failed'
})

const visionTextEmojiClass = computed(() => {
  if (aiStore.config?.ai_vision_text_test_success === null) return 'untested'
  return aiStore.config?.ai_vision_text_test_success ? 'success' : 'failed'
})

// Status text for popups
const connectionStatusText = computed(() => {
  if (aiStore.config?.ai_test_connected === null) return t('aiConfig.statusUntested')
  return aiStore.config?.ai_test_connected ? t('aiConfig.statusConnectionSuccess') : t('aiConfig.statusConnectionFailed')
})

const thinkingStatusText = computed(() => {
  if (aiStore.config?.ai_test_thinking_success === null) return t('aiConfig.statusUntested')
  return aiStore.config?.ai_test_thinking_success ? t('aiConfig.statusSupportsThinking') : t('aiConfig.statusNoThinkingSupport')
})

const visionStatusText = computed(() => {
  if (aiStore.config?.ai_vision_test_success === null) return t('aiConfig.statusUntested')
  return aiStore.config?.ai_vision_test_success ? t('aiConfig.statusConnectionSuccess') : t('aiConfig.statusConnectionFailed')
})

const visionTextStatusText = computed(() => {
  if (aiStore.config?.ai_vision_text_test_success === null) return t('aiConfig.statusUntested')
  return aiStore.config?.ai_vision_text_test_success ? t('aiConfig.statusOCRAccurate') : t('aiConfig.statusOCRFailed')
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
  { text: t('aiConfig.providerAnthropic'), value: 'anthropic', icon: '💬' },
  { text: t('aiConfig.providerOpenAI'), value: 'openai', icon: '🤖' },
]

const providerLabel = computed(() => {
  if (selectedProvider.value === 'anthropic') return `💬 ${t('aiConfig.providerAnthropic')}`
  if (selectedProvider.value === 'openai') return `🤖 ${t('aiConfig.providerOpenAI')}`
  return t('aiConfig.notSelected')
})

const validationError = computed(() => {
  if (saving.value) return null
  if (aiEnabled.value && !selectedProvider.value) return t('aiConfig.validationSelectProvider')
  if (aiEnabled.value && !apiKeyInput.value.trim() && !aiStore.config?.ai_api_key_masked) return t('aiConfig.validationApiKeyRequired')
  if (aiEnabled.value && selectedProvider.value && !modelIdInput.value.trim()) return t('aiConfig.validationModelIdRequired')
  if (aiEnabled.value) {
    const timeout = parseInt(timeoutInput.value)
    if (isNaN(timeout) || timeout < 10 || timeout > 600) return t('toast.aiTimeoutInvalid')
  }
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
  timeoutInput.value = String(aiStore.config?.ai_timeout_seconds ?? 60)
  apiKeyDisplay.value = aiStore.config?.ai_api_key_masked ?? ''
})

function onApiKeyInput(e: Event) {
  const val = (e.target as HTMLInputElement).value
  apiKeyInput.value = val
  apiKeyDisplay.value = val
  editingApiKey.value = true
}

async function onToggleRevealApiKey() {
  if (showApiKey.value) {
    // Hide: restore masked display
    apiKeyDisplay.value = maskedKey.value ?? ''
    showApiKey.value = false
    return
  }
  if (!aiStore.config?.id) return
  revealingApiKey.value = true
  try {
    const res = await aiApi.revealAIKey(aiStore.config.id)
    apiKeyDisplay.value = res.data.api_key
    showApiKey.value = true
  } catch {
    showToast(t('toast.operationFailed2'))
  } finally {
    revealingApiKey.value = false
  }
}

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
    const payload: { ai_provider?: string; ai_api_key?: string; ai_base_url?: string | null; ai_model_id?: string | null; ai_vision_model_id?: string | null; ai_timeout_seconds?: number } = {}
    payload.ai_provider = selectedProvider.value
    if (apiKeyInput.value.trim()) payload.ai_api_key = apiKeyInput.value.trim()
    payload.ai_base_url = baseUrlInput.value.trim() || null
    payload.ai_model_id = modelIdInput.value.trim() || null
    payload.ai_vision_model_id = visionModelIdInput.value.trim() || null
    payload.ai_timeout_seconds = parseInt(timeoutInput.value) || 60
    await aiStore.updateConfig(payload)
    apiKeyInput.value = ''
    editingApiKey.value = false
    showApiKey.value = false
    apiKeyDisplay.value = aiStore.config?.ai_api_key_masked ?? ''
    showToast(t('toast.aiConfigSaved'))
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : t('toast.saveFailedGeneric')
    showToast(msg.includes('API Key') ? msg : t('toast.saveFailedGeneric'))
  } finally {
    saving.value = false
  }
}

async function onTestConnection() {
  testingConnection.value = true
  try {
    await aiStore.testMainModel()
    await aiStore.fetchConfig()
    showToast(aiStore.config?.ai_test_connected ? t('toast.aiConnectionSuccess') : `❌ ${aiStore.config?.ai_test_message || t('toast.aiConnectionFailed')}`)
  } catch {
    showToast(t('toast.aiTestFailed'))
  } finally {
    testingConnection.value = false
  }
}

async function onTestThinking() {
  testingThinking.value = true
  try {
    await aiStore.testThinking()
    await aiStore.fetchConfig()
    showToast(aiStore.config?.ai_test_thinking_success ? t('toast.aiThinkingSupported') : `❌ ${aiStore.config?.ai_test_thinking_message || t('toast.aiThinkingNotSupported')}`)
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
    showToast(aiStore.config?.ai_vision_test_success ? t('toast.aiVisionConnectionSuccess') : `❌ ${aiStore.config?.ai_vision_test_message || t('toast.aiConnectionFailed')}`)
  } catch {
    showToast(t('toast.aiTestFailed'))
  } finally {
    testingVision.value = false
  }
}

async function onTestVisionText() {
  testingVisionText.value = true
  try {
    await aiStore.testVisionText()
    await aiStore.fetchConfig()
    showToast(aiStore.config?.ai_vision_text_test_success ? t('toast.aiOCRAccurate') : `❌ ${aiStore.config?.ai_vision_text_test_message || t('toast.aiOCRFailed')}`)
  } catch {
    showToast(t('toast.aiTestFailed'))
  } finally {
    testingVisionText.value = false
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
.tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 16px;
  color: var(--text-secondary);
  font-size: 13px;
}

/* Capability emoji buttons */
.capability-btns {
  display: flex;
  gap: 6px;
  cursor: pointer;
  padding: 4px;
}
.capability-emoji {
  font-size: 18px;
  transition: opacity 0.2s;
}
.capability-emoji.success {
  opacity: 1;
}
.capability-emoji.failed {
  opacity: 0.4;
  filter: grayscale(100%);
}
.capability-emoji.untested {
  opacity: 0.6;
}

/* Test popup styles */
.test-details {
  max-height: 80vh;
  overflow-y: auto;
}
.test-section {
  margin-bottom: 16px;
}
.test-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
  padding-left: 16px;
}
.test-buttons {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.test-buttons .van-button {
  flex: 1;
}
</style>