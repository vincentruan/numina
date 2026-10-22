import { ref, computed, type Ref, type ComputedRef } from 'vue'
import {
  fetchRecommendationPath,
  type RecommendedTopic,
} from '@/api/learning'

interface UseRecommendationPathReturn {
  allPathTopics: ComputedRef<RecommendedTopic[]>
  isLoading: Ref<boolean>
  error: Ref<string>
  refresh: () => Promise<void>
}

export function useRecommendationPath(): UseRecommendationPathReturn {
  const allPathTopics = ref<RecommendedTopic[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function refresh() {
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
  }

  return {
    allPathTopics: computed(() => allPathTopics.value),
    isLoading,
    error,
    refresh,
  }
}
