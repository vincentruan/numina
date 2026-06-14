/**
 * DeerFlow Suggestions 状态管理 Composable
 *
 * 参考: frontend/src/components/workspace/input-box.tsx followups 逻辑
 *
 * 职责:
 * - 管理 followups 状态
 * - 监听 streaming 结束触发 suggestions 请求
 * - 处理点击建议逻辑（空输入/非空输入）
 */

import { ref, watch, computed, type Ref } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import http from '@/api'
import { useFamilyStore } from '@/stores/family'

interface SuggestionMessage {
  role: 'user' | 'assistant'
  content: string
}

interface SuggestionsResponse {
  suggestions: string[]
}

/**
 * Suggestions Composable
 *
 * Note: State is declared inside the function to ensure each component
 * instance gets its own fresh state (not shared across instances).
 */
export function useSuggestions(
  messages: Ref<Array<{ type: string; id?: string; content?: string }>>,
  phase: Ref<string>,
  sessionId: Ref<string | null>,
  modelName: Ref<string>,
  inputValue: Ref<string>,
) {
  const { t } = useI18n()
  const familyStore = useFamilyStore()
  const familyId = computed(() => familyStore.currentFamily?.id)

  // State (inside function for per-instance isolation)
  const followups = ref<string[]>([])
  const followupsHidden = ref(false)
  const followupsLoading = ref(false)
  const lastGeneratedForAiId = ref<string | null>(null)

  // Confirm dialog state
  const confirmOpen = ref(false)
  const pendingSuggestion = ref<string | null>(null)

  // Track streaming state for end detection
  const wasStreaming = ref(false)

  watch(
    phase,
    (currentPhase) => {
      const streaming = currentPhase !== 'done' && currentPhase !== 'error'
      const wasStreamingValue = wasStreaming.value
      wasStreaming.value = streaming

      // 只在 streaming 结束时触发
      if (!wasStreamingValue || streaming) {
        return
      }

      // 找到最后一条 AI 消息
      const reversed = [...messages.value].reverse()
      const lastAi = reversed.find((m) => m.type === 'ai' || m.type === 'assistant')
      const lastAiId = lastAi?.id ?? null

      // 防止重复生成
      if (!lastAiId || lastAiId === lastGeneratedForAiId.value) {
        return
      }
      lastGeneratedForAiId.value = lastAiId

      // 取最近 6 条 human/ai 消息
      const recent: SuggestionMessage[] = messages.value
        .filter((m) => m.type === 'human' || m.type === 'ai' || m.type === 'assistant')
        .map((m) => ({
          role: m.type === 'human' || m.type === 'user' ? 'user' : 'assistant',
          content: m.content || '',
        }))
        .filter((m) => m.content.trim().length > 0)
        .slice(-6)

      if (recent.length === 0) {
        return
      }

      // 调用 suggestions API
      requestSuggestions(recent, sessionId.value, modelName.value, familyId.value)
    },
  )

  /**
   * 请求 suggestions API
   */
  async function requestSuggestions(
    recent: SuggestionMessage[],
    threadId: string | null,
    modelName: string,
    familyId: string | undefined,
  ) {
    if (!threadId || !familyId) {
      return
    }

    followupsHidden.value = false
    followupsLoading.value = true
    followups.value = []

    try {
      const response = await http.post<SuggestionsResponse>(
        `/ai/sessions/${threadId}/suggestions`,
        {
          messages: recent,
          n: 3,
          model_name: modelName,
        },
        {
          headers: { 'X-Family-Id': familyId },
        },
      )

      const suggestions = (response.data.suggestions ?? [])
        .map((s) => s.trim())
        .filter((s) => s.length > 0)
        .slice(0, 5)

      followups.value = suggestions
    } catch (error) {
      // 租户额度不足时显示提示（后端返回中文错误信息）
      if (
        error instanceof Error &&
        (error.message.includes('quota') ||
          error.message.includes('额度') ||
          error.message.includes('配额'))
      ) {
        showToast(`⚠️ ${t('aiChat.tenantQuotaExceeded')}`)
      } else {
        // 静默失败，不影响主流程
        followups.value = []
      }
    } finally {
      followupsLoading.value = false
    }
  }

  /**
   * 处理点击建议
   */
  function handleSuggestionClick(suggestion: string) {
    const current = inputValue.value.trim()

    if (current) {
      // 输入非空：弹出确认对话框
      pendingSuggestion.value = suggestion
      confirmOpen.value = true
    } else {
      // 输入为空：直接填入并发送
      inputValue.value = suggestion
      followupsHidden.value = true
      // 触发发送（由父组件处理）
    }
  }

  /**
   * 追加并发送
   */
  function confirmAppendAndSend() {
    if (!pendingSuggestion.value) return

    const current = inputValue.value.trim()
    const next = current ? `${current}\n${pendingSuggestion.value}` : pendingSuggestion.value

    inputValue.value = next
    followupsHidden.value = true
    confirmOpen.value = false
    pendingSuggestion.value = null
    // 触发发送（由父组件处理）
  }

  /**
   * 替换并发送
   */
  function confirmReplaceAndSend() {
    if (!pendingSuggestion.value) return

    inputValue.value = pendingSuggestion.value
    followupsHidden.value = true
    confirmOpen.value = false
    pendingSuggestion.value = null
    // 触发发送（由父组件处理）
  }

  /**
   * 隐藏 suggestions
   */
  function hideSuggestions() {
    followupsHidden.value = true
  }

  /**
   * 重置状态（发送新消息时）
   */
  function resetSuggestions() {
    followups.value = []
    followupsHidden.value = false
    followupsLoading.value = false
  }

  return {
    followups,
    followupsHidden,
    followupsLoading,
    confirmOpen,
    pendingSuggestion,
    handleSuggestionClick,
    confirmAppendAndSend,
    confirmReplaceAndSend,
    hideSuggestions,
    resetSuggestions,
  }
}