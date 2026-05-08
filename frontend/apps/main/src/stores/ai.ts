import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as aiApi from '@/api/ai'
import type { AIConfig } from '@/api/ai'

export const useAIStore = defineStore('ai', () => {
  const config = ref<AIConfig | null>(null)
  const loading = ref(false)
  const draftQuery = ref('')
  const deepThinkEnabled = ref(false)
  const webSearchEnabled = ref(false)

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

  async function testMainModel() {
    return aiApi.testMainModelOnly()
  }

  async function testThinking() {
    return aiApi.testThinkingOnly()
  }

  async function testVisionModel() {
    return aiApi.testVisionModelOnly()
  }

  async function testVisionImage() {
    return aiApi.testVisionModelOnly()
  }

  async function testVisionText() {
    return aiApi.testVisionTextOCR()
  }

  return {
    config,
    loading,
    draftQuery,
    deepThinkEnabled,
    webSearchEnabled,
    aiEnabled,
    aiProvider,
    fetchConfig,
    updateConfig,
    testConnection,
    testMainModel,
    testThinking,
    testVisionModel,
    testVisionImage,
    testVisionText,
  }
})
