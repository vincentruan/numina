import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { getAgents, createAgent, updateAgent, deleteAgent, toggleAgent } from '@/api/agent'
import type { Agent, AgentCreatePayload, AgentUpdatePayload } from '@/types/agent'

export const useAgentStore = defineStore('agent', () => {
  const builtinAgents = ref<Agent[]>([])
  const customAgents = ref<Agent[]>([])
  const loading = ref(false)

  const allAgents = computed(() => [...builtinAgents.value, ...customAgents.value])
  const enabledAgents = computed(() => allAgents.value.filter(a => a.is_enabled))

  async function loadAgents() {
    loading.value = true
    try {
      const data = await getAgents()
      builtinAgents.value = data.builtin
      customAgents.value = data.custom
    } finally {
      loading.value = false
    }
  }

  async function addAgent(payload: AgentCreatePayload): Promise<Agent> {
    const agent = await createAgent(payload)
    customAgents.value.push(agent)
    return agent
  }

  async function editAgent(id: string, payload: AgentUpdatePayload): Promise<Agent> {
    const agent = await updateAgent(id, payload)
    const idx = customAgents.value.findIndex(a => a.id === id)
    if (idx >= 0) customAgents.value[idx] = agent
    const bIdx = builtinAgents.value.findIndex(a => a.id === id)
    if (bIdx >= 0) builtinAgents.value[bIdx] = agent
    return agent
  }

  async function removeAgent(id: string): Promise<void> {
    await deleteAgent(id)
    customAgents.value = customAgents.value.filter(a => a.id !== id)
  }

  async function toggleAgentEnabled(id: string, enabled: boolean): Promise<void> {
    const agent = await toggleAgent(id, enabled)
    const idx = customAgents.value.findIndex(a => a.id === id)
    if (idx >= 0) customAgents.value[idx] = agent
    const bIdx = builtinAgents.value.findIndex(a => a.id === id)
    if (bIdx >= 0) builtinAgents.value[bIdx] = agent
  }

  return {
    builtinAgents,
    customAgents,
    allAgents,
    enabledAgents,
    loading,
    loadAgents,
    addAgent,
    editAgent,
    removeAgent,
    toggleAgentEnabled,
  }
})