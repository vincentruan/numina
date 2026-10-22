import { ref, readonly, type Ref, type DeepReadonly } from 'vue'
import {
  fetchRecommendationPath,
  type RecommendedTopic,
} from '@/api/learning'

interface UseRecommendationPathReturn {
  allPathTopics: DeepReadonly<Ref<RecommendedTopic[]>>
  isLoading: Ref<boolean>
  error: Ref<string>
  refresh: () => Promise<void>
}

export function useRecommendationPath(): UseRecommendationPathReturn {
  const allPathTopics = ref<RecommendedTopic[]>([])
  const isLoading = ref(false)
  const error = ref('')
  let refreshInFlight: Promise<void> | null = null

  async function refresh() {
    if (refreshInFlight) return refreshInFlight
    refreshInFlight = (async () => {
      isLoading.value = true
      error.value = ''
      try {
        const response = await fetchRecommendationPath(5)
        allPathTopics.value = response.path.topics
      } catch {
        allPathTopics.value = []
        error.value = 'Failed to load recommendations'
      } finally {
        isLoading.value = false
      }
    })()
    try {
      await refreshInFlight
    } finally {
      refreshInFlight = null
    }
  }

  return {
    allPathTopics: readonly(allPathTopics),
    isLoading,
    error,
    refresh,
  }
}
