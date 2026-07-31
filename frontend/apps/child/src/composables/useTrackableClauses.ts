import { ref, computed } from 'vue'
import { getTrackableClauses } from '@/api/manifesto'

export function useTrackableClauses() {
  const trackableCount = ref(0)
  const hasTrackable = computed(() => trackableCount.value > 0)
  const loading = ref(true)

  async function init() {
    try {
      const res = await getTrackableClauses()
      trackableCount.value = res.data.trackable_clause_indices?.length ?? 0
    } catch {
      trackableCount.value = 0
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    loading.value = true
    await init()
  }

  return { trackableCount, hasTrackable, loading, init, refresh }
}
