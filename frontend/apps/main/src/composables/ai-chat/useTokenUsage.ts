import { ref, onUnmounted } from 'vue'
import { getTokenUsage } from '@/api/ai-chat'

/**
 * Polls the thread-level token-usage endpoint during streaming.
 * Used as fallback before per-message usage_metadata arrives from values events.
 */
export function useTokenUsage() {
  const polledUsage = ref({
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
  })
  const loading = ref(false)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  function startPolling(threadId: string | null, intervalMs = 1500) {
    stopPolling()
    if (!threadId || threadId === 'new') return

    // Fetch immediately, then poll
    fetchOnce(threadId)
    pollTimer = setInterval(() => fetchOnce(threadId), intervalMs)
  }

  function stopPolling() {
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function fetchOnce(threadId: string) {
    if (!threadId || threadId === 'new') return
    try {
      loading.value = true
      polledUsage.value = await getTokenUsage(threadId)
    } catch {
      // Silently ignore polling errors
    } finally {
      loading.value = false
    }
  }

  onUnmounted(stopPolling)

  return { polledUsage, loading, startPolling, stopPolling, fetchOnce }
}
