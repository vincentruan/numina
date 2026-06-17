<script setup lang="ts">
/**
 * DeerFlow InputBox Vue 实现
 *
 * 参考: frontend/src/components/workspace/input-box.tsx
 *
 * 功能:
 * - Vant textarea 自动增高
 * - 空内容禁止发送
 * - running 时发送按钮变停止按钮
 * - 支持欢迎态居中输入
 * - 支持聊天态底部吸附输入
 * - DeerFlow 4-mode 选择器集成
 * - 模型选择弹出层集成
 */
import { ref, computed, watch } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import ModeSelector from './ModeSelector.vue'
import ModelSelectorPopup from './ModelSelectorPopup.vue'
import WelcomeExamples from './WelcomeExamples.vue'
import { useTenantAiResources, INPUT_MODE_CONFIGS, getResolvedMode } from '@/composables/ai-chat/useTenantAiResources'
import type { InputMode, SubmitPayload, InputContext } from '@/types/ai-chat/input-mode'

const { t } = useI18n()

// Props
const props = defineProps<{
  status: 'ready' | 'streaming' | 'submitted' | 'error' | 'reconnecting'
  isWelcomeMode?: boolean  // 欢迎态 vs 聊天态
  threadId?: string
  initialMode?: InputMode
  initialModelName?: string
}>()

const emit = defineEmits<{
  submit: [payload: SubmitPayload]
  stop: []
  contextChange: [context: InputContext]
  agentChange: [agentId: string]
  action: [type: 'file' | 'image' | 'camera']
}>()

// 租户资源
const {
  models,
  tenantConfig: _tenantConfig,
  supportsThinking: _supportsThinking,
  supportsSubagent,
  loading: resourcesLoading,
} = useTenantAiResources()

// State
const inputValue = ref('')
const focused = ref(false)
const modelDialogOpen = ref(false)

// 当前选中的模型和模式
const selectedModel = computed(() =>
  models.value.find(m => m.name === context.value.model_name) ?? models.value[0],
)

const context = ref<InputContext>({
  model_name: props.initialModelName ?? '',
  mode: props.initialMode ?? 'pro',
  reasoning_effort: 'medium',
})

// Agent selection
const showAgentMenu = ref(false)
const selectedAgentId = ref('numina') // Defaults to numina agent
const agentOptions = [
  { text: 'Numina Agent', value: 'numina' },
  { text: 'Open QA', value: 'chat' }
]

function onSelectAgent(action: { value: string }) {
  selectedAgentId.value = action.value
  emit('agentChange', action.value)
}

// Attachment selection
const showAttachmentMenu = ref(false)
const attachmentActions = [
  { text: 'File', value: 'file', icon: 'description' },
  { text: 'Image', value: 'image', icon: 'photo' },
  { text: 'Camera', value: 'camera', icon: 'photograph' }
]
function onSelectAttachment(action: any) {
  emit('action', action.value)
}

// 模型能力检查
const currentModelSupportsThinking = computed(() =>
  selectedModel.value?.supports_thinking ?? false,
)

// 自动降级模式（DeerFlow pattern）
watch(currentModelSupportsThinking, (supports) => {
  const resolved = getResolvedMode(context.value.mode, supports, supportsSubagent.value)
  if (resolved !== context.value.mode) {
    showToast(t('aiChat.tenantModelFallback'))
    context.value.mode = resolved
    emitContextChange()
  }
})

// Ultra 模式禁用检查
const isUltraDisabled = computed(() =>
  !supportsSubagent.value,
)

// 计算最终 API 参数
const finalPayload = computed(() => {
  const config = INPUT_MODE_CONFIGS[context.value.mode]
  return {
    thinking_enabled: config.thinking_enabled,
    is_plan_mode: config.is_plan_mode,
    subagent_enabled: config.subagent_enabled,
    reasoning_effort: config.reasoning_effort,
  }
})

