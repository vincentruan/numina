import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getAICapabilities } from '@/api/ai'
import type { AICapability } from '@/api/ai'

export const useCapabilityStore = defineStore('capability', () => {
  const capabilities = ref<AICapability[]>([])
  const loading = ref(false)

  const byId = computed(() =>
    Object.fromEntries(capabilities.value.map((capability) => [capability.id, capability])),
  )

  async function loadCapabilities() {
    loading.value = true
    try {
      const res = await getAICapabilities()
      capabilities.value = res.data
      return capabilities.value
    } finally {
      loading.value = false
    }
  }

  return {
    capabilities,
    loading,
    byId,
    loadCapabilities,
  }
})
