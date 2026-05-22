import api from '@/api'
import type { Agent, AgentCreatePayload, AgentListResponse, AgentUpdatePayload } from '@/types/agent'

export function getAgents(): Promise<AgentListResponse> {
  return api.get('/ai/agents').then(r => r.data)
}

export function getAgent(id: string): Promise<Agent> {
  return api.get(`/ai/agents/${id}`).then(r => r.data)
}

export function createAgent(payload: AgentCreatePayload): Promise<Agent> {
  return api.post('/ai/agents', payload).then(r => r.data)
}

export function updateAgent(id: string, payload: AgentUpdatePayload): Promise<Agent> {
  return api.put(`/ai/agents/${id}`, payload).then(r => r.data)
}

export function deleteAgent(id: string): Promise<void> {
  return api.delete(`/ai/agents/${id}`)
}

export function toggleAgent(id: string, enabled: boolean): Promise<Agent> {
  return api.put(`/ai/agents/${id}/toggle?enabled=${enabled}`).then(r => r.data)
}