// Methods
function adjustHeight(el: HTMLTextAreaElement) {
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function onSubmit() {
  if (props.status === 'streaming') {
    emit('stop')
    return
  }

  const text = inputValue.value.trim()
  if (!text) return

  emit('submit', {
    text,
    model_name: context.value.model_name,
    mode: context.value.mode,
    ...finalPayload.value,
    thread_id: props.threadId,
  })

  inputValue.value = ''
}

function onModeSelect(mode: InputMode) {
  // Ultra 模式租户限制检查
  if (mode === 'ultra' && !supportsSubagent.value) {
    showToast(t('aiChat.tenantUltraDisabled'))
    return
  }
  context.value.mode = mode
  context.value.reasoning_effort = INPUT_MODE_CONFIGS[mode].reasoning_effort
  emitContextChange()
}

function onModelSelect(modelName: string) {
  const model = models.value.find(m => m.name === modelName)
  if (!model) return

  context.value.model_name = modelName
  // 模型切换时重新解析模式
  const resolved = getResolvedMode(context.value.mode, model.supports_thinking ?? false, supportsSubagent.value)
  if (resolved !== context.value.mode) {
    showToast(t('aiChat.tenantModelFallback'))
    context.value.mode = resolved
  }
  modelDialogOpen.value = false
  emitContextChange()
}

function emitContextChange() {
  emit('contextChange', {
    ...context.value,
    reasoning_effort: INPUT_MODE_CONFIGS[context.value.mode].reasoning_effort,
  })
}

// DeerFlow WelcomeExamples handlers
function handleWelcomeExampleSelect(prompt: string) {
  inputValue.value = prompt
  // 自动发送（DeerFlow pattern: setTimeout → requestFormSubmit）
  setTimeout(() => onSubmit(), 0)
}

function handleSurpriseMe() {
  // 随机选择一个预设问题（DeerFlow pattern: SparklesIcon + surpriseMe）
  const surprisePrompts = [
    t('aiChat.welcomeExampleAnalyzePrompt'),
    t('aiChat.welcomeExamplePlanPrompt'),
    t('aiChat.welcomeExampleLearnPrompt'),
    t('aiChat.welcomeExampleOptimizePrompt'),
  ]
  const randomPrompt = surprisePrompts[Math.floor(Math.random() * surprisePrompts.length)]
  inputValue.value = randomPrompt
  setTimeout(() => onSubmit(), 0)
}

// 初始化默认模型
watch(models, (newModels) => {
  if (newModels.length > 0 && !context.value.model_name) {
    const defaultModel = newModels.find(m => m.is_default) ?? newModels[0]
    context.value.model_name = defaultModel.name
    // 根据模型能力设置初始模式
    const resolved = getResolvedMode(context.value.mode, defaultModel.supports_thinking ?? false, supportsSubagent.value)
    if (resolved !== context.value.mode) {
      context.value.mode = resolved
    }
    emitContextChange()
  }
}, { immediate: true })
</script>

<template>
  <div
    class="input-box"
    :class="[
      status,
      isWelcomeMode ? 'welcome-mode' : 'chat-mode',
      { focused },
    ]"
  >
    <!-- 欢迎态 Hero 区域 (DeerFlow pattern) -->
    <div v-if="isWelcomeMode" class="welcome-hero">
      <h2 class="hero-title">{{ selectedAgentId === 'numina' ? t('aiChat.heroTitleChat') : 'Open QA' }}</h2>
      <p class="hero-subtitle">{{ selectedAgentId === 'numina' ? t('aiChat.heroSubtitleChat') : 'A general purpose chat assistant.' }}</p>
    </div>

    <!-- 欢迎态示例按钮 (DeerFlow SuggestionList pattern) -->
    <WelcomeExamples
      v-if="isWelcomeMode"
      :agent-id="selectedAgentId"
      @select="handleWelcomeExampleSelect"
      @surprise="handleSurpriseMe"
    />

    <!-- 输入区域 -->
    <div class="input-row">
      <!-- Agent 选择按钮 -->
      <van-popover v-model:show="showAgentMenu" placement="top-start" :actions="agentOptions" @select="onSelectAgent">
        <template #reference>
          <button class="control-btn agent-btn" :disabled="!isWelcomeMode">
            <span class="agent-name">{{ agentOptions.find(a => a.value === selectedAgentId)?.text }}</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dropdown-icon" v-if="isWelcomeMode">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </template>
      </van-popover>

      <!-- 模型选择按钮 -->
      <button
        class="control-btn model-btn"
        :disabled="resourcesLoading"
        @click="modelDialogOpen = true"
      >
        <span class="model-name">{{ selectedModel?.display_name || t('aiChat.selectModel') }}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dropdown-icon">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>

      <!-- 附件选择按钮 -->
      <van-popover v-model:show="showAttachmentMenu" placement="top-start" :actions="attachmentActions" @select="onSelectAttachment">
        <template #reference>
          <button class="control-btn attach-btn">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
        </template>
      </van-popover>

      <!-- Textarea -->
      <textarea
        v-model="inputValue"
        class="input-textarea"
        :placeholder="isWelcomeMode ? t('aiChat.inputPlaceholder') : t('aiChat.continuePlaceholder')"
        :disabled="status === 'submitted'"
        rows="1"
        @input="adjustHeight($event.target as HTMLTextAreaElement)"
        @keydown.enter.ctrl="onSubmit"
        @focus="focused = true"
        @blur="focused = false"
      />

      <!-- 模式选择器 -->
      <ModeSelector
        :current-mode="context.mode"
        :supports-thinking="currentModelSupportsThinking"
        :ultra-disabled="isUltraDisabled"
        @select="onModeSelect"
      />

      <!-- 发送/停止按钮 -->
      <button
        class="submit-btn"
        :class="{ stop: status === 'streaming' }"
        :disabled="status === 'submitted' || (status !== 'streaming' && !inputValue.trim())"
        @click="onSubmit"
      >
        <!-- 发送图标 -->
        <svg v-if="status === 'ready'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>
        </svg>
        <!-- 加载图标 -->
        <svg v-if="status === 'submitted'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="animate-spin">
          <line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.17" y2="7.17"/><line x1="16.83" y1="16.83" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.17" y2="16.83"/><line x1="16.83" y1="7.17" x2="19.07" y2="4.93"/>
        </svg>
        <!-- 停止图标 (红色方块) -->
        <svg v-if="status === 'streaming'" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="2"/>
        </svg>
        <!-- 重连图标 (旋转) -->
        <svg v-if="status === 'reconnecting'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="animate-spin">
          <polyline points="1 4 1 10 7 10"/>
          <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
        </svg>
        <!-- 错误图标 -->
        <svg v-if="status === 'error'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>

    <!-- 底部背景层 (聊天态，DeerFlow pattern) -->
    <div v-if="!isWelcomeMode" class="chat-bg-layer" />

    <!-- 模型选择弹出层 -->
    <ModelSelectorPopup
      v-model:show="modelDialogOpen"
      :models="models"
      :current-model="context.model_name"
      @select="onModelSelect"
    />
  </div>
