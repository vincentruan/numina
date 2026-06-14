/**
 * DeerFlow useAiChatStream Composable
 *
 * 流式对话状态机，包含 reconnect、dedup、stop/cancel
 *
 * 参考: frontend/src/core/streaming/ 目录
 */

import { ref, computed, onUnmounted, type Ref, type ComputedRef } from 'vue'
import { showToast } from 'vant'
import { deduplicateMessages } from '@/utils/ai-chat/message-identity'
import type { ChatMessage } from '@/types/ai-chat/message-group'
import type { AgentEvent, NormalizedAiEvent, ProcessStep, Artifact } from '@/types/agent-stream'
import { normalizeAgentEvent } from '@/utils/aiEventNormalizer'

/**
 * 流式对话配置
 */
export interface AiChatStreamConfig {
  agentId: string
  sessionId?: string
  threadId?: string
  familyId?: string
  onSessionStart?: (sessionId: string) => void
  onError?: (error: Error) => void
  onComplete?: (result: unknown) => void
}

/**
 * 流式对话状态
 */
export interface AiChatStreamState {
  messages: Ref<ChatMessage[]>
  phase: Ref<'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'>
  processSteps: Ref<ProcessStep[]>
  artifacts: Ref<Artifact[]>
  isStreaming: ComputedRef<boolean>
  currentSessionId: Ref<string | null>
  currentThreadId: Ref<string | null>
  lastEventId: Ref<string | null>
  abortController: Ref<AbortController | null>
}

/**
 * DeerFlow 流式对话 Composable
 *
 * 功能:
 * - 流式消息接收
 * - 事件去重
 * - Stop/Cancel (AbortController)
 * - Reconnect 支持 (Last-Event-ID)
 * - 乐观用户消息
 */
