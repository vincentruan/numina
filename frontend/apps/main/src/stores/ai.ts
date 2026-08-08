import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as aiApi from '@/api/ai'
import type { ProviderConfig, AITaskStatus } from '@/api/ai'

/** Background task registry entry for tracking tasks across navigation. */
export interface BackgroundTask {
  capability: string
  taskId: string
  sessionId: string
  startedAt: string
  status: AITaskStatus['status']
  markdownFilePath?: string  // For report: Phase 1 success path
}

export const useAIStore = defineStore('ai', () => {
  const configs = ref<ProviderConfig[]>([])
  const loading = ref(false)
  const draftQuery = ref('')
  const deepThinkEnabled = ref(false)
  const webSearchEnabled = ref(false)
  const backgroundTasks = ref<Map<string, BackgroundTask>>(new Map())

  const activeConfigs = computed(() =>
    configs.value.filter((c) => !c.circuit_open),
  )
  const runningBackgroundTasks = computed(() =>
    Array.from(backgroundTasks.value.values()).filter(
      (t) => t.status === 'running' || t.status === 'post_processing' || t.status === 'queued',
    ),
  )
  const hasRunningBackgroundTasks = computed(() => runningBackgroundTasks.value.length > 0)

  // ── Background task registry ────────────────────────────────────────────────

  function registerBackgroundTask(task: BackgroundTask) {
    backgroundTasks.value.set(task.capability, task)
  }

  function updateBackgroundTask(capability: string, updates: Partial<BackgroundTask>) {
    const existing = backgroundTasks.value.get(capability)
    if (existing) {
      backgroundTasks.value.set(capability, { ...existing, ...updates })
    }
  }

  function getBackgroundTask(capability: string): BackgroundTask | undefined {
    return backgroundTasks.value.get(capability)
  }

  function clearBackgroundTask(capability: string) {
    backgroundTasks.value.delete(capability)
  }

  function clearAllBackgroundTasks() {
    backgroundTasks.value.clear()
  }

  async function fetchConfigs() {
    loading.value = true
    try {
      const res = await aiApi.getAIConfigs()
      configs.value = (res.data.configs ?? []).sort((a, b) => a.display_order - b.display_order)
    } finally {
      loading.value = false
    }
  }

  async function reorderConfigs(order: string[]) {
    await aiApi.reorderAIConfigs(order)
    order.forEach((id, idx) => {
      const cfg = configs.value.find((c) => c.id === id)
      if (cfg) cfg.display_order = idx
    })
    configs.value = [...configs.value].sort((a, b) => a.display_order - b.display_order)
  }

  async function resetCircuit(id: string) {
    await aiApi.resetCircuitBreaker(id)
    const cfg = configs.value.find((c) => c.id === id)
    if (cfg) {
      cfg.circuit_open = false
      cfg.failure_count = 0
      cfg.circuit_open_until = null
    }
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
    configs,
    loading,
    draftQuery,
    deepThinkEnabled,
    webSearchEnabled,
    activeConfigs,
    backgroundTasks,
    runningBackgroundTasks,
    hasRunningBackgroundTasks,
    registerBackgroundTask,
    updateBackgroundTask,
    getBackgroundTask,
    clearBackgroundTask,
    clearAllBackgroundTasks,
    fetchConfigs,
    reorderConfigs,
    resetCircuit,
    testConnection,
    testMainModel,
    testThinking,
    testVisionModel,
    testVisionImage,
    testVisionText,
  }
})