</template>

<style scoped>
.input-box {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  background: var(--card-bg);
  border-radius: 16px;
  transition: all 0.2s ease;
}

/* 欢迎态: 居中布局 */
.input-box.welcome-mode {
  align-items: center;
  justify-content: center;
  min-height: 200px;
  margin: 0 auto;
  max-width: 90%;
}

/* 聊天态: 底部吸附 */
.input-box.chat-mode {
  position: sticky;
  bottom: 0;
  border-radius: 0;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}

.welcome-hero {
  text-align: center;
  margin-bottom: 16px;
}

.hero-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.hero-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.input-textarea {
  flex: 1;
  min-height: 36px;
  max-height: 120px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  font-size: 16px;
  color: var(--text-primary);
  resize: none;
  outline: none;
  transition: border-color 0.2s;
}

.input-textarea:focus {
  border-color: var(--van-primary-color);
}

.control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  min-height: 44px; /* Touch target - DeerFlow pattern */
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.model-btn {
  min-width: 80px;
  min-height: 44px; /* Touch target - DeerFlow pattern */
}

.model-name {
  font-weight: 500;
}

.submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  min-height: 44px; /* Touch target - DeerFlow pattern */
  min-width: 44px;
  border-radius: 50%;
  background: var(--van-primary-color);
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

/* 停止按钮: 红色方块 (DeerFlow pattern) */
.submit-btn.stop {
  background: #ef4444;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-bg-layer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -16px;
  height: 16px;
  background: var(--bg-primary);
  z-index: -1;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 375px 响应式 */
@media (max-width: 375px) {
  .input-box {
    padding: 8px 12px;
    padding-bottom: calc(8px + env(safe-area-inset-bottom));
  }

  .input-box.welcome-mode {
    min-height: 160px;
    max-width: 95%;
  }

  .input-textarea {
    font-size: 14px;
    padding: 6px 10px;
  }

  .control-btn {
    padding: 4px 8px;
    font-size: 11px;
  }

  .model-btn {
    min-width: 60px;
  }

  .submit-btn {
    width: 32px;
    height: 32px;
  }

  .hero-title {
    font-size: 18px;
  }

  .hero-subtitle {
    font-size: 12px;
  }
}
</style>