export function useAiChatStream(config: AiChatStreamConfig): AiChatStreamState & {
  sendMessage: (content: string, attachments?: File[]) => Promise<void>
  stop: () => void
  reconnect: () => Promise<void>
  reset: () => void
} {
  // 状态
  const messages = ref<ChatMessage[]>([])
  const phase = ref<'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'>('done')
  const processSteps = ref<ProcessStep[]>([])
  const artifacts = ref<Artifact[]>([])
  const currentSessionId = ref<string | null>(config.sessionId || null)
  const currentThreadId = ref<string | null>(config.threadId || null)
  const lastEventId = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  // 去重 Set
  const seenEventIds = new Set<string>()

  // 计算 isStreaming
  const isStreaming = computed(() => {
    return phase.value !== 'done' && phase.value !== 'error' && phase.value !== 'interrupted'
  })

  // 清理 AbortController
  const cleanupAbortController = () => {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
  }

  // 组件卸载时清理
  onUnmounted(() => {
    cleanupAbortController()
  })

  /**
   * 处理 SSE 事件（可用于 reconnect 场景）
   */
  const _handleEvent = (event: AgentEvent) => {
    // 事件 ID 去重
    if (event.id) {
      if (seenEventIds.has(event.id)) {
        return // 重复事件，跳过
      }
      seenEventIds.add(event.id)
      lastEventId.value = event.id
    }

    // 归一化事件
    const normalized = normalizeAgentEvent(event)

    // 处理归一化事件
    handleNormalizedEvent(normalized)
  }

  /**
   * 处理归一化事件
   */
  const handleNormalizedEvent = (event: NormalizedAiEvent) => {
    switch (event.type) {
      case 'phase_change': {
        phase.value = event.phase
        break
      }

      case 'reasoning_delta': {
        // 更新 reasoning step
        const reasoningStep = processSteps.value.find(
          s => s.type === 'reasoning' && s.status === 'streaming',
        )
        if (reasoningStep) {
          reasoningStep.content += event.content
        } else {
          processSteps.value.push({
            type: 'reasoning',
            id: `reasoning-${Date.now()}`,
            content: event.content,
            status: 'streaming',
          })
        }
        break
      }

      case 'reasoning_done': {
        const streamingReasoning = processSteps.value.find(
          s => s.type === 'reasoning' && s.status === 'streaming',
        )
        if (streamingReasoning) {
          streamingReasoning.status = 'done'
          streamingReasoning.elapsedMs = event.elapsedMs
        }
        break
      }

      case 'tool_call': {
        processSteps.value.push({
          type: 'tool_call',
          id: event.toolCallId,
          name: event.name,
          displayName: event.displayName,
          icon: event.icon,
          toolType: event.toolType,
          args: event.args,
          status: 'pending',
        })
        break
      }

      case 'tool_running': {
        const pendingTool = processSteps.value.find(
          s => s.type === 'tool_call' && s.id === event.toolCallId,
        )
        if (pendingTool) {
          pendingTool.status = 'running'
        }
        break
      }

      case 'tool_result': {
        const runningTool = processSteps.value.find(
          s => s.type === 'tool_call' && s.id === event.toolCallId,
        )
        if (runningTool) {
          runningTool.status = event.success ? 'done' : 'error'
          runningTool.resultSummary = event.summary
          runningTool.error = event.error
          runningTool.elapsedMs = event.elapsedMs
        }
        break
      }

      case 'tool_progress': {
        const toolWithProgress = processSteps.value.find(
          s => s.type === 'tool_call' && s.id === event.toolCallId,
        )
        if (toolWithProgress) {
          toolWithProgress.progressMessage = event.progressMessage
        }
        break
      }

      case 'answer_delta': {
        // 更新最后一条 AI 消息
        const lastAiMsg = messages.value.find(m => m.type === 'ai' && m.phase !== 'done')
        if (lastAiMsg) {
          lastAiMsg.content += event.content
        } else {
          // 创建新的 AI 消息
          messages.value.push({
            id: `ai-${Date.now()}`,
            type: 'ai',
            role: 'assistant',
            content: event.content,
            displayTime: new Date().toLocaleTimeString(),
            phase: 'answering',
          })
        }
        break
      }

      case 'answer_done': {
        const answeringMsg = messages.value.find(m => m.type === 'ai' && m.phase === 'answering')
        if (answeringMsg) {
          answeringMsg.phase = 'done'
        }
        break
      }

      case 'subagent_update': {
        processSteps.value.push({
          type: 'subagent',
          id: event.taskId,
          taskId: event.taskId,
          title: event.title,
          description: event.description,
          status: event.status,
          result: event.result,
          error: event.error,
        })
        break
      }

      case 'artifact': {
        artifacts.value.push({
          id: event.id,
          title: event.title,
          url: event.url,
          path: event.path,
          kind: event.kind,
        })
        break
      }

      case 'state_snapshot': {
        // 恢复完整状态
        if (event.messages) {
          messages.value = deduplicateMessages(event.messages as ChatMessage[])
        }
        if (event.artifacts) {
          artifacts.value = event.artifacts
        }
        break
      }

      case 'error': {
        phase.value = 'error'
        showToast(`❌ ${event.message}`)
        if (config.onError) {
          config.onError(new Error(event.message))
        }
        break
      }

      case 'session_end': {
        phase.value = 'done'
        if (config.onComplete) {
          config.onComplete(undefined)
        }
        break
      }

      case 'plan_update': {
        // 更新计划步骤
        event.steps.forEach((step) => {
          const existing = processSteps.value.find(
            s => s.type === 'progress' && s.id === step.id,
          )
          if (existing) {
            existing.status = step.status as 'running' | 'done' | 'error'
          } else {
            processSteps.value.push({
              type: 'progress',
              id: step.id,
              title: step.label,
              status: step.status as 'running' | 'done' | 'error',
            })
          }
        })
        break
      }
    }
  }

  /**
   * 发送消息
   */
  const sendMessage = async (content: string, _attachments?: File[]) => {
    // 乐观用户消息
    const optimisticUserMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      type: 'human',
      role: 'user',
      content,
      displayTime: new Date().toLocaleTimeString(),
      sendStatus: 'sending',
    }
    messages.value.push(optimisticUserMessage)

    // 重置状态
    phase.value = 'connecting'
    seenEventIds.clear()
    cleanupAbortController()
    abortController.value = new AbortController()

    try {
      // TODO: 调用实际 API
      // const response = await fetch('/api/v1/ai/chat/stream', {
      //   method: 'POST',
      //   headers: {
      //     'Content-Type': 'application/json',
      //     'X-Family-Id': config.familyId || '',
      //     'Last-Event-ID': lastEventId.value || '',
      //   },
      //   body: JSON.stringify({
      //     question: content,
      //     agent_id: config.agentId,
      //     session_id: currentSessionId.value,
      //     thread_id: currentThreadId.value,
      //   }),
      //   signal: abortController.value.signal,
      // })

      // 模拟发送成功
      optimisticUserMessage.sendStatus = 'sent'

      // 处理 session.start 事件
      if (config.onSessionStart && !currentSessionId.value) {
        // TODO: 从实际响应获取 session_id
        const newSessionId = `session-${Date.now()}`
        currentSessionId.value = newSessionId
        config.onSessionStart(newSessionId)
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        // 用户主动取消，不显示错误
        optimisticUserMessage.sendStatus = 'sent'
        phase.value = 'interrupted'
      } else {
        phase.value = 'error'
        optimisticUserMessage.sendStatus = 'failed'
        showToast(`❌ 发送失败: ${error instanceof Error ? error.message : '未知错误'}`)
        if (config.onError) {
          config.onError(error instanceof Error ? error : new Error('未知错误'))
        }
      }
    }
  }

  /**
   * 停止生成
   */
  const stop = () => {
    cleanupAbortController()
    phase.value = 'interrupted'

    // 标记当前 AI 消息为 interrupted
    const currentAiMsg = messages.value.find(m => m.type === 'ai' && m.phase !== 'done')
    if (currentAiMsg) {
      currentAiMsg.phase = 'interrupted'
    }
  }

  /**
   * 重新连接
   */
  const reconnect = async () => {
    if (!lastEventId.value) {
      showToast('⚠️ 无历史事件，无法重新连接')
      return
    }

    phase.value = 'connecting'
    cleanupAbortController()
    abortController.value = new AbortController()

    try {
      // TODO: 调用 reconnect API 带 Last-Event-ID header
      showToast('📡 正在重新连接...')
    } catch (error) {
      phase.value = 'error'
      showToast(`❌ 重连失败: ${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  /**
   * 重置状态
   */
  const reset = () => {
    messages.value = []
    processSteps.value = []
    artifacts.value = []
    phase.value = 'done'
    currentSessionId.value = null
    currentThreadId.value = null
    lastEventId.value = null
    seenEventIds.clear()
    cleanupAbortController()
  }

  return {
    messages,
    phase,
    processSteps,
    artifacts,
    isStreaming,
    currentSessionId,
    currentThreadId,
    lastEventId,
    abortController,
    sendMessage,
    stop,
    reconnect,
    reset,
  }
}