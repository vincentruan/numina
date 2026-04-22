import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as aiApi from '@/api/ai'
import type { AIConfig } from '@/api/ai'

export const useAIStore = defineStore('ai', () => {
  const config = ref<AIConfig | null>(null)
  const loading = ref(false)
  const draftQuery = ref('')

  const aiEnabled = computed(() => config.value?.ai_enabled ?? false)
  const aiProvider = computed(() => config.value?.ai_provider ?? null)

  async function fetchConfig() {
    loading.value = true
    try {
      const res = await aiApi.getAIConfig()
      config.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(data: aiApi.AIConfigUpdate) {
    const res = await aiApi.updateAIConfig(data)
    config.value = res.data
    return res.data
  }

  async function testConnection() {
    return aiApi.testAIConfig()
  }

  return {
    config,
    loading,
    draftQuery,
    aiEnabled,
    aiProvider,
    fetchConfig,
    updateConfig,
    testConnection,
  }
})
