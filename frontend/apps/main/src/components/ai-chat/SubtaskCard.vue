<script setup lang="ts">
/**
 * DeerFlow SubtaskCard 组件
 *
 * 参考: frontend/src/components/workspace/messages/subtask-card.tsx
 *
 * 功能:
 * - 状态图标：completed=CheckCircle, failed=XCircle, in_progress=Loader2(spin)
 * - Shimmer 效果用于 in_progress 描述
 * - ShineBorder 动画边框用于 in_progress 状态
 * - 默认折叠，in_progress 时展开
 * - 显示 prompt、最新消息、结果/错误
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSubtask } from '@/composables/ai-chat/useSubtasks'
import MarkdownContent from './MarkdownContent.vue'
import ShimmerText from './ShimmerText.vue'
import ShineBorder from './ShineBorder.vue'
import FlipDisplay from './FlipDisplay.vue'
import IIcon from '@/components/IIcon.vue'
import { explainLastToolCallKey } from '@/utils/ai-chat/tool-explainer'
import type { AIMessage } from '@/types/agent-stream'

const { t } = useI18n()

const props = defineProps<{
  taskId: string
  isLoading?: boolean
}>()

const task = useSubtask(props.taskId)

// 默认折叠，in_progress 时自动展开
const collapsed = ref(true)
watch(
  task,
  (newTask) => {
    if (newTask?.status === 'in_progress') {
      collapsed.value = false
    }
  },
  { immediate: true },
)

// 状态图标
const statusIcon = computed(() => {
  if (!task.value) return 'loader'
  switch (task.value.status) {
    case 'completed':
      return 'check-circle'
    case 'failed':
    case 'cancelled':
    case 'timed_out':
      return 'x-circle'
    default:
      return 'loader'
  }
})

// 状态标签
const statusLabel = computed(() => {
  if (!task.value) return t('aiChat.subtaskRunning')
  switch (task.value.status) {
    case 'completed':
      return t('aiChat.subtaskCompleted')
    case 'failed':
      return t('aiChat.subtaskFailed')
    case 'cancelled':
      return t('aiChat.subtaskCancelled')
    case 'timed_out':
      return t('aiChat.subtaskTimedOut')
    default:
      return t('aiChat.subtaskRunning')
  }
})

// 当前动作说明（从 latestMessage 提取）
const currentAction = computed(() => {
  if (!task.value?.latestMessage) return null
  const result = explainLastToolCallKey(task.value.latestMessage as AIMessage)
  if (!result) return null
  return t(result.key, result.params)
})

// 是否显示动画边框
const showShineBorder = computed(
  () => task.value?.status === 'in_progress' && props.isLoading,
)
</script>

<template>
  <div
    v-if="task"
    class="subtask-card"
    :class="[task.status, { collapsed }]"
  >
    <!-- ShineBorder 动画（in_progress 时） -->
    <ShineBorder v-if="showShineBorder" :colors="['#A07CFE', '#FE8FB5', '#FFBE7B']" />

    <!-- 卡片头部 -->
    <div class="subtask-header" @click="collapsed = !collapsed">
      <!-- 任务图标 -->
      <IIcon icon="clipboard-list" class="task-icon" />

      <!-- 任务描述 -->
      <div class="task-description">
        <ShimmerText
          v-if="task.status === 'in_progress' && props.isLoading"
          :text="task.description || t('aiChat.subtaskExecuting')"
          :duration="3"
          :spread="3"
        />
        <span v-else class="description-text">{{ task.description }}</span>
      </div>

      <!-- 折叠时显示的状态摘要 -->
      <div v-if="collapsed" class="status-summary">
        <IIcon
          :icon="statusIcon"
          :class="['status-icon', { animate: task.status === 'in_progress' }, `status-${task.status}`]"
        />
        <span :class="['status-text', `status-${task.status}`]">
          {{ currentAction || statusLabel }}
        </span>
      </div>

      <!-- 展开/折叠图标 -->
      <IIcon icon="chevron-up" :class="['collapse-icon', { rotated: collapsed }]" />
    </div>

    <!-- 卡片内容（展开时） -->
    <div v-if="!collapsed" class="subtask-content">
      <!-- Prompt -->
      <div v-if="task.prompt" class="prompt-section">
        <MarkdownContent :content="task.prompt" :is-loading="false" />
      </div>

      <!-- 运行中：当前动作 -->
      <FlipDisplay v-if="task.status === 'in_progress' && currentAction" :unique-key="currentAction">
        <div class="action-section">
          <IIcon icon="loader" class="action-icon animate-spin" />
          <span class="action-text">{{ currentAction }}</span>
        </div>
      </FlipDisplay>

      <!-- 完成：结果 -->
      <div v-if="task.status === 'completed'" class="result-section">
        <IIcon icon="check-circle" class="result-icon status-completed" />
        <span class="result-label">{{ t('aiChat.subtaskComplete') }}</span>
        <MarkdownContent
          v-if="task.result"
          :content="task.result"
          :is-loading="false"
          class="result-content"
        />
      </div>

      <!-- 失败：错误信息 -->
      <div v-if="task.status === 'failed' || task.status === 'cancelled' || task.status === 'timed_out'" class="error-section">
        <IIcon icon="x-circle" class="error-icon status-failed" />
        <span class="error-label">{{ statusLabel }}</span>
        <div v-if="task.error" class="error-message">{{ task.error }}</div>
      </div>

      <!-- Token 使用 -->
      <div v-if="task.usage" class="usage-section">
        <span class="usage-label">Token: {{ task.usage.total_tokens }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.subtask-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: var(--card-bg);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.subtask-card.in_progress {
  border-color: var(--van-primary-color);
}

.subtask-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  cursor: pointer;
}

.task-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
}

.task-description {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
}

.description-text {
  font-weight: 500;
}

.status-summary {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.status-icon {
  width: 14px;
  height: 14px;
}

.status-icon.animate {
  animation: spin 1s linear infinite;
}

/* Status color classes for dark mode WCAG AA compliance */
.status-completed {
  color: var(--color-success, #22c55e);
}

.status-failed,
.status-cancelled,
.status-timed_out {
  color: var(--color-error, #ef4444);
}

.status-in_progress {
  color: var(--van-primary-color);
}

.status-text {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.collapse-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.collapse-icon.rotated {
  transform: rotate(180deg);
}

.subtask-content {
  padding: 8px 12px;
  border-top: 1px solid var(--border-color);
}

.prompt-section {
  padding-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.action-section {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}

.action-icon {
  width: 14px;
  height: 14px;
  color: var(--van-primary-color);
}

.action-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-icon {
  width: 16px;
  height: 16px;
}

.result-label {
  font-size: 13px;
  color: var(--color-success, #22c55e);
}

.result-content {
  padding-top: 8px;
}

.error-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.error-icon {
  width: 16px;
  height: 16px;
}

.error-label {
  font-size: 13px;
  color: var(--color-error, #ef4444);
}

.error-message {
  padding: 8px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-error, #ef4444);
}

.usage-section {
  padding-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 375px */
@media (max-width: 375px) {
  .subtask-card {
    padding: 6px;
  }

  .task-description {
    font-size: 12px;
  }

  .status-text {
    max-width: 120px;
  }

  .prompt-section,
  .action-text,
  .result-label,
  .error-label {
    font-size: 12px;
  }
}
</style>