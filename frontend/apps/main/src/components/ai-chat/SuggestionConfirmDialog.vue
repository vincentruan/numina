<script setup lang="ts">
/**
 * DeerFlow Suggestion Confirm Dialog
 *
 * 参考: frontend/src/components/workspace/input-box.tsx 第869-889行
 *
 * 功能:
 * - 当输入框已有内容时，点击追问建议弹出此对话框
 * - 三个选项："追加并发送"、"替换并发送"、"取消"
 *
 * DeerFlow i18n keys:
 * - t.inputBox.followupConfirmTitle: "追加还是替换？"
 * - t.inputBox.followupConfirmDescription: "当前输入框已有内容，请选择处理方式"
 * - t.inputBox.followupConfirmAppend: "追加并发送"
 * - t.inputBox.followupConfirmReplace: "替换并发送"
 * - t.common.cancel: "取消"
 */
import { computed } from 'vue'
import { Dialog, Button } from 'vant'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
  currentInput: string
  suggestion: string
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  append: []
  replace: []
}>()

// 预览文本（追加模式）
const appendPreview = computed(() =>
  props.currentInput.trim()
    ? `${props.currentInput.trim()}\n${props.suggestion}`
    : props.suggestion
)

// 预览文本（替换模式）
const replacePreview = computed(() => props.suggestion)

function handleAppend() {
  emit('append')
  emit('update:show', false)
}

function handleReplace() {
  emit('replace')
  emit('update:show', false)
}

function handleCancel() {
  emit('update:show', false)
}
</script>

<template>
  <Dialog
    :show="show"
    :title="t('aiChat.followupConfirmTitle')"
    :show-confirm-button="false"
    close-on-click-overlay
    teleport="body"
    @update:show="emit('update:show', $event)"
  >
    <div class="confirm-content">
      <!-- 说明 -->
      <p class="confirm-description">{{ t('aiChat.followupConfirmDescription') }}</p>

      <!-- 当前输入 -->
      <div class="preview-section">
        <span class="section-label">{{ t('aiChat.currentInputLabel') }}</span>
        <div class="preview-text current">{{ currentInput }}</div>
      </div>

      <!-- 建议内容 -->
      <div class="preview-section">
        <span class="section-label">{{ t('aiChat.suggestionLabel') }}</span>
        <div class="preview-text suggestion">{{ suggestion }}</div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons">
        <Button type="default" block plain @click="handleCancel">
          {{ t('common.cancel') }}
        </Button>
        <Button type="default" block @click="handleAppend">
          {{ t('aiChat.appendAndSend') }}
        </Button>
        <Button type="primary" block @click="handleReplace">
          {{ t('aiChat.replaceAndSend') }}
        </Button>
      </div>
    </div>
  </Dialog>
</template>

<style scoped>
.confirm-content {
  padding: 8px 0;
}

.confirm-description {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.preview-section {
  margin-bottom: 12px;
}

.section-label {
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
  margin-bottom: 4px;
}

.preview-text {
  padding: 8px 12px;
  background: var(--card-bg);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-word;
  white-space: pre-wrap;
}

.preview-text.current {
  border: 1px solid var(--border);
}

.preview-text.suggestion {
  border: 1px solid var(--van-primary-color);
  background: rgba(99, 102, 241, 0.05);
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

/* 375px */
@media (max-width: 375px) {
  .confirm-description,
  .preview-text {
    font-size: 13px;
  }

  .section-label {
    font-size: 11px;
  }
}
</style>