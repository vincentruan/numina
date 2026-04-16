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
          placeholder="留空使用默认端点（可选）"
          clearable
          :disabled="saving"
        />
        <van-field
          v-model="modelIdInput"
          label="模型 ID"
          placeholder="留空使用 provider 默认模型（可选）"
          clearable
          :disabled="saving"
        />
        <van-field
          v-model="visionModelIdInput"
          label="图像模型 ID"
          placeholder="留空使用主模型（可选）"
          clearable
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
          保存配置
        </van-button>
        <div
          v-if="validationError"
          class="tip"
        >
          <van-icon name="info-o" />
          <span>{{ validationError }}</span>
        </div>
        <van-button
          block
          plain
          class="test-btn"
          :loading="testing"
          :disabled="!aiStore.config?.ai_enabled"
          @click="onTest"
        >
          测试连接
        </van-button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import { useAIStore } from '@/stores/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const authStore = useAuthStore()
const aiStore = useAIStore()

const saving = ref(false)
const testing = ref(false)
const showProviderPicker = ref(false)
const apiKeyInput = ref('')
const baseUrlInput = ref('')
const modelIdInput = ref('')
const visionModelIdInput = ref('')
const selectedProvider = ref<string>('anthropic')
const aiEnabled = ref(false)
const showApiKey = ref(false)

const isOwner = computed(() => authStore.user?.role === 'owner')

const maskedKey = computed(() => aiStore.config?.ai_api_key_masked ?? null)

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
    showToast(val ? 'AI 助手已启用' : 'AI 助手已关闭')
  } catch {
    aiEnabled.value = !val
    showToast('操作失败，请重试')
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
    showToast('配置已保存')
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '保存失败，请重试'
    showToast(msg.includes('API Key') ? msg : '保存失败，请重试')
  } finally {
    saving.value = false
  }
}

async function onTest() {
  testing.value = true
  try {
    const result = await aiStore.testConnection()
    if (result.data.success) {
      showToast(`连接成功（${result.data.latency_ms ?? '-'}ms）`)
    } else {
      showToast(`连接失败：${result.data.message}`)
    }
  } catch {
    showToast('测试失败，请检查配置')
  } finally {
    testing.value = false
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
