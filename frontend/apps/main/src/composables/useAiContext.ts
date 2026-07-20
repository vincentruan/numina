import { useRoute, useRouter } from 'vue-router'
import { ref } from 'vue'
import { showFailToast } from 'vant'
import { getAiContext } from '@/api/ai'
import { useI18n } from 'vue-i18n'

type AiSource = 'liability_detail' | 'wish_detail' | 'liability_strategy' | 'wish_advice'

/**
 * A1b: parse route.query.source + route.query.id, fetch the family-scoped entity
 * context from /ai/context (3s timeout), and return a prefilled first-user-turn
 * message. On timeout/404, returns null + toasts (spec §7.3 design-lens). The
 * caller (AIChatBox) sends this as the first message so the AI has full context
 * without the user retyping.
 */
export function useAiContext() {
  const route = useRoute()
  const router = useRouter()
  const { t } = useI18n()
  const contextLoaded = ref(false)
  const contextLabel = ref<string | null>(null) // "已带入：负债详情" removable tag

  async function loadContext(): Promise<string | null> {
    const source = route.query.source as AiSource | undefined
    const id = (route.query.id as string) || '0'
    if (!source) return null

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 3000)
    try {
      const resp = await getAiContext(source, id, controller.signal)
      contextLabel.value = t(`aiChat.context.label.${source}`)
      contextLoaded.value = true
      // Build the first user turn: a framing instruction + the sanitized summary.
      return (
        t('aiChat.context.prefill', { source: t(`aiChat.context.label.${source}`) }) +
        '\n\n' +
        resp.summary
      )
    } catch {
      showFailToast(t('aiChat.context.loadFailed'))
      return null // plain blank chat proceeds
    } finally {
      clearTimeout(timeout)
    }
  }

  function clearContext() {
    contextLabel.value = null
    // Strip the query params so a refresh doesn't re-inject.
    router.replace({ query: {} })
  }

  return { loadContext, clearContext, contextLoaded, contextLabel }
}
