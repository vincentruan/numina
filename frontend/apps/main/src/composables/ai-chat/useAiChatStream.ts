/**
 * DeerFlow useAiChatStream Composable
 *
 * 流式对话状态机，包含 reconnect、dedup、stop/cancel
 *
 * 参考: frontend/src/core/streaming/ 目录
 */

import { ref, computed, onUnmounted, type Ref, type ComputedRef } from 'vue'
import { showToast } from 'vant'
import i18n from '@/i18n'
import { deduplicateMessages } from '@/utils/ai-chat/message-identity'
import type { ChatMessage } from '@/types/ai-chat/message-group'
import type { AgentEvent, NormalizedAiEvent, ProcessStep, Artifact } from '@/types/agent-stream'
import { normalizeAgentEvent } from '@/utils/aiEventNormalizer'
import { sendChatMessageStream } from '@/api/ai'
import { createAgentEventParser } from '@/composables/useAgentEventStream'
import { useUpdateSubtask } from '@/composables/ai-chat/useSubtasks'

// i18n helper
function t(key: string, params?: Record<string, unknown>): string {
  return i18n.global.t(key, params ?? {})
}

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

  // P1-#7: O(1) step lookup caches (avoid .find() on every streaming event)
  // Map<toolCallId, ProcessStep> for tool_running/tool_result/tool_progress
  const toolStepCache = new Map<string, ProcessStep>()
  // Ref to streaming reasoning step for reasoning_delta
  let streamingReasoningStep: ProcessStep | null = null

  // 组件卸载标记（防止 unmount 后的异步操作触发 toast）
  let isUnmounted = false

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
    isUnmounted = true
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
        // P1-#7: Use cached streamingReasoningStep for O(1) lookup
        if (streamingReasoningStep) {
          streamingReasoningStep.content += event.content
        } else {
          const newStep: ProcessStep = {
            type: 'reasoning',
            id: `reasoning-${Date.now()}`,
            content: event.content,
            status: 'streaming',
          }
          streamingReasoningStep = newStep
          processSteps.value.push(newStep)
        }
        break
      }

      case 'reasoning_done': {
        // P1-#7: Use cached streamingReasoningStep for O(1) lookup
        if (streamingReasoningStep) {
          streamingReasoningStep.status = 'done'
          streamingReasoningStep.elapsedMs = event.elapsedMs
          streamingReasoningStep = null // Clear cache when done
        }
        break
      }

      case 'tool_call': {
        const newStep: ProcessStep = {
          type: 'tool_call',
          id: event.toolCallId,
          name: event.name,
          displayName: event.displayName,
          icon: event.icon,
          toolType: event.toolType,
          args: event.args,
          status: 'pending',
        }
        // P1-#7: Add to cache for O(1) lookup
        toolStepCache.set(event.toolCallId, newStep)
        processSteps.value.push(newStep)
        break
      }

      case 'tool_running': {
        // P1-#7: Use cached toolStep for O(1) lookup
        const pendingTool = toolStepCache.get(event.toolCallId)
        if (pendingTool) {
          pendingTool.status = 'running'
        }
        break
      }

      case 'tool_result': {
        // P1-#7: Use cached toolStep for O(1) lookup
        const runningTool = toolStepCache.get(event.toolCallId)
        if (runningTool) {
          runningTool.status = event.success ? 'done' : 'error'
          runningTool.resultSummary = event.summary
          runningTool.error = event.error
          runningTool.elapsedMs = event.elapsedMs
          // Remove from cache when done (completed or error)
          toolStepCache.delete(event.toolCallId)
        }
        break
      }

      case 'tool_progress': {
        // P1-#7: Use cached toolStep for O(1) lookup
        const toolWithProgress = toolStepCache.get(event.toolCallId)
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
        // Wire to global SubtaskCard state (P0 fix: handleSubagentUpdate)
        const { handleSubagentUpdate } = useUpdateSubtask()
        if (event.taskId && event.status) {
          handleSubagentUpdate({
            subagent: {
              taskId: event.taskId,
              status: event.status as 'running' | 'done' | 'failed',
              title: event.title,
              description: event.description,
              result: event.result,
              error: event.error,
            },
          })
        }
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
        // 组件已卸载时不显示 toast（防止 abort 后的异步错误触发 toast）
        if (!isUnmounted) {
          showToast(t('aiChat.errorPrefix', { error: event.message }))
        }
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
    // P1-#7: Clear O(1) lookup caches for new message
    toolStepCache.clear()
    streamingReasoningStep = null
    cleanupAbortController()
    abortController.value = new AbortController()

    // Store reader for cleanup (P0-#2: Stream reader resource leak fix)
    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null

    try {
      // 调用实际 streaming API
      reader = await sendChatMessageStream(
        content,
        false, // deepThink - default
        false, // webSearch - default
        abortController.value!.signal,
        currentSessionId.value || undefined,
        config.agentId,
        'medium', // reasoningEffort
        'ai_chat_page', // source
      )

      // 标记用户消息发送成功
      optimisticUserMessage.sendStatus = 'sent'

      // 创建 NDJSON 解析器
      const parser = createAgentEventParser((event: AgentEvent) => {
        _handleEvent(event)

        // 从 session.start 事件获取 session_id
        if (event.type === 'session.start' && event.session_id) {
          if (!currentSessionId.value) {
            currentSessionId.value = event.session_id
            if (config.onSessionStart) {
              config.onSessionStart(event.session_id)
            }
          }
        }
      })

      // 读取流
      const decoder = new TextDecoder()
      phase.value = 'thinking'

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }

        const chunk = decoder.decode(value, { stream: true })
        parser.push(chunk)
      }

      parser.flush()
      phase.value = 'done'

    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        // 用户主动取消，不显示错误
        optimisticUserMessage.sendStatus = 'sent'
        phase.value = 'interrupted'
        // Cancel the reader on abort to release the stream lock
        if (reader) {
          try {
            await reader.cancel()
          } catch {
            // Ignore cancel errors - stream may already be closed
          }
        }
      } else {
        phase.value = 'error'
        optimisticUserMessage.sendStatus = 'failed'
        // 组件已卸载时不显示 toast（防止 abort race 的异步错误）
        if (!isUnmounted) {
          showToast(t('aiChat.sendFailedError', { error: error instanceof Error ? error.message : t('common.failed') }))
        }
        if (config.onError) {
          config.onError(error instanceof Error ? error : new Error(t('common.failed')))
        }
      }
    } finally {
      // Always release the reader lock to prevent 'ReadableStream is locked' errors
      if (reader) {
        try {
          reader.releaseLock()
        } catch {
          // Ignore release errors - reader may already be released
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
    seenEventIds.clear() // 清理去重 Set，防止 reconnect 时状态污染

    // 标记当前 AI 消息为 interrupted
    const currentAiMsg = messages.value.find(m => m.type === 'ai' && m.phase !== 'done')
    if (currentAiMsg) {
      currentAiMsg.phase = 'interrupted'
    }
  }

  /**
   * 重新连接
   *
   * 注意: 当前后端不支持 Last-Event-ID reconnect，
   * 此函数仅显示提示信息。完整 reconnect 需要后端支持。
   */
  const reconnect = async () => {
    if (!lastEventId.value) {
      showToast(t('aiChat.reconnectNoHistory'))
      return
    }

    // 当前不支持 reconnect，提示用户重新发送
    showToast(t('aiChat.reconnectNotSupported'))
    phase.value = 'done'
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
    // P1-#7: Clear O(1) lookup caches
    toolStepCache.clear()
    streamingReasoningStep = null
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