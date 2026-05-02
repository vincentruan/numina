import { ref } from 'vue'

/**
 * Wraps an async operation with loading state and double-submit prevention.
 * Use for save/submit buttons to avoid duplicate requests on slow networks.
 *
 * Usage:
 *   const { loading, execute } = useRequest()
 *   await execute(() => updateSettings({ theme: 'dark' }))
 */
export function useRequest() {
  const loading = ref(false)

  async function execute<T>(fn: () => Promise<T>): Promise<T | undefined> {
    if (loading.value) return undefined
    loading.value = true
    try {
      return await fn()
    } finally {
      loading.value = false
    }
  }

  return { loading, execute }
}
